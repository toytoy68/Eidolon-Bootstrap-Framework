# Contre-revue C-TASK-G027 — cache interrompu et rapport Web v2 (`2bad4e6`)

Auteur : Claude, 06/10/2026. Fiche [C-TASK-G027](../../../../collaboration/tasks/C-TASK-G027.md).
Cible figée : `2bad4e6d6eb6d9459fc1468273b0cc40068d9f04` ; base avant correctif
`3edcc9ee65537e8dfb02ee6a94bcc672c76561ed`. Deux copies `git archive`.
SHA-256 identiques à [sha256.txt](../codex-web-disclosure/sha256.txt) (4/4) :
`research.py` `66b31481…`, `research_report.py` `aae051d7…`,
`tests/test_research_disclosure.py` `7a091c9e…`, `examples/research_disclosure_demo.py` `253c6007…`.
Ni `src/` ni `tests/` Python modifiés.

```sh
cd eidolon-core
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=$TREE/eidolon-core/src:$TREE/eidolon-core \
  python docs/validation/2026-10-06/claude-g027/probes_g027.py
```

Python 3.11.15, Linux. Aucun réseau : lecteur injecté, ou vrai
`WebReader`/`fetch` avec DNS et pair HTTP simulés. Le pair HTTP **enregistre la
requête exacte qu'il reçoit**. Mêmes sondes sur les deux arbres :

- [avant `3edcc9e`](probes-3edcc9e.txt)
- [après `2bad4e6`](probes-2bad4e6.txt)
- [tests de Codex rejoués sur la copie figée : OK](codex-tests-on-frozen.txt)

Une page lue n'est jamais un fait vérifié : ces sondes vérifient le transport,
le cache et l'affichage, pas la vérité des textes.

## Verdict : cache et rapport v2 **CONFIRMÉS CORRIGÉS** ; limites annoncées rendues concrètes

### 1. Cache

| Cas | Avant | Après |
| --- | --- | --- |
| Annulation juste après la lecture | reçu gardé, **mais en cache** : le run suivant le réutilise (1 lecture) | reçu gardé (READ, texte), statut CANCELLED, **pas de cache** ; le run suivant **relit**, le 3e prend le cache |
| Budget du coordinateur dépassé à la page 2 | page 1 **en cache** | page 1 hors cache (relue) |
| Revalidation DNS lente d'un cache valide, puis budget dépassé | page **adoptée** (READ, `cache_hit`, comptée lisible) | **non adoptée** (DISCOVERED, 0 page lisible) |
| Cache normal : +30 s / +91 s (TTL 60 s) / autre coordinateur | hit / relu / isolé | identique |
| Revalidation : destination finale devenue privée | POLICY_REFUSED | POLICY_REFUSED |

### 2. Rapport v2 (vrai `WebReader`, redirection, paramètres secrets)

Le pair reçoit les requêtes **complètes** :
`news.example/a?token=…&x=1` puis `mirror.example/b?session=…`. La connexion
n'est donc pas modifiée. Le fragment n'est jamais transmis.

| Point | Avant | Après |
| --- | --- | --- |
| `url`, `final_url`, `retrieval.final_url` | avec paramètres secrets | origine et chemin seulement |
| Secret présent dans le rapport | **oui** | **non**, nulle part |
| `url_sha256` = SHA-256 de l'URL canonique réellement demandée | absent | **égal** ; idem pour `final_url_sha256` |
| `*_query_sha256` | absent | présent quand il y a des paramètres |
| Sauts du transport | chemin, avec `query_sha256` | inchangés (déjà minimisés) |
| Deux URL ne différant que par `?id=1` / `?id=2` | URL différentes | **même chemin affiché**, empreintes distinctes : 2 sources |
| Refus 403 sur une URL avec secret | secret visible | secret absent, `ACCESS_DENIED` gardé |
| Rapport issu du cache | secret visible | secret absent, même empreinte qu'à la lecture |

### 3. Données hostiles : limites annoncées, rendues concrètes (P3)

`RESEARCH-REPORT-V2.md` annonce que les chemins, titres et extraits ne sont pas
anonymisés. Les sondes montrent ce que cela laisse passer dans `url` :

- `…/reset;jsessionid=SECRET` : le **paramètre de session** reste visible.
  `urlsplit` le laisse dans le chemin.
- `…/a%3Ftoken%3DSECRET` : une requête **encodée dans le chemin** reste
  visible.
- `…/u/SECRET/profile` : un identifiant dans le chemin reste visible.
- Titres et extraits contenant des URL secrètes : tels quels.

C'est conforme au contrat, sans défaut.

**Propositions**, au choix :

- retirer aussi les paramètres `;…` du dernier segment (`jsessionid`,
  `sid`) ;
- signaler un chemin qui contient `%3F` ou `%3D`.

## Limites de cette revue

- Lenteur DNS et horloges **simulées**.
- Pas de fournisseur ni de site réels.
- La projection n'est pas une API de validation de rapports arbitraires : non
  testée comme telle, comme annoncé.
