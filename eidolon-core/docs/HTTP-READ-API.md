# API HTTP de consultation — contrat C-009a

Codex/GPT, 06/10/2026. Implémentation locale livrée dans
`src/eidolon_core/http_api.py` ; G031 peut développer le client contre ce contrat.
Preuves : `docs/validation/2026-10-06/codex-beta-api/`.

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
| POST `/v1/command-receipt` | `{store_id, client_id, command_key, mission_id}` | reçu historique ou absence, selon [C-009b](HTTP-RECEIPTS.md) |
| POST `/v1/missions/m-ID/poll` | `{cursor: objet, limit?: 1..100}` | DELTA ou RESET_REQUIRED selon ClientSync |

Le POST transporte un curseur ou une clé de reçu sans le mettre dans l'URL ; **aucune écriture**.
La première page omet le curseur (null également accepté pour la liste).
Seul `application/json` (avec charset=utf-8 facultatif) est accepté en POST.
Pas de paramètres d'URL, de clés inconnues, de clés JSON dupliquées ni de NaN.
Requête <=8192 octets, réponse <=262144 octets ; connexion fermée après réponse.
Profondeur JSON limitée à 16. Seule la version existante du schéma est lue ;
base absente ou copie de restauration en revue refusée, sans création/migration.

Erreurs JSON : `{protocol: 'eidolon-http-read/1', error: CODE,
authorizes_execution: false}`. HTTP 401 authentification, 403 Host/Origin,
400 entrée/curseur, 404 mission/route, 405 méthode, 413 volume requête,
409 identité Store/mission du reçu divergente, 415 type, 503 BUSY, stockage/état indisponible ou réponse trop volumineuse.
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

Serveur local de développement, **quatre connexions simultanées au plus**.
Une connexion supplémentaire reçoit un **503 BUSY** fixe avant parsing et
authentification, sans lecture de la base ni thread supplémentaire. Écriture
bornée à 50 ms ; si le socket est déjà fermé/non inscriptible, la livraison de
ce refus n’est pas garantie. Le client ne doit pas le confondre avec un résultat
de commande ni renvoyer automatiquement une commande. Lecture : délai d’inactivité 3 s et
échéance totale de 5 s pour ligne, en-têtes et corps, même si des octets arrivent
régulièrement. Écriture : délai socket séparé de 3 s. Les connexions en attente
de lecture sont interrompues à la fermeture du serveur, puis ses workers joints.
SQLite : budget coopératif de 2 s par connexion de lecture, contrôlé toutes
les 1000 instructions de sa VM ; interruption renvoyée comme STATE_UNAVAILABLE,
et attente des verrous déjà limitée à 2 s. Cela ne borne pas les E/S du système
de fichiers ni les calculs Python. Ce n’est pas un délai total garanti, ni une
protection contre tout déni de service local ; pas de serveur public. Pas de TLS intégré : le tunnel SSH protège le trajet PC–serveur.
Pas de service systemd installé, pas de découverte/appairage automatique.
La consultation ne valide ni le modèle, ni les effets, ni le fonctionnement
du serveur complet. SQLite ouvert en mode ro ; ses fichiers auxiliaires WAL
peuvent dépendre du mode du producteur. Aucun journal métier n'est écrit.

## Lancement de développement Linux

Depuis `eidolon-core/`, dans un environnement Python 3.11+ où les tests Core
passent. Ne pas lancer les scripts Bootstrap pour cette recette.

```sh
export PYTHONPATH=src:.
EIDOLON_BETA_STATE="$(mktemp -d /tmp/eidolon-beta-XXXXXX)"
python -m eidolon_core --state "$EIDOLON_BETA_STATE" demo
python -m eidolon_core.access_token --output "$EIDOLON_BETA_STATE/read-token" --format human
python -m eidolon_core.http_api --state "$EIDOLON_BETA_STATE" \
  --token-file "$EIDOLON_BETA_STATE/read-token" --port 8765
```

Le dernier processus reste au premier plan (Ctrl+C pour arrêter). Le token
est généré dans un fichier privé, jamais affiché par le serveur. Le consulter
localement pour le saisir dans le client ; ne pas le publier ou le coller dans
les échanges. Une rotation se fait avec un nouveau fichier puis un redémarrage.

**G031 est intégré** : ajouter à la dernière commande
`--web-root desktop/connected` pour servir le [client connecté](../desktop/connected/README.md).
Sans web-root, `/` renvoie 404. Le prototype autonome existant ne doit pas être
passé comme web-root. La consultation des reçus historiques G036 est intégrée ; elle ne modifie pas
la capture courante et ne prouve pas l’exécution de la commande.

C-053 : `/eidolon-logo.png` est un asset facultatif à nom fixe, avec les mêmes
contrôles de racine, de taille et de liens que les autres fichiers. Son absence
n'empêche pas le lancement et donne 404 ; un logo présent mais invalide est refusé.
Aucun navigateur de fichiers ni chemin d'asset arbitraire n'est ajouté.

Sur le PC, tunnel SSH (remplacer les deux valeurs entre chevrons) :

```text
ssh -N -L 127.0.0.1:8765:127.0.0.1:8765 <utilisateur>@<serveur>
```

Puis ouvrir `http://127.0.0.1:8765`. Le tunnel doit
garder le même port local ; un port occupé nécessite un autre port **aux deux
extrémités** et le même `--port` côté serveur. Arrêter le tunnel ne stoppe pas
Core. Aucun essai de tunnel ou Windows réel revendiqué ici.

