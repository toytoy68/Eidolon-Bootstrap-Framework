# Proposition C-TASK-G041 — contrat des futures commandes distantes

Auteur : Claude, 06/10/2026. Fiche [C-TASK-G041](../../../collaboration/tasks/C-TASK-G041.md).
Statut : **étude**. Aucun endpoint d'écriture n'est ajouté, aucune
activation, aucun choix produit présumé. [Corpus de 18 scénarios](scenarios.json).

Sources lues dans le dépôt :

- [COMMAND-RECEIPTS.md](../../COMMAND-RECEIPTS.md) (C-008b, décisions) ;
- [CANCEL-RECEIPTS.md](../../CANCEL-RECEIPTS.md) (C-008c) ;
- [SIMULATED-ACTIONS-C005A.md](../../SIMULATED-ACTIONS-C005A.md) ;
- [HTTP-READ-API.md](../../HTTP-READ-API.md) (C-009a) ;
- [HTTP-RECEIPTS.md](../../HTTP-RECEIPTS.md) (C-009b) ;
- `approvals.py`.

## 1. Point de départ

Core sait déjà enregistrer localement une **décision** (approve, reject,
revoke) et une **demande d'annulation**, avec :

- une clé `command_key` conservée avant l'envoi ;
- un reçu historique ;
- la même transaction que l'effet sur la mission ;
- des refus explicites : `COMMAND_KEY_REUSED`, `STALE`, annulation déjà
  demandée.

Ce qui manque pour le faire **à distance** :

- **qui** commande : `actor` et `client_id` sont des libellés, pas une
  identité authentifiée ;
- **avec quel droit** : le seul jeton existant ouvre la lecture ;
- la **révocation** ;
- le comportement après une restauration de la base.

## 2. Principes proposés

1. **Le jeton de consultation ne devient jamais un droit d'écriture**, ni par
   un drapeau, ni par une route qui l'accepterait (scénario R01).
2. **Trois portées séparées** : `read`, `decide` (approve, reject, revoke),
   `cancel`. Un identifiant `cancel` ne peut pas approuver (R02). `run` reste
   local et hors de cette tranche (R17).
3. **Chaque commande est liée** :
   - au serveur (`store_id`, plus une **génération** de service à ajouter, R12) ;
   - à la mission (`mission_id`) ;
   - pour une décision, à la **révision vue** (`expected_revision`) et aux
     **paramètres exacts** (`proposal_sha256`, R04, R05).
   L'annulation garde sa règle actuelle : sans révision, pour ne pas être
   bloquée par l'avancement (R16).
4. **Identité de l'appareil ou de la session authentifiée**, écrite par le
   serveur dans le reçu (R13). Le libellé `actor` reste un commentaire, pas
   une preuve.
5. **Idempotence** :
   - le client crée la clé **avant** d'envoyer et la garde jusqu'au reçu ;
   - même clé et même contenu : le reçu historique (R06) ;
   - même clé et autre contenu : refus (R07) ;
   - réponse perdue : consulter le reçu, **jamais** une nouvelle clé
     automatique (R08, R18).
6. **Révocation côté serveur, immédiate.** Elle coupe aussi la lecture de cet
   appareil (R09) et n'efface aucun reçu (R10).
7. **Aucune décision ne vient d'un modèle ni d'une page** : seule une action
   humaine sur la proposition affichée (R15). Même garde Host/Origin, sans
   cookie, que C-009a (R14).
8. **Reçus** : on garde le principe actuel. `FOUND` est un enregistrement,
   `NOT_FOUND` laisse l'incertitude, et aucun des deux n'autorise un renvoi.

## 3. Deux façons d'authentifier l'opérateur pour la bêta

