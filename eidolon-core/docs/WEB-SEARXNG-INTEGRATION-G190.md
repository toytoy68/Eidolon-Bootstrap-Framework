# G190 — Plan d'intégration SearXNG dans Eidolon Core

Date : 12/10/2026. Propriétaire : GPT (contrats et recette). Statut : préparation, **aucun runtime activé**.
Lot Claude E1 : adaptateur SearXNG + tests isolés. Ne pas modifier ses fichiers simultanément.

## Objectif minimal
Permettre à une mission authentifiée de demander une recherche Web publique, obtenir des résultats horodatés et sourcés, puis restituer une réponse citée sans révéler le contenu privé du Memory Engine.

## Interfaces proposées
- `SearchProvider.search(query, *, max_results, deadline, request_id)` → `SearchResponse` avec `status`, `provider`, `fetched_at`, `results`, `error_code`.
- Chaque résultat : URL canonique HTTP(S), titre, extrait borné, position, provenance, date de publication optionnelle ; jamais de commande ou instruction exécutable.
- `ResearchCoordinator` reçoit un fournisseur explicitement configuré. Par défaut : backend synthétique existant, sans migration ni changement de comportement.
- `Policy` autorise séparément `web.search` et `web.fetch` ; aucun accès Web implicite à partir du prompt SOUL ou d'une réponse du modèle.
- `Mission Manager` conserve les reçus de recherche et le statut de l'opération indépendamment de la conclusion du LLM.

## Risques à traiter avant activation
1. SearXNG auto-hébergé : protéger l'endpoint local, éviter exposition publique, authentifier les appels Core→SearXNG ou restreindre réseau/identité de processus.
2. Les résultats SearXNG contiennent des URL non fiables. Avant fetch : validation DNS/IP à chaque redirection, interdiction des réseaux internes, métadonnées cloud et schémas non HTTP(S).
3. Ne pas laisser un résultat Web influencer les permissions ou injecter de nouveaux outils. Extraction en zone non fiable et citations liées à l'URL réellement consultée.
4. Budget : limite de requêtes, taille de résultats, durée, concurrence et annulation ; réponse 429/timeout/erreur explicitement distinguée d'une recherche vide.
5. Confidentialité : ne pas transmettre par défaut les souvenirs, secrets, logs, chemins locaux ou le prompt SOUL dans la requête au fournisseur.
6. Journalisation : stocker les paramètres minimisés, horodatage, fournisseur, statut et empreintes ; expurger secrets et données privées.

## Scénarios d'acceptation
- A1 : recherche publique via serveur SearXNG simulé, schéma validé, citations conservées.
- A2 : fournisseur absent / 429 / 500 / timeout → erreur explicite, aucune source inventée.
- A3 : réponse JSON malformée / URL hostile / extrait gigantesque → rejet ou troncature contrôlée.
- A4 : injection de prompt dans titre/extrait → aucune commande, aucune modification de politique.
- A5 : résultat avec URL privée → non consultable, fetch refusé.
- A6 : demande utilisateur contenant une donnée privée → minimisation/confirmation avant sortie.
- A7 : crash/reprise de mission → pas de succès sans reçu durable, pas de double exécution implicite.
- A8 : activation réelle VM : test de recherche publique avec sources, puis désactivation et rollback vérifiés.

## Plan de travail
E1 Claude : adaptateur et tests HTTP simulés.
E1b GPT : revue de sécurité et contrat d'intégration (ce document).
E2 Claude : étude index documentaire ciblé ; GPT contre-revue frontières avec Memory.
E3 après E1 : intégration sous feature flag désactivé, tests unitaires et régressions.
E4 après rétablissement MCP : recette sur VM de test, vraie recherche, surveillance et journal des preuves.

## Critères de sortie
Une recherche est « fonctionnelle » seulement après validation d'un fournisseur réel et d'un parcours utilisateur complet ; les tests simulés ne suffisent pas. Aucun navigateur interactif ou accès authentifié aux sites dans G190.
