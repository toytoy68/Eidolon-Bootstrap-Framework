# Corpus synthétique de recherche Web — C-TASK-G007

Auteur : Claude, 05/10/2026. Fiche [C-TASK-G007](../../../../collaboration/tasks/C-TASK-G007.md).
Base : `51d525e` (contient C-MSG-G017). Statut : corpus **indépendant** du
coordinateur `research.py` de Codex, que je n'ai ni lu ni modifié. Il sert
d'oracle externe : un coordinateur passe le corpus s'il produit les états attendus.

Tout est fictif : domaines en `.example`, pages écrites pour l'essai, aucune
donnée personnelle, aucun service réel contacté pour simuler un blocage.

## Fichiers

| Fichier | Rôle |
| --- | --- |
| `cases.json` | 20 cas : situation, justification (`why`), mise en place, oracle attendu |
| `bodies/` | 11 pages HTML/TXT synthétiques ; chaque usage cite son SHA-256 et sa taille |
| `build_corpus.py` | Génère `cases.json` de façon déterministe à partir de `bodies/` |
| `check_corpus.py` | Vérifie le corpus (code 0 seulement si tout passe) |
| `check-output.txt` | Sortie réellement obtenue ici, Python 3.11.15 |
| `run_against_research.py` | Fait passer les 20 cas dans `research.py` de Codex (importé, jamais modifié) |
| `research-run.txt` | Résultat de ce passage, cas par cas |

```sh
cd eidolon-core/docs/validation/2026-10-05/claude-g007
python3 build_corpus.py && python3 check_corpus.py
```

`check_corpus.py` contrôle : identifiants uniques ; présence des 12 situations
exigées par la fiche ; vocabulaire d'états fermé ; fichiers présents avec
empreinte et taille exactes ; hôtes réservés `.example` ; cache rattaché à une
page ; absence d'adresse électronique hors `example.invalid` et d'adresse IP
privée. Essai de mutation exécuté ici : un état inconnu, une empreinte fausse,
un cas obligatoire retiré, une adresse électronique d'apparence réelle et un
hôte non réservé sont tous détectés. Le vérificateur ne fait pas tourner de
coordinateur : brancher `research.py` sur ce corpus relève de l'adaptateur de Codex.

## Passage dans `research.py` (commit `99641df`)

Le coordinateur de Codex est arrivé pendant ce lot ; le corpus a été branché
dessus par des doubles (fournisseurs, lecteur, DNS), sans réseau. Chaque cas
reçoit un verdict : `PASS` (conforme à l'oracle), `KNOWN_GAP` (limite que
`WEB-RESEARCH-PROTOTYPE.md` annonce déjà : pas d'extracteur HTML, pas de
`robots.txt`, pas de comparaison d'affirmations, pas d'indépendance éditoriale,
pas de copie périmée affichée) ou `FINDING` (écart non annoncé).

**Résultat : 9 PASS, 7 KNOWN_GAP, 4 FINDING** ([sortie](research-run.txt)).

| Écart | Cas | Constat |
| --- | --- | --- |
| Paramètres de suivi | W07 | `?utm_source=…` n'est pas retiré de l'URL canonique : la même page est lue deux fois et compte pour deux sources |
| Statut global ambigu | W14, W15 | « tous les fournisseurs en panne » et « rien trouvé » donnent le même `NO_READABLE_SOURCE` ; seul `providers[]` les distingue |
| Données personnelles | W20 | La requête est envoyée telle quelle au fournisseur, courriel et téléphone compris |

Bons comportements observés, au-delà de l'oracle : une page HTML déclarée
`text/plain` est reconnue comme HTML et non lue ; le cache sert dans sa minute
de validité puis relit après expiration ; un changement de politique n'utilise
pas le cache ; un 429 suspend le domaine sans réessai.

## Schéma d'un cas

