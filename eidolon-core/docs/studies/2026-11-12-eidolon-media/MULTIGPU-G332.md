# G332 — FLUX.1 Schnell réellement réparti sur deux V10016Go

Eidolon Core Technologies (ECT), 12/11/2026, Europe/Paris.
**Répartition et génération hors ligne réussies. Qualité non validée globalement.**
La [file des candidats](CANDIDATE-QUEUE-G332.md) comprend 27 entrées image et
10 entrées vidéo, certaines contenant plusieurs variantes. Ce lot n'a pas testé
les 37 entrées : il a exécuté un premier candidat dont le générateur dépasse 16Go.

## Ce qui existait / ce qui a été ajouté

Existants réutilisés : ComfyUI0.3.26 isolé, PyTorch2.6.0+cu124,
venv préférences avec Diffusers0.32.2/Accelerate1.3.0, tokenizers Comfy,
sondes de qualité et API média. SD1.5/SDXL/Wan1.3B/SVD restent les profils API.

Ajouts : catalogue des candidats avec blocages licence/Volta/mémoire,
manifeste de quatre fichiers figés, téléchargement explicite avec SHA256 et
réserve disque, runner `flux_dual_probe.py`, trois tests de refus/intégrité,
mesures et revue visuelle. Aucun paquet ni custom node installé, aucun pilote,
CUDA, service critique ou modèle de production remplacé.

FLUX reste un **runner expérimental autonome**, pas un nouveau profil de l'API.
Pas de nouveau LoRA, entraînement ou promotion. G329-02 et l'invalidation du
candidat G329 sont préservés.

## Poids et placement effectivement observés

[Manifeste vérifié](candidate-downloads-g332.json) : 34 151 796 252 octets au total,
environ31,8Gio sur disque. Tous les SHA256 ont été vérifiés au téléchargement
puis avant chargement. Pas de poids ni d'image privée publiés dans le dépôt.

- Générateur : FLUX.1 Schnell, fichier23 782 506 688octets, SHA `9403429e…d2a0a`.
  Source publique Comfy-Org, **SHA identique à celui publié par BFL**. Le dépôt
  BFL lui-même renvoie401 sans acceptation/connexion ; aucun accès contourné.
- CLIP-L et T5XXL FP16 : conditionnement comfyanonymous, calcul encodage **CPU FP32**.
- VAE `ae.safetensors` depuis Comfy-Org/Z-Image-Turbo : **SHA identique au VAE BFL**
  `afc8e282…529e38`. Seul ce fichier est réutilisé, pas le modèle Z-Image.
- Poids Schnell Apache-2.0 ; conserver les notices et licences des encodeurs.

Le générateur est converti en FP16, sans quantification. Accelerate distribue ses
blocs ; les paramètres restent résidents pendant les quatre générations :

| Composant | Placement réel |
| --- | --- |
| Embeddings et blocs doubles0–16 | GPU0 |
| Blocs doubles17–18, blocs simples, sortie | GPU1 |
| Paramètres du générateur GPU0 | 11 623 900 160octets, environ10,83Gio |
| Paramètres du générateur GPU1 | 12 158 456 960octets, environ11,32Gio |
| Total générateur FP16 | **22,15Gio**, supérieur aux16Gio d'une carte |
| Encodeurs texte | RAM CPU, FP32 ; aucun appel extérieur |
| VAE | GPU0 FP32, tuilage activé |

Ce n'est ni deux jobs indépendants, ni un générateur déchargé sur CPU. Le pipeline
complet utilise toutefois la RAM pour l'encodage : ne pas le présenter comme
entièrement résident en VRAM. Pas de BF16/FP8 natif, FlashAttention, xFormers ou
nouveau kernel Triton. Attention mathématique PyTorch.

## Résultats mesurés et limites de comparaison

Unité `eidolon-media-flux-dual-g332`, exécution21:38:01–21:39:25 CET, sortie0.
Encodeurs/encodage des **trois prompts ensemble** :27,61s ; chargement/placement
générateur + VAE :13,14s. Les durées suivantes sont génération/décodage après
préparation, hors écriture PNG et encodage. Vérification des hashes incluse dans
la durée globale mais pas dans ces temps de génération.

| Sortie | Format | Étapes / seed | Génération | Revue GPT |
| --- | --- | --- | --- | --- |
| G332-00 — main | 512×512 | 4 /20261113 | 1,84s | **REJET** : quatre doigts visibles |
| G332-01 — tasse et bol | 768×432,16:9 | 4 /20261113 | 1,96s | **ACCEPTÉE** : deux objets, bonnes couleurs/positions |
| G332-02 — katana | 768×432,16:9 | 4 /20261113 | 1,96s | **REJET** : géométrie lame/poignée/fourreau incohérente |
| G332-03 — répétition main | 512×512 | 4 /20261113 | 1,56s | **REJET** identique à00 |

