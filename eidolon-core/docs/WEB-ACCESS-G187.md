# G187 — Accès Web réel pour Eidolon : contrat de sécurité et recette

Statut : spécification pour revue croisée ; aucun fournisseur Web activé ni déploiement.
Références : G181-MEMORY-INTERNET-2026-10-12.md ; C-MSG-G187.

## Périmètre

Trois capacités distinctes, chacune explicitement autorisée :
1. `web.search` : rechercher des résultats publics via un fournisseur configuré, avec titre, URL, extrait et horodatage éventuel.
2. `web.fetch` : récupérer le contenu textuel d'une URL publique validée ; limite de taille, MIME, redirections, durée et profondeur.
3. `browser.interact` : hors périmètre de la première version (JS, cookies, comptes, formulaires, actions et sessions).

Ne pas confondre connectivité réseau de la VM avec accès Web utilisable par le dialogue. Pas de port entrant requis.

## Contrat d'outil minimal

Entrée : `request_id`, `actor_id` authentifié, `mission_id`, `operation`, `query` ou `url`, `purpose`, `max_results`, `deadline`.
Sortie : `status` (`OK|EMPTY|BLOCKED|TIMEOUT|ERROR`), `results`, `source_urls`, `fetched_at`, `provider`, `error_code`, `truncated`.
Chaque source garde sa provenance et sa date ; un extrait ou contenu Web reste **non fiable** et ne peut autoriser une commande.

## Politique de sécurité

- Le Policy Engine décide avant chaque appel ; aucune permission Web implicite issue de SOUL, d'un souvenir ou d'une page.
- Rejeter `file:`, `ftp:`, `data:`, `javascript:` et autres schémas ; HTTP(S) seulement, avec politique de redirection explicite.
- DNS résolu et adresses vérifiées avant connexion, y compris après chaque redirection ; refuser IP privées, loopback, link-local, multicast, metadata cloud, réseaux réservés et hôtes internes. Prévenir DNS rebinding et IPv6 bypass.
- Timeout connexion et lecture, plafond de réponse, nombre de redirections, taille requête, résultats et concurrence ; journaliser les erreurs sans secrets.
- Aucune transmission automatique de Memory, SOUL, tokens, logs privés ou fichiers utilisateur au fournisseur. Si la requête contient des données privées, confirmation et minimisation.
- Traiter le contenu externe comme données non fiables (prompt injection). Les instructions contenues dans une page ne deviennent jamais des instructions du Core.
- Respecter les conditions d'utilisation, robots et limitations du fournisseur ; privilégier un fournisseur officiel/documenté et un fallback explicite.
- Pas de navigateur connecté, téléchargement exécutable ni écriture sur le système dans cette phase.

## Pipeline d'intégration proposé

Demande utilisateur → mission Core → Policy (permission et budget) → recherche → sélection d'URL → fetch sûr → extraction bornée → citations → synthèse du modèle → validation de provenance → reçu durable.

Memory Engine peut fournir un contexte local au Core, mais ce contexte ne doit pas être injecté par défaut dans les requêtes externes. En cas d'indisponibilité Web, rapporter l'échec et éventuellement répondre depuis des connaissances locales en indiquant la limite.

## Tests d'acceptation

- Recherche publique réelle : sources consultables, dates et provenance.
- Résultats vides, fournisseur 429/500, coupure, timeout : erreurs explicites, pas de sources inventées.
- URL internes, localhost, IP privées, IPv6 local, URL encodées, DNS rebinding, redirection vers réseau privé : refus avant lecture.
- Pages contenant instructions hostiles : aucune élévation de permissions, aucune action hors recherche.
- Secret fictif présent dans Memory : jamais envoyé à un endpoint externe.
- Deux appels simultanés : budgets et annulations indépendants, reçus stables.
- Reprise après crash : ne pas annoncer une recherche effectuée sans reçu et sources vérifiables.
- Tests réseau en environnement isolé, puis recette VM après autorisation ; les fixtures restent des tests unitaires, pas une preuve de fonctionnement réel.

## Décisions encore ouvertes

Fournisseur de recherche, politique des domaines autorisés, budget d'appels, stockage des extraits, durée de conservation, consentement pour requêtes sensibles, mécanisme de fallback. Claude doit réaliser la contre-revue avant l'activation.

## Répartition

Claude : audit et adaptateur fournisseur avec tests sur branche réservée.
GPT : contrat, menace SSRF/exfiltration, validation de provenance et intégration contrôlée au Mission Manager après coordination.
