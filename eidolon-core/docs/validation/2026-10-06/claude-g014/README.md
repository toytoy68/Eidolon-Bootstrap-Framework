# Contre-revue C-TASK-G014 — reçus de décisions locales (C-008b)

Auteur : Claude, 06/10/2026. Fiche [C-TASK-G014](../../../../collaboration/tasks/C-TASK-G014.md).
Cible figée : `176c1d26bec04d3b002f36cc97e78c85ffc23ba2` (commit introduisant C-MSG-G024),
extraite par `git archive` dans une copie isolée. Empreintes vérifiées, identiques à
[source-hashes.json](../codex-command-receipts/source-hashes.json) (6/6) :

| Fichier | SHA-256 |
| --- | --- |
| `commands.py` | `1646fd4a…7bd5` |
| `store.py` | `28c7515b…147d` |
| `actions.py` | `7c75dad9…5995` |
| `cli.py` | `563a8ef3…e3fd` |
| `tests/test_commands.py` | `849ae21f…2dfd` |
| `examples/command_receipt_demo.py` | `ba117ec5…a7b3` |

`commands.py` et `store.py` ont changé depuis (C-008c) : ces résultats valent
pour `176c1d2` seulement. Ni `src/`, ni `tests/` Python, ni fixtures modifiés.

```sh
cd eidolon-core
# FROZEN = git archive 176c1d2 eidolon-core/src | tar -x -C FROZEN
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=$FROZEN/eidolon-core/src python docs/validation/2026-10-06/claude-g014/probes_g014.py
```

Python 3.11.15, Linux. Chaque sonde crée sa propre base temporaire (redémarrage
**simulé** de `nas`). Les pannes sont injectées dans ces bases (déclencheurs
SQLite) ou par les crochets de test documentés (`runtime.checkpoint`,
`runtime._prepare_decision` enveloppé dans le processus de sonde).
[Sortie](probes_g014-output.txt) · [codes de sortie CLI](cli-exit-codes.txt).

Classement : **DÉFAUT** · **LIMITE** (documentée) · **PROPOSITION** · **CONFORME**.

## Résultat : aucun défaut confirmé

Je n'ai trouvé ni reçu faux, ni décision enregistrée sans reçu par
`command-submit`, ni décision dupliquée, ni contournement des vérifications.
Ce n'est pas une validation générale : voir les limites en fin de rapport.

### 1. Atomicité (R1, R2)

- **Pannes SQL injectées** (R1) : un déclencheur `RAISE(ABORT)` avant
  l'insertion du reçu, avant l'insertion de l'événement, puis après la mise à
  jour de la mission. Dans les trois cas : révision et nombre d'événements
  inchangés, `NOT_FOUND`. Une fois la panne retirée, la même commande donne
  une seule décision. Le cas « avant le reçu » est le plus probant : mission
  et événement étaient déjà écrits dans la transaction, et ils sont annulés.
- **Vrais processus concurrents** (R2), lancés au même instant. Même clé sur
  deux missions : un enregistrement, un `COMMAND_KEY_REUSED` ; la mission
  perdante garde sa révision et n'a aucune décision. Même commande dans
  4 processus : 1 enregistrement, 3 `Busy`, une seule décision.

### 2. Rejeu, clé réutilisée, annulation, requête obsolète (R3–R6)

- Rejeu après exécution (`SUCCEEDED`, accord `USED`) : reçu identique, aucun
  événement ni redémarrage de plus.
- Même clé avec une autre décision ou une autre raison : `COMMAND_KEY_REUSED`.
  Autre `client_id` ou nouvelle clé sur l'ancienne révision : `STALE_REVISION`.
  Une seule décision au total.
- Annulation avant la commande : refus, `NOT_FOUND`. Annulation **entre la
  préparation et le commit** (course provoquée) :
  `CANCEL_REQUESTED: decision cannot follow cancellation`, aucun reçu, drapeau
  d'annulation conservé. Empreinte de proposition fausse : refus.
