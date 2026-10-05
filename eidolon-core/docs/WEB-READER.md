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

Un refus HTTP garde seulement une observation d'en-têtes, `kind=http_headers`.
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
- Contexte TLS revérifié avant chaque échange ; un contexte injecté affaibli
  depuis sa construction ne peut plus ouvrir la connexion. Cela ne protège pas
  contre du code de confiance qui muterait le contexte concurremment.
- Une réponse complète arrivée tard reste disponible avec deadline_exceeded.
  Le coordinateur rend DEADLINE, garde le reçu et ne le met pas au cache.
  Une annulation concurrente garde aussi le reçu, sans annoncer l'objectif atteint.

Le budget temporel reste **coopératif** : DNS et appels en cours ne sont pas
interrompus. La limite d'en-têtes configurée est vérifiée après le parseur
stdlib, qui possède ses propres bornes ; ce n'est pas un plafond d'allocation
égal à max_header_bytes. Le nombre de lectures compte les appels au lecteur,
pas chaque saut HTTP ; la politique borne séparément les redirections.

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

Pas d'extracteur HTML général, JavaScript, authentification, robots.txt,
minimisation automatique des requêtes, fournisseur réel, persistance du cache
ou des quotas, ni intégration aux permissions/exécutants des missions. C-D08
et les tests VM restent différés. Les hypothèses de G007 sont intégrées comme
propositions ; son corpus est contrôlé mais pas encore exécuté contre le
coordinateur. READ_TARGET_MET ne peut pas être traduit en ANSWERED sans contrat
supplémentaire sur la question, ses sources et les contradictions.
