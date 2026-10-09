# Worker Image/Vidéo — C-064

Une file privée durable relie une **proposition média soumise** à un travail.
Elle ne lance rien à la réception de l'accord. Un opérateur lance explicitement
un ticket ; le résultat moteur reste non vérifié. POSIX, serveur Core seulement.

## Intégration conversation (Claude G122/G123)

```python
from eidolon_core.media_worker import MediaWorker

worker = MediaWorker(private_root, worker_id=configured_worker_id,
                     store_id=conversations.store_id)
receipt = worker.enqueue(
    submission, conversations=conversations,
    authenticated_client_id=paired_client['client_id'],
    authenticated_actor=paired_client['actor'])
```

- `paired_client` doit venir du contrôle du **jeton de conversation**, jamais des
  champs envoyés par le client. Le jeton de lecture ne donne aucun droit.
- `conversations.current_proposal(conversation_id)` doit relire la proposition
  média figée enregistrée par Core. C-064 n'accepte pas un JSON de proposition
  fourni par le navigateur ; G122 raccorde sa persistance et le dialogue.
- `enqueue` vérifie propriétaire, acteur, magasin, version, empreinte courante.
  Le reçu ne contient ni chemin, ni prompt, ni configuration. Aucun appel moteur.
- Même client et même clé avec soumission identique : même ticket, même après
  une proposition ultérieure. Même clé avec texte/motif différent :
  `MEDIA_COMMAND_KEY_REUSED`. Même proposition et nouvelle clé :
  `MEDIA_PROPOSAL_ALREADY_SUBMITTED`. Aucun renvoi ne crée un second travail.
- La file fait autorité pour les reçus média : ne pas créer une seconde file ou
  faire `execute()` dans la route. Après une réponse perdue :
  `worker.receipt(client_id=paired_id, command_key=original_key)`.
- Un ticket est un identifiant opaque, **pas un droit**. `tickets`, `result`,
  `poll_once`, `collect_once` prennent un `client_id` issu de l'authentification.
  L'API reste responsable de ce contrôle ; les commandes CLI sont opérateur.
- Le chemin et l'identité de la file sont une configuration serveur fixe, jamais
  une sélection faite par le navigateur. Une seule file active par magasin Core.
  La garantie d'un essai porte sur cette file, pas sur des copies/restaurations
  manuelles concurrentes ou des appels CLI directs à `eidolon-media run`.

### Résultats et suivi

```python
view = worker.result(ticket_id, client_id=paired_id,
                     conversations=conversations, artifact_store=server_artifact_store)
```

Lecture locale : `{receipt, result, observation}`. `result` est la vue G101,
construite depuis le travail dont **l'identifiant exact a été réservé** avant
exécution. Un travail différent ayant la même requête est refusé. Le navigateur
ne fournit aucun travail, collecte, chemin ou référence d'artefact.

- `ACCEPTED` : demande en attente, `result: null`, `NOT_STARTED`.
- `ATTEMPTED` : tentative durable ; le processus peut encore tourner ou avoir
  disparu. Ne pas déduire « arrêté » ou « sans effet ».
- `RETURNED` : le moteur a répondu et le journal lié a été relu ; **aucune
  réussite de l'objectif**. Le travail peut rester `QUEUED`.
- `REVIEW_REQUIRED` : erreur après admission ; revue, aucun nouvel essai.
- Journal absent/modifié : `JOB_UNAVAILABLE_OR_CHANGED`, aucune relance.
- Collecte absente après admission : `COLLECTION_UNAVAILABLE_OR_CHANGED`.
- Sorties présentes : empreintes vérifiées par G101 ; collecte partielle et
  texte d'analyse annoncés comme tels. Aucune ouverture depuis la page ici.

`poll_once(ticket_id, client_id=paired_id)` fait un GET explicite de l'historique,
retourne seulement l'état et les identifiants liés, sans chemins distants. Il ne
modifie pas le travail. `collect_once(..., artifact_store=...)` fait un unique
**essai** de collecte : GET puis import local. L'intention est persistée avant
l'appel ; une coupure conserve les imports partiels, aucun rejeu ne les duplique.
Un historique encore incomplet consomme aussi cet essai : sonder d'abord le moteur.
Aucune de ces méthodes ne libère la réservation ni n'annule le moteur.

