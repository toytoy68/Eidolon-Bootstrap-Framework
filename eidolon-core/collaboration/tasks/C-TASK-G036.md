# G036 — Reçus de commande dans le client connecté

Auteur : Codex/GPT, 06/10/2026. Attribué à Claude à la demande de toytoy
à 19 h 08 (six tâches supplémentaires). Base initiale : 4d0f606.
Statut : attribué ; respecter les dépendances précisées ci-dessous.

Après G031 et publication C-009b. Consommer POST /v1/command-receipt selon docs/HTTP-RECEIPTS.md. Ajouter une consultation explicite par store_id/client_id/command_key/mission_id, sans aucun bouton qui soumet une commande. FOUND = enregistrement historique ; NOT_FOUND conserve l’incertitude ; STORE_CHANGED exige resynchronisation. Ne jamais modifier le snapshot courant à partir du reçu. Token en mémoire, réponses de sélection/connexion anciennes ignorées. Réserver desktop/connected/ et ses tests. Tester décision APPROVED historique puis REVOKED, annulation enregistrée sans arrêt confirmé, clé absente et mauvais Store. Commencer les fixtures si la cible backend n’est pas encore publiée.

Un commit/message par livraison, sources et preuves séparées des constats
rapportés. Publier sur ta branche pour intégration. Ne pas modifier les fichiers
réservés Codex (http_api.py, receipt_lookup.py, tests Python associés).
Aucun déploiement, VM/NAS/GPU ou service personnel à contacter ici.

Cible prête G049 : backend 37dc199ec5da7da49655c4be1bc27e90d5b62d7d,
client intégré en e1059dd13f7a62b9eaba97b1475f57294d96d82e. Fixtures et
scénario reproductible : docs/validation/2026-10-06/codex-http-receipts/.
