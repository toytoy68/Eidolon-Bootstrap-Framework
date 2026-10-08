# C-TASK-G074 — Contre-revue des configurations locales et de leur identité

Auteur : Codex/GPT. Date : 08/10/2026, Europe/Paris.
Attribution : Claude. Statut : PRÊT, non déclaré en cours.
Base de lecture : `6f46219bfe578902f892d48c7437b042b2616a10`, `feat/eidolon-core-v0.1`.
Noter le SHA exact si une base plus récente est utilisée.

Cible figée : C-036/C-038, `model_config.py`, `model-config-check`, identités
des deux adaptateurs. Périmètre : `docs/validation/2026-10-08/claude-g074/`.

Essayer les URL loopback IPv4/IPv6, ports, chemins, caractères invisibles,
clés inconnues, booléens à la place d'entiers, options du mauvais fournisseur,
permissions publiques/liens/FIFO et remplacements concurrents. Prouver que
l'inspection n'accède ni à la valeur de clé, ni au réseau, ni à Store/Runtime.
Changer une option doit changer l'identité correspondante ; changer la valeur
de clé sans renommer sa variable doit garder la limite documentée.
Signaler aussi les différences entre API Python et politique CLI sans les
présenter toutes comme des défauts. Aucune URL/service utilisateur contacté.

Livrer un commit distinct, une réponse signée et les preuves réellement exécutées.
Préserver les autres contributions. Pas de main, déploiement ni modification du
Memory Engine. Si un lot est bloqué, avancer un autre lot prêt. Les fiches ne
lancent pas de session Claude.
