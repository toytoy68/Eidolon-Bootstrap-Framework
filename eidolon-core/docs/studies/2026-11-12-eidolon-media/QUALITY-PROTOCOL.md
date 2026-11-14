# Protocole de qualification visuelle — G328

Eidolon Core Technologies (ECT) · 12 novembre 2026 · Version 1

## Question et hypothèses

Les recettes précédentes prouvent l'exécution locale, pas une qualité suffisante.
Les demandes main/katana ont montré des défauts structurels. Avant tout entraînement,
vérifier le workflow et mesurer une référence reproductible, échecs compris.

Le [guide officiel SDXL](https://huggingface.co/docs/diffusers/main/using-diffusers/sdxl)
(consulté le 12/11/2026, sections Text-to-image et Micro-conditioning) présente
1024×1024 comme référence et explique le conditionnement par dimensions.
Nos essais 1024×576 et 768×576 n'établissent donc pas la qualité à cette référence.
**Hypothèse à tester, pas diagnostic acquis.** Le code ComfyUI local
`comfy_extras/nodes_clip_sdxl.py` confirme les deux encodeurs et les dimensions.

## Première campagne exécutable

`quality_probe.py` réutilise l'API et son ordonnanceur, sans modifier Core,
Memory, le pilote, les modèles ou le moteur. Douze essais séquentiels :

| Axe | Valeurs figées avant lancement |
| --- | --- |
| Cas synthétiques publics | Tasse rouge ; main adulte ouverte ; katana et fourreau séparés |
| Seeds | 104729 et 130363 pour chaque cas et chaque configuration |
| Configurations | 1024×576 et 1024×1024, sans agrandissement ni recadrage |
| Modèle | SDXL base1.0 officiel, SHA256 contrôlé avant exécution |
| Échantillonnage | DPM++2M, Karras, CFG6, 30 étapes, denoise1 |
| Conditionnement | Même texte dans les deux encodeurs ; dimensions originales/cibles égales au latent ; crop0 |
| Négatif | `blurry, distorted, text, watermark` identique |
| Précision | Runtime existant FP16 ; VAE FP32 ; split attention ; aucun refiner/LoRA |
| Ordre | Ordre des deux géométries inversé à la seconde seed |

Cette comparaison change **surface, ratio et conditionnement associé** : elle
compare deux configurations. Elle ne permet pas d'attribuer causalement un gain
au seul nombre de pixels. Une même seed avec un latent différent n'est pas le
même bruit spatial. Deux seeds ne suffisent pas à estimer la fiabilité générale.

## Preuves conservées et mesures

Répertoire privé hors dépôt, créé exclusivement : refus si déjà existant.
Manifest : plan complet/hash, SHA modèle vérifié, commits moteur/source, hash
du lanceur, commande moteur, inventaire Python. Avant chaque POST : intention
durable et clé d'idempotence. Après : reçu, état terminal, graphe réellement
exécuté vérifié contre le plan, métadonnées, PNG original et son hash.

Sondes toutes les ~250ms **plus la durée de lecture nvidia-smi** : VRAM occupée,
charge, puissance, limite de puissance, température GPU/HBM des trois cartes ;
CPU Tdie si disponible. Journal JSONL écrit pendant l'essai. Sonde indisponible
= valeur absente, jamais zéro inventé. Pics échantillonnés, pas maxima absolus.
Le temps mural comprend soumission/polling ; le temps service est séparé.
Chargement et débruitage ne sont pas encore chronométrés séparément.

Chaque essai décharge les modèles/cache Comfy ; le cache disque Linux reste
intact. Ce n'est **pas** un démarrage machine à froid. Une future série chaude
devra être identifiée séparément. Puissance GPU ≠ consommation de la machine :
pas de Wh secteur tant que la sonde Shelly n'est pas intégrée et synchronisée.

## Garde-fous et interruption

Une seule campagne locale (verrou flock), une image à la fois, 12 maximum,
180s maximum par tâche. Vérification file API/moteur vide avant chaque essai,
capacité restante (limite128), GPU sans processus étranger, ≥2Gio disponibles,
GPU<65°C, HBM<70°C via le garde existant. GPU1 conserve sa consigne200W ; aucun
changement GPU0/GTX1060. Le service continue son contrôle pendant la génération.
Ce contrôle coopératif n'est pas une réservation globale atomique contre Eva.

Échec/OOM/état incertain/conflit : arrêt de la campagne, aucun retry automatique.
Délai dépassé : annulation du seul identifiant connu via l'API, puis arrêt ;
vérifier effectivement la terminaison avant une nouvelle campagne. Si le POST
échoue sans reçu, conserver l'intention et rapprocher sa clé avec la base/API :
ne pas resoumettre aveuglément. Les interruptions ne sont pas des résultats
valables. Aucune purge de l'historique ou des fichiers en cas d'échec.

## Grille visuelle préétablie

Noter chaque image, sans choisir seulement la meilleure seed. Échelle0–4 :
0 absent/inexploitable ; 1 défaut majeur ; 2 défaut visible ; 3 petits défauts ;
4 aucune anomalie évidente à cette inspection. Critères séparés :

1. Fidélité : objets, couleurs, pose et relation demandés.
2. Structure : géométrie/anatomie, continuité, nombre de parties.
3. Composition : objets entiers, séparation, cadrage.
4. Finition : texture, lumière, contours, artefacts.

Défauts éliminatoires par cas : tasse absente/multipliée ou anse impossible ;
main avec nombre de doigts incorrect/fusion ou articulations manifestement
impossibles ; katana non identifiable, lame/fourreau fusionnés, fourreau remplacé
par une seconde lame. Une belle texture ne compense pas ces défauts.
Acceptable pour ce cas : tous les critères≥3 et aucun défaut éliminatoire.
Conserver observations écrites et identité du relecteur. Aucune validation
médicale/anatomique professionnelle n'est revendiquée.

Pour une comparaison humaine, présenter des identifiants neutres avec ordre
mélangé et paramètres masqués ; la géométrie visible empêche un aveugle complet.
Une revue par l'assistant doit être étiquetée comme telle, jamais comme avis de
toytoy. PNG décodable/API SUCCEEDED ≠ réussite esthétique. Notes initialement
`NOT_REVIEWED` ; aucun calcul de score automatique à partir des pixels.

## Étapes suivantes conditionnelles

1. Vérifier les douze images et publier médianes/min/max, n, échecs, notes.
2. Si nécessaire, isoler à géométrie fixe les facteurs conditionnement, CFG,
   étapes, puis refiner/checkpoint (un facteur à la fois, licence/hash vérifiés).
3. Étendre à au moins quatre seeds et aux cas gardés hors réglage : deux adultes
   avec tenues différentes devant un château ; paysage architectural ; objet
   mécanique. Ne pas retoucher leurs prompts après lecture des résultats.
4. N'adopter un profil que si ≥3/4 seeds acceptables par cas requis, sans
   régression du témoin ni incident système. Ce seuil est un critère de projet,
   pas une garantie statistique. Nouvelle recette offline après changement.
5. Qualifier ensuite le format écran à surface adaptée, dans les limites VRAM,
   puis la vidéo : stabilité temporelle, identité, mouvement, frames/FPS/durée.
6. Entraînement/LoRA seulement après cette comparaison et avec un jeu légal,
   séparé en apprentissage et évaluation. Aucun entraînement lancé par ce lot.

Prompts de confirmation figés dès cette version (pas encore exécutés), seeds
155921, 196613, 262147, 327673 :

- `Photograph of two adults standing in front of a Japanese castle. A samurai in black armour on the left and a woman in a red kimono on the right. Both visible from head to foot, daylight.`
- `Photograph of a stone bridge with three arches crossing a river, a medieval town behind it, clear daylight, wide view.`
- `Studio photograph of one metal bicycle on a grey background, side view, two wheels, complete frame and chain visible.`

Défauts éliminatoires de confirmation : personnages/tenues inversés ou corps
fusionnés ; nombre d'arches incorrect/structure impossible ; roues surnuméraires
ou cadre manifestement interrompu. Appliquer aussi les quatre notes communes.

## Exécution

Depuis l'environnement isolé, avec PID réellement relevé par systemctl :

```sh
PYTHONPATH="$LAB/source/eidolon-core/src" "$LAB/venv/bin/python" \
  "$LAB/source/eidolon-core/docs/studies/2026-11-12-eidolon-media/quality_probe.py" \
  --root "$LAB" --output "$LAB/quality-001" --engine-pid "$MEDIA_ENGINE_PID"
```

`LAB` désigne `/srv/eidolon/workspaces/media-20261112`. Utiliser une unité
transitoire non privilégiée avec réseau limité à localhost comme OPERATIONS.
Les prompts du jeu sont synthétiques/publics ; aucune image ou métadonnée privée
d'exploitation à committer. Résultats de cette campagne : QUALITY-RESULTS.md.
