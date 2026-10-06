# Reçus persistants de décisions locales — C-008b

Auteur : Codex/GPT, 06/10/2026, Europe/Paris. Base `37604a1`.
Statut : implémenté pour les décisions du redémarrage **simulé** C-005a.
Python 3.11+/POSIX, bibliothèque standard, SQLite. Pas de serveur réseau,
d'identité authentifiée ni d'accès aux machines de toytoy.

## Démonstration et CLI

Depuis eidolon-core/ :

```sh
PYTHONPATH=src:. python -m examples.command_receipt_demo --format human
PYTHONPATH=src:. python -m examples.command_receipt_demo
PYTHONPATH=src:. python -m unittest tests.test_commands -v
```

La démo crée une mission et attend son accord. Une exception après commit
supprime la réponse au client ; un nouveau Store retrouve le reçu. Une sonde
explicite répète la commande et vérifie l'absence de seconde décision. Enfin,
un appel run distinct exécute et vérifie le redémarrage fictif. Aucun réseau
n'est simulé : seule la perte de la réponse est injectée. Les tests exécutent
également de vrais processus enfants quittant brutalement avant/après commit.

Sur un état déjà créé avec --profile action-sim :

```sh
PYTHONPATH=src python -m eidolon_core --state /tmp/eidolon-demo --profile action-sim command-submit --request command.json
PYTHONPATH=src python -m eidolon_core --state /tmp/eidolon-demo command-receipt --store-id s-ID --client-id desktop-test --command-key decision-001
```

Les valeurs s-ID, mission et proposition proviennent de client-snapshot ;
command.json suit exactement le contrat ci-dessous. La démo JSON fournit un
exemple réel dans command mais son état temporaire est supprimé en fin de démo.
L'ancienne commande decide reste disponible sans reçu de commande ; ce lot
n'invente pas de reçus rétroactifs. La consultation command-receipt ne construit
ni Runtime, ni modèle, ni monde simulé. L'initialisation Store effectue seulement
sa migration additive habituelle. Une base absente n'est pas créée par ces CLI.

JSON par défaut, --format human réutilise la présentation ECT. Code 0 signifie
« décision enregistrée » ou « reçu trouvé », jamais « outil exécuté ». Code 2 :
erreur, conflit ou reçu absent. Les sorties humaines restent marquées INFO pour
un reçu seul ; la démo affiche OK uniquement après ses assertions.

## Commande eidolon-decision-command/1

DecisionCommands(ActionRuntime(store)).submit(command) accepte exactement :

| Champ | Contrat |
| --- | --- |
| protocol | eidolon-decision-command/1 |
| store_id | Identifiant s-UUID de la capture locale |
| client_id | Espace de clés local, 1–80 caractères ASCII alphanumériques, point, tiret ou soulignement ; premier alphanumérique |
| command_key | Clé stable selon les mêmes bornes, créée et conservée avant émission |
| mission_id | Identifiant m-UUID existant |
| expected_revision | Révision entière de la mission relue, de 0 à 2^53−2 |
| proposal_sha256 | Empreinte exacte de l'action proposée, 64 caractères hexadécimaux minuscules |
| decision | approve, reject ou revoke |
| actor / reason | Libellés explicites bornés à 200 / 4 000 caractères ; pas de secret |

Fichier UTF-8 borné à 32 768 octets. Champs supplémentaires, doublons JSON,
valeurs non finies, substituts isolés, révision booléenne et encodages non UTF-8
sont refusés. Pas de champ « résultat » ou de permission fournie par le modèle.
La requête est copiée puis son JSON canonique est haché.

La clé est unique **dans un Store et un client_id, toutes missions confondues**.
Le même contenu retourne le reçu historique, y compris après une révocation ou
l'exécution. Un contenu différent avec la même clé est refusé COMMAND_KEY_REUSED.
Changer de client_id ne contourne ni la révision, ni le statut de proposition.
Aucune expiration automatique des clés, reçus ou propositions.

## Transaction et concurrence

