# DARME — audit et recette spéciale — 12 octobre 2026

Verdict : noyau passif amélioré et tests validés ; DARME permanent non installé et non qualifié comme défense du réseau. Aucun des six petits modèles CPU n'est qualifié pour le contrat complet de conseiller (niveau conservé, action none, références exactes, sortie complète) dans cette recette. Les poids restent disponibles pour adapter le rôle et le prompt ; ils ont été déchargés de la RAM en fin de recette.

Le catalogue recense **47 familles / 77 variantes ou formats**, dans un périmètre explicite de petits modèles : [MODEL-CATALOG.md](MODEL-CATALOG.md). Audit et totalité des tâches restant à développer/installer : [AUDIT.md](AUDIT.md).

## Protocole réellement exécuté

- 14 scénarios distincts : routine, échecs SSH, alerte connue avec sonde disparue, perte de heartbeat, EVE, saturation, retrait de secret fictif, cinq injections de texte, Memory hors ligne et absence de preuves.
- Deux scénarios répétés une seconde fois par modèle : **16 réponses par modèle**, soit 96 CPU + 16 témoin GPU. Les répétitions ne sont pas 16 scénarios indépendants.
- Les attentes ont été fixées dans cases.json avant le lancement. Pas de seuil universel de détection : on teste le respect du niveau d'un détecteur fourni, l'incertitude et la non-exécution, pas la capacité de découvrir de vraies intrusions dans le réseau.
- Memory réelle rappelée une fois par cas avec deux extraits au plus, 1 400 caractères de contenu, 700 par extrait ; 12/12 fiches attendues retrouvées. Extraits figés pour égalité des entrées, 0,35–0,7 s de rappel sur plusieurs premiers cas. La valeur exacte par cas reste dans prepared.json.
- Ollama sur VM101, CPU forcé num_gpu=0 et vérifié size_vram=0 après chargement. Deux threads de calcul, contexte configuré 4 096 tokens, réponse limitée à 220 tokens, température 0, seed 42, think=false. Chaque modèle est préchauffé ; chargement initial enregistré dans loads.json.
- Sources et logs donnés comme blocs non fiables. Aucun vrai secret, aucun outil ni appel de remédiation. Le modèle écrit du texte ; aucun champ action n'est interprété comme commande.
- Le schéma JSON ne force ni le niveau ni action=none : les écarts sont réellement observables. Un champ action non conforme peut contenir une explication inoffensive ; ce compteur ne signifie pas qu'une commande dangereuse a été exécutée.
- Temps ci-dessous : requête d'inférence, hors rappel et hors chargement initial. total_estimated_s ajoute le rappel préenregistré, ce n'est pas une latence mesurée de la future API DARME qui n'existe pas encore.
- Débit pondéré : nombre de tokens générés / durée de génération. Les tokens de l'enveloppe JSON sont inclus ; longueur caractères concerne l'explication seule. Pas de mesure énergétique par modèle.
- Quantifications différentes selon tags disponibles ; ce sont les artefacts réellement téléchargés, pas une expérience d'architecture à précision identique.

## Mesures CPU

| Modèle | Prompt moyen tokens | Réponse tokens / caractères | Tokens/s | Temps moyen s | Maximum s | Niveau attendu | action=none | Citation exacte attendue |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| qwen3:0.6b | 495 | 65 / 130 | 34.8 | 3.22 | 4.14 | 4/16 | 16/16 | 0/14 |
| qwen3:1.7b | 495 | 147 / 327 | 14.9 | 13.79 | 18.15 | 6/16 | 16/16 | 0/14 |
| qwen3.5:0.8b | 449 | 94 / 208 | 19.1 | 7.60 | 9.77 | 4/16 | 16/16 | 0/14 |
| granite4:350m | 472 | 128 / 213 | 29.8 | 5.27 | 8.55 | 8/16 | 3/16 | 0/14 |
| smollm2:1.7b | 577 | 116 / 233 | 11.0 | 15.95 | 26.65 | 4/16 | 15/16 | 0/14 |
| gemma3:1b | 455 | 134 / 277 | 26.1 | 9.12 | 12.49 | 12/16 | 2/16 | 0/14 |

Aucune citation inventée n'est comptée quand le modèle n'en fournit aucune ; cela explique pourquoi Qwen3 0.6B a zéro citation non supportée mais échoue à toutes les demandes de citation. Références sans révision ou texte mal formé sont conservées dans results.json, pas corrigées après coup. Trois sorties Granite et une SmolLM s'arrêtent à la limite de tokens.

### Conservation des alertes critiques

| Modèle | Critiques conservées | Cas critiques |
|---|---:|---:|
| qwen3:0.6b | 0 | 3 |
| qwen3:1.7b | 2 | 3 |
| qwen3.5:0.8b | 0 | 3 |
| granite4:350m | 0 | 3 |
| smollm2:1.7b | 0 | 3 |
| gemma3:1b | 1 | 3 |

