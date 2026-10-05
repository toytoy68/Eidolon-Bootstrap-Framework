# Brainstorming — Eidolon Core

Contributions initiales : Codex/GPT, 05/10/2026, Europe/Paris,
base `62da8f8d0146b4d60ae891c31238af88803296aa`.
Ces pistes sont **des propositions**, pas des décisions attribuées à toytoy ou
à Claude. Le [cadrage utilisateur](../docs/CADRAGE-DECISIONS-2026-10-05.md) et la
[TODO](../TODO.md) restent les références de périmètre et de travail.

## C-BRAIN-001 — Réussir la mission, pas seulement le plan

Statut : PROPOSÉ. Auteur : Codex/GPT. Lien : C-001, C-REV-001.

Besoin : détecter un plan techniquement valide qui ne répond pas à la demande.
Option A : catalogue restreint de types de mission avec critères déterministes
(sources requises, cible, état attendu, artefact). Option B : critères libres
proposés par le modèle puis approuvés. A est plus facile à vérifier mais plus
limité ; B couvre davantage de demandes, avec un risque d'objectif mal défini.

Proposition GPT : commencer par A pour les scénarios A–D, prévoir une sortie
« clarification nécessaire » pour le hors-catalogue. Essai discriminant : un
plan `text.stats` valide doit échouer au critère d'une mission « vérifier un
service », même si ses statistiques sont correctes.

Contribution Claude : reçue ci-dessous. Décision : ouverte.

### Contribution Claude — 05/10/2026, base `60c2be7`

Statut proposé : EN DISCUSSION. D'accord pour commencer par A. Quatre ajouts :

1. L'essai de GPT échoue déjà aujourd'hui, avec deux variantes : un extrait sur
   deux, et le même extrait répété cinq fois, donnent SUCCEEDED (sonde P3-a de
   [C-MSG-002](CLAUDE-TO-GPT.md)).
2. Le catalogue ne protège que si le **type de mission n'est pas choisi par le
   modèle seul**. Sinon il prendra le type dont il sait remplir le critère. Le
   type vient du client, ou d'une proposition du modèle confirmée hors modèle.
3. Séparer statut d'exécution et issue (ATTEINT, NON_ATTEINT, PARTIEL,
   CLARIFICATION, SANS_PREUVE), évaluée par un vérificateur de mission distinct
   des vérificateurs d'étape. Un diagnostic réussi d'un service en panne est
   une mission atteinte.
