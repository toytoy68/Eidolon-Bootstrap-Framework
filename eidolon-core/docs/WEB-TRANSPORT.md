# Transport HTTP de lecture candidat — C-002b

Auteur : Claude, 05/10/2026, fiche [C-TASK-G006](../collaboration/tasks/C-TASK-G006.md).
Base : `ffd4354` (contient la politique `web-destination/2`, `02af040`).
Statut : module **candidat**, hors runtime et hors CLI. Aucune capacité n'est
accordée à un modèle. Aucun site réel n'a été contacté.

Module : [`src/eidolon_core/web_transport.py`](../src/eidolon_core/web_transport.py).
Tests : [`tests/test_web_transport.py`](../tests/test_web_transport.py), 15 tests.
Démo : `PYTHONPATH=src:. python -m examples.web_transport_demo` (aucun socket ouvert).
`egress.py` est lu, pas modifié.

## Ce que fait `fetch()`

```python
result = fetch(url, policy=WebPolicy(...), resolver=resolveur, connector=None, limits=TransportLimits())
```

1. `egress.decide(url, resolver, policy)` ; une `Decision` passée en entrée est
   refusée : seule une URL est acceptée, et la décision est toujours recalculée.
2. Destination refusée : `DESTINATION_REFUSED`, **aucune connexion** vers elle.
3. Connexion TCP à `Decision.address` seulement. Le nom n'est **jamais résolu
   une seconde fois** (testé : un résolveur qui renverrait 127.0.0.1 au second
   appel n'est appelé qu'une fois).
4. En HTTPS, le socket est enveloppé avec `server_hostname = Decision.host` :
   SNI et vérification du certificat portent sur le nom contrôlé, pas sur l'IP.
5. Requête fixe : `GET`, en-têtes `Host`, `User-Agent`, `Accept: */*`,
   `Accept-Encoding: identity`, `Connection: close`. Ni corps, ni cookie, ni
   identifiant, ni en-tête choisi par l'appelant.
6. Redirections 301/302/303/307/308 : jamais suivies par la bibliothèque. Le
   code appelle `egress.follow()` avec la **même politique** ; budget de
   redirections de la politique ; URL déjà visitée → `REDIRECT_LOOP`.
7. Réponse 2xx : corps lu par blocs jusqu'à la borne ; `Content-Encoding`
   autre qu'`identity` ou `Transfer-Encoding` autre que `chunked` → refus
   `ENCODED_CONTENT`. **Aucune décompression**, donc pas de bombe de décompression.

## Résultat

`FetchResult` : URL finale canonique, adresse et port réellement contactés,
statut, type de contenu (borné, caractères imprimables), date d'observation
UTC, taille, SHA-256 des octets reçus, `policy_id`, chaîne des sauts et octets
(`body`). Chaque saut garde URL sans requête, empreinte de la requête si elle
existe, adresse, port, statut ; jamais de contenu. `evidence()` rend une forme
compacte sans le corps, avec deux limites explicites : ce sont des octets reçus,
non vérifiés, et une observation datée, pas un contenu actuel garanti.

## Erreurs

`WebTransportError(code)` ; le message ne recopie jamais un corps ni une valeur
d'en-tête reçue (testé avec un marqueur dans un corps 500).

`DESTINATION_REFUSED` (avec le motif de la politique), `REDIRECT_LOOP`,
`HTTP_STATUS`, `ENCODED_CONTENT`, `TRUNCATED`, `BODY_TOO_LARGE`,
`HEADERS_TOO_LARGE`, `AMBIGUOUS_HEADER` (en-tête de contrôle dupliqué),
`TLS_CERTIFICATE`, `TLS_ERROR`, `TIMEOUT`, `CONNECTION_FAILED`,
`BAD_HTTP_RESPONSE`, `DEADLINE_EXCEEDED`.

## Ce que bornent vraiment les délais

| Borne | Couvre | Ne couvre pas |
| --- | --- | --- |
| `connect_seconds` | Établissement TCP et poignée de main TLS (délai du socket) | La résolution DNS |
| `read_seconds` | **Chaque** lecture sur le socket | La durée totale du corps : un serveur qui envoie un octet toutes les 9 s ne la dépasse jamais |
| `total_seconds` | Vérifié avant chaque saut et entre deux blocs du corps | Un appel bloquant en cours : le dépassement réel peut atteindre `total_seconds` + `read_seconds` (ou + `connect_seconds`) |
| Résolveur | Rien : `resolver()` est appelé tel quel | Un `getaddrinfo` système peut bloquer sans limite propre |

