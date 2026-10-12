# Accès Web G187 — audit du transport, fournisseurs, contrat d'outil (Claude)

Auteur : Claude. Date : 12/10/2026, Europe/Paris. Demande : C-MSG-G187.
Statut : **étude et proposition**. Aucun code runtime modifié, aucun
fournisseur activé, aucun port ouvert. Sondes :
`tests/test_web_g187_probes.py` (3 vertes, 1 échec attendu).

## 1. Ce qui existe déjà (lu et sondé)

| Brique | Fichier | État |
| --- | --- | --- |
| Politique de destination | `egress.py` (`web-destination/2`) | solide : schémas, ports, noms locaux, formes numériques ambiguës, **toutes** les adresses DNS publiques, NAT64, 6to4 et Teredo, exclusions configurables, chaque redirection revérifiée |
| Transport de lecture | `web_transport.py` | GET seul vers l'**adresse épinglée** ; SNI et certificat sur le nom vérifié ; ni proxy, ni cookie, ni décompression ; corps, en-têtes et durée bornés ; `Retry-After` prudent ; reçu sans contenu (`evidence()`) |
| Lecteur | `web_reader.py` | adapte le transport à `ResearchCoordinator` ; échecs nommés |
| Extraction HTML | `html_extract.py` | bornée, facultative |
| Coordinateur | `research.py`, `research_guard.py`, `research_pauses.py` | multi-fournisseurs, pauses durables, requête nettoyée **une fois** |
| **Fournisseur de recherche** | — | **absent** : seules les pages d'essai (`research_runtime.FixtureProvider`) existent |

Mes sondes confirment, sans réseau :
- `file:`, `ftp:`, `data:`, `javascript:` et `http:` (par défaut) sont refusés
  **avant** toute résolution DNS ;
- une redirection vers les métadonnées cloud, `127.0.0.1`, `::1` ou un nom
  privé est refusée **sans contact** ;
- un DNS qui change de réponse après le contrôle ne change pas l'adresse
  contactée.

## 2. Écarts trouvés

- **W1 — Le DNS échappe au budget total** (`expectedFailure`, mesuré :
  1,0 s pour un budget de 0,2 s).
  - `system_resolver` appelle `getaddrinfo`, qui n'a pas de délai ; les
    reprises de `resolv.conf` peuvent durer des dizaines de secondes.
  - Proposition : un résolveur qui reçoit le temps restant (fil de travail
    avec délai, ou résolution DNS bornée) ; la sonde passera alors au vert.
- **W2 — Proxy.** Le transport refuse tout proxy, et c'est voulu : un proxy
  change la destination réelle.
  - Conséquence : il exige une sortie **directe** depuis la VM.
  - Dans mon conteneur, tout passe par un proxy obligatoire : le transport
    y échoue (`RESOLUTION_FAILED`). Je ne peux donc **pas** faire la recette
    réelle ; elle doit se faire sur la VM.
- **W3 — Le fournisseur de recherche n'est pas un « lecteur ».**
  - Une API de recherche demande une clé, envoie la requête en paramètre et
    rend du JSON.
  - Le transport actuel interdit les en-têtes personnalisés : il faut un
    connecteur de fournisseur séparé, avec la clé hors du contexte du
    modèle et jamais journalisée.
- **W4 — Ce qui part chez le fournisseur.** `clean_query` ne retire ni les
  noms ni la prose privée (voir I2, C160). La requête envoyée doit être
  montrée et approuvée, et jamais rédigée par un modèle qui a lu MEMORY.

## 3. Fournisseurs de recherche : état au 12/10/2026

**Limite** : les pages officielles sont inaccessibles depuis mon conteneur
(réseau). Ces informations viennent de résultats de recherche, souvent des
sites tiers, et sont **à vérifier** sur les pages officielles avant tout
choix.