| | A. Session opérateur locale | B. Appairage persistant de l'appareil |
| --- | --- | --- |
| Principe | à chaque session, un secret d'écriture **court** est généré **sur le serveur** (CLI), affiché là, saisi sur le PC, gardé en mémoire de la page ; expiration (par ex. 30 min) | une fois, le PC génère une clé, le serveur l'enregistre après confirmation sur le serveur ; chaque commande est signée |
| Ce qu'il faut sur le serveur | une commande `session-open --scope decide\|cancel --ttl` ; table de sessions | table d'appareils, enregistrement, révocation, vérification de signature |
| Révocation | expiration ou `session-close` | `device-revoke` |
| Perte du PC | la session expire seule | révoquer l'appareil explicitement |
| Identité dans le reçu | identifiant de session, et l'opérateur qui l'a ouverte sur le serveur | identifiant d'appareil |
| Complexité | faible ; aucun stockage durable côté PC | plus élevée ; clé stockée sur le PC (où, protégée comment ?) |
| Adapté à | une bêta à un opérateur, présent sur le serveur | un usage quotidien, plusieurs appareils |

**Recommandation pour la bêta : A**, portée `cancel` d'abord, puis `decide`.
L'ouverture d'une session demande un geste **sur le serveur** : le secret ne
voyage que par le tunnel et par l'opérateur. B pourra venir avec
l'application Windows.

## 4. Test discriminant proposé

Le corpus `scenarios.json` sert de **liste d'acceptation**. Chaque scénario
précise l'état de départ, l'action, le résultat attendu et la raison. Le plus
discriminant est **R08** : un client qui crée une nouvelle clé après une
réponse perdue échoue, même si le serveur est parfait. Puis **R01** et
**R02** : un jeton de lecture ou de mauvaise portée ne doit produire **aucune**
écriture, vérifiée sur les octets de la base.

Pour un futur banc :

- vrai serveur et vrais processus ;
- réponse coupée **après** le commit (comme les tests C-008b) ;
- base comparée octet par octet pour chaque refus ;
- même `command_key` envoyée deux fois en parallèle.

## 5. Décisions qui reviennent à toytoy (non reçues)

| ID | Question |
| --- | --- |
| T1 | À distance, autoriser seulement l'**annulation** pour la bêta, ou aussi les **décisions** (approuver une action simulée) ? |
| T2 | Session courte ouverte sur le serveur (A) ou appairage du PC (B) ? |
| T3 | Qui peut ouvrir une session : un seul opérateur (toytoy), ou plusieurs comptes ? |
| T4 | Durée maximale d'une session d'écriture ? |
| T5 | Une approbation doit-elle demander une confirmation supplémentaire sur le serveur (deux gestes), ou le PC suffit-il ? |

## 6. Détails d'implémentation (Codex, sans décision utilisateur)

- Routes séparées : `POST /v1/commands/decision` et `POST /v1/commands/cancel`,
  avec les mêmes corps que C-008b et C-008c, plus l'en-tête de session.
  Aucune route `run`.
- Portée vérifiée **avant** la lecture du corps. Réponses 401, 403 ou 409 sans
  contenu privé, comme C-009a.
- Génération de service (`store_generation`) incrémentée à la restauration et
  à la préparation de revue, présente dans la commande et dans le reçu (R12).
- Client : la clé est conservée **avant** l'envoi, en mémoire de la page.
  - Si la page est rechargée, il ne reste qu'une **incertitude affichée**.
  - Pour éviter cela, la conserver en `sessionStorage` : la clé n'est pas
    un secret, mais c'est **un choix à confirmer**.
- Limite de débit des commandes par session. Journal d'audit sans le secret.

## 7. Limites

- Aucune de ces protections ne résiste à un opérateur qui modifie directement
  la base ou le serveur.
- Pas d'« exactement une fois » : l'idempotence couvre une réponse perdue, pas
  un renvoi avec une autre clé.
- L'étude ne choisit ni le stockage d'une clé d'appareil sous Windows, ni la
  cryptographie de B.
- Rien n'est testé : il n'existe aucun endpoint d'écriture.

## Décision reçue le 07/10/2026

toytoy : « Autoriser tout . Appairage durable et confirmation unique ».
Retenu :

- T1 : annulation **et** décisions ;
- T2 : appairage durable (option B, et non la recommandation A) ;
- T5 : confirmation unique sur le PC.

T3 et T4 restent ouverts. Rien n'est implémenté ni activé. Voir
[C-D12](../../CADRAGE-DECISIONS-2026-10-05.md).
