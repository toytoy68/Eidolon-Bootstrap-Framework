# C-TASK-G025 — banc Web indépendant G007 rejoué sur la branche Core

Auteur : Claude, 06/10/2026. Fiche [C-TASK-G025](../../../../collaboration/tasks/C-TASK-G025.md).
Base figée : **`6d1661d1dd77653ff89708767dded82bb7e31d85`**
(`origin/feat/eidolon-core-v0.1`, copie `git archive`). Elle contient les pauses
persistantes, les correctifs d'audit (`97abdb2`, `cd80be2`) et le rapport v2
(`2bad4e6`).

Corpus : [claude-g007](../../2026-10-05/claude-g007/README.md), **inchangé**
(20 cas, 11 pages). Runner : [run_g007_on_head.py](run_g007_on_head.py). C'est
une copie de `run_against_research.py` dont seul le chemin du corpus (`HERE`)
et l'en-tête changent ; les oracles ne sont pas modifiés. Aucun `src/` ni
`tests/` modifié ; aucune requête réelle (doubles de fournisseur, de lecteur et
de DNS).

```sh
cd eidolon-core
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=$FROZEN/eidolon-core/src:$FROZEN/eidolon-core \
  python docs/validation/2026-10-06/claude-g025/run_g007_on_head.py
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=$FROZEN/eidolon-core/src:$FROZEN/eidolon-core \
  python docs/validation/2026-10-06/claude-g025/extra_probes.py
```

Sorties :

- [banc G007 sur 6d1661d](research-run-6d1661d.txt)
- [sondes complémentaires](extra_probes-output.txt)

## Avant / maintenant

| Cas | 05/10 (`99641df`) | 06/10 (`6d1661d`) | Lecture |
| --- | --- | --- | --- |
| W01 429 fournisseur → repli | PASS | PASS | |
| W02 429 site | PASS | PASS | désormais **persistant** (voir sondes) |
| W03 403 | PASS | PASS | |
| W04 challenge | PASS | PASS | |
| W05 page ressemblant à un challenge | KNOWN_GAP | KNOWN_GAP | HTML non extrait |
| W06 délai, extrait seul | PASS | PASS | extrait jamais promu en texte |
| **W07 paramètres de suivi** | FINDING | **FINDING** | toujours 2 lectures et 2 sources ; voir F-W07 |
| W08 sources liées | KNOWN_GAP | KNOWN_GAP | pas d'indépendance éditoriale |
| W09 cache et expiration | PASS | PASS | |
| W10 copie périmée | KNOWN_GAP | KNOWN_GAP | non réutilisée, non proposée |
| W11 changement de politique | PASS | PASS | |
| W12 login | PASS | PASS | |
| W13 résultats contradictoires | KNOWN_GAP | KNOWN_GAP | pas de comparaison d'affirmations |
| **W14 tous fournisseurs en panne** | FINDING | **FINDING** | même statut global que W15 |
| **W15 rien trouvé** | FINDING | **FINDING** | idem |
| W16 budget de lecture | PASS | PASS | |
| W17 robots.txt | KNOWN_GAP | KNOWN_GAP | non consulté |
| W18 soft-404 HTML | KNOWN_GAP | KNOWN_GAP | HTML non extrait |
| W19 paywall HTML | KNOWN_GAP | KNOWN_GAP | HTML non extrait |
| **W20 données personnelles dans la requête** | FINDING | **FINDING** | voir F-W20 |

**Total identique : 9 PASS, 7 KNOWN_GAP, 4 FINDING.** Aucun oracle n'a été
modifié pour faire passer un cas. Les 4 écarts ne sont pas documentés comme
limites dans `WEB-RESEARCH-PROTOTYPE.md` ni dans `RESEARCH-REPORT-V2.md`.
Les 7 KNOWN_GAP restent annoncés ; 3 d'entre eux (W05, W18, W19) relèvent de
l'extracteur HTML (G026).

## Sondes complémentaires sur ce qui a changé depuis le 05/10

| Point | Résultat | Verdict |
| --- | --- | --- |
| **Refus persistant** : 429 avec RA=120 et pauses durables, coordinateur reconstruit | 1 lecture au total, puis `RETRY_WAIT`, pause active | PASS (nouveau) |
| **Cache après retard** : page `deadline_exceeded` | pas de cache au second run (2 lectures) | PASS |
| **Cache après expiration du budget** pendant la page 2 | run 1 `DEADLINE` ; page 1 **non** mise en cache (`cache_hit=False`) | PASS (`2bad4e6`) |
| Cache normal | `cache_hit=True`, 1 lecture | PASS |
| Extrait seul (W06) | `readable_pages=0`, texte nul | PASS |
| Requête dans le rapport | absente (seulement `query_sha256`) | PASS |

### F-W07 — paramètres de suivi : écart toujours présent, plus trompeur à l'affichage (P3)

`https://news.example/a` et `…/a?utm_source=x` donnent :

- 2 lectures ;
- `readable_pages=2` : **une seule page satisfait `required_pages=2`** ;
- depuis le rapport v2, **la même URL affichée deux fois**, différenciée
  seulement par `url_sha256`.

Le contrat v2 l'assume : « ne pas fusionner sur le seul champ url affiché ».
Mais le compteur de pages lisibles reste gonflé. Deux documents réellement
distincts (`?id=1` et `?id=2`) s'affichent aussi au même chemin : c'est
correct, ils restent deux sources.

**Proposition** : ignorer les paramètres de suivi connus (`utm_*`, `fbclid`,
`gclid`) lors de la canonicalisation. **Ou**, plus général, ne pas compter deux
fois une page lisible dont `body_sha256` est identique (statut
`DUPLICATE_CONTENT`).

### F-W14/W15 — « tout en panne » et « rien trouvé » : même statut global (P3)

Inchangé : `NO_READABLE_SOURCE` dans les deux cas ; seul `providers[]` les
distingue. Proposition maintenue : un statut ou une limitation
`PROVIDERS_UNAVAILABLE`.

### F-W20 — données personnelles envoyées au fournisseur (P2, confidentialité)

Le rapport ne contient plus la requête : c'est un progrès du v2. Mais la
requête `joindre jean@example.invalid au 01 23 45 67 89` est **toujours
envoyée telle quelle** au fournisseur de recherche. Aucune détection, aucun
avertissement. Le contrat v2 précise qu'il minimise les **champs URL du
rapport**, pas les données envoyées.

**Proposition** : avant toute recherche externe, détecter les motifs
évidents (courriel, téléphone, IBAN) et exiger une confirmation explicite, ou
refuser. Le choix revient à toytoy.

## Limites

- Doubles synthétiques seulement : pas de moteur ni de site réel.
- Le banc garde ses oracles du 05/10. Un comportement nouveau n'est jugé que
  par les sondes complémentaires.
- Le runner indexe certains états par l'URL affichée (`states()`). Avec les
  URL minimisées, deux sources de même chemin peuvent s'y confondre. Aucun cas
  du corpus n'en dépend pour son verdict (W07 compte `sources`), mais un futur
  runner devrait indexer par `id`.
