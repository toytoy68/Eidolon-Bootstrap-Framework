# G052 — contre-revue du budget d'invocations (C-015) et du seuil des reçus

Auteur : Claude, 07/10/2026. Fiche [C-TASK-G052](../../../../collaboration/tasks/C-TASK-G052.md).

Cibles figées par `git archive` :

- `7d8efb9` ;
- `0fdf18e` (C-012), seulement pour fabriquer des reçus « hash sans seuil ».

`runtime.py`, `store.py` et `receipt_lookup.py` sont identiques à la tête
`48a33fc`. Sources Codex non modifiées ; la proposition est jointe à part.

```sh
python3 docs/validation/2026-10-07/claude-g052/probes_g052.py <copie 7d8efb9>/eidolon-core/src <copie 0fdf18e>/eidolon-core/src
```

Montage :

- mission de démonstration et outils simulés par défaut ;
- arrêts brutaux par `os._exit` dans des sous-processus lancés par la
  sonde ;
- altérations faites sur des copies.

Sorties : [cible](probes.txt), [avec la proposition](probes-proposal.txt).

## Budget d'invocations : conforme

| Cas | Résultat |
| --- | --- |
| Limites 1 à 5 | 1 et 2 : bloqué après 1 et 2 réservations ; **3 : bloqué à 2 réservations, aucun outil lancé** (il faut 2 places : outil et première vérification) ; 4 et 5 : réussite en 4 ; la relance ne consomme rien |
| Arrêt juste après la réservation 1 ou 2 | pas de remboursement ; la reprise refait le rappel et le plan, puis est bloquée à 3 sur 4 : comptage prudent, documenté |
| Arrêt après la réservation 3 (outil, après `CALL_STARTED`) | `REVIEW_REQUIRED / UNKNOWN_EFFECT` alors qu'aucun worker n'a démarré : prudent |
| Reprise avec une autre limite (65, 4, sans budget) | `BLOCKED / CONFIGURATION_CHANGED` ; une reprise ensuite avec la **bonne** limite réussit (pas de blocage définitif) |
| Mission sans budget, reprise à 64 | `CONFIGURATION_CHANGED` : aucune migration silencieuse |
| Compteur seul diminué, événement seul supprimé, limite portée à 4096, champ supprimé | `INVOCATION_BUDGET_INVALID` |
| Compteur **et** événement retirés ensemble | accepté (réécriture cohérente, documentée) |
| 4 processus sur la même mission (reprise après un arrêt) | un seul la traite (ici bloquée par le budget), les 3 autres `Busy` ; ordinaux contigus, jamais au-delà de la limite |

Observation : `_ensure_invocation_budget` relit **tous** les événements de la
mission à chaque invocation. Le coût augmente donc avec l'historique ; non
mesuré à 4096.

## Seuil des reçus : atomique, avec une fenêtre de migration

| Cas | Résultat |
| --- | --- |
| Base neuve | seuil = séquence du premier reçu ; hash retiré + altération au-delà → **refusé** |
| Valeurs de seuil `0`, `abc`, `' 5'`, au-delà du journal, entier SQLite | lecture refusée **et** nouvelle commande refusée (`INVALID_RECEIPT_HASH_BOUNDARY`) |
| Panne après insertion du seuil, avant le commit | rien n'est écrit ; le renvoi de la même clé pose le seuil et le reçu |
| 4 premiers reçus en parallèle | un seul seuil, 4 reçus `EVENT_HASH` |
| Seuil supprimé, puis hash retiré + altération | FOUND `LEGACY_FIELDS` |
| Seuil relevé à `max(sequence)`, puis hash retiré + altération | FOUND `LEGACY_FIELDS` |

Les deux dernières lignes demandent plusieurs écritures cohérentes dans la
base : même classe que la réécriture complète, que la documentation exclut.
Pour la fiche : **aucun seuil stocké dans la base ne résiste à qui peut
réécrire toute la base**. Seule une référence extérieure (signature, ou
empreinte gardée hors de la base) y résisterait.

### G052-1 — fenêtre de migration C-012 (P3)

Les reçus écrits par `0fdf18e` portent déjà une empreinte, mais aucun seuil.
Le premier reçu écrit ensuite par `7d8efb9` pose le seuil **sur lui-même**.
Les reçus `0fdf18e` restent donc **en dessous**, et le retrait de leur
empreinte, suivi d'une altération, est accepté comme `LEGACY_FIELDS`.

C'est limité aux bases utilisées entre ces deux versions (quelques heures
de développement), mais c'est exactement le cas G048-1.

### G052-2 — seuil relevé seul, empreinte intacte (P3)

Relever seulement le seuil (une écriture) reste accepté : le reçu est
toujours `EVENT_HASH`, donc pas encore exploitable. Mais il ne lui manque
plus que le retrait de l'empreinte.

## Proposition (non appliquée)

[proposal-receipt-boundary.diff](proposal-receipt-boundary.diff) :

- **store** : à la première pose, seuil = plus petite séquence d'un
  événement de commande **déjà** porteur d'une empreinte (sinon, la
  séquence courante) ;
- **lecture** : un reçu porteur d'une empreinte **sous** le seuil est
  refusé : le seuil a été déplacé.

Mesuré :

- la fenêtre de migration est refusée (`503`) ;
- le seuil relevé seul est refusé (`503`) ;
- les autres sondes sont inchangées ;
- suite complète : **696 OK**, 7 ignorés ([sortie](proposal-tests.txt)).

Limites de la proposition :

- elle reste contournable par une réécriture cohérente (seuil, empreintes
  et reçus) ;
- un ancien binaire, sans empreinte, relancé après C-012 écrirait des reçus
  au-delà du seuil, qui deviendraient illisibles. C'est prudent, mais à
  annoncer ;
- la lecture teste la présence de la clé dans les octets de l'événement :
  prototype, à remplacer par le détail décodé.

## Limites

- Linux, Python 3.11, outils simulés.
- Les arrêts sont placés juste après des écritures choisies, et le
  parallélisme est limité à 4 processus.
- Le coût de la relecture du journal n'est pas mesuré sur de gros
  historiques.
