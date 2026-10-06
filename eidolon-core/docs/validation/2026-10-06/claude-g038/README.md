# G038 — banc de bout en bout client–API réel

Auteur : Claude, 06/10/2026. Fiche [C-TASK-G038](../../../../collaboration/tasks/C-TASK-G038.md).
Base : `4a32f38`. Ce banc **étend** celui de G031/G036 sans recréer ses
scénarios : mauvais jeton, arrêt et relance, nouveau Store et reçus restent
dans `server.test.js` et `receipts.test.js`. Le saut si Chromium manque et
le nettoyage protégé ajoutés par Codex sont gardés, et maintenant regroupés
dans `tests/helpers.js` (`cleanup`).

```sh
cd eidolon-core
NODE_PATH=<dossier contenant playwright> node --test "desktop/connected/tests/**/*.test.js"
```

Prérequis : Python ≥ 3.11 (sinon les tests serveur sont « skipped », donc
**non exécutés**) et Chromium (sinon les tests navigateur sont « skipped »).
Vrai `http_api` sur `127.0.0.1:0` ; états synthétiques dans des dossiers
temporaires ; 150 ou 250 missions créées en un seul processus Python, avec le
même `Runtime.create` que la CLI. Le banc attend des conditions, jamais un long
délai fixe.

[Résultat : 43/43 en 17 s, 0 sauté](node-tests.txt). Environnement : Linux,
Python 3.11.15, Node 22.22.0, Chromium headless (Playwright 1.56.1).
**Aucun Windows réel.**

## Nouveaux scénarios (`tests/integration/e2e.test.js`)

| Scénario | Vérifié |
| --- | --- |
| 154 missions | 2 pages, curseur renvoyé tel quel, liste complète, ordonnée, sans doublon |
| 254 missions | **2 requêtes**, 200 affichées, « Liste tronquée : 200 affichées sur 254 annoncées » |
| Mission créée par la CLI **entre deux pages** | `RESET_REQUIRED`, les 100 premières gardées et périmées, relecture explicite complète (125) |
| Annulation par la CLI puis 4 `poll` | chaque événement **une fois** ; la base a reçu exactement les 2 événements de la CLI ; le client n'utilise que les routes de lecture |
| Chemins d'échec | démarrage refusé (état absent), scénario qui lève une erreur, navigateur impossible à lancer : serveur arrêté et dossier supprimé à chaque fois |
| Chromium, 154 missions | 154 boutons, sélection au clavier de la 121e, puis serveur arrêté : « injoignable », liste gardée. [Capture](g038-150-missions.png) |

## Constat corrigé dans le client

**R-G038-1 (P3)** : au-delà de 200 missions, le client lisait une **troisième
page** puis la jetait entière. La borne de 200 n'était constatée qu'en
essayant d'ajouter la 201e. [Avant : 3 requêtes](truncation-before-4a32f38.txt).
Correction dans `session.js` seulement : la lecture s'arrête dès que 200
éléments sont affichés et qu'il en reste. Le consommateur partagé du
prototype (`mission-list-state.js`) est inchangé.

## Limites

- Linux et Chromium headless seulement ; aucun tunnel SSH ni Windows.
- Pas de concurrence entre plusieurs navigateurs.
- Le nettoyage ne couvre que les processus et dossiers créés par le banc. Un
  arrêt brutal de Node lui-même (SIGKILL) laisserait le serveur enfant et le
  dossier temporaire.