```json
{"id": "W04", "title": "…", "category": "challenge", "why": "…",
 "setup": {"query": "…", "providers": {"engine-a": {"status": "ok", "results": [{"url", "title", "snippet"}]}},
           "provider_order": ["engine-a", "engine-b"],
           "pages": {"https://…": {"status": 200, "headers": {…}, "body": "bodies/…", "body_sha256": "…", "size": 0}},
           "cache": [], "robots": {}, "policy": {"blocked_domains": []},
           "budget": {"provider_calls": 4, "page_fetches": 5, "seconds": 30}},
 "expected": {"outcome": "NEEDS_USER", "items": [{"url": "…", "state": "CHALLENGE"}],
              "must_not": ["treat_challenge_as_read", "change_identity"]}}
```

Statuts de fournisseur simulés : `ok`, `down`, `timeout`, `http_429` (avec
`retry_after_seconds`). Statuts de page : un code HTTP ou `timeout`. Horloge
synthétique commune : `2026-10-05T15:00:00+00:00`.

## Vocabulaire de l'oracle

Ces noms sont les miens ; ils restent à faire correspondre aux états de
`research.py`. La correspondance doit être **injective** : deux états distincts
ici ne doivent pas fusionner (par exemple `PROVIDER_UNAVAILABLE` et `NO_RESULTS`).

- **Issue de la recherche** : `ANSWERED`, `ANSWERED_WITH_CONFLICT`, `PARTIAL`,
  `NO_EVIDENCE`, `NO_RESULTS`, `UNAVAILABLE`, `NEEDS_USER`, `BUDGET_EXHAUSTED`.
- **État d'une source** : `READ`, `SNIPPET_ONLY`, `RATE_LIMITED`, `ACCESS_DENIED`,
  `CHALLENGE`, `LOGIN_REQUIRED`, `NOT_FOUND`, `PARTIAL_CONTENT`,
  `NOT_EXPLOITABLE`, `POLICY_REFUSED`, `ROBOTS_DISALLOWED`, `CACHE_STALE`,
  `NOT_FETCHED_BUDGET`.
- **État d'un fournisseur** : `USED`, `RATE_LIMITED`, `PROVIDER_UNAVAILABLE`.
- `must_not` : interdits observables (« réessayer avant Retry-After »,
  « compter un miroir comme source indépendante »…).

## Les 20 cas

| ID | Situation | Attendu | Exigé par la fiche |
| --- | --- | --- | --- |
| W01 | 429 + Retry-After 120 s sur A, B disponible | Repli sur B, A `RATE_LIMITED`, aucune attente au-delà du budget | 429/retry |
| W02 | Page en 429, Retry-After 5 s | Indisponibilité explicite **ou** un seul réessai après 5 s | (ajout) |
| W03 | 403 sur un résultat, autre résultat lisible | `ACCESS_DENIED` + `READ`, recherche répondue | 403 |
| W04 | Défi anti-robot servi en 200 | `CHALLENGE`, issue `NEEDS_USER`, aucun changement d'identité | défi 200 |
| W05 | Vrai article qui cite les phrases d'un défi | `READ` : pas un défi | article CAPTCHA |
| W06 | Page injoignable, seul l'extrait existe | `SNIPPET_ONLY`, issue `PARTIAL` | extrait seul |
| W07 | Même URL (avec `utm_`) par deux moteurs | Une seule lecture | doublon moteurs |
| W08 | Copie identique sur un autre domaine | 1 source indépendante, pas 2 | (ajout) |
| W09 | Cache périmé, site disponible | Relecture et nouvelle date | cache périmé |
| W10 | Cache périmé, site en panne | Copie datée `CACHE_STALE`, jamais présentée comme actuelle | (ajout) |
| W11 | Domaine bloqué après mise en cache | `POLICY_REFUSED`, ni lecture ni restitution du cache | changement de politique |
| W12 | Page de connexion | `LOGIN_REQUIRED`, `NEEDS_USER`, aucun identifiant envoyé | page de connexion |
| W13 | Trois valeurs différentes, trois dates | Désaccord montré avec les dates, aucun choix silencieux | contradictions |
| W14 | Tous les fournisseurs en panne | `UNAVAILABLE`, distinct de « aucun résultat » | fournisseur en panne |
| W15 | Fournisseurs répondent, rien trouvé | `NO_RESULTS` | (ajout) |
| W16 | 5 résultats, budget de 2 lectures | 2 lus, 3 `NOT_FETCHED_BUDGET` visibles | budget insuffisant |
| W17 | Chemin interdit par robots.txt | `ROBOTS_DISALLOWED`, aucune lecture de ce chemin | (ajout) |
| W18 | Page 200 « introuvable » | `NOT_FOUND` | (ajout) |
| W19 | Article coupé par un abonnement | `PARTIAL_CONTENT` | (ajout) |
| W20 | Requête avec courriel et téléphone fictifs | Requête envoyée minimisée, rien de personnel ne sort | (ajout) |