## Vérifier les prérequis sans démarrer

Ajouter `--check --format human` à la commande de lancement ci-dessus. Le
[diagnostic C-009c](HTTP-PREFLIGHT.md) contrôle état, jeton et assets existants
sans ouvrir de port. JSON par défaut, codes de retour 0/2. Il ne teste ni la
disponibilité du port, ni le navigateur ou le tunnel.

La création locale du jeton est documentée dans [READ-TOKEN.md](READ-TOKEN.md).
Un refus avec `CREATED_REVIEW_REQUIRED` exige un examen local ; ne pas
supposer que le nouveau fichier est absent parce que le code de retour vaut 2.

### Précision G045 — budgets et capacité (07/10)

Le budget SQL est par connexion, pas par requête HTTP. `health`, inventaire
et reçu utilisent une connexion ; snapshot/poll en ouvrent deux successivement
(existence puis projection), donc peuvent consommer environ deux budgets SQL,
en plus du travail Python et des entrées/sorties non couverts. Les petites
requêtes sous le pas du progress handler ne sont pas interrompues par ce mécanisme.
Ce n'est pas une échéance globale dure de 2 s ou 4 s.

G045 mesure encore des refus à quatre clients séquentiels : la place reste
occupée jusqu'à la fermeture du socket. La variante libérant la place avant
`shutdown_request` réduit les refus dans son banc mais permet des threads de
fermeture hors de la table de comptage. Elle n'est pas adoptée dans ce lot :
la borne des connexions suivies et la fermeture au `server_close` sont conservées.
Le chiffre de refus G045 est une mesure du banc, pas une prévision de production.

### Lecture des gros champs SQLite — C-054

Les corps de mission et détails d'événement sont ouverts en lecture seule avec
`sqlite3.Connection.blobopen`, dans la transaction de lecture qui a sélectionné
leur ligne. Leur longueur en octets est contrôlée **avant** lecture et décodage,
avec une limite inchangée de 16 Mio par champ. Le stockage doit rester de type
TEXT ; un BLOB n'est pas implicitement accepté. Aucune lecture non bornée de
remplacement si cette API est indisponible.

Cela corrige l'allocation native observée par Claude C102 :
`substr(CAST(TEXT AS BLOB), ...)` limitait le résultat Python tout en matérialisant
le grand champ dans SQLite. Le banc Linux Python 3.12 / SQLite 3.53.1 sur un TEXT
de 256 Mio mesure un pic de 300,6 Mio avant et de 12,5 Mio après.
Ce contrôle porte sur ces deux champs, pas sur toute allocation de schéma,
d'index ou de métadonnées de la base. Ce n'est pas une borne RSS globale ni une
qualification Windows. [Banc reproductible](validation/2026-10-09/codex-hour-0833/README.md).


## Politique du client et saturation — C-023

La CSP complète est identique sur les assets, réponses API, erreurs et réponse
préauthentification BUSY. Les en-têtes proviennent d’une constante commune ;
la saturation n’ajoute toujours aucun worker ni lecture de requête/jeton/état.
Le test G055 de Claude distingue cette politique Web de la navigation Tauri et
de son ACL IPC : la coquille seule n’est pas un filtre réseau des sous-ressources.
[Suivi reproduit](validation/2026-10-07/codex-g055-followup/README.md).


## Catalogue de recherches C-030

Option serveur --research-archives : [contrat et codes](HTTP-RESEARCH-ARCHIVES.md).
POST /v1/research-archives est une consultation paginée authentifiée, sans mutation.
Sans option, ARCHIVES_NOT_CONFIGURED. Aucun chemin n'est fourni par le client.

## Lecture bornée et mode SQLite — C-045, 08/10/2026

La consultation prend en charge le journal SQLite classique utilisé par Core.
Une base passée extérieurement en WAL est refusée **avant la connexion** avec
`READ_ONLY_WAL_UNSUPPORTED` côté Python ; l'API conserve son refus public
`STATE_UNAVAILABLE`. Cela évite que SQLite `mode=ro` crée des fichiers `-wal`
et `-shm`. Le diagnostic ne change jamais le mode de journalisation, ne supprime
pas ces fichiers et n'utilise pas `immutable=1`, qui ignorerait les verrous des
écrivains normaux. Une conversion éventuelle exige un arrêt et une opération
SQLite explicite hors de cette API, après sauvegarde et examen de l'état.

Les corps de mission et les détails d'événement utilisés pour les empreintes
sont bornés **dans la requête SQL**, à 16 Mio + un octet sentinelle. Au-delà,
la page entière est refusée ; aucun JSON partiel n'est présenté. La projection
publique garde sa taille et son protocole. Le rattrapage ne charge plus le corps
de chaque événement : seules ses références et les ancres nécessaires sont lues.
Les champs stockés doivent être du texte UTF-8 ; un BLOB UTF-16/UTF-8 n'est pas
silencieusement interprété comme un corps de mission ou un détail valide.

Ces limites bornent les valeurs chargées en Python, pas le coût total d'une base
arbitraire, du stockage ou du décodage d'un corps admissible. Le délai SQL demeure
coopératif. Les changements de mode/remplacements par un écrivain extérieur qui
ignore ces prérequis restent hors garantie de concurrence du Core.