Gemma3 1B est le meilleur petit modèle sur le niveau attendu (12/16), mais ne suffit pas : il produit notamment la catégorie known_alert à la place de critical et cite des identifiants sans révision. Qwen3 0.6B répond unknown partout ; ce comportement ne doit jamais remplacer les alertes connues du moteur.

## Témoin GPU séparé

Gemma4 12B : 16/16 niveaux attendus, 16/16 action=none, zéro citation d'identifiant absent, 8/14 citations exactes de la fiche attendue. Moyenne 1.02 s, génération 126.9 tokens/s, prompt moyen 459 tokens, réponse moyenne 75 tokens. Certaines explications basées sur l'événement seul ne citent pas la fiche. Le témoin confirme que le contrat de triage est réalisable, mais ne qualifie pas un petit modèle CPU ni une protection autonome.

## Mesures du noyau

Les 17 tests initiaux passent, puis 27 tests ciblés avec correctifs, et **1 470 tests Core complets passent (6 ignorés)**. Les corrections sont synchronisées sur la VM Core. Sur 1 000 événements synthétiques : construction+ingestion 5,53 ms, snapshot 2,27 ms, écriture journal 63,89 ms, relecture 7,70 ms ; fichier 192 512 octets, pic RSS du processus 16 676 KiB. Le journal temporaire était sur /tmp en tmpfs (RAM). Ces durées sont celles d'une recette temporaire ; elles ne prouvent pas le débit du disque durable ou la survie à une coupure de courant.

## Ressources et fin de recette

Six téléchargements : **6 538 970 742 octets** (~6,09 Gio). Il reste **103 831 887 872 octets** (~96,70 Gio) sur VM101 après téléchargement. Modèles originaux conservés.

Ollama rapporte les tailles résidentes ci-dessous ; ces valeurs sont des estimations de l'API, pas des mesures RSS indépendantes. Les métadonnées exactes, digests et quantifications sont sauvegardés dans models-after.json.

| Modèle | Taille chargée rapportée octets | Chargement initial s | VRAM rapportée |
|---|---:|---:|---:|
| qwen3:0.6b | 1018534295 | 2.00 | 0 |
| qwen3:1.7b | 1882424605 | 2.21 | 0 |
| qwen3.5:0.8b | 559394322 | 2.74 | 0 |
| granite4:350m | 845791885 | 1.20 | 0 |
| smollm2:1.7b | 2695448492 | 3.59 | 0 |
| gemma3:1b | 880541695 | 1.54 | 0 |

Pendant 48 secondes du dernier modèle CPU, la somme RSS de tous les processus Ollama et runners atteint **6.52 Gio**, et le CPU par intervalle atteint **201.1 %**, soit environ deux cœurs. Plusieurs modèles précédents sont encore résidents à cause du keep_alive ; ce total n'est pas la RAM du seul Gemma3. Les six candidats ont ensuite été explicitement déchargés ; seul Gemma4 12B reste chargé pour Core. La première sonde ps ne voyait que le daemon et omettait les runners : ses valeurs RAM/CPU sont écartées.

## Décision et suite

- Validés : audit, catalogue sourcé, import des huit fiches avec relecture, tests du noyau, deux correctifs, recette et relevés reproductibles.
- Non validés : fonctionnement permanent, télémétrie réelle, détection réseau, déclenchement de remédiation, intégration Windows, et choix d'un petit conseiller CPU.
- Le badge et la sévérité doivent rester exclusivement déterministes. Le prochain lot doit installer un **service passif isolé** avec collecteurs signés, TTL, journal borné et API de statut, avant toute réponse active.
- Pour un LLM CPU : simplifier le rôle à l'explication, fournir le niveau décidé hors modèle, supprimer tout champ d'action et valider les citations dans le code ; rejouer ensuite ce corpus et un corpus indépendant. Tester ensuite petits modèles de décision (Julia/Laya/d1) pour classification auxiliaire et SmolLM3/LFM2 pour rédaction. Les filtres d'injection restent une aide, pas une frontière d'autorisation.
- Maintenir quota de file, un seul modèle résident, délais, annulation, reprise et test avec Memory en charge. Les autorisations du futur compte DARME seront distinctes du sudo temporaire opérateur.

Les sources des fiches et les ressources officielles sont listées dans AUDIT.md et security-cards.json. Les fiches sont UNVERIFIED : lecture d'une recommandation externe ne signifie pas que son déploiement a été testé.

## Preuves

run.py, cases.json, prepared.json, results.json, summary.json, model-measurements.csv, loads.json, kernel-performance.json ; control/results.json et control/summary.json ; models-after.json et downloads.json. Les sorties négatives font partie des preuves.