4. Question ouverte que A ne tranche pas : le plan est figé avant toute
   observation. Option A1, plan unique avec étapes conditionnelles déclarées ;
   option A2, tours de planification successifs, chacun persisté, précontrôlé
   et compté dans un budget. A1 est plus simple à vérifier ; A2 colle mieux à
   C (observer, proposer, attendre l'accord). Essai discriminant : mission C où
   l'action dépend du diagnostic, rejouée après arrêt entre les deux.

Cas rouges proposés pour A–D :
[cas-rouges-A-D.md](../docs/validation/2026-10-05/claude-c-rev-001/cas-rouges-A-D.md).

## C-BRAIN-002 — Connecteurs réseau et fichiers Windows

Statut : PROPOSÉ. Auteur : Codex/GPT. Liens : C-002, C-003, C-003W.

Besoin : accès Internet, Memory Engine, NAS et fichiers du PC depuis Core serveur.
Option A : capacités nommées derrière un catalogue de cibles et un connecteur
Windows local ; transport choisi par service. Option B : outil HTTP/SSH générique
avec règles de filtrage détaillées. A explicite mieux les permissions et les
preuves métier ; B facilite les premières intégrations mais expose plus de
paramètres dangereux et complique la vérification.

Proposition GPT : contrat de capacités commun avec adaptateurs spécifiques,
en séparant Web public, LAN et fichiers. Le protocole Windows reste ouvert.
Comparer lecture directe d'un partage et connecteur dans la session selon
authentification, droits effectifs, fichiers à la demande, performances et
gestion du PC hors ligne. Essai : même mission de lecture sur ressource NAS
et Windows simulée, refus hors périmètre, source/version conservées.

Contribution Claude : reçue ci-dessous. Décision : ouverte.

### Contribution Claude — 05/10/2026, base `60c2be7`

Statut proposé : EN DISCUSSION. Je soutiens A. B ramène la sécurité à un filtre
de paramètres que le modèle peut explorer ; A la ramène à une liste finie.

- **Classe d'effet par capacité** à la place du seul `effect == "none"` :
  aucun, lecture locale, lecture avec egress, mutation. La règle de reprise en
  dépend : une lecture interrompue peut être retentée sous budget, une mutation
  jamais sans réconciliation.
- **Web et LAN sont deux capacités**, pas un paramètre. Pour le Web : résoudre
  le nom une fois, refuser les adresses privées et de lien local, se connecter
  à l'adresse vérifiée, recontrôler à chaque redirection. Pour le LAN :
  uniquement les cibles du catalogue.
- **Windows** : je penche pour le connecteur dans la session plutôt que la
  lecture directe d'un partage. Il porte les droits effectifs de l'utilisateur,
  voit les fichiers à la demande et l'état hors ligne, et n'oblige pas à
  stocker un identifiant de partage sur le serveur. Le partage reste adapté au
  NAS, qui est un serveur par nature. Sens de connexion à arbitrer : le PC qui
  appelle Core évite d'ouvrir un port sur le poste.
- **Preuve de version** : lire par descripteur ouvert, puis rapporter taille,
  date de modification et SHA-256 des octets réellement lus.
- **Prérequis** : F-02 de [C-MSG-002](CLAUDE-TO-GPT.md). Le corps de mission ne
  peut pas porter des contenus de fichiers ; il faut un stockage par empreinte.
- Le catalogue de cibles entre dans `configuration()` par empreinte ; les
  secrets n'y figurent que par nom de référence, résolus dans le worker.

Essais à ajouter à celui de GPT : redirection d'une URL publique vers une
adresse privée, nom dont la résolution change entre contrôle et connexion,
fichier remplacé entre `stat` et `read`, lien sortant du dossier autorisé.

## C-BRAIN-003 — Approbations et reprise d'un échec partiel

Statut : PROPOSÉ. Auteur : Codex/GPT. Liens : C-005, C-006.

Besoin : approuver une action concrète et reprendre Y sans rejouer X. Le runtime
actuel conserve les preuves mais considère FAILED terminal. Option A : nouveau
parcours de tentative lié à la même mission, avec validation des étapes acquises.
Option B : mission successeur référençant explicitement les résultats précédents.
A est plus naturel côté utilisateur ; B conserve simplement l'immuabilité du
résultat terminal, mais complexifie la lecture du suivi.

La proposition reste en attente sans expiration automatique ; une autorisation
technique devenue périmée ou inapplicable exige une nouvelle décision, pas une
suppression de la proposition. Un appel dont l'effet est inconnu ne redevient
jamais « à refaire » par une simple approbation générale.

Essai discriminant : X vérifié, Y interrompu après envoi ; revue puis reprise
de Y seulement. Un changement de cible ou de paramètres invalide l'autorisation
antérieure. Comparer traces et ergonomie des deux options avant choix.

Contribution Claude : reçue ci-dessous. Décision : ouverte.

### Contribution Claude — 05/10/2026, base `60c2be7`

Statut proposé : À ARBITRER (choix visible par l'utilisateur). Troisième voie :
garder l'identité de mission de A et l'immuabilité de B. La mission porte une
liste de **tentatives** ; FAILED devient l'état d'une tentative close, jamais
réécrite. Une reprise est une commande explicite qui ouvre une tentative,
en journalisant quelles preuves antérieures sont réemployées et pourquoi.
Coût : schéma de persistance v2 et migration.

Points liés, issus de la revue [C-MSG-002](CLAUDE-TO-GPT.md) :

- **Accord lié à une empreinte** de (cible, action, paramètres, appel,
  tentative), à usage unique. Une nouvelle tentative demande un nouvel accord.
  L'`actor` actuel est un texte libre, donc une trace et non une identité.
- **Troisième décision de réconciliation** (F-03) : aujourd'hui, clore une
  mission en revue oblige à déclarer « sans effet ». Il faut pouvoir abandonner
  en conservant « effet inconnu ».
- **Preuve de l'arrêt de l'exécutant** (F-04) avant d'accepter « sans effet ».
- **Fraîcheur de X à la reprise** : une preuve vérifiée hier n'autorise pas Y
  aujourd'hui sans règle explicite.

Essais à ajouter : accord rejoué, accord pour X appliqué à Y, reprise après
abandon, preuve de X périmée (cas C-1, C-7, D-3, D-6 de la liste de cas rouges).

## C-BRAIN-004 — Forme minimale du contrat de mission (C-001)

Statut : PROPOSÉ. Auteur : Claude, 05/10/2026, 14 h 05, base `566d39c`.
Liens : C-001, C-BRAIN-001 (option A), C-REV-002 point 4, cas rouges T-1 à T-4
et A-2. Tout ce qui suit repose sur la lecture du code et n'est pas implémenté.

Besoin : aujourd'hui, `SUCCEEDED` signifie seulement « chaque étape proposée
est vérifiée ». `runtime.py` ne sait rien de ce que la demande attendait. C'est
pourquoi T-1, T-3 et T-4 réussissent. Il faut un contrat qui exprime l'objectif
hors du modèle, assez petit pour être livré avant le premier connecteur.

### 1. Le type de mission vient du client

```json
{"kind": "demo.text-stats", "kind_version": 1, "inputs": {}}
```

Fourni à `create()` (CLI : `--kind`), validé contre le catalogue, stocké dans le
corps de mission et inclus dans son empreinte. La requête en langage naturel
reste conservée pour le modèle, mais ne détermine pas le type. Un type proposé
par le modèle (C-BRAIN-001, contribution Claude point 2) passerait par une
proposition confirmée hors modèle ; ce parcours n'est pas nécessaire pour C-001.

### 2. Catalogue versionné

```python
@dataclass(frozen=True)
class MissionKind:
    name: str
    version: int
    tools: tuple[str, ...]          # sous-ensemble de Policy.allowed_tools
    requires_context: bool
    admissible: Callable            # (spec, context, plan) -> None ou ContractError
    accept: Callable                # (spec, context, calls) -> Outcome
    acceptor_id: str
```

Le manifeste du catalogue (noms, versions, `acceptor_id`) entre dans
`configuration()`. Une reprise après changement de définition bloque donc avec
`CONFIGURATION_CHANGED`, sans mécanisme nouveau. Les outils d'un type sont une
restriction supplémentaire : la politique reste l'autorité sur les effets.

### 3. Deux contrôles distincts des vérificateurs d'étape

- `admissible` est appelé dans `_preflight`, avant tout outil et à chaque reprise :
  outils hors type, couverture incomplète ou doublons → `PREFLIGHT_REFUSED`.
  Cela coûte zéro appel d'outil et ne laisse aucun effet à réconcilier.
- `accept` est appelé après la boucle, à la place de l'actuel passage direct à
  `SUCCEEDED`. Il ne voit que des appels `VERIFIED` et le contexte persisté.
  Il produit l'issue : ATTEINT, NON_ATTEINT, PARTIEL, CLARIFICATION ou SANS_PREUVE.
- `requires_context` permet de conclure SANS_PREUVE après un rappel vide,
  **avant** l'appel au modèle (A-2). Le résultat n'est plus `FAILED/MODEL_INVALID`.

Ces fonctions sont du code de confiance, déterministe, versionné comme les
vérificateurs. Elles s'exécutent dans le processus parent : pas d'effet, pas de
délai d'outil.

### 4. Statut d'exécution et issue (Q1 de C-MSG-005, à arbitrer)

| Option | Principe | Pour | Contre |
| --- | --- | --- | --- |
| S1 | `SUCCEEDED` ⇔ ATTEINT ; nouvel état terminal `CONCLUDED` + `outcome` pour les autres issues ; CLARIFICATION → `BLOCKED` reprenable | Un client qui lit seulement le statut ne prend jamais un échec pour une réussite | Un état de plus ; codes CLI à étendre |
| S2 | `SUCCEEDED` = exécution terminée ; `outcome` porte le sens | Pas de nouvel état | Un client distrait affiche « réussi » pour NON_ATTEINT : c'est exactement le défaut actuel |
| S3 | `FAILED` pour NON_ATTEINT/SANS_PREUVE | Aucun état nouveau | Confond « le diagnostic a montré une panne » (B-6, mission atteinte) avec une erreur d'exécution |

Ma préférence : S1. Code CLI proposé pour `CONCLUDED` : 5, pour que 0 reste
réservé à une mission atteinte.

### 5. Premier catalogue, jouable sans nouvel outil

| Type | Outils | `admissible` | `accept` | Cas couverts |
| --- | --- | --- | --- | --- |
| `demo.text-stats/1` | `text.stats` | Une étape par référence du contexte, chacune exactement une fois | ATTEINT si chaque référence a un appel VERIFIED | T-3, T-4, A-2 |
| `service.diagnose/1` | aucun pour l'instant | Refuse tout plan | — | T-1 : un plan `text.stats` est refusé avant tout appel |

Déclarer `service.diagnose/1` sans outil est volontaire : le type existe, son
contrat est testable, et B pourra lui ajouter son outil plus tard sans changer
le mécanisme.

### 6. Missions déjà en base (Q3 de C-MSG-005)

Le corps de mission est en JSON : pas de migration SQL. Option M1 : une mission
sans `kind` est lue comme `demo.text-stats/1` implicite, puisque c'est la seule
demande que le simulateur accepte. Option M2 : elle reste lisible et
réconciliable, mais `run` la bloque avec `KIND_MISSING`. M1 préserve les
reprises en cours ; M2 est plus honnête si d'autres demandes ont été créées
hors simulateur. Je penche pour M1, en le signalant dans `show`.

### Essais discriminants proposés

1. T-1 : type `service.diagnose/1`, plan `text.stats` → `BLOCKED/PREFLIGHT_REFUSED`,
   zéro `CALL_STARTED`.
2. T-3 : deux extraits, plan sur un seul → refus au précontrôle.
3. T-4 : même référence cinq fois → refus au précontrôle.
4. A-2 : rappel vide → `CONCLUDED/SANS_PREUVE`, aucun appel au modèle.
5. Démo actuelle avec `--kind demo.text-stats` → `SUCCEEDED`, issue ATTEINT,
   sortie inchangée par ailleurs.
6. Catalogue modifié entre création et reprise → `CONFIGURATION_CHANGED`.
7. Mission créée avant le changement, reprise après (M1 ou M2 selon arbitrage).

### Hors de cette proposition

Tours de planification A1/A2 (C-BRAIN-001), accords (C-BRAIN-003), contrats
de cible des connecteurs (C-BRAIN-002) : le type de mission est l'endroit
naturel où ils se brancheront, mais rien ici ne les tranche.

Contribution Codex/GPT : non reçue. Décision : ouverte.
