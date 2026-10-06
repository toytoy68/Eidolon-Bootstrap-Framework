# Intégration G031 — Codex/GPT, 06/10/2026

Claude a livré a613dc6a2ad85fc7ebac171da38bf8eea882fc7e (C045). Fusion sans
conflit métier avec C-009b ; message et archives Claude conservés. Intégration
publiée e1059dd13f7a62b9eaba97b1475f57294d96d82e.

Revue des sources session/view/main/build, de la documentation et du banc.
Bundle cohérent (`node desktop/connected/build.js --check`). API Python
C-009b inchangée pendant l’intégration, ses 87 tests ciblés restent la preuve
du lot précédent ; pas de nouvelle passe globale.

## Reproduction Linux, Python 3.12.14

```sh
NODE_PATH="$CODEX_PRIMARY_RUNTIME_NODE_MODULES" node --test desktop/connected/tests/*.test.js
```

[node-tests.txt](node-tests.txt) : **18 réussis, deux sautés**, 6,233 s.
14 scénarios session scriptés, quatre contre le serveur Python réel (assets,
annulation via autre processus, panne/redémarrage, changement de Store).
Chromium absent ici : les deux tests navigateur réussis rapportés par Claude
ne sont pas revendiqués comme reproduits par Codex.

## Défaut du banc corrigé

[before-cleanup-fix.txt](before-cleanup-fix.txt) conserve la première passe :
quatre scénarios serveur passent, les deux lancements Chromium échouent ; le
processus ne termine pas car launch était avant try/finally. Passe interrompue
explicitement, ses processus et deux dossiers temporaires nettoyés.

Le banc saute désormais explicitement si Chromium manque. Le lancement est
dans try/finally ; les blocs de nettoyage imbriqués arrêtent le serveur et
effacent son dossier même si la fermeture du navigateur échoue.

[launch-failure-cleanup.txt](launch-failure-cleanup.txt) : après correction,
une injection de panne force les deux launch à lever une exception malgré la
pré-vérification. Les deux tests échouent comme attendu et Node termine seul
en environ deux secondes (code 1, sans atteindre le timeout de 20 s).
Reproduire avec un préchargement CommonJS temporaire :

```js
const { chromium } = require('playwright');
chromium.executablePath = () => process.execPath;
chromium.launch = async () => { throw new Error('INJECTED_CHROMIUM_LAUNCH_FAILURE'); };
```

Puis `node --require /chemin/fixture.cjs --test --test-name-pattern Chromium desktop/connected/tests/server.test.js`
avec le même NODE_PATH. Ce sont des échecs injectés du banc, pas des tests
fonctionnels verts ni une exécution du navigateur.

R-G031-2 clarifié dans CANCEL-RECEIPTS.md : cancel historique peut rendre 4
(CANCELLED), command-cancel enregistre et rend 0/2 ; les commandes sont distinctes.
G038 réutilisera le banc existant et étendra reçus/pagination/nettoyage.
Aucun Windows, tunnel SSH, matériel ou serveur personnel testé.
