# G331 — Formulations comparées après la correction de G329-02

Eidolon Core Technologies (ECT) · 12 novembre 2026, Europe/Paris.
Base examinée : `38d49032c468365cda1d1392bf45fa1355c007b8`.

## Plan enregistré avant calcul

12 images : main ouverte, tasse rouge/bol bleu, katana/fourreau ; pour chaque
sujet, formulation G329 et formulation plus explicite, deux nouvelles seeds
20261113 et20261114. Ordre original/détaillé puis détaillé/original. Tous les
résultats seront présentés, y compris les échecs. Les prompts sont dans
`prompt_probe.py`, dont le hash sera conservé avant exécution.

Modèle SDXL base inchangé, aucun LoRA,1024²,30étapes,DPM++2M/Karras,CFG6.
Moteur et seed identiques à l'intérieur de chaque comparaison. Le prompt est
la seule variable volontaire. Une formulation plus détaillée est une hypothèse,
pas une garantie d'amélioration. Deux seeds ne suffisent pas à une conclusion générale.

Critères : nombre de sujets/objets, intégrité des objets, cohérence des raccords,
articulations et plis de la main, séparation des doigts, présence et continuité
du katana et de son fourreau, catégories/couleurs/positions tasse-bol. Texture
photographique et cohérence structurelle sont jugées séparément. Cas douteux
classés UNCERTAIN et exclus des exemples préférés. Jugements GPT révisables,
distincts d'une approbation de toytoy.

Réutilisation du lanceur G328 : vérification SHA du modèle, files vides, absence
de processus GPU étranger, exécution séquentielle, sondes GPU/VRAM/puissance/
températures GPU et HBM/CPU, aucune reprise automatique. GPU1 à200W inchangé.
Génération sur moteur confiné à localhost, aucun service critique interrompu.

Les paires d'apprentissage ne mélangeront jamais les deux formulations : seuls
un accepté et un rejeté de même prompt/configuration peuvent former une paire.
Le candidat G329 invalidé reste exclu. Aucun entraînement n'est requis pour
ce diagnostic ; quelques paires supplémentaires ne suffisent pas à qualifier
un nouvel apprentissage. Aucun gain de qualité ne sera inféré des seuls temps GPU.

## Résultats

Les 12 générations se terminent techniquement sans erreur ; les graphes exécutés
correspondent au plan et les PNG sont lisibles. Inspection GPT réelle des douze
copies JPEG1024² : **0 acceptée,12 rejetées,0 incertaine**. Aucun gain de taux
d'acceptation avec les formulations détaillées sur ces deux seeds. Ce résultat
ne prouve pas que tout changement de prompt est inutile, ni que le modèle serait
incapable de produire un bon résultat sur d'autres paramètres.

| Sujet | Prompt original | Prompt détaillé | Défauts observés |
| --- | --- | --- | --- |
| Main | 0/2 acceptée | 0/2 acceptée | Plis et volumes incohérents, raccords doigts-paume/pouce, reliefs articulaires sur face palmaire |
| Tasse et bol | 0/2 | 0/2 | Couleurs/catégories mélangées, troisième récipient ajouté |
| Katana et fourreau | 0/2 | 0/2 | Lames/poignées multipliées, éléments coupés, fourreau absent |

Le rendu de matière peut être convaincant tout en échouant sur la demande et la
structure. G331-11 montre une seule lame complète mais reste rejetée car son
fourreau manque. Aucune acceptation de convenance pour fabriquer un gagnant.

Registre privé `LAB/preference-lab/dataset-g331`,12 avis et0 paire ; préfixes de lot
désormais paramétrables dans `feedback_build.py`, avec tests de séparation et
refus de préfixes contenant des chemins. Le registre G329 révision13 et la décision
utilisateur sur G329-02 restent intacts. Aucun assemblage automatique des lots.
**Aucun entraînement dans G331** : décision enregistrée dans `training-decision.json`.
Le candidat G329 reste invalidé ; les poids du modèle de base sont inchangés.

## Mesures réelles

V100 GPU1 à200W, SDXL base seul ; GPU0 et GTX1060 non réservés par cette campagne.
Temps par tâche18,78–21,69s, médiane21,25s ; somme252,61s. Ces temps vont du dépôt
de tâche à sa terminaison, avec chargement éventuel ; ils ne comprennent pas
l'audit, le hash initial du modèle, l'inspection ou la préparation du rapport.
Pic9168Mio (8,95Gio), GPU38°C, HBM44°C, CPU Tdie49,5°C. Aucune erreur de sonde.
Puissance GPU maximale échantillonnée263,73W malgré consigne200W inchangée ;
ce pic n'est ni une puissance moyenne ni une mesure de consommation secteur.

Après campagne :79 tâches API toutes terminales, queue Comfy vide, GPU1 à624Mio
et0%,30°C GPU/HBM. Les12 services recensés avant sont toujours actifs, paquets
du venv identiques au manifeste. Aucun service relancé, aucun pilote/CUDA/Memory
modifié. Cela ne constitue pas une recette exhaustive de production.
Exécution confinée à localhost ; propriétés d'isolation relevées pendant le lot.
Pas de coupure physique d'Internet ni de nouveau test vidéo dans ce lot.

## Vérifications et suite

21 tests ciblés réussis ici et21 sur X399 : registre, construction de lots,
comparabilité des prompts et contrôles du lanceur. Cinq nouveaux tests. Le script
de formulation exécuté correspond exactement à son SHA enregistré avant lancement.
Le manifeste intégral, les graphes par tâche, sondes, PNG et journaux restent sur
X399. [Preuves](prompt-validation-g331.json), [décisions](feedback-g331-decisions.json).

Le test de formulation seul n'a pas fourni de nouveaux exemples positifs. Une
suite utile devra tester séparément un autre facteur (réglages ou conditionnement
visuel), avec le même contrôle, avant tout nouvel apprentissage. Les validations
anciennes devront être revues avec la grille renforcée avant réemploi. Aucune
nouvelle méthode ni amélioration de poids n'est déclarée validée ici.

`LAB=/srv/eidolon/workspaces/media-20261112`.

