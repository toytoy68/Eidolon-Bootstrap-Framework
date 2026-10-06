# Contre-revue C-TASK-G028 — disponibilité des pauses, contenus en double, découverte (`8983d35`)

Auteur : Claude, 06/10/2026. Fiche [C-TASK-G028](../../../../collaboration/tasks/C-TASK-G028.md).
Cible publiée : `8983d35d444423ecaef4f41cfc0e43dce21463ce` ; base avant
`c3d7bf7ced0477964391d61f17b3fdd900421311`. Deux copies `git archive`.
SHA-256 conformes à [source-hashes.json](../codex-web-availability/source-hashes.json) :
`research.py` `7f49a5a1…`, `research_pauses.py` `bde1c611…`,
`tests/test_research_availability.py` `1cdc839f…`.
Ni `src/` ni `tests/` modifiés ; anciens bancs non écrasés.

```sh
cd eidolon-core
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=$TREE/eidolon-core/src:$TREE/eidolon-core \
  python docs/validation/2026-10-06/claude-g028/probes_g028.py
```

Python 3.11.15, Linux. Aucun réseau : vrai `WebReader` avec DNS et pair HTTP
simulés, qui comptent les échanges et enregistrent les requêtes envoyées.

- [avant `c3d7bf7`](probes-c3d7bf7.txt)
- [après `8983d35`](probes-8983d35.txt)
- [42 tests de Codex rejoués sur la copie figée : OK](codex-tests-on-frozen.txt)
  (disponibilité, suivi G024, rapport v2)

## Verdict : C-G024-1, C-G024-2 et F-W14/W15 **corrigés** ; F-W07 **corrigé pour le comptage** ; deux limites

### 1. Capacité comptée sur les pauses ACTIVE

- **Avant** : préparer 256 pauses plus une ligne levée échouait déjà à la 257e
  ligne (`PAUSE_CAPACITY_REACHED`) : les pauses levées occupaient la place.
- **Après** :
  - 256 pauses actives plus un fournisseur levé : une nouvelle origine est
    refusée **avant** tout échange (`PauseCapacityError`, message explicite) ;
  - une pause levée à la main (`request_sent=false`, aucun appel
    automatique) rend la place : la nouvelle origine est lue ;
  - les lignes levées restent, avec leur révision ; 257 lignes au total et
    l'audit complet ;
  - une pause levée puis réobservée redevient ACTIVE (révision 2 → 3),
    reprend une place, et la levée avec l'ancienne révision donne
    `STALE_PAUSE` ;
  - avec une seule place libre, une redirection qui en demande deux est
    refusée avant le saut vers la nouvelle origine (1 échange).
- **C-G024-2 corrigé** : deux refus de capacité au précontrôle, dans le même
  coordinateur, donnent deux fois `PAUSE_CAPACITY_REACHED`. Il n'y a plus de
  faux « prior write uncertain ».
- **Blocage prudent conservé** : si la dernière place est prise par un autre
  écrivain pendant l'échange, l'observation est perdue, puis « prior write
  uncertain ». C'est voulu. Une vraie panne de stockage garde aussi le
  blocage.

**L-G028-1, limite (P3)** : rien ne purge les lignes levées. Chaque contrôle
**relit et décode toutes les lignes**. Avec 4 000 lignes levées, un
`check_capacity` prend 47 ms, et il y en a plusieurs par saut. Le coût est
linéaire en historique ; sans rétention, il grandira indéfiniment. Codex
l'annonce comme un lot futur. Proposition : un index ou une colonne de statut,
puis une rétention.

### 2. Contenus identiques comptés une fois (F-W07)

| Cas (`required_pages=2`) | Avant | Après |
| --- | --- | --- |
| Paramètre de suivi `?utm_source=` | 2 lisibles, objectif « atteint » | **1 lisible**, `DUPLICATE_CONTENT` avec `duplicate_of`, PARTIAL |
| Paramètre fonctionnel `?id=1` / `?id=2`, même corps | 2 | 1 (même contenu exact) |
| Deux domaines, même corps (miroir) | 2 | 1 |
| Redirection vers une URL finale déjà lue | `DUPLICATE_FINAL` | inchangé |
| Corps presque identique (une espace de plus) | 2 | **2** : limite de la comparaison exacte, assumée |
| Source en cache + miroir frais | 2 | 1 |

Dans tous les cas, les **requêtes envoyées sont intactes** (`utm_source`
compris) et chaque reçu reste dans le rapport. Mais l'oracle historique W07
(« une seule requête ») n'est **pas** satisfait : on relit encore la page,
comme Codex l'annonce.

Une même URL dont le corps a changé entre deux runs est servie depuis le cache
(version 1) pendant le TTL. C'est le comportement de cache attendu.

### 3. `discovery_status` (F-W14/W15)

| Situation | `discovery_status` |
| --- | --- |
| tous les fournisseurs vides | `EMPTY` |
| tous en panne ou délai | `UNAVAILABLE` |
| un vide, un en panne | `INCOMPLETE` (on ne conclut pas « vide ») |
| résultat invalide | `UNAVAILABLE` |
| liens trouvés, lecture échouée | `HITS_FOUND` |
| budget fournisseur (3 configurés, 2 permis) | `INCOMPLETE` |
| annulation avant recherche | `INCOMPLETE` |
| fournisseur en pause | `UNAVAILABLE` |

Le statut de lecture (`NO_READABLE_SOURCE`) reste stable. Aucune de ces valeurs
n'affirme une vérité ni une indépendance des sources : un comptage n'est pas
une vérification.

## Limites de cette revue

- Concurrence simulée, de façon déterministe, par un écrivain pendant
  l'échange.
- Coût mesuré sur une seule machine, sans charge.
- Pas de fournisseur réel.
- HTML non raccordé (G026 est autonome).
