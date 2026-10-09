# C-TASK-G099 — Évolution du format de stockage des conversations

Auteur : Codex/GPT. Attribution : Claude. Date : 09/10/2026, Europe/Paris.
Statut : PRÊT selon dépendances. Base Codex : 6d6c99f607dd29c1cb12f325f930da05f97b8b67.
Claude observé : ccf9a9e74fc9d4f895ca290b06738cdd15375791, C103 (G084 annoncé engagé).

Après G085/G093. Versionner le stockage et prévoir inspection hors ligne, rejet d’une version future, sauvegarde vérifiable puis migration explicite d’une ancienne version supportée. Ne pas migrer automatiquement une base ouverte en lecture.

**Livrable et acceptation.** Tests : ancienne version, nouvelle version inconnue, migration interrompue et disque en erreur. Conserver identifiants/ordre/références et ne pas rejouer les missions liées. Documenter retour arrière et limites.

Conserver G084–G089 en priorité, puis respecter les dépendances de G090–G101.
Les autres tâches G080–G083 restent attribuées. Lire la tête actuelle et coordonner
les fichiers partagés. Publier code, tests exécutés et limites séparément des
résultats rapportés. Aucun main, déploiement ou changement Memory Engine.

## Reprise Codex du 09/10 après 17 h 37 — C-068/C-069

Toytoy signale Claude arrêté et autorise Codex à poursuivre.
G099-R1 : media_links ajoutée au digest logique et aux comptages. Schéma v5 pour job_id figé ; sauvegarde et migration explicites. Tests Python à exécuter.
[Preuves et limites](../../docs/validation/2026-10-09/codex-takeover-c068/README.md).
