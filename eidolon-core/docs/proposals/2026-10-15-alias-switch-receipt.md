# Reçu de bascule d'alias Qdrant (Claude, G256-3)

Auteur : Claude. Date : 15/10/2026, Europe/Paris. Base Memory : `81084e0`.
Statut : **proposition expérimentale**. Pas de journal de production, pas
de suppression. Ne clôt pas G201 Q3.

Expérience : [patch Memory 0049](../../collaboration/memory-patches/0049-claude-g256-alias-switch-receipt.patch).
Elle comprend `tests/claude_memory_eval/alias_switch_receipt.py` et 6 tests.

## 1. Pourquoi

La rétention (G252-7) exige, pour proposer le retrait d'une génération, une
**date de retrait** et une **référence d'audit**. Ce reçu est la forme
minimale de cette référence.

## 2. Contenu d'un reçu

| Champ | Rôle |
| --- | --- |
| `schema` | `eidolon-alias-switch-receipt/1` |
| `switch_id` | 32 hexadécimaux, unique : détecte le rejeu |
| `alias`, `previous_generation`, `new_generation` | la bascule elle-même (`alias__<32 hex>`) |
| `new_descriptor_sha256`, `manifest_sha256` | ce que la nouvelle génération prétend contenir |
| `switched_at` | secondes Unix de l'hôte |
| `observed_before`, `observed_after` | l'alias **relu** avant et après ; ils doivent valoir l'ancienne et la nouvelle génération |
| `receipt_sha256` | empreinte du JSON canonique de tous les champs |

## 3. Refus

| Cas | Code |
| --- | --- |
| Champ manquant, ou empreinte absente | `RECEIPT_INCOMPLETE` |
| Champ en trop (par exemple du texte privé) | `RECEIPT_UNEXPECTED_FIELD` |
| Un champ modifié après coup | `RECEIPT_DIGEST_MISMATCH` |
| `switch_id` déjà vu | `RECEIPT_REPLAYED` |
| L'alias relu ne montre pas la bascule (quelqu'un d'autre a basculé entre-temps, ou la bascule n'a pas pris) | `SWITCH_NOT_OBSERVED` |
| Même génération avant et après | `RECEIPT_NOT_A_SWITCH` |
| Chaîne : un reçu ne part pas de la génération où le précédent est arrivé | `CHAIN_BROKEN` |
| Chaîne : le temps recule, ou un autre alias apparaît | `CHAIN_TIME_REGRESSED`, `RECEIPT_OTHER_ALIAS` |

## 4. Lien avec la rétention

`retirement_facts(reçus, alias=…, initial_generation=…, observed_target=…)`
donne `{génération: (retired_at, switch_id)}` :

- seulement si la chaîne entière est valide **et** finit sur la cible lue
  maintenant ; sinon le résultat est vide, donc rien n'est prouvé ;
- une génération réactivée puis de nouveau retirée garde sa **dernière**
  date de retrait ;
- la cible actuelle n'est jamais « retirée ».

Le test de bout en bout passe ces faits au classificateur. Le résultat est
`REVIEW_CANDIDATE` après le délai de grâce et `KEEP_RECENT` avant.

## 5. Preuves et limites

- 10 sabotages : 9 tués, 1 équivalent, retiré du code (double retrait
  d'une génération réactivée).
- C'est une fonction pure. L'écriture durable du journal (append-only,
  `fsync`, verrou) reste à concevoir avec GPT. Un reçu ne prouve rien sur
  le **contenu** de la génération : `manifest_sha256` doit être comparé au
  manifeste au moment du retrait.
