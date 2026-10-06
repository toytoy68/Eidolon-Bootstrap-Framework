# G043 — Fraîcheur du client face aux réponses refusées

Auteur : Codex/GPT, 06/10/2026, demande toytoy à 19 h 27 Paris.
Base : 7de3646ab2fe15c945b0a81425a98d1a58211bef. Attribué à Claude.

PRÊT après les modifications client engagées. Examiner desktop/connected/src/session.js et ses consommateurs : une réponse HTTP 200 rejetée par le protocole ne doit pas avancer la date de dernière lecture acceptée ni faire croire à un état courant. Tester réponse invalide, liste/sélection ancienne, reconnexion concurrente et RESET_REQUIRED. Reproduire les écarts avant correction ; corriger uniquement le client et ses tests, régénérer app.js. Coordonner avec G036/G037 ; réutiliser leurs tests plutôt que les dupliquer.

Publier un commit/message par lot avec preuves et limites. Aucun déploiement,
VM, NAS, GPU ni installation système. Ne pas modifier les fichiers réservés
Codex : http_api.py, preflight.py, receipt_lookup.py et leurs tests Python.
