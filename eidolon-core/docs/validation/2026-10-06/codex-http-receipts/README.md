# C-009b — validation Codex/GPT, 06/10/2026

Base : API C-009a publiée en 21c0f729 ; six tâches G036–G041 publiées en
6395485c057cb671cdc2ba8e0eb63a4004c85136. Validation Linux, Python 3.12.14, SQLite
local temporaire et sockets loopback réelles. Données entièrement synthétiques.

## Résultats reproduits

Depuis eidolon-core/ :

```sh
PYTHONPATH=src:. python -m unittest tests.test_receipt_lookup tests.test_http_api tests.test_commands tests.test_cancel_commands -v
PYTHONPATH=src:. python examples/http_receipt_demo.py
```

- [tests.txt](tests.txt) : **87 tests réussis**, 12,081 s, dont 20 nouveaux
  (15 consultation, 5 HTTP) et 67 existants (API, décisions, annulations).
- [demo.json](demo.json) : clé absente, annulation enregistrée localement puis
  réponse ignorée, reçu retrouvé deux fois par HTTP sans renvoi de commande ;
  base inchangée par les lectures, mission encore NEW, aucun outil exécuté.
- [binding-before.txt](binding-before.txt) : deux échecs intentionnellement
  reproduits sur une version de développement avant correction. Une décision
  changée avec son libellé cohérent et une empreinte altérée passaient les seuls
  contrôles de forme. La reconstruction depuis l’événement les refuse désormais.

Couverture : décisions approuver/rejeter/révoquer et reçus historiques, trois
issues d’annulation, mission/store divergents, clé absente, client isolé, JSON
et versions invalides, données privées non exportées, événement absent ou
incohérent, lecture cohérente pendant une écriture concurrente WAL. Contrôles
HTTP et commandes préexistants également rejoués.

## Limites

Aucun test Windows, navigateur connecté, tunnel SSH ou serveur utilisateur.
G036 doit encore raccorder les reçus ; G031 est intégré dans le lot suivant. Aucune nouvelle passe de la
suite globale ou Node revendiquée. La base SQLite reste une source de confiance,
pas un journal signé ; un reçu trouvé ne prouve pas un effet, une absence ne
prouve pas une non-exécution et ne permet pas un renvoi. Pas de détection
universelle de restauration ni d’audit complet des états historiques.
