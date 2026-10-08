# C-TASK-G077 — Étude du contexte d’activité et de la reprise suggérée

Auteur : Codex/GPT. Date : 08/10/2026, Europe/Paris.
Attribution : Claude. Statut : PRÊT, non déclaré en cours.
Base de lecture : `6f46219bfe578902f892d48c7437b042b2616a10`, `feat/eidolon-core-v0.1`.
Noter le SHA exact si une base plus récente est utilisée.

Périmètre : `docs/proposals/2026-10-08-claude-activity-context.md` uniquement.
Aucune capture du PC, extension navigateur, webcam ou collector installé.

Besoin rapporté : relier applications/onglets et missions pour suggérer la reprise
d'un travail interrompu. Comparer déclaration manuelle, métadonnées d'activité
locales et collecte enrichie. Proposer un événement minimal avec origine, instant,
poste, session, durée de validité et niveau de confiance ; distinguer observation,
inférence et instruction utilisateur. Examiner bruit, poste partagé, onglet ancien,
veille/redémarrage, tâche terminée ailleurs, mode privé et désactivation/effacement.
Un contexte ancien ne doit ni reprendre une action ni accorder une permission.
Définir le rôle de Core et celui de Memory Engine sans écrire dans ses sources,
une rétention proposée et cinq scénarios discriminants sur données synthétiques.
Comparer coût/confidentialité/utilité ; laisser choix et seuils à arbitrer.

Livrer un commit distinct, une réponse signée et les preuves réellement exécutées.
Préserver les autres contributions. Pas de main, déploiement ni modification du
Memory Engine. Si un lot est bloqué, avancer un autre lot prêt. Les fiches ne
lancent pas de session Claude.
