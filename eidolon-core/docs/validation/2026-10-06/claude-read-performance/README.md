# G039 — coût de la consultation bêta (10, 100, 1000 missions)

Auteur : Claude, 06/10/2026. Fiche [C-TASK-G039](../../../../collaboration/tasks/C-TASK-G039.md).
Base : `5513718`. Le serveur mesuré est celui de la branche : C-009e (4 places
de connexion, délais), C-009b (reçus). Ni le moteur ni l'API ne sont modifiés.

```sh
cd eidolon-core
PYTHONPATH=src python3 docs/validation/2026-10-06/claude-read-performance/bench_read.py
PYTHONPATH=src python3 docs/validation/2026-10-06/claude-read-performance/bench_slots.py
```

## Protocole

- Taille N : jeu C-009g (6 missions, 3 reçus), plus N−6 missions `NEW` créées
  avec `Runtime.create` dans un seul processus.
- Le **vrai `http_api`** tourne dans un **processus séparé** sur
  `127.0.0.1:0`. Le client `http.client` ouvre une connexion par requête, comme
  le client G031.
- Chaque mesure : **3 répétitions de 10 requêtes**, puis médiane et maximum
  par requête.
- Tout est créé dans un dossier temporaire, supprimé à la fin
  (`"cleaned": true`).
- Aucune relecture automatique du client n'est simulée.

Machine : conteneur Linux x86_64, 4 CPU, noyau 6.18, Python 3.11.15, SQLite
3.45.1, dossier temporaire en ext2/ext3. **Ce n'est pas la VM de toytoy** :
aucune promesse de performance pour un disque ou une VM réels.

Sorties brutes : [bench_read](results-run1.jsonl), [places de connexion](results-slots.txt)
(3 passages).

## Latence par requête (médiane / max, ms)

| Requête | 10 missions | 100 | 1000 | Taille de réponse (1000) |
| --- | --- | --- | --- | --- |
| health | 1,3 / 1,9 | 1,3 / 2,4 | 1,4 / 1,8 | 130 o |
| liste, page de 20 | 2,1 / 3,4 | 2,7 / 4,0 | 2,3 / 3,1 | 5,9 Ko |
| liste, page de 100 | 2,1 / 3,5 | 5,3 / 9,1 | 4,9 / 7,6 | 26,8 Ko |
| snapshot | 1,8 / 3,8 | 1,9 / 3,0 | 1,9 / 3,9 | 824 o |
| poll sans nouvel événement | 1,9 / 2,2 | 2,3 / 4,1 | 2,3 / 5,3 | 821 o |
| reçu trouvé | 1,6 / 3,2 | 2,1 / 5,1 | 1,7 / 2,4 | 908 o |
| reçu absent | 1,2 / 3,0 | 1,8 / 10,1 | 1,4 / 1,9 | 341 o |

**Liste complète** à 1000 missions :

- par pages de 100 : 10 pages, 268 Ko, environ 51 ms ;
- par pages de 20 : 50 pages, 295 Ko, environ 125 ms.

Le client G031 s'arrête à 200 missions (2 pages). Le coût d'une page dépend
de sa taille, presque pas du nombre total de missions.

**Au repos** (10 s sans requête) : 0,00 à 0,01 s de CPU, mémoire résidente
d'environ 24 Mo, stable de 10 à 1000 missions.

**Verrou d'écriture SQLite** tenu par une autre connexion (journal en mode
rollback) :

- tenu 0,5 s : la page attend, puis 200 en environ 534 ms ;
- tenu 3 s : **503 `STATE_UNAVAILABLE` après 2,0 s**, le délai SQLite du
  lecteur ;
- dans les deux cas, health répond normalement juste après.

## F-G039-1 — connexions refusées sans réponse dès 4 clients (P2 pour le client)

Chaque client envoie 100 snapshots à la suite, avec une nouvelle connexion
par requête. 3 passages :

| Clients simultanés | Requêtes sans réponse HTTP |
| --- | --- |
| 1 | 0 / 100 (×3) |
| 2 | 0 / 200 (×3) |
| 3 | 0, 0, **2** / 300 |
| 4 | **89, 76, 85** / 400 (≈ 20 %) |
| 5 | 346, 373, 292 / 500 |

Le refus est une fermeture sans réponse (`RemoteDisconnected`). Une place
semble rester occupée juste après l'envoi de la réponse, le temps que le
thread finisse. Un client qui se reconnecte aussitôt la trouve donc encore
prise. C'est une hypothèse, tirée de `process_request` et de
`_serve_connection` ; elle n'a pas été instrumentée.

Pour le client G031, un tel refus est lu comme une **panne réseau** : la page
affiche « Serveur injoignable » et marque les données périmées. Un navigateur
ouvre plusieurs connexions (assets, préconnexions), donc ce cas est
plausible avec un seul utilisateur. Le banc ne l'a pas observé dans Chromium.

Propositions (Codex décide, `http_api.py` lui est réservé) :

1. répondre `503 BUSY` avec un code explicite plutôt que fermer sans
   réponse ;
2. ou libérer la place avant la fermeture finale, ou accepter une courte file
   d'attente bornée.

Côté client, une seule relecture automatique d'une **lecture** après une
fermeture sans réponse serait sans risque d'effet. Je ne l'ajoute pas sans
accord.

## Limites

- Un seul type de machine, sans charge concurrente. Les mesures ne qualifient
  ni la VM, ni le disque, ni le tunnel SSH.
- Les 1000 missions sont toutes `NEW` et de petite taille. Des missions
  longues ou avec beaucoup d'événements ne sont pas mesurées.
- Le verrou est simulé par `BEGIN EXCLUSIVE` ; un vrai écrivain Core peut se
  comporter autrement.
