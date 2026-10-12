# G191 — Revue de raccordement Web, Core et SearXNG

Date : 12/10/2026. Statut : revue du code existant, sans activation ni déploiement.

## Constats dans le code

- `research_runtime.py` déclare explicitement un parcours sur fixtures : `SyntheticResearchBackend`, `FixtureProvider`, `FixtureReader`, `ResearchFixturePolicy`. La politique limite l'effet à `local_synthetic_state`.
- `research.py` fournit `ResearchCoordinator`, `Hit`, `Page`, `ResearchLimits`, `AccessFailure`. Les fournisseurs et lecteurs y sont injectables mais réputés fiables ; aucune implémentation réseau intégrée dans ce module.
- Les limites existantes incluent 3 fournisseurs, 10 résultats par fournisseur, 5 lectures, 128000 octets par page, 30 secondes, cache borné. Les erreurs distinguent notamment RATE_LIMITED, TIMEOUT, ACCESS_DENIED, POLICY_REFUSED, TRUNCATED, TLS_ERROR.
- `egress`, `web_transport`, `web_reader` et `html_extract` existent. Leur présence ne constitue pas une qualification d'un connecteur SearXNG réel.

## Décision d'intégration proposée

**Ne pas remplacer** le parcours synthétique, qui sert de référence de régression. Introduire une nouvelle configuration explicite pour un fournisseur réel ; conserver l'injection par interfaces du coordinateur. SearXNG produit des `Hit`, le lecteur contrôlé produit des `Page`.

### Frontières

1. Core authentifie la mission et obtient l'autorisation `web.search` avant de transmettre la requête.
2. L'adaptateur SearXNG traite uniquement un endpoint de confiance explicitement configuré ; les résultats qu'il renvoie restent non fiables.
3. `web.fetch` ne réutilise pas automatiquement la confiance accordée au endpoint SearXNG. Chaque URL de résultat doit repasser les contrôles egress et DNS/redirections.
4. Les recherches ne reçoivent pas automatiquement des extraits privés de Memory.
5. Le rapport lie chaque citation à une URL effectivement récupérée, pas seulement affichée dans les résultats de recherche.
6. Les budgets, erreurs et reçus doivent survivre à l'arrêt de la mission sans annoncer une réussite non vérifiée.

## Points de revue du lot Claude E1

- Contrat exact `search(query, limit)` et traduction vers `Hit`.
- JSON strict et borné, extraction de `results[].url/title/content` sans confiance dans les métadonnées tierces.
- URL du fournisseur configurée hors prompt ; aucune URL arbitraire fournie par le modèle.
- Authentification/restriction réseau de SearXNG, gestion 429 et timeouts.
- Rejets de données hostiles, limites de taille et absence de journalisation des requêtes privées.
- Tests HTTP simulés indépendants, puis recette réseau réelle seulement après autorisation.

## Scénarios avant promotion

S1 : tests de non-régression du backend synthétique.
S2 : SearXNG local simulé → résultats structurés ; données hostiles rejetées.
S3 : lecteur refuse les résultats en IP privée, métadonnées cloud ou redirection interne.
S4 : modèle ne peut ni changer le fournisseur ni augmenter les permissions.
S5 : 429/timeout et mémoire indisponible → réponse honnête, sans citations inventées.
S6 : vraie recherche publique sur VM test, journaux expurgés, rollback.
S7 : session Windows/mobile → résultat avec sources et erreurs visibles.

## Suite

Attendre la livraison E1 de Claude avant modification des modules partagés. Conserver G181/G182 Memory et les recettes Darme comme priorités de validation. Aucun test VM effectué dans cette revue.
