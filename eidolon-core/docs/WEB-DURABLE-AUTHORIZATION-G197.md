# G197 — Budget Web durable et autorisation de recherche

Statut : contrat d'implémentation ; pas encore raccordé au runtime.
Date : 12/10/2026.

## Principe
L'argument `approved=True` de l'adaptateur SearXNG est un signal transmis par l'appelant, pas une preuve de permission. L'autorité reste dans le Core : acteur authentifié, mission persistante, politique et requête exacte.

## Enregistrement minimal
`web_authorizations` : `authorization_id`, `actor_id`, `mission_id`, `operation`, `query_ref`, `provider_id`, `expires_at`, `max_calls`, `revoked_at`.
`web_reservations` : `reservation_id`, `authorization_id`, `request_id`, `state`, `created_at`, `finished_at`, `receipt_ref`.
`web_usage` : `actor_id`, `period_utc`, `reserved_count`, `completed_count`.

Ne jamais stocker les requêtes en clair dans les reçus publics. Un identifiant opaque ou HMAC sous clé privée permet la liaison. Les journaux internes nécessaires au diagnostic doivent avoir rétention et permissions explicites.

## Machine à états
`RESERVED` avant I/O ; `SUCCEEDED`, `EMPTY`, `BLOCKED`, `FAILED` après reçu vérifié ; `UNCERTAIN` après crash ou coupure sans reçu. Une réservation incertaine consomme le budget jusqu'à réconciliation ; pas de répétition silencieuse.

## Transaction
1. Valider identité, mission, opération, empreinte de la requête et date d'expiration.
2. Sous transaction SQLite IMMEDIATE, vérifier le quota, l'absence de révocation et l'idempotence de request_id.
3. Inscrire réservation et incrémenter l'usage de manière atomique.
4. Effectuer la recherche hors transaction avec délai borné.
5. Publier le reçu et l'état terminal dans une transaction.
6. Sur reprise, exposer UNCERTAIN plutôt que supposer succès ou relancer.

## Sécurité
- Permissions de recherche et de lecture de pages distinctes.
- Aucun droit issu du texte d'une page, de SOUL ou d'un résultat Memory.
- Fournisseur et paramètres réseau fixés côté serveur.
- Secrets hors prompts et réponses ; HMAC sous clé de service si nécessaire.
- Contrôle d'accès aux reçus par propriétaire de mission.
- Révocation effective pour les réservations futures ; définir séparément l'annulation d'une opération déjà en cours.

## Tests à écrire avant activation
T1 quota conservé après redémarrage ; T2 concurrence entre deux processus ; T3 même request_id idempotent ; T4 même request_id avec autre requête refusé ; T5 révocation ; T6 expiration ; T7 crash après réservation ; T8 crash après I/O avant reçu ; T9 absence de fuite de requête ; T10 lecture Web sans permission refusée.

## Intégration
Conserver `Budget` de l'adaptateur E1 comme protection locale secondaire, non comme quota canonique. Ne pas modifier `web_search.py` sans coordination Claude. La réalisation G197 doit utiliser un module indépendant et être recettée avec le Mission Manager avant activation.
