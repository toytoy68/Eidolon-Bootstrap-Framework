# Lecteur HTTP raccordé au coordinateur de recherche

Auteur : Codex/GPT. Date : 05/10/2026. Intégration Claude G006/G007 : `534f4f4`.
Modules : `web_reader.py`, `web_transport.py`, `research.py`.
Statut : **candidat testé sur simulations et HTTP/TLS locaux**, hors runtime
et hors CLI principale. Aucun fournisseur Internet ou modèle réel raccordé.

## Parcours disponible

`ResearchCoordinator` reçoit les résultats d'un fournisseur, contrôle l'URL
par la politique `/2`, puis appelle `WebReader`. Celui-ci utilise `fetch()` :
nouvelle décision de destination, IP épinglée, contrôle de chaque redirection,
GET fixe sans identifiant, corps borné. Le coordinateur distingue ensuite
texte lu et contenu inexploitable ; son résultat n'est pas une mission réussie.

Le lecteur est une configuration figée : résolveur, connecteur, limites,
`transport_id`. Son identifiant comprend l'empreinte des limites et cette
identité de transport. Les dépendances injectées restent du code de confiance ;
changer leur comportement exige une nouvelle identité/configuration. Elles ne
sont pas rendues immuables ni isolées par le dataclass.

Le protocole optionnel `read_guarded(url, policy, before_hop)` permet au
coordinateur d'interdire une connexion après annulation/délai, ou vers un
domaine déjà en attente. `fetch()` appelle ce contrôle **après** sa propre
décision d'autorisation, à chaque saut. Il ne peut pas autoriser une destination
refusée par la politique. Un lecteur tiers n'implémentant que `read()` garde
le contrat précédent, sans cette vérification supplémentaire entre ses sauts.

## Provenance et refus

Une page lue garde `retrieval` : URL finale, IP/port sélectionnés, sauts,
statut HTTP, date d'observation, taille et SHA-256 des octets. Taille/empreinte,
URL, statut et politique sont contrôlés avant adoption par le coordinateur.
Le cache conserve la date et la provenance originales ; il ne crée pas une
nouvelle observation. Le contenu reste une donnée non fiable.

Un refus HTTP garde seulement une observation de statut/en-têtes,
`kind=http_headers`, avec `headers_validated`. Pour un statut 429/503 reçu
mais des en-têtes rejetés, l'observation garde le statut et `header_error`,
sans aucune valeur d'en-tête : `headers_validated=false`, `retry_after=null`,
`retry_review_required=true`. La suspension reste indéfinie dans cette session,
y compris pour une autre URL du domaine ; aucun délai ambigu n'est adopté.
Ce chemin exige un statut entier valide. Si le parseur HTTP échoue avant de
rendre une réponse (par exemple plus de 100 en-têtes), aucun statut exploitable
n'est disponible et l'erreur reste INVALID_RESPONSE.
Le connecteur ne lit pas le corps d'erreur ; aucune empreinte de ce corps n'est
inventée. 401/403 deviennent ACCESS_DENIED, 429 RATE_LIMITED, les autres codes
non 200 HTTP_ERROR. Un défi HTML 200 reste CHALLENGE_SUSPECTED, jamais READ.
Les échecs transport restent distingués : TIMEOUT, POLICY_REFUSED, TLS_ERROR,
TRUNCATED, TOO_LARGE, INVALID_RESPONSE, UNSUPPORTED_CONTENT ou UNAVAILABLE.

## Attente sans relance bloquante

