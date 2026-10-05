# Revue de logique des maquettes — Codex/GPT

Date : 05/10/2026, Europe/Paris. Base : `176edac2f92c0af5da60f14456fc5365470651b1`.
Source : Main.dc.html original Claude, SHA-256 `bd35b3742c8372c6553f87ada37947823b9d7cb6bf4d517915ee913a43138170`.

Depuis la racine du dépôt :

```sh
node eidolon-core/docs/validation/2026-10-05/codex-desktop-review/probe-main.cjs
```

Exécuté sous Node v24.19.0/Linux. [Résultat conservé](probe-main.json) :
quatre assertions de comportement réussies, reproduisant trois écarts :
refus → œil « Au travail », accord local hors ligne, undo → attente restaurée.
Une assertion supplémentaire vérifie la présence du script extrait.

La sonde exécute la logique originale dans un contexte avec DCLogic simulé.
Elle constate les raccourcis de la maquette ; leur reproduction n'est pas une
validation de leur comportement souhaité. Aucun rendu HTML, clic navigateur,
accord Core, réseau, appareil ou Windows testé. Les huit sources ont été lues,
mais le moteur support.js du canevas n'est pas fourni. Aucun nouveau résultat
de la suite Core revendiqué dans ce lot documentaire.

Voir [revue et propositions](../../../proposals/2026-10-05-codex-desktop-review/README.md).
