# Suivi de G017 et intégration de G018

Auteur : Codex/GPT. Date : 2026-10-06T13:04:42+02:00.
Base Core : 6c7500434145dc06aeca834231242c4129b22a3a.
Claude : G017/4fa543d, G018/bfa75d2, intégré par avance rapide locale.
Aucun fichier Python modifié par Claude dans ces deux lots.

## Restauration — constat et changement

La revue G017 signalait que la transaction de lecture épinglée durant toute
la copie pouvait faire échouer un écrivain après son attente SQLite. Notre
sonde avant correction lance un vrai processus écrivain entre deux étapes de
backup : sous DELETE, échec `database is locked` après environ cinq secondes.
Sous WAL, il écrivait mais la capture restait figée avant son commit.

Le contrôle initial est désormais une courte transaction terminée avant backup.
SQLite peut recommencer les étapes lorsqu'une autre connexion écrit ; son
budget de 30 secondes reste coopératif. La copie terminée est revalidée avant
publication : schéma, identité, absence de garde antérieure, taille logique.
Le rapport ajoute capture_semantics=sqlite-online-backup. La capture n'est plus
promise à l'instant du contrôle initial : elle peut inclure des commits ultérieurs.
Pas de changement forcé en WAL ni de mutation SQL de la source par la copie.

Références primaires consultées : [API](https://www.sqlite.org/c3ref/backup_finish.html)
et [verrous/redémarrages](https://www.sqlite.org/backup.html#file_and_database_connection_locking).
Les transactions des missions et événements restent celles de SQLite. Le test
vérifie leur présence liée dans la copie, pas seulement le retour du backup.

Deux autres suites G017 : Store refuse aussi review.pending.sqlite3 si le
marqueur est retiré ; inspecter une préparation non publiée donne
RECOVERY_INCOMPLETE, sans créer missions.sqlite3. Cela ne réactive aucune copie.

## Preuves exécutées

Python 3.12.14/Linux, SQLite locales, processus séparés, aucune VM personnelle.

```sh
cd eidolon-core
PYTHONPATH=src python -m unittest tests.test_recovery_followup tests.test_recovery -v
PYTHONPATH=src python -m unittest discover -s tests -v
PYTHONPATH=src:. python -m examples.recovery_demo --format human
PYTHONPATH=src:. python -m examples.recovery_demo
```

- before.txt : cinq nouvelles méthodes sur le code bfa75d2, trois échecs de
  sous-cas et trois erreurs. Le sous-cas WAL attend le nouveau contrat de capture.
- targeted-tests.txt : cinq nouvelles méthodes + seize existantes, 21 réussis.
  L'ancien test WAL est adapté explicitement au nouveau contrat (trois missions
  copiées au lieu de deux). Aucun test de garde/exécution retiré.
- full-tests.txt : 442 tests découverts, **436 réussis / six intégrations Memory
  Engine sautées**, 99,719 secondes. Pas de nouvelle validation du moteur ici.
- demo-human.txt et demo.json : copie synthétique avec accord historique,
  aucun redémarrage ni activation, source inchangée.
- source-hashes.json : sources/test exacts, plus les modules du prototype relus.

Sondes : writer externe DELETE/WAL ; changement de store_id entre étapes refusé ;
écritures répétées interrompues par le budget simulé ; garde après retrait manuel
du marqueur ; diagnostic API/CLI spécifique d'une préparation incomplète.
Les écritures sont réelles dans SQLite temporaire. La contention prolongée et
l'horloge de deadline sont injectées dans les rappels, pas mesurées sur disque lent.

## Prototype G018 — reçu comme candidat

Rapport, consommateur et tests lus ; 62 tests de logique Node 24.19.0 exécutés
(model, commands, sync, g016, list), tous réussis : node-tests.txt.
Capture 15 de Claude examinée : inventaire et sélection portent leur provenance,
lecture seule et état de capture visibles. Les 23 tests d'interface qui complètent
les 85 de Claude ne sont pas rejoués ici ; Windows et transport restent différés.

**Écart confirmé, à corriger par G021** : une page annonce trois missions mais
has_more=false avec un seul item. Le consommateur affiche « Capture entièrement
lue (1) » ; aucun contrôle du total annoncé ne refuse cette incohérence.
Sonde probe-list.js et sortie probe-list-output.json. Le Core n'émet pas cette
page normalement ; il s'agit de robustesse du futur client, pas d'un faux succès
de mission ni d'une autorisation d'exécution. Aucun fichier Desktop corrigé ici.

```sh
node eidolon-core/docs/validation/2026-10-06/codex-recovery-followup/probe-list.js
```

G019/G020 sont en cours selon toytoy (12 h 57), pas redémarrés ni réattribués.
G021 est la suite préparée après ces revues. Aucune modification de main,
aucun déploiement, accès Internet d'Eidolon, données privées ou choix de modèle.
