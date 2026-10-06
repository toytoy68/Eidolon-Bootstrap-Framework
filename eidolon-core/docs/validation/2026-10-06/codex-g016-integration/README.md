# Intégration G010/G016

Codex/GPT, 06/10/2026. Tête Claude examinée `1b9f7dd400a06acea3d6a06e15a6cfff8d3689d5`,
étude G010 `7a1c682`, correctifs G016 `1b9f7dd`. Intégration intacte par avance rapide.

Sur checkout isolé, Node 24.19.0/Linux :

```sh
node --test desktop/prototype/tests/model.test.js desktop/prototype/tests/commands.test.js desktop/prototype/tests/sync.test.js desktop/prototype/tests/g016.test.js
G016_SYNC_STATE=/chemin/cc9a64b/sync-state.js node --test desktop/prototype/tests/g016.test.js
```

[49 tests de logique réussis](node-tests.txt). Sur le fichier de cc9a64b,
[2 réussis et 5 échoués](regressions-before.txt), comme annoncé par Claude.
Les 18 tests UI de Claude restent rapportés, pas réexécutés. Capture 13 inspectée :
revue requise principale, annulation secondaire, effet UNKNOWN visible, aucun
bouton de relance. Le badge TRACE C-008a est peu précis pour cette fixture dérivée :
conserver une provenance explicite dans les futurs scénarios G018.

Les trois écarts G012 sont clos pour les cas reproduits. Le second reset est le
dernier reçu, pas nécessairement le plus récent produit par le serveur : ordre
réseau et incarnation distante restent à traiter avant un transport réel.

G010 : étude et extraits de sources lus ; essai Chromium d'origine HTTP seulement
rapporté. Les versions/API citées ne sont pas requalifiées par cette intégration.
Tauri reste un candidat, aucun framework choisi et aucun paquet Windows testé.
Réponses utilisateur sur SmartScreen/poste indisponible reçues via C-MSG-C027,
conservées comme décisions rapportées par Claude, sans achat ni déploiement.
