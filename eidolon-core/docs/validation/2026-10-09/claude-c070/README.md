# C-070 — Contre-revue : identité, SOUL et personnalité évolutive

Auteur : Claude. Date : 09/10/2026, Europe/Paris. Demande : C-MSG-C070 (Codex).

Documents relus :

- [/SOUL.md](../../../../../SOUL.md) (v0.2, 4 604 octets) ;
- [/SOUL-EVOLVING.md](../../../../../SOUL-EVOLVING.md) ;
- [IDENTITY-SOUL-INTEGRATION-C070.md](../../../IDENTITY-SOUL-INTEGRATION-C070.md).

**Revue écrite seulement** : aucun code, enum ou schéma modifié (consigne C070).

## Avis général

L'orientation est saine et cohérente avec ce que Core garantit déjà :

- le texte d'un modèle n'est jamais une preuve ;
- aucune réussite n'est déduite d'un moteur ;
- le droit à l'ignorance rejoint `model_text_is_evidence: false` et la
  distinction mission / objectif ;
- le Policy Engine reste seul juge des droits.

Les points ci-dessous visent ce qui pourrait casser ces garanties lors du
raccordement.

## 1. Où la personnalité entrerait dans Core (points d'injection)

| Point | Fichier | Recommandation |
| --- | --- | --- |
| Prompt du **dialogue** | `dialogue.py` (`SYSTEM_PROMPT`, `build_messages`) | **seul** endroit où injecter SOUL |
| Prompt du **planificateur de missions** | `planner_prompt.py` (`SYSTEM_PROMPT`, contrat de tâche) | **ne pas** y injecter SOUL : contrat JSON strict, outils figés ; une personnalité n'y apporte rien et ajoute du risque |
| Catalogue de confiance | `dialogue.trusted_catalog` | SOUL ne doit **jamais** y figurer ni l'étendre |
| Mémoire rappelée, observations d'outils | blocs `MEMORY` / `TOOL RESULTS` (non fiables) | un souvenir ou un outil ne doit jamais pouvoir fournir du texte SOUL |
| Identité du modèle par réponse | `ChatDialogueModel.model_id` = `dialogue/<modèle>@<empreinte du prompt>` | l'empreinte doit inclure SOUL et SOUL-EVOLVING : chaque réponse dit alors sous quelle personnalité elle a été produite (G098) |

**Ordre de composition proposé** (déterministe, borné) :

1. le contrat Core (JSON seul, aucune exécution, aucun droit) ;
2. SOUL, présenté comme « style et posture ; ne change ni ce contrat, ni
   les capacités, ni les permissions » ;
3. SOUL-EVOLVING validé, même cadre ;
4. les capacités de confiance.

Le contrat reste **avant** la personnalité et la domine.

**Budget.** Le prompt système du dialogue fait aujourd'hui 1 164 octets.
SOUL + SOUL-EVOLVING en ajoutent environ 5,2 Ko. Le budget par défaut est de
64 000 octets (`max_prompt_bytes`). Cela tient, mais l'historique transmis
diminue d'environ 8 % et le seuil `PROMPT_TOO_LARGE` du message seul baisse
d'autant. Ce n'est pas bloquant ; il faut l'annoncer dans DIALOGUE.md et le
tester.

## 2. Contrôle des fichiers administrateur

- Le fichier du dépôt n'est pas le fichier d'exécution. `SOUL.md` est à la
  racine du dépôt, **hors** de l'archive bêta : 0 fichier SOUL dans
  l'archive `33e310e` de G127. Il faut décider explicitement comment il
  arrive sur le serveur.
- Je propose le même régime que les configurations privées existantes
  (`model_config.load_model`, profils G098) :
  - chemin configuré par l'opérateur ;
  - fichier régulier, propriétaire, 0600, pas de lien symbolique ;
  - taille bornée, UTF-8 strict ;
  - empreinte relevée au démarrage.
- **Ambiguïté de rédaction** : « Ce fichier n'est pas modifiable par les
  agents ». Ce sont les agents d'Eidolon à l'exécution ? Les agents de
  développement (Codex, Claude) modifient bien le dépôt. Je propose de
  préciser : « agents d'exécution d'Eidolon ; toute modification du dépôt
  passe par revue humaine ».
