# G213 — Revue migration journal et suite Memory
Date : 13 octobre 2026. Aucune intervention VM.

Sur Memory refactor/architecture-v1, commits 3820208 et facf2e1 :
- M2 : conservation de la valeur historique sqlite_sequence pendant la migration v1 vers v2.
- Deux tests de non-réutilisation des séquences après compactage partiel ou complet.

Claude : merci de rejouer ces tests et la suite Memory, puis de vérifier le cas d'une table vide, les migrations répétées et la concurrence. Relever toute divergence de schéma.

M4 reste à traiter : création directe d'un journal v2. Avant de modifier ChangeJournal, inventorier les tests et appels qui supposent actuellement une création v1, et prévoir une migration compatible sans effet de bord. Ne pas appliquer de migration automatiquement à une base existante.

Poursuivre la revue I1/W1 et les sondes Qdrant selon les priorités existantes.

Aucun merge main, aucun déploiement, aucune suppression Qdrant.
