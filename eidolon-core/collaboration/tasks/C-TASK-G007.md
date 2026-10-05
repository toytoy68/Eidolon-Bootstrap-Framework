# C-TASK-G007 — Alternatives de recherche et corpus indépendant

Auteur : Codex/GPT. Date : 05/10/2026. Destinataire : Claude Code.
Base : `c8cd94a` ou descendant contenant G017. Statut : prêt à prendre.
Demande toytoy : brainstorming commun puis développement d'une solution Eidolon.

1. Lire C-BRAIN-G010, ajouter une contribution signée et contradictoire si utile.
   Distinguer les solutions pour découvrir, lire et prouver une source. Examiner
   API spécialisées, corpus local, moteurs interchangeables, extraction existante,
   navigateur isolé, intervention utilisateur et coûts réels à qualifier.
2. Préparer un corpus **synthétique** indépendant, JSON/HTML/TXT, avec oracle
   attendu et justification sous `docs/validation/2026-10-05/claude-g007/`.
   Au moins : 429/retry, 403, défi HTTP 200, article légitime parlant de CAPTCHA,
   source uniquement en extrait, doublon entre moteurs, cache périmé,
   changement de politique, page de connexion, résultats contradictoires,
   fournisseur en panne et budget insuffisant. Pas de données personnelles.
3. Proposer trois tests de recette future et un classement MVP/suivant/différé.
   Sources officielles, tests réellement exécutés et hypothèses séparés.

Ne pas modifier `research.py`, ses tests/démo ou le runtime pendant le lot Codex.
Le corpus peut être livré avant un adaptateur d'exécution. G006 est reçu mais pas
encore revu par Codex ; ne pas en élargir le périmètre sous cette fiche.
Aucune rotation automatique d'identité, aucun service réel à contacter pour
simuler un blocage. Pas de déploiement, abonnement ou navigateur à installer.
