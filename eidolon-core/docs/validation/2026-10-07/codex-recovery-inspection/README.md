# C-025 — lecture stricte et bornée des copies de revue

Codex/GPT, 07/10/2026. Base a022297, arbre publié 7c8d97b.
Python 3.12.14/Linux, copies temporaires synthétiques uniquement.

## Défauts reproduits

`before.txt` : après altération de métadonnées dans une copie synthétique,
`inspect_review` réémettait `execution_authority=True` ; un rapport liste
provoquait `AttributeError`, hors du diagnostic CLI. Le Runtime restait bloqué
par la garde REVIEW_ONLY. Ce n’était donc pas une activation de sauvegarde ;
la sortie d’inspection était trompeuse ou indisponible.

## Correction

Contrat strict du rapport : clés/types/identités/date/empreinte et invariants
historiques, aucune autorité ni effet réconcilié affirmé. JSON dupliqué,
non fini ou non UTF-8 refusé par diagnostic constant. Les anciennes copies
sans `capture_semantics` restent admises ; aucun champ n’est inventé.

Lecture en une transaction, métadonnées/mission bornées dès la sélection SQL,
10 000 missions maximum, corps 16 Mio, rapport 32 Kio, base logique 256 Mio.
Budget coopératif SQL/Python de deux secondes ; un dépassement refuse tout le
rapport, sans capture partielle. Le délai d’attente SQLite est aussi de deux
secondes. Les délais physiques du stockage ne sont pas garantis.

## Tests

`PYTHONPATH=src python -m unittest tests.test_recovery_inspection tests.test_recovery tests.test_recovery_followup tests.test_runtime_inspect -q`

**47 tests réussis**, dont dix nouveaux (targeted-tests.txt). Contrats invalides,
clés dupliquées, contenu surdimensionné, ancien rapport, identité/statut/annulation
incohérents, approbation historique USED, CLI sans fuite/traceback, bornes sans
mutation et interruption d’un vrai comptage SQL coûteux. Les tests de copie
concurrente DELETE/WAL et de garde après crash restent verts.

Aucune réparation ni réactivation, aucun fichier privé utilisateur manipulé.
La validation de structure n’est pas une signature ni un détecteur de rollback
cohérent. Les annotations acteur/raison et identifiants d’appel historiques
restent des libellés fournis, pas des identités authentifiées.