## Commandes opérateur

Installer le paquet Core fournit `eidolon-media-worker` ; l'équivalent est
`python -m eidolon_core.media_worker_cli`. Les chemins ci-dessous sont à adapter,
les identifiants viennent des sorties réelles. Aucun moteur n'est installé par
ces commandes.

```sh
eidolon-media-worker --root /CHEMIN_PRIVE/media-worker --state /ETAT_CORE init

eidolon-media-worker --root /CHEMIN_PRIVE/media-worker --state /ETAT_CORE \
  --worker-id mw-IDENTIFIANT list --client-id pc

eidolon-media-worker --root /CHEMIN_PRIVE/media-worker --state /ETAT_CORE \
  --worker-id mw-IDENTIFIANT run --client-id pc --ticket mt-IDENTIFIANT \
  --config /CONFIG_PRIVEE/media.json --execute-local

eidolon-media-worker --root /CHEMIN_PRIVE/media-worker --state /ETAT_CORE \
  --worker-id mw-IDENTIFIANT poll --client-id pc --ticket mt-IDENTIFIANT

eidolon-media-worker --root /CHEMIN_PRIVE/media-worker --state /ETAT_CORE \
  --worker-id mw-IDENTIFIANT collect --client-id pc --ticket mt-IDENTIFIANT \
  --artifact-root /ARTEFACTS_PRIVES --artifact-store-id mas-IDENTIFIANT --collect-local

eidolon-media-worker --root /CHEMIN_PRIVE/media-worker --state /ETAT_CORE \
  --worker-id mw-IDENTIFIANT --format human result --client-id pc --ticket mt-IDENTIFIANT \
  --artifact-root /ARTEFACTS_PRIVES --artifact-store-id mas-IDENTIFIANT
```

`init` requiert un état Core et un dépôt de conversations existants/courants.
Il ne les crée ni ne les migre. Le parent de la nouvelle file doit être privé,
existant et appartenir à l'opérateur. Aucune CLI d'enqueue de JSON arbitraire :
la soumission passe par le code serveur authentifié.

`run` exige une configuration média comprenant un `resource_pool` C-061
existant et explicitement identifié. La source jointe et son propriétaire sont
revérifiés juste avant admission, puis le contenu est relu par l'exécuteur.
La configuration est choisie par l'opérateur, jamais par le modèle. Seule son
empreinte est conservée dans la file ; le journal média contient le plan moteur.

## Coupures et capacité

- Une tentative est fsyncée **avant** réservation de ressource, création du
  journal, transfert, FFmpeg et appel moteur. L'identifiant du travail est déjà
  lié au ticket. Une panne disque après admission peut laisser une réservation
  orpheline ; son job_id permet la comparaison avec le ticket.
- Pas d'expiration, de réinitialisation, de suppression ni de relance automatique.
  Une même proposition ne gagne pas un essai supplémentaire avec une nouvelle clé.
- Revue manuelle : lire ticket/journal/moteur ; conserver les éléments incertains.
  Pour refaire une opération, créer une nouvelle proposition et recueillir un
  nouvel accord, après vérification du moteur et libération exacte de la
  réservation avec `eidolon-media resource-release`.
- File bornée à 128 tickets et 8 Mio. La saturation refuse la nouvelle demande
  avant effet ; l'archivage de cette file reste à concevoir. Ne pas supprimer
  queue.json pour « débloquer » : cela détruirait les garanties d'idempotence.
- Verrou POSIX coopératif ; un autre écrivain donne `WORKER_BUSY`. Pas de boucle
  automatique de commande. Répertoires/fichiers privés, liens refusés, identité
  de racine vérifiée. Pas de protection contre un processus hostile du même UID.
- Ce worker ne régule pas le dialogue, ne mesure pas la VRAM et ne bloque pas les
  autres clients du moteur qui ignorent le groupe C-061.

## État de livraison

C-064 fournit code, CLI, contrats et tests synthétiques. G122/G123 raccordent
encore le dialogue, la soumission et l'interface. Aucun démon de traitement ni
lancement automatique depuis l'accueil n'est activé par cette livraison.
Les essais modèles réels, V100, VM et PC restent distincts.
