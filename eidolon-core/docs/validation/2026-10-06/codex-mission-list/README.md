# Validation C-008e — inventaire paginé des missions

Codex/GPT, 06/10/2026, Europe/Paris. Base `58990e24d72f4cb27a7fea3c2e4b99d637d53a84`.
Python 3.12.14/Linux ; données synthétiques locales uniquement.
[Empreintes des sources](source-hashes.json) · [Contrat](../../../MISSION-LIST.md).

Depuis eidolon-core/, avec PYTHONDONTWRITEBYTECODE=1 :

```sh
PYTHONPATH=src:. python -m unittest tests.test_mission_list -v
PYTHONPATH=src:. python -m unittest discover -s tests -t . -v
PYTHONPATH=src:. python -m examples.mission_list_demo
PYTHONPATH=src:. python -m examples.mission_list_demo --format human
```

[18 tests ciblés réussis](targeted-tests.txt), 0,406 seconde. [Suite complète](core-tests.txt) :
404 découverts, **398 réussis / six intégrations Memory Engine sautées**,
96,960 secondes. [Démo JSON](demo.json) et [humaine](demo-human.txt) exécutées
sur deux états temporaires distincts. Trois missions NEW, une annulation demandée,
zéro lancement d'outil ; première continuation refusée, puis trois pages cohérentes.

## Vérifié

- État vide explicite ; cinq missions sur trois pages, ordre stable, aucune perte
  ni doublon, requête répétable et curseur réutilisable après reconstruction du lecteur.
- Écriture concurrente WAL pendant la lecture : génération et projections restent
  liées à la même capture ; la page suivante exige un reset.
- Création, progression et annulation (sans changement de révision) entre pages :
  reset sans items ; autre identité de Store : STORE_CHANGED.
- Changement de tête ou suppression d'événement : reset ; historique absent et
  entiers non représentables exactement en JavaScript : refus.
- Curseurs/champs/limites invalides, doublons JSON, UTF-8 invalide, BOM, profondeur,
  dépassement de taille et nombre non fini refusés ; pas de repli silencieux.
- Capture BLOCKED/CLARIFICATION avec objectif null visible ; PENDING conservé
  sans expiration. Projection sans demande ni donnée brute ; base inchangée à la lecture.
- Copies historiques gardées refusées, y compris avec un Store déjà construit.
- CLI JSON et humaine sans construire Runtime ; code 2 pour reset ; état absent
  non créé ; panne SQLite sans message brut. Affichage ECT exécuté.

Aucun test UI dans ce lot ; prototype Claude inchangé. Pas de nouveau test du
Memory Engine, modèle réel, GPU, Windows, VM ou NAS. Pas de garantie de progression
sous mutations continues, de durée maximale ni d'anti-altération face à SQL brut.