Quatre succès techniques, **1 acceptation/3 rejets**, soit1/3 parmi les scènes
distinctes. Les deux mains sont identiques pixel par pixel et par SHA du PNG.
Pas de garantie de reproductibilité entre autres runtimes/GPU. Revue utilisateur
encore ouverte ; aucun résultat admis automatiquement à un entraînement.

Ce petit lot n'est pas une comparaison contrôlée avec G331 : autre moteur,
résolutions et recette différents. Ne pas annoncer un gain général de vitesse
ou de qualité face à SDXL sur la base de ces seules valeurs. Un seul seed,
trois scènes, aucune image1024² ni édition ou vidéo FLUX testée ici.

| Mesure échantillonnée toutes~0,5s | GPU0 V100 | GPU1 V100 |
| --- | --- | --- |
| Pic VRAM nvidia-smi, contexte inclus | **14 314Mio /13,98Gio** | **12 992Mio /12,69Gio** |
| Pic température GPU | 36°C | 34°C |
| Pic température HBM | 36°C | 36°C |
| Pic puissance GPU observé | 304,59W | 196,87W |
| Limite puissance, inchangée | 300W | 200W |

CPU Tdie54,375°C au maximum, aucune erreur de sonde. Pic mémoire du cgroup
rapporté par systemd~53,7G. Aucun wattmètre mural/Shelly relevé ici ; ne pas
additionner deux maxima non nécessairement simultanés comme consommation totale.
Essai court : pas une validation thermique soutenue.

## NVLink observé, pas seulement supposé

TopologieNV6, accès peer CUDA vrai dans les deux sens. Les compteurs des six
liens passent de0 à des valeurs non nulles pendant chaque génération ; les
émissionsGPU0 correspondent aux réceptionsGPU1, et réciproquement. Les relevés
bruts avant/après sont conservés dans [les preuves](multigpu-validation-g332.json).
Cela démontre du trafic NVLink pendant ce processus isolé ; ce n'est pas un
benchmark de débit maximal, ni une preuve d'accélération par rapport à PCIe.
Les CRC/Replay/Recovery des deux cartes restent tous à0 après l'essai.

## Isolation et contrôles après essai

Processus toytoy, umask0077, NoNewPrivileges, ProtectSystem=strict, PrivateTmp,
écriture limitée au laboratoire, modèles en lecture seule ; CPU8équivalents,
RAM90Gio, durée maximale1800s. UUID des deux V100 explicitement sélectionnés.
HF_HUB_OFFLINE/TRANSFORMERS_OFFLINE=1 et réseau du cgroup bloqué sauf localhost.
Téléchargement dans une unité distincte, terminé avant l'inférence ; seuls
Hugging Face et ses hôtes de distribution interviennent pendant l'installation.
Hôtes finaux inscrits dans les receipts locales ; aucun prompt envoyé.

Les garde-fous surveillent processus tiers et températures. Ce n'est pas encore
un bail GPU atomique partagé avec tous les services : ne pas utiliser ce runner
en concurrence non coordonnée. Pas d'arrêt Eva ni de service existant.

[Contrôles finaux](multigpu-final-g332.json) : GPU0 revenu1Mio/GPU1 à624Mio,
0% activité, seul Comfy préexistant12976 ; queue vide,79tâches API terminales
(77réussies,2annulées déjà existantes),12services Eidolon/Ollama recensés actifs,
VM Memory-engine active. Pas de recette fonctionnelle exhaustive de ces services.
Environ28Gio libres sur volume modèles : ne pas télécharger tout le catalogue
simultanément ; libération/archivage contrôlé à prévoir si nécessaire.

Tests : **243 découverts**,239réussis/4ignorés dans le workspace ;
**243 découverts**,238réussis/5ignorés surX399. Inclut3nouveaux tests sur faux
partage, checksum et chemins/révisions de téléchargement. La première commande
locale sans racine de package a eu4erreurs d'import `tests` ; corrigée en lançant
depuis `eidolon-core` avec `PYTHONPATH=src:.` et `discover -s tests -t .`.
Ces tests logiciels ne remplacent pas les quatre générations matérielles.

## Suite de la campagne

1. Étendre FLUX au jeu multi-seeds et aux résolutions supérieures progressivement ;
   conserver les rejets de main/katana. Aucun gain anatomique acquis.
2. Tester RealVisXL/Juggernaut dans le laboratoire isolé puis les autres lignes,
   en conservant les portes licence/FP16/mémoire de la file.
3. Après qualification seulement, intégrer le backend réparti à la file API
   avec réservation des deux GPU, annulation et reprise validées.
4. Modèles trop grands pour32Go : étudier quantification/offload, pas les rejeter
   sans étude ni prétendre qu'ils rentrent en additionnant simplement les cartes.

PR#7 reste en brouillon pour revue, sans fusion. Aucune décision supplémentaire
nécessaire pour poursuivre les essais déjà autorisés ; les licences à accès
restreint et incompatibilités seront traitées modèle par modèle.
