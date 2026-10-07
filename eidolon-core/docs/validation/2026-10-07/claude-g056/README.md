# G056 — coût du budget d'invocations et variante filtrée en SQL

Auteur : Claude, 07/10/2026. Fiche [C-TASK-G056](../../../../collaboration/tasks/C-TASK-G056.md).

Base : `2568e16` (tête `feat` `a1669eb` fusionnée), en copie `git archive`.
`runtime.py` et `store.py` ne sont **pas modifiés** dans le dépôt ; la
proposition est un diff à part.

```sh
python3 docs/validation/2026-10-07/claude-g056/bench_g056.py <copie>/eidolon-core/src
python3 docs/validation/2026-10-07/claude-g056/bench_g056.py <copie + diff>/eidolon-core/src --proposal
```

## Méthode

- Le vrai `Runtime` crée une mission (limite 4096). Le banc ajoute ensuite,
  avec sqlite3, N réservations `INVOCATION_RESERVED` et **2 événements de
  remplissage d'environ 300 octets par réservation**, pour imiter les
  autres événements d'une vraie mission. Le compteur est réglé sur N.
- N = 64, 256, 1024 et **4095**. À 4096, le budget est plein : la
  vérification lit tout, puis répond `EXHAUSTED`. 4095 est donc la dernière
  vérification utile.
- Médiane de 30 appels (15 au-delà de 1024), Linux, Python 3.11, disque du
  conteneur.
- Concurrence bornée : 4 processus × 10 vérifications simultanées sur la
  même base, à N = 4095.

Sorties : [actuel](bench-current.txt), [proposition](bench-proposal.txt).

## Résultats

| N réservations | Événements de la mission | Base | Vérification actuelle | Avec la proposition |
| --- | --- | --- | --- | --- |
| 64 | 193 | 120 Kio | 0,95 ms | 0,43 ms |
| 256 | 769 | 340 Kio | 2,55 ms | 1,23 ms |
| 1024 | 3 073 | 1,2 Mio | 9,1 ms | 2,7 ms |
| 4095 | 12 286 | 4,7 Mio | **38,6 ms** | **14,4 ms** |
| 4095, 4 processus simultanés | — | — | 47 à 51 ms par appel | 10 à 20 ms par appel |

- **Le coût est linéaire** dans l'historique de la mission. Presque tout
  passe dans `store.events()` : la mission entière est relue et chaque
  événement décodé en JSON, même s'il n'est pas une réservation.
- La vérification est faite avant **chaque** réservation, et deux fois
  avant un outil. Le coût cumulé est donc **quadratique**. Estimation par
  ajustement linéaire du coût unitaire, somme jusqu'à N :

| Mission menée jusqu'à N | Actuel | Proposition |
| --- | --- | --- |
| 64 (défaut) | ≈ 0,02 s | ≈ 0,01 s |
| 1024 | ≈ 5 s | ≈ 2 s |
| 4096 (maximum) | ≈ 80 s | ≈ 30 s |

Avec la limite par défaut (64), le coût est **négligeable**. Il ne pèse
qu'aux limites hautes.

## Proposition (non appliquée)

[proposal-budget-query.diff](proposal-budget-query.diff) :

- `Store.invocation_reservations(id)` lit **seulement** les détails des
  événements `INVOCATION_RESERVED`, dans l'ordre du journal ;
- `_ensure_invocation_budget` l'utilise à la place de `events()`.

Les contrôles Python sont inchangés : nombre, ordinaux 1..N, limite, type
du détail. Aucun schéma ni index n'est ajouté.

Détection conservée, mesurée à N = 4095 sur copies, avant comme après :

| Altération | Actuel | Proposition |
| --- | --- | --- |
| compteur seul diminué | INVALID | INVALID |
| dernière réservation supprimée | INVALID | INVALID |
| réservation du milieu renommée en autre événement | INVALID | INVALID |
| ordinal du milieu modifié | INVALID | INVALID |
| limite d'une réservation modifiée | INVALID | INVALID |
| détail non objet | INVALID | INVALID |
| retrait cohérent (compteur et événement) | accepté | accepté (limite documentée de C-015) |

Suite complète avec la proposition : **739 OK**, 7 ignorés
([sortie](proposal-tests.txt)). Même résultat sans la proposition.

Pistes **non proposées** :

- un index `(mission_id, kind, sequence)` modifierait le schéma ;
- un point de contrôle incrémental (vérifier seulement les dernières
  réservations) rendrait le coût constant, mais **ne détecterait plus** une
  altération ancienne. Il faudrait une empreinte chaînée.

## Limites

- Historiques synthétiques : ce ne sont pas de vraies missions de 4096
  appels.
- Les temps dépendent du disque et du cache du conteneur. Seuls les
  rapports et les ordres de grandeur comptent.
- Les coûts cumulés sont des **estimations**, non mesurées de bout en bout.
- Pas de mesure sous Windows ou sur la VM.
