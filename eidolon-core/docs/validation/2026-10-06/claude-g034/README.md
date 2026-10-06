# G034 — contre-revue de l'API HTTP de consultation C-009a (`21c0f729`)

Auteur : Claude, 06/10/2026. Fiche [C-TASK-G034](../../../../collaboration/tasks/C-TASK-G034.md).
Cible figée : `21c0f729f3d5aa73b411a9879fe207df8d4f8a02`, copie `git archive`
(`src/` et `tests/`). `http_api.py` `ede2f8d3…`, `tests/test_http_api.py`
`2314aff9…`. Le lot additionnel C-009b (reçus, `37dc199`) **n'est pas revu
ici**. Ni `http_api.py` ni les tests de Codex ne sont modifiés.

```sh
PYTHONPATH=$FROZEN/eidolon-core/src python3 docs/validation/2026-10-06/claude-g034/probes_g034.py
```

Linux, Python 3.11.15. Serveur `ReadServer` réel sur `127.0.0.1`, port
éphémère. Les sondes envoient des **octets HTTP bruts** par socket. Les états
synthétiques sont créés par la CLI de la même copie, dans des dossiers
temporaires. Aucun autre hôte n'est contacté.

- [Sondes : 107 lignes, 80 réponses examinées](probes-21c0f729.txt)
- [25 tests de Codex rejoués sur la copie figée : OK](codex-http-tests-on-frozen.txt)
- [Client G031 (20 tests, dont 2 Chromium) contre l'API figée : 20/20](g031-client-on-frozen-api.txt).
  `desktop/` de la branche a été copié dans l'arbre figé : le serveur est
  celui de `21c0f729`.

## Verdict

Le contrat tient sur tous les points de la fiche. **Une limite de
disponibilité** est à chiffrer pour la bêta (D-G034-1). **Aucune fuite** n'a
été trouvée, et l'API seule n'écrit rien.

| Point | Résultat |
| --- | --- |
| Jeton absent, erroné, dupliqué, dans l'URL, `bearer` minuscule, double espace, octet nul | 401, aucune donnée |
| Host absent, autre, dupliqué, majuscules, sans port, `[::1]` | 403 (400 si dupliqué) |
| Origin `null`, autre, `https`, dupliqué, Host `localhost` + Origin `127.0.0.1` | 403 (400 si dupliqué) ; Origin exact accepté |
| URL : requête, `/` final, `%68`, `..`, `.`, id majuscules, forme absolue, fragment | 404 ; chemin de 70 000 → 414 |
| `//v1/health` | 200 : `http.server` réduit lui-même les `/` initiaux. Sans danger |
| JSON : UTF-8 invalide, clé dupliquée, NaN, `1e400`, profondeur 17, tableau, vide, surrogate isolé | 400 `INVALID_JSON` |
| `limit` `true`, 0, 101, `"5"`, `2.0` ; champ inconnu ; poll sans curseur ou curseur d'une autre mission | 400 avec code précis |
| Corps tronqué (fermeture d'écriture) | 400 `INCOMPLETE_BODY`, immédiat |
| Corps de 8193 octets ; `Content-Length` dupliqué, négatif ; `chunked` ; GET avec corps ; type non JSON ou `charset=latin-1` | 413 / 400 / 415 |
| Octets en trop après le corps, requête collée derrière | ignorés : **une seule** réponse, connexion fermée |
| PUT, DELETE, PATCH, OPTIONS, TRACE, HEAD, CONNECT, `get`, `FOO` | 405 ; préflight OPTIONS d'une autre origine : 403 |
| Statique sans `--web-root` | 404 ; `/index.html` et `/../state/…` : 401 (aucun fichier servi) |
| Garde de restauration ajoutée **pendant** l'exécution | 503, puis 200 une fois retirée |
| Base absente / corrompue au démarrage | refus, **rien créé** |
| Base remplacée par des zéros pendant l'exécution | 503 `STATE_UNAVAILABLE` |
| Pagination puis création par une **CLI distincte** | page 2 : `RESET_REQUIRED` / `STATE_CHANGED`, 0 item |
| Poll après annulation par la CLI | `DELTA` : `CANCEL_REQUESTED`, `CANCELLED` |
| Écriture par l'API (empreintes des fichiers d'état avant et après les sections A à H) | **aucune** |
| Jeton, chemin d'état, texte de la demande, `Traceback`, `sqlite`, SQL dans les 80 réponses | **absents** |
| Processus CLI réel : stdout et stderr | jeton absent ; code 0 sur Ctrl+C |

## D-G034-1 — un seul client local lent bloque toute la consultation (P2 disponibilité)

Le serveur traite une requête à la fois. Son délai de 3 s porte sur **chaque**
lecture de socket, pas sur la requête entière.

| Situation | Requête légitime de santé |
| --- | --- |
| Un client envoie une ligne d'en-tête toutes les 2 s | **pas de réponse après 8 s** (délai de la sonde) |
| Une connexion ouverte sans rien envoyer (comme une préconnexion de navigateur) | 200 après **2,8 s** |

C'est la limite annoncée (« pas de garantie de délai total face à un client
local hostile »). Les mesures montrent qu'elle touche aussi des cas ordinaires :

- par le tunnel SSH, toute connexion inactive retient le serveur près de 3 s ;
- tout processus local peut bloquer la consultation indéfiniment ;
- le client G031 abandonne une requête au bout de 10 s et affiche alors
  « injoignable ».

Non mesuré avec un vrai navigateur derrière un tunnel.

**Propositions** (Codex décide ; `http_api.py` lui est réservé) :

1. un délai **total** par requête (échéance absolue vérifiée entre les
   lectures) ;
2. ou `ThreadingHTTPServer` avec un nombre borné de requêtes simultanées ;
3. a minima, une ligne dans HTTP-READ-API.md et dans la recette G035.

## Remarques mineures (P3, sans risque)

- **R-G034-1** : un 401 n'envoie pas d'en-tête `WWW-Authenticate`. Sans effet
  sur le client G031 ; c'est seulement une note de conformité HTTP.
- **R-G034-2** : `Bearer` est sensible à la casse, et `Host: LOCALHOST:port`
  est refusé. Choix stricts, cohérents avec le contrat ; le client envoie
  la forme exacte.

## Limites

- Pas de tunnel SSH réel, de Windows ni de navigateur derrière un tunnel.
- Les sondes ne couvrent pas une base en mode WAL ouverte en lecture seule
  sans fichier `-shm`. La limite est annoncée par Codex.
- C-009b (reçus HTTP) : non revu dans ce lot.
