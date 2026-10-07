# G045 — contre-revue de la saturation (503 BUSY) et du budget SQL (`d9265fa`)

Auteur : Claude, 07/10/2026. Fiche [C-TASK-G045](../../../../collaboration/tasks/C-TASK-G045.md).
Cible figée : `d9265faf6fad96845129767d814568d2c0b8ca58` (C-010b et C-010c),
copie `git archive`, `http_api.py` `bbdec659…`. Rien n'est modifié dans les
sources de Codex. La variante S6 est une **proposition mesurée** : elle tourne
dans un script séparé ([variant_server.py](variant_server.py)).

```sh
PYTHONPATH=$FROZEN/eidolon-core/src python3 docs/validation/2026-10-07/claude-g045/probes_g045.py
```

- Linux, Python 3.11.15, SQLite 3.45.1, 4 CPU.
- Jeu C-009g créé avec la copie figée, serveur dans un **processus séparé**
  sur `127.0.0.1:0`, sockets brutes, dossiers temporaires supprimés.
- [Sortie](probes-d9265fa.txt).

## Verdict

| Point | Résultat |
| --- | --- |
| S1 : 1 à 2 clients | **100 %** de réponses 200 |
| S1 : 3 / 4 / 5 clients | 2 / 71 / 285 refus `503`, toujours explicites, jamais de fermeture muette |
| S2 : contenu de BUSY | **une seule réponse fixe** quelle que soit la requête (vide, invalide, avec jeton) : aucun jeton, aucune donnée, avant authentification |
| S3 : POST de 8 Ko pendant la saturation | 50/50 `503` reçus (pas de RST avant la réponse, sur boucle locale) |
| S4 : retour au service | 2 ms après la fermeture des connexions qui occupaient les places ; 3,0 s si elles restent muettes (délai d'inactivité) |
| S5 : requête SQLite sans fin | **interrompue après 2,00 s** (`interrupted`) |
| S5 : verrou d'écriture 1,5 s puis requête sans fin | interrompue à 2,00 s : l'attente du verrou compte dans le budget |
| S5 : 2,2 s de travail Python puis requête courte | **pas** interrompue : le budget ne voit ni Python, ni une requête de moins de 1000 instructions |
| S5 : budgets par requête HTTP | health, liste, reçu : 1 connexion ; **snapshot : 2 connexions**, donc jusqu'à 2 × 2 s |

## G045-1 — refus BUSY entre clients séquentiels (P3, limite connue)

Avec 4 clients qui enchaînent leurs requêtes, environ 18 % sont refusées,
alors qu'aucun n'a deux connexions ouvertes à la fois. La place n'est libérée
qu'**après** la fermeture du socket. Le client reçoit sa réponse (longueur
connue), se reconnecte aussitôt, et trouve la place encore prise.

**Proposition mesurée (S6)** : retirer le thread de la table des places
**avant** `shutdown_request`. Même banc, même machine :

| | 3 clients | 4 clients | 5 clients |
| --- | --- | --- | --- |
| actuel | 0 refus / 300 | **83** / 400 | 329 / 500 |
| place libérée avant la fermeture | 0 / 300 | **19** / 400 | 331 / 500 |

Le gain est net à 4 clients ; à 5, la limite de 4 places domine, comme
prévu. Coût : `server_close` n'attendrait plus un thread déjà retiré de la
table (il ne lui reste qu'à fermer son socket). À valider par Codex ; je ne
modifie pas `http_api.py`.

## G045-2 — budget SQL : ce qu'il borne et ce qu'il ne borne pas (P3)

- Il borne le travail **SQLite** par connexion, attente de verrou comprise.
- Il ne borne ni le Python (projection, JSON), ni une suite de petites
  requêtes, ni le total d'une requête HTTP qui ouvre plusieurs connexions.
- Le pire cas d'un snapshot est donc d'environ 4 s de SQL, plus le Python.

C'est cohérent avec le commentaire du code (« does not interrupt filesystem
I/O or Python projection work »). Ajouter le nombre de budgets par route au
contrat éviterait de lire « 2 s par requête ».

## Pas de régression observée

1 et 2 clients : 0 refus sur 100 et 200 requêtes, comme en G039. Le service
revient immédiatement après une saturation.

## Limites

- Boucle locale seulement : à travers un tunnel SSH, une réinitialisation de
  connexion avant la réponse BUSY reste possible ; non testé.
- Pas de grande base, ni de disque lent réel.
- Variante S6 mesurée sur une seule machine.
