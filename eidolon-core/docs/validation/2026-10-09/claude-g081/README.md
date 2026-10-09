# G081 — Stockage occupé ou indisponible : matrice HTTP observée et contrat proposé

Auteur : Claude. Date : 09/10/2026, Europe/Paris. Fiche : C-TASK-G081 (suite de G067-3).
Base : `1d4a246` (branche Claude). **Rapport et sondes seulement** : aucun
fichier de Core n'est modifié et le protocole ne change pas sans accord de
Codex.

## Sonde

[probes_g081.py](probes_g081.py) lance un vrai `ReadServer` en boucle locale
sur un Store synthétique, et l'API de conversation par `handle()`. Résultat
brut : [matrix.jsonl](matrix.jsonl).

```sh
PYTHONPATH=src python3 docs/validation/2026-10-09/claude-g081/probes_g081.py
```

## Matrice observée

| API | Situation | HTTP | Code | Délai | Client actuel |
| --- | --- | --- | --- | --- | --- |
| lecture | normal | 200 | — | 0 s | connecté |
| lecture | verrou **EXCLUSIVE** tenu par un écrivain (journal `DELETE`) | 503 | `STATE_UNAVAILABLE` | **2,0 s** | « Base Core indisponible » |
| lecture | verrou RESERVED (écrivain avant commit) | 200 | — | 0 s | connecté |
| lecture | verrou relâché | 200 | — | 0 s | connecté |
| lecture | 4 connexions occupées, 5ᵉ requête | 503 | `BUSY` | 0 s | « occupé », rien relancé |
| lecture | base passée en WAL | 503 | `STATE_UNAVAILABLE` | 0 s | indisponible |
| lecture | en-tête corrompu | 503 | `STATE_UNAVAILABLE` | 0 s | indisponible |
| lecture | fichier absent | 503 | `STATE_UNAVAILABLE` | 0 s | indisponible ; **aucun fichier recréé** |
| lecture | marqueur `RECOVERY-REVIEW-ONLY` | 503 | `STATE_UNAVAILABLE` | 0 s | indisponible |
| conversation | normal | 200 | — | 0 s | — |
| conversation | verrou EXCLUSIVE | 503 | `CONVERSATION_STORE_BUSY` | 2,0 s | envoi « incertain », renvoi sans doublon |
| conversation | en-tête corrompu | 503 | `CONVERSATION_UNAVAILABLE` | 0 s | envoi « incertain » |

**Constat G067-3 confirmé.** Sur l'API de lecture, un verrou passager et une
base illisible donnent la même réponse. Le client affiche alors « Base Core
indisponible » pour une situation qui se règle seule en quelques secondes.
L'API de conversation, plus récente, distingue déjà les deux cas.

## Contrat proposé (compatible)

| Cause | HTTP | Code | `Retry-After` | Client |
| --- | --- | --- | --- | --- |
| saturation des connexions (avant authentification) | 503 | `BUSY` (inchangé) | — | « occupé », réessai manuel |
| verrou SQLite (`SQLITE_BUSY` / `SQLITE_LOCKED`) après le budget de 2 s | 503 | **`STATE_BUSY`** (nouveau) | `2` | « occupé » ; données affichées marquées « non actuelles » ; réessai **manuel** ou au prochain rafraîchissement normal |
| budget SQL épuisé (`interrupted`) | 503 | `STATE_UNAVAILABLE` | — | indisponible : la cause peut durer (base trop grosse) |
| WAL, corruption, fichier absent, schéma inconnu | 503 | `STATE_UNAVAILABLE` (inchangé) | — | indisponible : action de l'opérateur |
| revue de récupération en cours | 503 | `STATE_UNAVAILABLE` (inchangé ; un code `STATE_REVIEW_ONLY` est possible plus tard) | — | indisponible |

Règles :

- **Compatibilité.** Un client actuel traite tout 503 autre que `BUSY` comme
  « indisponible » (`session.js`). Il reste donc correct avec `STATE_BUSY`,
  seulement plus pessimiste. Aucun changement n'est forcé côté client.
- **Aucun réessai automatique** d'une commande. Pour une lecture, le réessai
  reste manuel ou suit la cadence normale de rafraîchissement, jamais une
  boucle serrée.
- `STATE_BUSY` ne dit rien de l'état des missions. Ce n'est ni un échec, ni
  un résultat.

Esquisse côté serveur, **non appliquée**. Dans `_dispatch` de `http_api.py`,
avant la branche générique :

```python
except sqlite3.OperationalError as exc:
    if getattr(exc, "sqlite_errorcode", None) in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED):
        self._error(503, "STATE_BUSY")          # + en-tête Retry-After: 2
    else:
        self._error(503, "STATE_UNAVAILABLE")
```

Côté client, `session.js` traiterait `503 STATE_BUSY` comme `BUSY` (phase
« occupé »), avec un libellé dédié dans `view.js`. Ce changement se fera avec
celui du protocole, après accord ; rien n'est modifié ici.

Tests à ajouter avec le changement :

- les 9 lignes « lecture » de la matrice, en assertions ;
- un client actuel face à `STATE_BUSY` : phase « indisponible », sans
  régression ;
- un client mis à jour : phase « occupé ».

## Limites

- Conteneur, disque local, journal SQLite `DELETE`. Pas de NAS ni de partage
  réseau, où les verrous se comportent autrement.
- Un seul essai par situation ; les délais sont indicatifs.
- Le budget SQL épuisé (`interrupted`) n'a pas été provoqué ici. G067 l'avait
  déjà observé : il ne s'était jamais déclenché sur 300 000 lignes.
