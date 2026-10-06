# Revue d'intégration du prototype Claude G009 — Codex/GPT

06/10/2026. Source 111da40, reçue pendant le lot C-008a. Prototype intégré
intact, sans modification de src/ ou tests/ Python par Claude. Lecture du
README, rapport, logique et rendu source ; inspection des captures 01 et 05
fournies par Claude, pas de nouvelle capture produite ici.

- model-tests.txt : **17 tests réussis**, Node 24.19.0/Linux, copie isolée.
- ui-environment-failure.txt : essai complet, 17 réussis et **10 échecs au
  lancement du navigateur**. Playwright est résolvable mais l'exécutable
  Chromium attendu manque ; aucune interaction graphique exécutée ici.
  Les 27 réussis annoncés par Claude restent son résultat rapporté, pas celui
  de notre environnement. Aucun navigateur installé pour masquer cet écart.
- probe-command.cjs / probe-command.json : deux reproductions de G013.

## Défaut de prototype G013 : commande incertaine remplacée

Scénario accuse-perdu : accord envoyé sous k0-0, accusé perdu, reconnexion et
rejeu. L'accord apparaît APPROVED, mais sa commande reste unknown, à juste
titre. dispatch(revoke) ou dispatch(request-cancel) remplace alors client.command
par une nouvelle clé sending. L'ancienne clé n'est ni dans decisionHistory,
ni sélectionnable par la consultation de reçu, qui ne vise que client.command.
Elle reste dans outbox : les traces brutes ne disparaissent pas, mais le suivi
actif de son reçu est perdu. Aucun effet réel : tout est simulé.

Demandé à Claude dans G013 : conserver chaque commande non résolue par clé et
ne pas sacrifier son reçu quand une autre demande part. Ne pas interdire toute
annulation par principe : son suivi peut être indépendant. Tests d'absence de
double envoi et de rattachement des réponses à la bonne requête.

## Raccordement G012

Les événements internes de G009 sont des patches (MISSION_RUNNING, etc.) ;
ceux de client-sync/1 sont des références. G012 doit conserver deux repères
état observé / événements reçus ; aucune contiguïté numérique supposée entre
événements d'une mission (d'autres missions utilisent les séquences intercalées).
La projection Core peut n'avoir aucune proposition, contrairement à plusieurs
fonctions de la démo G009. Prévoir action_view=null sans inventer d'accord.
Les indicateurs micro restent visibles hors ligne dans la capture 05 inspectée.
Aucun client Windows, commande distante ou authentification qualifié.

Reproduire depuis la racine du dépôt :

```sh
node eidolon-core/desktop/prototype/tests/model.test.js
node eidolon-core/docs/validation/2026-10-06/codex-g009-review/probe-command.cjs
```

La seconde sonde affirme le comportement défectueux de 111da40 : sa réussite
est une reproduction, pas une validation du comportement attendu après G013.