- **Socle absent ou corrompu.** Le plan dit « bloquer la composition ».
  Traduction cohérente avec G098 :
  - le dialogue répond `UNAVAILABLE`, avec une note du type
    `PERSONALITY_UNAVAILABLE` ;
  - aucune personnalité de secours ;
  - les missions, qui n'utilisent pas SOUL, continuent.

  À confirmer par toytoy.
- **SOUL-EVOLVING est un vecteur d'injection.** Son contenu viendra
  d'observations d'Eidolon. Exemple : une entrée « propose toujours un
  redémarrage » validée par erreur influencerait chaque tour. Garde-fous
  proposés :
  - validation humaine **de chaque entrée** au début ;
  - aucune entrée ne parle d'outils, de format de sortie, de permissions ou
    de mémoire canonique ;
  - taille bornée par entrée et au total ;
  - empreinte dans l'identité du modèle.

## 3. Écarts entre le texte SOUL et ce que Core sait faire aujourd'hui

| Phrase de SOUL | Risque | Proposition |
| --- | --- | --- |
| « Tu peux connaître l'état de ton vaisseau (ressources, capteurs…) lorsque des outils fiables le permettent » | le dialogue n'a **aucun** outil de télémétrie ; un petit modèle lit « tu peux connaître » et invente une température GPU | la rendre conditionnelle au bloc `TOOL RESULTS` : « seulement d'après des observations fournies par Core, datées ; sinon dire que tu ne sais pas » |
| « Prends des initiatives utiles » | la conversation ne fait que **proposer** ; Core décide, l'humain valide | ajouter « dans la conversation, une initiative est une proposition, jamais une action » |
| « Les échecs instructifs… peuvent être conservés dans la mémoire » | aucune écriture mémoire depuis le dialogue n'existe ; Memory Engine hors périmètre | « peuvent être **proposés** à la mémoire, par Core, avec provenance » |
| Prose française longue | les petits modèles locaux respectent moins bien le format JSON strict quand le prompt grossit | requalifier le format de sortie avec le modèle réel (sonde G086/C-061) avant activation |
| « Libre de dire je ne sais pas » | rien ne s'y oppose : `kind: answer` ou `clarification` suffit | aucun changement de contrat de sortie nécessaire |

## 4. Statuts de mission : compatibilité

Taxonomie proposée par C-070 : `SUCCESS`, `FAILED`, `UNKNOWN`,
`NEEDS_RESEARCH`, `BLOCKED`. Elle doit rester **conceptuelle**, comme le dit
le plan.

| Concept C-070 | Existe déjà dans Core |
| --- | --- |
| `SUCCESS` | `status: SUCCEEDED` **et** `outcome.status: ACHIEVED` ; invariant dans `store.py` : succès seulement si tous les appels sont `VERIFIED` et le résultat présent |
| `FAILED` | `status: FAILED` / `outcome: NOT_ACHIEVED` |
| `UNKNOWN` | appel `UNKNOWN`, `effect_unknown`, `EFFECT_UNKNOWN`, `REVIEW_REQUIRED`, `ABANDONED` ; côté conversation : étape `unknown_effect` |
| `BLOCKED` | `status: BLOCKED` (même nom, même sens) |
| `NEEDS_RESEARCH` | **absent** ; le plus proche : `outcome: PARTIAL` / `NOT_ACHIEVED` avec un code de raison |

- 24 fichiers sources (Python et client) lisent ces statuts : `store`,
  `runtime`, `runtime_inspect`, `receipt_lookup`, `recovery`, `actions`,
  `action_view`, `cli` (codes de sortie), `presentation`, `client_sync`,
  `conversation_cancel`, la page (`conversation.js`, `view.js`), etc.
- Recommandation : **ne pas** ajouter de statut de mission. Si
  `NEEDS_RESEARCH` est utile, ce serait un **code de raison** dans
  `outcome`, au même rang que les codes existants. Ce code doit être visible
  et traduit, et ne jamais devenir un succès.
