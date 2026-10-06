# API HTTP de consultation — contrat C-009a

Codex/GPT, 06/10/2026. Contrat de réalisation réservé à Codex ; G031 peut
développer le client contre ce contrat. Statut initial : en cours, preuves
à consigner dans `docs/validation/2026-10-06/codex-beta-api/` à la livraison.

## Accès

HTTP uniquement sur **127.0.0.1**, port 8765 par défaut. Accès depuis le PC
par tunnel SSH, même port local/distant. Aucun bind LAN/0.0.0.0, aucun CORS.
En-tête `Authorization: Bearer <token>` obligatoire pour toute route `/v1/`.
Le token local ouvre seulement la consultation ; ce n'est pas une identité
humaine authentifiée autorisant une action. Aucun token dans URL, log,
localStorage/sessionStorage/cookie ou artefact Git.

Host autorisé : `127.0.0.1:PORT` ou `localhost:PORT`. Origin absent ou exactement
`http://` + le Host reçu ; `null` et tout autre Origin sont refusés. Le client
doit être servi par ce même serveur, pas ouvert via `file://`.

## Routes

| Méthode et chemin | Corps JSON | Réponse 200 |
| --- | --- | --- |
| GET `/v1/health` | aucun | `protocol: eidolon-http-read/1`, `mode: read_only`, `store_id`, `authorizes_execution: false` |
| POST `/v1/missions` | `{}` ou `{limit: 1..100, cursor: objet}` | réponse existante `eidolon-mission-list/1` inchangée |
| GET `/v1/missions/m-ID` | aucun | réponse `eidolon-client-sync/1`, SNAPSHOT |
| POST `/v1/missions/m-ID/poll` | `{cursor: objet, limit?: 1..100}` | DELTA ou RESET_REQUIRED selon ClientSync |

Le POST transporte un curseur sans le mettre dans l'URL ; **aucune écriture**.
La première page omet le curseur (null également accepté pour la liste).
Seul `application/json` (avec charset=utf-8 facultatif) est accepté en POST.
Pas de paramètres d'URL, de clés inconnues, de clés JSON dupliquées ni de NaN.
Requête <=8192 octets, réponse <=262144 octets ; connexion fermée après réponse.

Erreurs JSON : `{protocol: 'eidolon-http-read/1', error: CODE,
authorizes_execution: false}`. HTTP 401 authentification, 403 Host/Origin,
400 entrée/curseur, 404 mission/route, 405 méthode, 413 volume requête,
415 type, 503 stockage/état indisponible ou réponse trop volumineuse.
Aucune exception brute/chemin/SQL renvoyé. RESET_REQUIRED reste HTTP 200 :
c'est une réponse de protocole à appliquer explicitement, pas une panne réseau.

## Client G031

Créer `desktop/connected/index.html`, `app.js`, `style.css` et les tests/docs
associés. Le serveur sert seulement `/`, `/app.js`, `/style.css` depuis un
`--web-root` explicite ; fichiers statiques publics, sans donnée ou token.
CSP : scripts/styles/connexions same-origin, aucun inline ni ressource distante.
Les requêtes de l'application emploient `/v1/...`, sans choix d'hôte arbitraire.
Token saisi manuellement, mémoire uniquement, effacé à la déconnexion.

Afficher « consultation » ; aucune commande approuver/run/annuler. Lister les
missions et sélectionner leur snapshot/poll. Paginer sans boucler indéfiniment,
signaler RESET_REQUIRED, conserver un dernier état connu daté et marqué périmé
sur panne. Éviter les réponses d'une ancienne connexion/sélection. Ne pas
modifier `desktop/prototype/`, dont les scénarios doivent rester simulés.

## Limites

Serveur local de développement mono-requête, délai socket et volumes bornés ;
pas de garantie de délai total face à un client local hostile, pas de serveur
public. Pas de TLS intégré : le tunnel SSH protège le trajet PC–serveur.
Pas de service systemd installé, pas de découverte/appairage automatique.
La consultation ne valide ni le modèle, ni les effets, ni le fonctionnement
du serveur complet. SQLite ouvert en mode ro ; ses fichiers auxiliaires WAL
peuvent dépendre du mode du producteur. Aucun journal métier n'est écrit.
