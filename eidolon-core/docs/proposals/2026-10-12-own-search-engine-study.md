# Notre propre moteur de recherche — étude à mener avec GPT

Auteur : Claude. Date : 12/10/2026, Europe/Paris.
Statut : **étude ouverte**, rien n'est installé ni lancé.

**Décision de toytoy** (session Claude, 12/10/2026, vers 21 h) : « On reste
sur du gratuit donc SearXNG… Mais !!! Étudie avec GPT la possibilité de
créer notre propre [moteur] à nous ! »

Sources : recherches Web du 12/10/2026, souvent des sites tiers, **à
vérifier** ; liste en fin de document.

## 1. Ce qui est réaliste à la maison

| Approche | Taille | Faisable ? |
| --- | --- | --- |
| Indexer **tout le Web** nous-mêmes | Une seule collecte Common Crawl de 2026 : environ 2,2 milliards de pages et 365 à 400 Tio non compressés | **Non** : stockage, bande passante et maintenance hors de portée |
| Moteur libre existant, auto-hébergé (**YaCy**, GPL-2.0 ; **Marginalia**, AGPL-3.0) | Index propre, petit ; YaCy en pair-à-pair ou en mode isolé | **Possible**, mais qualité modeste d'après les retours ; YaCy est en Java, Marginalia demande de l'infrastructure |
| **Index ciblé Eidolon** : nos propres sources choisies, indexées avec nos briques | De 100 000 à 1 million de pages : environ 0,5 à 5 Go de texte, et environ 0,4 à 4 Go de vecteurs (1 024 dimensions) | **Oui** : c'est la proposition |

## 2. Proposition : hybride SearXNG et « index Eidolon »

- **SearXNG** pour le Web général, gratuit et auto-hébergé : c'est la
  décision de toytoy.
- **Index Eidolon** pour ce qui compte vraiment pour nous : des sources
  **choisies par toytoy**, explorées poliment, et indexées avec ce que nous
  avons déjà :
  - **collecte** : le transport sûr existant (`egress` et `web_transport` :
    adresses publiques, redirections revérifiées, bornes) et l'extraction
    HTML bornée ;
  - **index** : la recherche lexicale et Qdrant de Memory, avec le modèle
    d'embedding déjà téléchargé (G182) ;
  - **interface** : deux fournisseurs dans `ResearchCoordinator`, qui en
    accepte déjà jusqu'à 8. Les résultats gardent leur source et leur date.
- Les deux sont gratuits. L'index Eidolon ne dépend d'aucun moteur extérieur
  pour ses propres sources.

## 3. Sources pour l'index Eidolon (à choisir par toytoy)

1. **Wikipédia en français** depuis les **dumps officiels**, sans
   exploration : licence CC BY-SA, attribution à conserver.
2. **Documentations techniques** utiles : Debian, Proxmox, Python, Docker,
   NVIDIA, etc.
3. **Flux RSS** de sites d'actualité choisis : titres, résumés et liens,
   sans copier les articles.
4. Plus tard, d'autres sites ajoutés **un par un** sur décision de toytoy.

## 4. Règles du robot d'exploration

- `robots.txt` respecté, User-Agent identifiable, au plus 1 requête toutes
  les quelques secondes par site, horaires creux.
- Liste blanche de domaines : jamais d'exploration libre « de lien en
  lien » hors liste.
- On garde un **extrait court**, l'URL, la date et l'empreinte, pas des
  copies complètes d'articles (droit d'auteur).
- Le contenu indexé reste une **donnée non fiable** : les injections de
  consigne sont neutralisées comme partout.
- **Index séparé de Memory** : aucune donnée privée ne s'y mélange, et
  aucune requête privée ne part dehors.
- Fraîcheur visible : chaque résultat porte la date de sa collecte.

## 5. Étapes proposées

| Étape | Contenu | Qui (proposition à discuter avec GPT) |
| --- | --- | --- |
| E0 | SearXNG sur la VM, recette réelle (vraies requêtes, sources ouvertes, erreurs, débit) | GPT/Codex (VM), Claude en contre-revue |
| E1 | Adaptateur `web.search` SearXNG, avec faux serveur en 127.0.0.1 | Claude (nouveaux fichiers, périmètre de C161) |
| E2 | Wikipédia FR depuis un dump : extraction, index lexical et vecteurs, évaluation sur un corpus de questions figé **avant** | Claude (code et banc), GPT (provisionnement VM) |
| E3 | Robot d'exploration poli sur une liste blanche, avec reprise sur incident | Claude (code), GPT (contrat de sécurité) |
| E4 | Fusion des résultats SearXNG et index Eidolon, avec provenance | à répartir |

## 6. Ce qu'il faut décider ou mesurer

- La liste des sources de départ (toytoy).
- La place disque sur la VM Memory ou Core (GPT, à mesurer).
- Le banc de qualité : questions types, avec les bonnes sources figées avant
  l'essai, comme le corpus Memory.
- Licences : Wikipédia CC BY-SA (attribution) ; YaCy ou Marginalia
  seulement si on les choisit, leurs licences GPL et AGPL étant à respecter
  pour un service.

## Sources

- [Mwmbl (README)](https://github.com/mwmbl/mwmbl)
- [Marginalia (Wikipédia)](https://en.wikipedia.org/wiki/Marginalia_(search_engine))
- [awesome-selfhosted, moteurs de recherche](https://awesome-selfhosted.net/tags/search-engines.html)
- [YaCy avec Docker (XDA)](https://www.xda-developers.com/built-my-own-search-engine-decentralized-web-crawling-tool/)
- [Common Crawl (aiwiki)](https://www.aiwiki.ai/wiki/common_crawl)
- [Common Crawl, avril 2026](https://davanstrien-common-crawl-april-2026.static.hf.space/index.html)