Deux cas sont volontairement difficiles :
- **W05 face à W04** : l'article contient mot pour mot les phrases du défi.
  Un détecteur par mots-clés échoue sur l'un ou l'autre. Il faut des signaux de
  structure : longueur du texte principal, balise `<article>`, présence d'un
  script de défi, méta-rafraîchissement, `<noscript>`.
- **W08** : les octets diffèrent (titre), le texte principal est identique.
  Comparer le SHA-256 brut ne suffit pas ; il faut comparer le texte extrait.

## Trois tests de recette future (sur vrai réseau, après accord)

1. **R-WEB-1 — Trois chemins, une question.** Une question de documentation
   précise (une option d'un logiciel à une version donnée), résolue par
   (a) le dépôt source à un tag, (b) une API officielle si elle existe,
   (c) une recherche puis lecture. Mesurer : réponse correcte, preuve (commit,
   URL, date, empreinte), latence, nombre de requêtes. Attendu : (a) donne la
   preuve la plus stable ; l'écart avec (c) est consigné.
2. **R-WEB-2 — Politesse et quotas.** 50 lectures sur une liste blanche de
   sites autorisés. Attendu : zéro réessai avant `Retry-After`, budget par
   domaine jamais dépassé, `robots.txt` respecté, en-tête `User-Agent`
   identifiable avec contact. Tout 429 ou 403 reçu est consigné tel quel.
3. **R-WEB-3 — Lecture assistée.** Une page qui exige une connexion ou un
   défi : Core ne la contacte qu'une fois, propose la lecture assistée,
   l'utilisateur ouvre la page dans son propre navigateur et l'envoie à Core.
   Attendu : provenance « fournie par l'utilisateur », empreinte cohérente,
   Core n'a jamais tenté de contourner le défi.

## Classement proposé (sans décision)

| Niveau | Contenu |
| --- | --- |
| **MVP** | États distincts du corpus ; connecteurs « source d'abord » (dépôts versionnés au commit, registres et API officielles sans clé quand ils existent) ; transport G006 et politique `web-destination/2` ; politesse (budget par domaine, `Retry-After` sans attente bloquante, `robots.txt`, requêtes conditionnelles) ; minimisation des requêtes ; cache local adressé par contenu avec fraîcheur |
| **Suivant** | Une API de recherche officielle derrière l'interface commune ; bibliothèque locale hors ligne (ZIM/Kiwix, documentations téléchargées) avec index FTS5 ; lecture assistée par le client Windows ; repli vers une archive publique étiquetée comme copie datée |
| **Différé** | SearXNG auto-hébergé ; navigateur isolé ; exploration large du Web ; tout mécanisme qui changerait d'identité (exclu par C-D09) |

La justification détaillée est dans ma contribution à
[C-BRAIN-G010](../../../../collaboration/BRAINSTORMING.md#c-brain-g010--recherche-web-fiable-malgré-les-blocages).