| Option | Ce que disent les sources | Avis |
| --- | --- | --- |
| **Brave Search API** | index indépendant ; paiement à l'usage, environ 5 $ pour 1 000 requêtes, avec un crédit mensuel de 5 $ qui aurait remplacé l'offre gratuite en février 2026 ; carte bancaire, pas de plafond de dépense par défaut ; mention « Powered by Brave » demandée | **candidat principal** : API officielle et documentée. Il **faut** un plafond de dépense côté Eidolon |
| **SearXNG** auto-hébergé | métamoteur AGPL-3.0, sortie `format=json` ; il interroge d'autres moteurs, qui peuvent bloquer ou limiter | **repli local**. Les conditions d'usage des moteurs interrogés sont à respecter ; ce n'est pas une source « officielle » |
| Google Custom Search JSON API | fermée aux nouveaux clients, fin pour tous le 1er janvier 2027 | **exclu** |
| Bing Search API | retirée le 11 août 2025 | **exclu** |
| API « pour agents » (Tavily, Exa, etc.) et API de résultats Google tiers (SerpApi…) | payantes ; certaines récupèrent les pages Google | à étudier seulement si Brave ne convient pas ; conditions d'usage à lire |
| API spécialisées (Wikipedia, arXiv…) | gratuites, ciblées | utiles **en plus**, pas en remplacement |

Proposition : **Brave en premier** (clé dans un fichier privé 0600 sur la
VM, plafond mensuel dans la politique), **SearXNG en repli**, sous une seule
interface `web.search`.

Le choix et la dépense reviennent à toytoy : je ne l'attribue à personne.

## 4. Contrat d'outil proposé, compatible avec G187

```text
web.search(query, max_results ≤ 10, deadline) → status OK|EMPTY|BLOCKED|TIMEOUT|ERROR
  results[]: {title ≤ 300, url (canonique, refiltré par egress.decide), snippet ≤ 500, provider, rank}
  receipt:   {provider, provider_version, query_sha256, query_shown_to_user: true, sent_at, results_count,
              cost_units, error_code}
web.fetch(url, deadline) → le WebReader actuel ; le texte extrait reste une donnée non fiable
```

Règles :
1. Une URL d'un résultat passe **de nouveau** par `egress.decide` avant
   `web.fetch` : un fournisseur peut rendre une URL interne.
2. La **requête exacte** est affichée ; une requête qui contient une donnée
   privée exige une confirmation séparée.
3. La clé n'apparaît ni dans le prompt, ni dans les reçus, ni dans les
   journaux ; seul un identifiant de fournisseur y figure.
4. Budget : nombre de requêtes par mission et par jour, et coût cumulé ; au
   plafond, `BLOCKED` explicite et aucune requête.
5. `EMPTY` n'est jamais complété par des sources inventées. En cas d'échec,
   le rapport dit « pas de recherche faite ».
6. Les fixtures restent des tests unitaires et ne comptent pas comme accès
   Internet.

## 5. Tests à écrire avec l'adaptateur

- Faux serveur de fournisseur en local (127.0.0.1, sans Internet), avec les
  cas : succès, vide, 401, 429 avec `Retry-After`, 500, JSON invalide,
  réponse trop grande, URL interne dans les résultats, champs trop longs,
  coupure.
- La clé ne sort jamais : recherche dans les reçus, les exceptions et les
  journaux capturés.
- Un secret de MEMORY n'apparaît dans aucune requête sortante (journal du
  faux serveur).
- Plafond de budget atteint : aucune requête n'est envoyée.
- W1 vert : un DNS lent reste dans le budget.
- **Recette réelle sur la VM**, après autorisation : 3 requêtes publiques,
  sources ouvertes et vérifiées à la main.

## 6. Périmètre déclaré avant implémentation (demande G187)

Si GPT et toytoy valident, je toucherais **seulement** des fichiers
nouveaux :
- `src/eidolon_core/web_search.py` : contrat, budget, adaptateurs Brave et
  SearXNG, connecteur à clé ;
- `tests/test_web_search.py` : faux serveurs en 127.0.0.1.

Je ne toucherais **pas** à `egress.py`, `web_transport.py`, `web_reader.py`,
`research_*.py`, `dialogue.py` ni au Mission Manager. Pour W1, je
publierais un diff à faire relire, sans modifier le fichier.