Il n'y a donc **pas de budget global garanti**. Pour une garantie dure, le
futur raccordement doit exécuter `fetch()` dans l'exécutant à délai du runtime
(`worker.invoke`), qui peut l'interrompre.

## Sources de comportement (Python 3.11.15 installé)

Lu dans `/usr/lib/python3.11/http/client.py` (SHA-256 `a6c48f3709b4…`) :
- `HTTPConnection.connect()` (l. 979) crée le socket ; la sous-classe la
  remplace pour se connecter à l'adresse épinglée ; `HTTPSConnection.connect()`
  (l. 1485) enveloppe le socket avec `server_hostname = self.host`, ici le nom ;
- `_MAXLINE = 65536` et `_MAXHEADERS = 100` (l. 111-112, 230) : au-delà, une
  exception, traduite en `HEADERS_TOO_LARGE` (testé avec 120 en-têtes) ;
- `putrequest(..., skip_host=True, skip_accept_encoding=True)` : sans
  `skip_host`, la bibliothèque ajouterait un second `Host` ;
- `read(amt)` ne signale pas une fin prématurée (commentaire « Ideally, we would
  raise IncompleteRead ») ; le module compare donc la taille reçue à
  `Content-Length` (testé : 10 octets reçus sur 1 000 annoncés → `TRUNCATED`) ;
- `http.client` ne lit pas les variables de proxy (c'est `urllib` qui le fait) ;
  testé avec `HTTP_PROXY`/`HTTPS_PROXY` pointant vers un port fermé.

TLS : `ssl.create_default_context()` par défaut (certificat requis, vérification
du nom). Un contexte injecté qui désactive l'une des deux est refusé à la
construction. Le site de documentation Python n'a pas été consulté depuis cette
session ; ces constats viennent du code installé et des tests.

## Tests

- **Simulés** (connecteur et DNS injectés) : absence de seconde résolution,
  destinations refusées jamais contactées (LAN, bouclage, http, port), exclusions
  du foyer via un nom et via une redirection, redirections recontrôlées et
  requête de saut masquée, boucle et budget, erreurs nommées sans écho du
  corps, délai global entre sauts, entrées et configuration TLS refusées.
- **Loopback réel** (`http.client`, serveurs 127.0.0.1) : `Host` porte le nom,
  proxy ignoré, exactement cinq en-têtes envoyés, corps trop gros, réponse
  tronquée, serveur lent, contenu gzip, 120 en-têtes, boucle de redirection,
  connexion refusée.
- **TLS loopback** : autorité de test et certificats générés par `openssl`
  pendant le test ; SNI reçu par le serveur = nom contrôlé ; certificat d'un
  autre nom et autorité non approuvée → `TLS_CERTIFICATE`.

**Comment le loopback reste honnête** : la politique n'est pas affaiblie. Le
DNS simulé rend une adresse publique de test ; la décision est prise sur elle ;
seul un connecteur **de test** (`LoopbackConnector`) remplace ensuite cette
adresse par 127.0.0.1 pour joindre le serveur local. Ce connecteur n'existe que
dans les tests.

## Raccordement proposé (non fait)

- Exécuter `fetch()` dans `worker.invoke` pour une borne de temps dure et la
  reprise prudente existante ; résolveur système appelé dans l'exécutant.
- Capacité `web.read` (classe `egress_read`) du catalogue ; `Policy` l'autorise
  par liste ; la politique entre dans `configuration()` via `policy_id`.
- Stocker `evidence()` dans la mission, et les octets dans un futur magasin
  d'artefacts borné (TODO), pas dans le corps de mission SQLite.
- Traiter le contenu comme donnée non fiable : jamais d'instruction ni
  d'extension de permission tirée d'une page.

## Limites

Aucun site réel, aucun réseau du foyer, aucun pare-feu ni VPN. Pas d'analyse
HTML, de navigateur, de JavaScript, d'authentification de service ni d'écriture
distante. HTTP/1.1 seulement. Les erreurs TLS dépendent d'OpenSSL 3.0.13 local.
`AMBIGUOUS_HEADER` ne couvre que les en-têtes lus par le module.
