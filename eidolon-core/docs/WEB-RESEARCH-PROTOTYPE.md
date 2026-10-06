# Recherche Web Eidolon — prototype du coordinateur

Auteur : Codex/GPT. Date : 05/10/2026. Base Core `c8cd94a`, cadrage C-D09,
[C-BRAIN-G010](../collaboration/BRAINSTORMING.md#c-brain-g010--recherche-web-fiable-malgre-les-blocages).
Module `research.py`, distinct du transport HTTP candidat G006 livré par Claude
sur sa branche à cette base initiale. **Aucun service de recherche réel raccordé**.

Suite livrée : G006/G007 intégrés dans `534f4f4`, transport durci et
[WebReader raccordé sur serveur local](WEB-READER.md). Ce document décrit le
premier prototype ; le contrat du lecteur détaille les nouvelles observations
HTTP, contrôles entre sauts, suspensions et reçus tardifs.

Le rapport courant est en **version 2** : [contrat URL/cache](RESEARCH-REPORT-V2.md).
Les URL exposées sont minimisées, avec empreintes ; le transport/cache garde
ses URL canoniques complètes. Le texte reçu n'est pas anonymisé.

## Fonctionnement livré

Le coordinateur reçoit une requête explicite et un nombre de pages à lire.
Il interroge les fournisseurs configurés dans l'ordre, sans nouvelle tentative
automatique du même fournisseur. Une erreur/quota/absence de résultat permet de
passer au suivant dans les limites prévues. Les URL sont contrôlées par la
politique `/2`, puis un lecteur injecté récupère les pages autorisées.

Trois interfaces de code Python de confiance :

- `provider.provider_id` et `provider.search(query, limit) -> iterable[Hit]` ;
- `reader.reader_id` et `reader.read(canonical_url, policy) -> Page` ;
- résolveur injecté, déjà utilisé par `egress.decide`.

Seule la requête explicite est transmise au fournisseur, aucun contexte mémoire
implicite. Les URL retournées sont des données non fiables, jamais des permissions.
Le lecteur doit appliquer la politique à **toutes les connexions/redirections**.
Le contrôle de l'URL finale par le coordinateur est un contrôle supplémentaire,
pas une protection rétroactive contre un lecteur qui aurait déjà contacté le LAN.
L'adaptateur WebReader repasse par `fetch(url, policy=...)`, qui contrôle chaque
IP avant connexion ; le raccordement est documenté séparément dans WEB-READER.md.

## Un résultat trouvé n'est pas une source lue

Chaque source conserve les fournisseurs qui l'ont trouvée, leurs titres et
extraits dans `found_by`. Le champ `text` n'est rempli qu'après une réponse
complète HTTP 200 contenant du texte UTF-8 non vide pris en charge. Le lecteur
annonce le `policy_id`, contrôlé avant adoption. Le coordinateur recalcule le
SHA-256 des octets reçus et conserve taille, URL finale, type et horodatage.
Cette provenance n'est pas une signature ni une vérification des affirmations.

Les URL canoniques identiques sont dédupliquées ; deux redirections vers la même
URL finale ne comptent pas pour deux pages distinctes. Des URL différentes avec
le même contenu ou une source commune peuvent encore compter séparément : aucune
indépendance éditoriale n'est prétendue. Un DOI ou des métadonnées seuls demandent
un autre objectif ; ils ne deviennent pas ici une lecture de l'article.

| Statut du rapport | Sens exact |
| --- | --- |
| `READ_TARGET_MET` | Nombre demandé de pages distinctes lues dans le périmètre du prototype |
| `PARTIAL` | Au moins une page lue, objectif quantitatif non atteint |
| `NO_READABLE_SOURCE` | Aucun texte admissible lu, même si le moteur a donné des extraits |
| `CANCELLED` | Annulation constatée ; découvertes et reçus déjà disponibles conservés |
| `DEADLINE` | Budget temporel dépassé ; reçus disponibles conservés, pas de succès annoncé |

`limitation` indique READ_BUDGET/PROVIDER_BUDGET le cas échéant. Aucun de ces états
n'est un `SUCCEEDED` de mission Core ; le module ne modifie ni missions ni mémoire
et ne fournit pas de réponse rédigée par un LLM.

## Blocages et texte pris en charge

- Fournisseur : EMPTY distinct de UNAVAILABLE/RATE_LIMITED/PROVIDER_ERROR.
- Lecture : HTTP 401/403, 429, erreurs HTTP, contenu trop grand, tronqué, vide,
  encodage invalide ou format non pris en charge restent distincts.
- HTML : quelques titres exacts de défi et formulaires avec champ password
  produisent CHALLENGE_SUSPECTED/LOGIN_SUSPECTED. Un article parlant des CAPTCHA
  n'est pas automatiquement classé défi. Une forme HTML évidente, même déclarée
  text/plain, passe par ce contrôle.
- Seuls **text/plain et text/markdown UTF-8** sont lus dans cette tranche.
  Un HTML normal reste UNSUPPORTED_CONTENT : l'extracteur est un prochain lot.
  Aucune promesse de reconnaître toutes les pages de défi, surtout mal étiquetées.
- Une erreur arbitraire d'adaptateur devient un code générique sans copier son
  texte. Cela n'est pas un détecteur de secrets présents dans les pages/extraits.

## Budgets, cache et attente

Valeurs par défaut : trois fournisseurs, dix résultats chacun, cinq lectures,
128 000 octets par page, 30 secondes vérifiées entre opérations. La consommation
d'un itérable de résultats est bornée à la limite plus un ; un lot mal formé
est refusé avant lecture. Les tailles des extraits/titres et configurations sont
bornées. Les objets Python retournés existent néanmoins avant validation : pas
de bac à sable mémoire pour un fournisseur de confiance.

Cache RAM de session, seize pages au plus, 60 secondes, clé comprenant lecteur,
politique et URL. Nouvelle copie du résultat à la sortie. La date d'observation
et le hash restent ceux de la lecture initiale, `cache_hit=true` est visible.
Avant réutilisation, URL demandée **et finale** sont recontrôlées, y compris DNS.
Changer la politique ou le lecteur ne réutilise pas l'entrée d'une autre identité.
Le lecteur doit changer son identifiant/version si sa configuration sémantique
change. Pas de cache disque, authentifié, partagé ou durable dans cette tranche.

Une lecture 429/AccessFailure RATE_LIMITED enregistre une suspension du domaine
(hôte/port), utilisant `retry_after` validé en secondes, 60 secondes par défaut.
Pas de sommeil ni relance automatique. Après 64 domaines suspendus, une pause
globale conservatrice borne cet état RAM sans oublier une interdiction active.
WebReader parse le vrai en-tête Retry-After (date ou durée) et conserve les
valeurs hors périmètre comme demande de revue. Les quotas de recherche sont signalés mais
ne sont pas conservés entre recherches : ordonnanceur par fournisseur à développer.

Le TTL des copies Web ne change **aucun accord humain** ni proposition mémoire.
Les propositions sans décision conservent les règles Core existantes.

Le délai global est **coopératif** : un résolveur/fournisseur/lecteur bloquant
peut le dépasser. Le coordinateur ne le tue pas ; il constate ensuite le délai.
Le raccordement aux exécutants à délai de Core reste nécessaire avant exposition
réelle. Une annulation constatée après une lecture ne jette pas son reçu.
Une opération interrompue ne conserve aucune nouvelle entrée de cache ; une
revalidation DNS du cache interrompue n'adopte pas son texte.

## Démonstration reproductible

Depuis `eidolon-core/`, Python 3.11+ et bibliothèque standard :

```sh
PYTHONPATH=src:. python -m examples.research_demo
PYTHONPATH=src:. python -m examples.research_demo --format human
PYTHONPATH=src:. python -m unittest tests.test_research -v
```

Trois scénarios : repli après quota, réutilisation sans seconde lecture, résultat
partiel avec défi HTTP 200. Les domaines, documents et DNS sont fictifs ; aucune
connexion n'est ouverte. Le mode humain reprend le standard Eidolon.
[Preuves de validation](validation/2026-10-05/codex-research/README.md).

## Suite et séparation des travaux

G007 est reçu : comparaison contradictoire et corpus indépendant, dont la
cohérence est vérifiée mais pas encore la conformité du coordinateur. G006 et
son raccordement sont intégrés, testés sur simulation et loopback. Prochains
travaux : adapter un fournisseur réel choisi, choisir
un extracteur HTML, budget durable/attente par fournisseur, provenance des sauts
et artefacts, puis objectif de mission avec critères de source indépendants du LLM.

SearXNG, Brave ou Crossref sont des pistes du brainstorming, pas des dépendances
installées ou des choix adoptés. Aucun index global du Web développé, aucune
rotation d'identité, aucun abonnement, VM, navigateur ou pare-feu/VPN modifié.
