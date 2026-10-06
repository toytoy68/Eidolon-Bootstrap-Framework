# Contre-revue C-TASK-G024 — suites Web et parseur (`cd80be2`)

Auteur : Claude, 06/10/2026. Fiche [C-TASK-G024](../../../../collaboration/tasks/C-TASK-G024.md).
Cible figée : `cd80be28d239eceb24d46c01d7d6401c09fedd6e` ; base avant correctif
`e2d01ff94a374078dd8bffcf99362049944671f1`. Deux copies `git archive`.
SHA-256 de la cible (16 premiers caractères) :

- `research.py` `11b6da6a7ac1a9b3`
- `research_pauses.py` `40cdd247601d32f1`
- `commands.py` `3aaec1c54249f52b`
- `tests/test_review_followup.py` `7605645c03bd52ba`

Ni `src/` ni `tests/` Python modifiés.

```sh
cd eidolon-core
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=$TREE/eidolon-core/src:$TREE/eidolon-core \
  python docs/validation/2026-10-06/claude-g024/probes_g024.py
```

Python 3.11.15, Linux. Aucun réseau : vrai `WebReader`/`fetch` avec DNS et
pair HTTP simulés, qui comptent les échanges. Horloges injectées.
**Mêmes sondes sur les deux arbres** :

- [avant `e2d01ff`](probes-e2d01ff.txt)
- [après `cd80be2`](probes-cd80be2.txt)
- [13 tests de Codex rejoués sur la copie figée : OK](codex-followup-tests-on-frozen.txt)

Ce ne sont pas des recettes réseau.

## Verdict par point

### 1. D-G019-1 — consultation lente avant un échange : **CONFIRMÉ CORRIGÉ**

Chaque consultation de pause coûte 6 s sur l'horloge du coordinateur.

| Cas | Avant | Après |
| --- | --- | --- |
| Budget 13 s, lecture directe | **1 échange** à 18 s, READ | **0 échange**, TIMEOUT / DEADLINE |
| Budget 19 s, redirection | **2 échanges** | 1 échange (premier saut, dans le budget), le **saut suivant est arrêté** |
| Annulation pendant la consultation du saut | **1 échange**, READ | **0 échange**, CANCELLED |
| Budget 60 s, lecture normale | READ | READ (aucune régression) |
| 429 reçu pendant que le budget expire | pause conservée | pause conservée (**le reçu déjà arrivé reste persisté**) |

### 2. L-G019-1 — capacité épuisée : **CORRIGÉ pour le recontact ; nouveau défaut de disponibilité**

Ce qui est corrigé :

- **Nouvelle origine qui refuse, table pleine** (256 lignes) : avant, elle
  était recontactée à chaque reconstruction. Après : **0 échange**,
  `PAUSE_CAPACITY_REACHED` avant l'appel, sur 2 reconstructions.
- **Redirection qui demande 2 lignes** (255 occupées) : le premier saut (302)
  part ; le saut vers la nouvelle origine est refusé **avant** la connexion.
  Une seule origine nouvelle (1 ligne) passe, et la pause est enregistrée
  (256 lignes).
- **Dernière ligne prise par un autre écrivain pendant l'échange** :
  l'observation est perdue (`PAUSE_CAPACITY_REACHED`). C'est la limite
  annoncée « pas de réservation ». Le coordinateur reconstruit **ne
  recontacte pas** (table pleine).
- **Stockage absent** avant le contrôle : `PAUSE_STORAGE_UNAVAILABLE`,
  0 échange. Contrôles invalides : `INVALID_PAUSE_SCOPE`.

**C-G024-1 — DÉFAUT de disponibilité (P2)**. La table compte aussi les
lignes `RELEASED`, et rien ne les purge. Le contrôle de capacité porte aussi
sur le **fournisseur**. Une fois 256 périmètres vus, une recherche n'est donc
possible que si le fournisseur **et** chaque origine touchée ont déjà une
ligne.

| Table pleine (256 lignes, dont 2 levées) | Avant | Après |
| --- | --- | --- |
| fournisseur avec une ligne, origine connue | READ | READ |
| fournisseur avec une ligne, nouvelle origine qui ne refuserait pas | READ | **CAPACITY_REACHED, 0 échange** |
| fournisseur **sans** ligne, origine connue | READ | **CAPACITY_REACHED, aucune recherche** |

Le refus est sûr : aucun faux succès, aucun appel interdit. Mais la recherche
Web devient **définitivement indisponible** après 256 périmètres distincts,
sans outil pour libérer de la place, sauf du SQL brut. Le contrat annonce
« rétention sans purge », pas un arrêt total de la recherche.

**Propositions**, au choix :

- ne compter que les pauses `ACTIVE`, l'historique restant dans
  `pause_events` ;
- ou une purge explicite et auditée des lignes `RELEASED` ;
- et un diagnostic distinct (`PAUSE_CAPACITY_REACHED: release or purge
  reviewed pauses`).

**C-G024-2 — diagnostic trompeur (P3)**. Un refus de capacité passe par
`_persistent`, qui met le coordinateur en panne. Le run suivant du **même**
coordinateur répond `PAUSE_STORAGE_UNAVAILABLE: prior write uncertain`, alors
qu'aucune écriture n'a été tentée. C'est sûr, mais faux sur la cause.
**Proposition** : ne pas marquer `_pause_fault` pour un refus de capacité
issu d'une lecture.

### 3. R-G020-1 — `mission_id` invalide : **CONFIRMÉ CORRIGÉ**

- `M-1` et `42`, en texte et en octets, pour la décision comme pour
  l'annulation : `INVALID_COMMAND: invalid mission_id`. Avant : message
  générique.
- La CLI rend le code 2, sans trace, **base inchangée** (octets identiques).
- Pas de régression : clé dupliquée, mauvais protocole et `client_id`
  invalide gardent leur message précis.

### 4. Documentation et garanties réelles

Confirmé par les sondes :

- **Aucune réservation** : la course de la dernière ligne perd l'observation.
- **Arrêt coopératif** : contrôles avant l'échange seulement, aucun
  interrompu en vol.
- **Fenêtre de panne avant persistance** : toujours ouverte (non retestée ;
  limite connue).

## Non testé

- Concurrence réelle entre processus : la course est simulée, de façon
  déterministe, par un écrivain pendant l'échange.
- Lenteur SQLite réelle (simulée par l'horloge).
- Fournisseurs Internet réels.
