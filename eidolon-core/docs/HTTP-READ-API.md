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
409 identité Store/mission du reçu divergente, 415 type, 503 stockage/état indisponible ou réponse trop volumineuse.
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
passé comme web-root. La consultation des reçus dans le client attend G036.

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
