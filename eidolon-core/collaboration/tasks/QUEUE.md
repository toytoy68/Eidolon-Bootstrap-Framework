# File courante de Claude Code — Eidolon Core

Mise à jour Codex/GPT : 06/10/2026, C-MSG-G037, après réception C034/0e65233.
Revue générale intégrée. Clarification : G022–G024 **non faites** ; la mention
« terminées selon toytoy » dans G036 était un décalage de suivi, corrigé ici.

| Ordre | Fiche | État | Livrable / cible |
| --- | --- | --- | --- |
| 1 | [G022](C-TASK-G022.md) | PRÊT | Contre-revue restauration 3f16d7d |
| 2 | [G023](C-TASK-G023.md) | PRÊT après G022 | Abandon explicite, résultat non vérifié |
| 3 | [G024](C-TASK-G024.md) | PRÊT après G023 | Contre-revue cd80be2 |
| 4 | [G025](C-TASK-G025.md) | PRÊT après G024 | Banc G007 actualisé |
| 5 | [G026](C-TASK-G026.md) | PRÊT après G025 | Extracteur HTML autonome et borné |
| 6 | [G027](C-TASK-G027.md) | PRÊT après G026 | Contre-revue 2bad4e6, cache et rapport v2 |

L'utilisateur a demandé cette attribution ; enchaîner sans nouveau feu vert,
un commit/message par lot. Branches/checkouts distincts ; pas de fusion main.
Ne pas refaire la revue globale ni G021. Si un lot bloque, signaler le motif
puis prendre un lot indépendant. Chaque contre-revue garde sa cible exacte.
Codex possède research.py et la projection du rapport ; Claude possède runtime
pour G023, puis html_extract.py/tests/demo dédiés pour G026, sans raccordement.
VM, GPU, NAS, Windows, modèles réels, Bootstrap et déploiement restent hors file.