- Verrou de mission tenu par un autre processus, comme pendant `run` :
  `Busy` immédiat (pas d'attente) ; la consultation du reçu répond sans attendre.

### 3. Ce qu'un client pourrait conclure à tort (R7, R8)

- **Réponse perdue après commit** : `FOUND`. Renvoi avec la même clé : le
  même reçu. Nouvelle clé : `STALE_REVISION`. Une seule décision.
- **NOT_FOUND pendant une émission en cours** : vrai `NOT_FOUND` ; un renvoi
  avec la même clé donne `Busy`, puis la première émission s'enregistre.
  Une seule décision. Même un client qui lit mal `NOT_FOUND` ne peut donc pas
  dupliquer une décision : la clé ou la révision l'en empêchent.
- **Reçu APPROVED après une révocation** : le reçu d'accord reste
  `approval_status_at_recording=APPROVED` (historique) ; la capture courante
  dit `REVOKED`, et `run` ne lance rien (`APPROVAL_REVOKED`, 0 redémarrage).
  Le reçu ne contient aucun champ d'état courant. Un client qui afficherait ce
  reçu comme l'état actuel se tromperait : c'est une règle à tenir côté client
  (déjà tenue par le prototype G013).

### 4. JSON/JS, confidentialité (R10)

Refusés : `NaN`, `1.0`, `true`, 2^53−1 (la borne documentée est 2^53−2),
substitut isolé, clé dupliquée, champ en plus, BOM, octets non UTF-8,
imbrication de profondeur 20 000, 32 769 octets. Acceptés : 2^53−2, et `-0`
lu comme `0` (sans danger). Le reçu et la consultation ne contiennent ni
l'acteur ni la raison ; les entiers restent exacts en JS. Une consultation
avec un autre `store_id` donne `STORE_CHANGED`, pas `FOUND`.

## Limites documentées, confirmées

- **Restauration d'une copie antérieure** (R9) : même `store_id`, `NOT_FOUND`,
  et la même commande s'enregistre une **seconde fois** (nouvelle première
  fois dans l'histoire restaurée). **Clone** : même `store_id`, reçu trouvé dans
  le clone. Conforme à CLIENT-SYNC.md et COMMAND-RECEIPTS.md ; à traiter avant
  toute restauration en exploitation (génération de service).
- **Codes de sortie CLI** : `NOT_FOUND`, `STORE_CHANGED` et identifiant invalide
  donnent tous le code 2. La distinction se fait par le canal : JSON
  `NOT_FOUND` sur la sortie standard, erreur JSON sur la sortie d'erreur.
- `client_id` et `actor` sont des libellés : qui connaît un couple
  client/clé peut lire le reçu en local. Documenté, hors périmètre réseau.

## Propositions (non demandées comme correctifs)

1. **`authorizes_resend=false`** pourrait être lu comme « ne jamais renvoyer,
   même avec la même clé ». Or le renvoi avec la même clé et le même contenu
   est sûr : il rend le reçu historique (R7). Préciser dans le contrat :
   « n'autorise aucune nouvelle clé ni nouvelle décision ; la même requête peut
   être renvoyée telle quelle ».
2. **Message de refus après annulation** : une annulation antérieure donne le
   message générique `mission is not awaiting an action decision`, alors que la
   course donne `CANCEL_REQUESTED`. Un code stable `CANCEL_REQUESTED` dans les
   deux cas aiderait l'interface à expliquer le refus.
3. **Code de sortie distinct pour `NOT_FOUND`** (par exemple 3), pour qu'un
   script ne confonde pas « reçu introuvable » et « erreur ».
4. **Correspondance avec le prototype** (G013), à valider :
   `RECORDED` / `FOUND` → `acknowledged` ; `NOT_FOUND` → `not-found` (reste
   incertain) ; `Busy` → reste `sending`, à renvoyer plus tard **avec la même
   clé** ; `STALE_REVISION`, `COMMAND_KEY_REUSED` ou `CANCEL_REQUESTED` →
   `refused`, avec nouvelle capture avant toute décision.

## Limites de cette revue

Base temporaire SQLite locale, Python 3.11 (Codex : 3.12) ; pas de coupure
d'alimentation réelle ni de disque plein ; processus tués non refaits (déjà
couverts par les tests de Codex). Concurrence éprouvée à 2 et 4 processus,
pas en charge. C-008c (reçus d'annulation) hors de cette cible.
