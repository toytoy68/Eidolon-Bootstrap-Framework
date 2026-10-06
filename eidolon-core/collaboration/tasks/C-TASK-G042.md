# G042 — Contre-revue de la consultation des reçus

Auteur : Codex/GPT, 06/10/2026, demande toytoy à 19 h 27 Paris.
Base : 7de3646ab2fe15c945b0a81425a98d1a58211bef. Attribué à Claude.

PRÊT. Cible figée 37dc199ec5da7da49655c4be1bc27e90d5b62d7d, base 6395485. Relire receipt_lookup.py/http_api.py et les tests. Éprouver les reçus historiques décision/annulation, champs altérés, lien événement/empreinte, concurrence SQLite, absence ambiguë et données privées. Sondes sur états synthétiques uniquement ; distinguer corruption isolée et modification cohérente de toute la base. Ne pas modifier ces sources réservées Codex ; livrer rapport, sondes reproductibles et sévérité. Cette revue complète G034, qui conserve son ancienne cible.

Publier un commit/message par lot avec preuves et limites. Aucun déploiement,
VM, NAS, GPU ni installation système. Ne pas modifier les fichiers réservés
Codex : http_api.py, preflight.py, receipt_lookup.py et leurs tests Python.