Les validations de contrat, configuration, paramètres, permissions et statut
restent celles d'ActionRuntime.decide. Les deux interfaces partagent maintenant
_prepare_decision. Le verrou de mission protège la préparation ; save effectue
ensuite BEGIN IMMEDIATE et vérifie à nouveau la révision, l'identité du Store,
le lien du reçu à la décision et le drapeau d'annulation courant. Une annulation
enregistrée avant la transaction refuse la décision, même à révision inchangée.
Cette protection couvre aussi l'ancienne interface decide.

La modification de mission, l'événement ACTION_DECISION et le reçu sont écrits
dans **la même transaction SQLite**. Toute erreur avant commit annule les trois.
L'unicité (client_id, command_key) tranche également une course entre missions
ayant des verrous différents : la transaction perdante est annulée entièrement.
Un processus tué après commit peut perdre sa réponse sans perdre le reçu.

Un reçu existant se consulte sans verrou de mission, même pendant run. Une
nouvelle commande peut recevoir Busy si la mission est occupée ; aucun mécanisme
de répétition automatique n'est ajouté. La lecture d'un reçu et la capture de
mission restent deux lectures distinctes, pas un état global figé ensemble.

## Reçu et consultation

Le reçu eidolon-command-receipt/1 contient RECORDED, store_id, client_id,
command_key, mission_id, request_sha256, decision, proposal_sha256,
approval_status_at_recording, mission_revision, event_sequence, recorded_at,
execution_evidence=false. Révision et séquence restent des entiers sûrs JSON/JS.
L'acteur et la raison restent dans la mission/journal ; ils ne sont pas recopiés
dans le reçu. Celui-ci est une observation historique : APPROVED à l'enregistrement
peut désormais être REVOKED ou USED. Le reçu ne doit pas remplacer la capture
actuelle ni inverser une révocation reçue plus tard.

lookup_receipt(store, store_id=..., client_id=..., command_key=...) retourne
une enveloppe eidolon-command-lookup/1 avec FOUND et receipt, ou NOT_FOUND et
receipt=null ; execution_evidence=false et authorizes_resend=false dans les
deux cas. Une identité de Store différente produit STORE_CHANGED.

**NOT_FOUND n'est pas une preuve d'absence d'effet** : la commande peut encore
être en cours, la clé peut être incorrecte, la décision peut provenir de decide,
ou une sauvegarde ancienne peut avoir été restaurée. Consulter, resynchroniser
et revoir l'incertitude ; ne jamais changer de clé puis relancer automatiquement.
Un reçu trouvé prouve un enregistrement dans cette base de confiance, pas
l'autorisation actuelle d'exécuter. Le runtime revalide l'accord et les conditions
lors du run séparé ; seuls ses résultats vérifiés peuvent conclure la mission.

## Limites et prochaine tranche

- client_id et actor sont des libellés, **pas une authentification**. Ne pas
  exposer ces fonctions directement sur le réseau. Appairage, session et
  autorisations par identité sont une tranche distincte.
- Cette interface reste limitée à approve/reject/revoke. C-008c ajoute une
  interface distincte [d’annulation avec reçu](CANCEL-RECEIPTS.md), utilisant la
  même consultation et le même espace de clés ; vérifier receipt.protocol.
  Pas encore de reçus pour run, create ou reconcile. Aucun outil externe exécuté
  par submit.
- Identité copiée avec la base : une restauration/clonage conserve store_id et
  peut perdre des reçus récents. Pas de détection universelle de rollback ni de
  garantie « exactement une fois ». Après restauration, revue opérateur avant
  réémission ; une génération serveur sera à définir pour l'API distante.
- Migration additive sous user_version=1 ; pas de suppression ni purge des
  reçus. Rétention, sauvegarde cohérente et quotas restent à définir avant serveur
  permanent. Ne pas revenir à un ancien binaire pendant des commandes en cours.
- SQLite synchrone FULL et arrêts de processus testés ; coupure électrique,
  stockage VM/NAS, Windows natif et comptes concurrents réels non qualifiés.
- L'identifiant/hachage n'est ni une signature ni une preuve contre un opérateur
  qui modifie directement la base locale. Pas de corpus ni secret utilisateur.

[Preuves du lot](validation/2026-10-06/codex-command-receipts/README.md).
[Lecture du futur client](CLIENT-SYNC.md). Le prototype Claude reste simulé ;
la contre-revue G014 doit précéder un éventuel raccordement de ses commandes.