`Retry-After` accepte une durée entière positive ou nulle, ou une date HTTP.
Le délai est arrondi vers le haut, une date passée donne zéro. Ce format est
défini par [RFC 9110 §10.2.3](https://www.rfc-editor.org/rfc/rfc9110.html#section-10.2.3),
consultée pour ce lot. Une valeur invalide ou supérieure à un jour déclenche
`retry_review_required=true` : suspension de session sans échéance automatique,
plutôt que raccourcissement du délai demandé. Aucun sommeil ni nouvel essai
automatique dans l'appel. Une redirection avec attente est rendue au coordinateur
sans contacter sa cible ; une réponse 503 avec attente est aussi respectée.

La suspension porte sur les domaines demandés et finaux (hôte/port), puis est
recontrôlée à chaque nouveau saut. Une autre URL redirigeant vers un domaine
suspendu donne RETRY_WAIT sans connexion vers celui-ci. La suspension est RAM,
bornée ; au débordement, une pause globale conservatrice conserve l'attente
la plus longue. Elle n'est pas durable : redémarrer le processus ou recréer le
coordinateur perd cet état. La revue n'est pas une nouvelle approbation de mission.

## Corrections de frontière du transport G006

- Validation stricte de RawResponse et des paires d'en-têtes avant utilisation.
- Content-Length dupliqué (même identique), ou combiné à Transfer-Encoding :
  AMBIGUOUS_HEADER. Longueur invalide : BAD_HTTP_RESPONSE. Longueur déclarée
  différente des octets : TRUNCATED, même si un connecteur annonce complete=True.
- Encodage/longueur contrôlés avant lecture du corps par le connecteur standard.
  Chunked sans Content-Length reste supporté ; aucune décompression ajoutée.
- Contexte TLS : `CERT_REQUIRED` et `check_hostname` revérifiés avant chaque
  échange. Ce contrôle ne couvre PAS minimum_version, ciphers/security_level,
  verify_flags ni une mutation concurrente. L3 de G008 corrige ici une promesse
  documentaire trop large ; le durcissement de ces autres paramètres reste ouvert.
- Une réponse complète arrivée tard reste disponible avec deadline_exceeded.
  Si le délai du transport est dépassé, le coordinateur rend DEADLINE, garde
  le reçu et ne le met pas au cache. Une annulation concurrente garde aussi le
  reçu sans annoncer l'objectif atteint. Attention C1 de G008 : un délai du seul
  coordinateur ou une annulation peut encore laisser ce reçu dans le cache,
  avec sa date originale ; l'harmonisation de cette règle reste ouverte.

Le budget temporel reste **coopératif** : DNS et appels en cours ne sont pas
interrompus. Un pair envoyant au goutte-à-goutte peut dépasser largement la
somme total_seconds + read_seconds : le timeout socket est renouvelé au fil
des recv internes. La limite d'en-têtes configurée est vérifiée après le parseur
stdlib, qui possède ses propres bornes ; ce n'est pas un plafond d'allocation
égal à max_header_bytes. Le nombre de lectures compte les appels au lecteur,
pas chaque saut HTTP ; la politique borne séparément les redirections.

## Contrat connecteur révisé après G008 — Codex/GPT

D2 : `exchange(..., limits, remaining_seconds)` reçoit une durée positive,
jamais une échéance absolue issue de l'horloge injectée de fetch. Le connecteur
standard calcule son échéance locale avec time.monotonic ; les redirections
reçoivent seulement le reste du budget et le temps du before_hop est décompté.
La limite de connexion est au plus cette durée restante. Cette correction
n'ajoute pas d'interruption dure d'une lecture en cours.

Changement de protocole candidat : remplacer l'ancien argument `deadline`
dans les connecteurs tiers/doubles. Aucune détection silencieuse de l'ancienne
signature. `transport_id` par défaut passe à `stdlib-http/3` et reader_id à
`web-reader/2/…` pour distinguer la sémantique. Les sondes Claude archivées sont
inchangées : les rejouer exige une copie adaptée explicitement, pas une réécriture
de leurs preuves historiques. Redirection sans Location : INVALID_RESPONSE (C5).

Le compteur readable_pages décrit les reçus lisibles, même tardifs (C2) :
seul le statut global dit si le seuil est atteint dans le budget. Un statut
HTTP_ERROR peut porter une attente (C3) : lire aussi retry_after et
retry_review_required. final_url et source.url gardent encore les paramètres
URL en clair (C4) ; le masquage des sauts n'est pas une minimisation complète.
Données synthétiques seulement jusqu'au lot de minimisation.

[Preuves et tri G008](validation/2026-10-05/codex-g008-fixes/README.md).

## Démonstration

Depuis `eidolon-core/`, Python 3.11+ et bibliothèque standard :

```sh
PYTHONPATH=src:. python -m examples.research_http_demo --format human
PYTHONPATH=src:. python -m examples.research_http_demo
PYTHONPATH=src:. python -m unittest tests.test_web_reader tests.test_web_transport_boundaries -v
```

Un serveur lié uniquement à 127.0.0.1 sert quatre fixtures. Le fournisseur et
le DNS sont simulés. Un connecteur **de démonstration seulement** remplace l'IP
publique sélectionnée par 127.0.0.1 ; les IP affichées dans les reçus sont donc
des valeurs de fixture, pas des machines réellement contactées. La politique
ne reçoit aucune exception autorisant le loopback.

Assertions : cinq requêtes locales (dont une redirection), un texte lu,
trois refus/contenus inexploités et résultat PARTIAL pour deux lectures requises.
[Preuves](validation/2026-10-05/codex-web-reader/README.md).

## Limites et prochaine tranche

Extraction HTML optionnelle C-011 ci-dessous ; pas de JavaScript, authentification, robots.txt,
minimisation automatique des requêtes, fournisseur réel, persistance du cache
ou des quotas, ni intégration aux permissions/exécutants des missions. C-D08
et les tests VM restent différés. Les hypothèses de G007 sont intégrées comme
propositions ; son corpus a été exécuté par Claude sur `99641df` (C018), résultat rapporté
non requalifié par ce lot de correctifs du transport. READ_TARGET_MET ne peut pas être traduit en ANSWERED sans contrat
supplémentaire sur la question, ses sources et les contradictions.


## Complément C-002c — pauses persistantes optionnelles

[ResearchPauses](RESEARCH-PAUSES.md) peut être fourni au coordinateur pour
conserver les suspensions par fournisseur/origine. WebReader utilise le contrôle
avant chaque saut déjà présent ; aucun transport ni identité réseau modifiés.
Avec cette option, toutes les pauses exigent une levée explicite. Sans elle,
les pauses décrites dans le présent document restent en RAM. La persistance ne
couvre pas une réponse perdue avant son enregistrement : voir les limites du lot.

## C-011 — extraction HTML optionnelle, 07/10/2026

```python
from eidolon_core.html_extract import ExtractLimits
from eidolon_core.web_reader import WebReader

# resolver/connector restent des composants de confiance explicitement fournis.
reader = WebReader(resolver, connector, html_limits=ExtractLimits())
```

Par défaut `html_limits=None` : HTML reste inexploité. Le lecteur conserve
les octets reçus et leur provenance ; le coordinateur effectue l'extraction
locale. `reader_id` passe à `web-reader/3/…` et inclut version/limites de
l'extracteur. Une modification de ces limites donne une autre identité/cache.
Cette option n'active aucun fournisseur Internet ni outil de mission.

Seuls `text/html` et `text/html; charset=utf-8` (casse/espaces/guillemets tolérés)
sont extractibles. Charset différent, paramètres supplémentaires ou HTML
détecté mais annoncé en texte brut : UNSUPPORTED_CONTENT. Pas de devinette
d'encodage. UTF-8 strict ; BOM accepté par l'extracteur.

Avant extraction : statuts HTTP, complétude du transport et taille restent
prioritaires, puis signaux d'accès. Titres exacts de challenge déjà traités,
champ password → LOGIN_SUSPECTED, titres exacts « Subscribe to continue »,
« Subscription required », « Abonnez-vous pour continuer » → PAYWALL_SUSPECTED.
Ce dernier état entre aussi dans les pauses persistantes nécessitant revue.
Ce sont des **heuristiques limitées**, pas une détection universelle des murs
d'accès ; un article parlant de CAPTCHA n'est pas refusé sur ce seul mot.

| Extraction | État du lecteur dans le rapport | Compte comme page lue / cache |
| --- | --- | --- |
| OK, complète | READ | Oui, sauf annulation/délai pour le cache |
| EMPTY | EMPTY_CONTENT | Non |
| PARTIAL (taille/profondeur/segments) | EXTRACTION_PARTIAL | Non ; texte partiel non adopté |
| REFUSED | EXTRACTION_REFUSED | Non |

Le rapport conserve `body_sha256`/`body_bytes` et `retrieval` des octets reçus.
Le champ `extraction` contient version, limites, statut/complétude, avertissements
et SHA-256 source/texte. L'empreinte source doit correspondre au reçu HTTP,
y compris pour une extraction partielle. Le cache conserve l'observation
initiale et ces métadonnées, sans nouveau fetch des ressources intégrées.

La déduplication utilise le hash du texte extrait pour HTML (celui des octets
pour texte brut inchangé) : deux habillages HTML du même texte ne satisfont
pas un objectif de deux pages. Cela ne prouve pas l'indépendance des sources.
Le texte est `untrusted_external_text`, `authorizes_execution=false` : même
une instruction visible dans la page reste une donnée, jamais un ordre.

Pas de rendu CSS complet, JavaScript, authentification, contournement de défi
ou abonnement. Les seuils de lecture ne constituent pas une réponse validée.
[Preuves du raccordement](validation/2026-10-07/codex-html/README.md).
