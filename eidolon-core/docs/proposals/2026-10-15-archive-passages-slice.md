# Passages d'archives en production : tranche minimale (Claude, G252-10)

Auteur : Claude. Date : 15/10/2026. Base Memory : `9a61648`.
Statut : **proposition** + expérience
([patch Memory 0047](../../collaboration/memory-patches/0047-claude-g252-archive-passages-slice.patch)).
Aucun corpus privé, aucun modèle réel, pipeline de production inchangé.

## 1. Ce qui existe déjà

Le **rappel** sait déjà vérifier et citer un passage :

- `hit.ranking['passage'] = {message_index, start, end}` ;
- vérification contre le canon (`validate_canonical_reference`) ;
- extrait résolu dans le texte canonique (`resolve_passage`) ;
- une archive sans passage est exclue (`INDEX_PASSAGE_MISSING`).

Il manque la **production** de ces passages par l'adaptateur d'index.

## 2. Contrat proposé pour l'adaptateur

| Élément | Proposition |
| --- | --- |
| Projection | `archive-passage-v1:1200:160` (découpage `chunk_messages`, taille, recouvrement), enregistrée dans le descripteur à côté d'`embedding_id`. Toute différence donne `INDEX_INCOMPATIBLE`. |
| Identité du point | `uuid5(projection : id : révision : sha256 des octets : message : début : fin)` |
| Charge du point | `kind=passage`, `information_id`, `revision`, `canonical_sha256`, `projection_id`, `generation`, `passage`. **Aucun texte.** |
| Requête | renvoie `IndexHit` avec `revision`, `canonical_sha256` et `passage`. Le rappel vérifie l'empreinte **puis** le passage. |
| Citation | l'extrait est toujours tiré des octets canoniques prouvés, jamais de l'index |
| Migration | nouvelle génération sous un nouvel alias (`…_passages`) par `rebuild` explicite ; l'ancien index par document reste intact |

## 3. Preuves de l'expérience (3 tests)

- Seule la **tranche du message** est citée, jamais l'archive entière ni
  un autre message.
- Après modification de l'archive, les points de l'ancienne version ne
  sont **jamais** cités (`INDEX_REVISION_MISMATCH`).
- L'identité du point change avec la projection, la révision, les octets
  et les décalages.

## 4. Hors périmètre

- Choix du modèle d'embedding.
- Seuil d'abstention (voir la calibration G218 / G220).
- Calcul des vecteurs.
- Volume réel des archives.

Dans l'expérience, le score est un double de test.