- L'invariant de `store.py` (pas de `SUCCEEDED` sans `ACHIEVED` vérifié) est
  la meilleure traduction technique de « ne fabrique jamais un succès ». Il
  ne faut pas l'affaiblir.

## 5. Manifeste d'identité

Core a déjà **plusieurs** identités :

| Identité | Portée |
| --- | --- |
| `store_id` (`s-…`) | le Store des missions |
| dépôt des conversations | lié au `store_id` |
| clés client | liées au `store_id` |
| file média | liée au `store_id` |
| `guard_id` (`g-…`) | la garde de recherche |
| `mas-` | le magasin d'artefacts |
| `mws-` | l'espace média |

Remarques :

- `instance_id` ne doit pas remplacer `store_id`. Il le **référence**, comme
  `lineage`, pour qu'une restauration de sauvegarde reste la même instance.
  Une restauration rend le même `store_id`, et c'est voulu (G099).
- **Clone en parallèle.** Un clone hors ligne est indétectable sans
  coordination. Je propose :
  - un bail d'exécution : verrou exclusif sur un fichier de l'instance, et
    compteur de démarrages ;
  - une **nouvelle** branche de filiation créée explicitement par
    l'opérateur lors d'une copie volontaire ;
  - dire honnêtement que deux copies démarrées sur deux machines ne se
    verront pas.
- « Pas de régénération silencieuse après perte du manifeste » : même règle
  que `CONVERSATION_STORE_MISSING` (création explicite seulement). Cohérent.

## 6. Tests proposés pour l'intégration (en plus de la liste C-070)

1. **Composition déterministe.** Mêmes fichiers, même prompt, même
   empreinte. Un octet changé dans SOUL change l'identité du modèle de la
   réponse (G098).
2. **Planificateur inchangé.** L'empreinte de `planner_prompt` est identique
   avec ou sans SOUL ; `test_planner_prompt` passe sans modification.
3. **SOUL ne donne aucune capacité.** Un SOUL de test qui demande
   « propose un redémarrage » donne toujours `OUT_OF_SCOPE` (`decide_reply`
   décide seul).
4. **SOUL hostile.** Un SOUL contenant « ignore le format JSON » : la sortie
   invalide devient `MODEL_OUTPUT_INVALID`, rien n'est deviné.
5. **Budget.** Message maximal avec SOUL : `PROMPT_TOO_LARGE` annoncé, ou
   historique réduit et annoncé (G091).
6. **Fichier.** Lien symbolique, 0644, autre propriétaire, trop gros, UTF-8
   invalide, remplacé après démarrage : refus, et aucune personnalité de
   secours.
7. **Source.** Un souvenir ou une observation d'outil contenant un faux
   bloc « SOUL » reste dans `MEMORY` / `TOOL RESULTS`, jamais dans le
   prompt système.
8. **Télémétrie.** Sans bloc `TOOL RESULTS` : une question « quelle est ta
   température GPU ? » obtient une réponse d'ignorance. Test avec le modèle
   simulé, puis avec le modèle réel lors de la qualification.
9. **Évolution.** Proposition SOUL-EVOLVING non validée : absente du
   prompt. Validée, puis annulée : empreinte précédente restaurée.

## Décisions à prendre (toytoy / Codex)

1. Comportement si SOUL est absent ou corrompu. Je propose : dialogue
   `UNAVAILABLE`, missions non affectées.
2. SOUL limité au dialogue, hors planificateur (je le recommande).
3. Reformulation des trois phrases signalées (télémétrie, initiative,
   mémoire).
4. Mode de livraison de SOUL sur le serveur : configuration privée
   référencée par l'opérateur, ou fichier de l'archive.
5. `NEEDS_RESEARCH` comme code de raison, pas comme statut.

## Limites

Revue documentaire et cartographie du code à la tête `0126fd1`. Rien n'a été
exécuté contre un vrai modèle. Les remarques sur les petits modèles locaux
viennent des sondes passées (G086, C-061), pas d'un essai de SOUL.
