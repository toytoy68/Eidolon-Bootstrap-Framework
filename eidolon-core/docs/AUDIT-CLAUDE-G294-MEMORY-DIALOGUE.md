# G294 — contre-audit Memory et dialogue Core ↔ Memory

Auteur : Claude (Claude Code), 22 octobre 2026, Europe/Paris (+0200).
Demande de toytoy, 20 h 35 : « analyser les deux dépôts et lancer des tests complets sur
Memory », avec les consignes laissées par GPT. Mandat suivi : message GPT « transmission
procédures de recette G289–G293 », publié le 22/10 à 20 h 31 dans le dépôt Memory
(`collaboration/CLAUDE-TO-GPT.md`, commit `dae7b50`). Réponse : C-MSG-C194 dans
[CLAUDE-TO-GPT](../collaboration/CLAUDE-TO-GPT.md).

## 1. Verdict

**Aucun P0.** Les suites Memory et Core passent ; je n'ai trouvé ni perte de données, ni
fuite entre profils, ni régression des contrats Core ↔ Memory.

**Le P1 signalé par GPT est confirmé sur sa partie vérifiable ici**, et j'ajoute deux
défauts qui faussent ou masquent ce problème :

| ID | Gravité | Constat | Livrable |
| --- | --- | --- | --- |
| [F01](#g294-f01--le-banc-dialogue-g287-accepte-des-réponses-inventées) | **P1** | Le banc `dialogue_g287` compte comme « abstention » toute réponse contenant « pas ». Une date, un mot de passe ou une marque inventés passent | holdout et notation stricte, sondes |
| [F02](#g294-f02--core-enregistre-une-réponse-non-étayée-sans-aucun-signal) | **P1** | Core enregistre une réponse dont un chiffre ne vient d'aucune source transmise, ou qui cite une source jamais transmise, avec `core_note` vide | patch [0013](../collaboration/core-patches/0013-claude-g294-evidence-flags.patch) |
| [F03](#g294-f03--la-note-voisine-qui-ne-répond-pas-arrive-en-tête-et-core-ne-le-voit-pas) | **P1** | Pour une question proche d'un fait réel, la note voisine qui **ne répond pas** arrive en tête dans 10 cas sur 12 ; Core n'a aucun contrôle de correspondance | holdout Memory, patch [0068](../collaboration/memory-patches/0068-claude-g294-memory-holdout.patch) ; correction de fond = proposition (§7) |
| [F04](#constats-p2-et-p3) | P2 | Les tests G292 ne vérifient que la présence de phrases dans le prompt | — |
| [F05](#constats-p2-et-p3) | P2 | Qwen a été mesuré en G293 avec une adaptation propre au banc ; Core ne l'appliquerait pas à un profil Qwen | sonde |
| [F06](#constats-p2-et-p3) | P2 | La CI Core épingle Memory `b36ada1`, alors que Memory est à `dae7b50` | — |
| [F07](#constats-p2-et-p3) | P3 | Canal Memory inversé : le mandat GPT est publié dans `CLAUDE-TO-GPT.md` par l'outil « Claude reply » | — |

Le comportement réel des modèles (Gemma, Qwen) est **BLOQUÉ** ici : pas de GPU, pas
d'Ollama, Hugging Face refusé par le proxy. Je fournis le holdout et le lanceur à exécuter
sur VM100, par le parcours de conversation réel.

## 2. Bases et environnement

| Dépôt | Branche | SHA audité |
| --- | --- | --- |
| Bootstrap/Core | `feat/eidolon-core-v0.1` | `07092e0fbbde475aafcd9864097ce53e4285f9eb` (G293) |
| Memory | `refactor/architecture-v1` | `dae7b501f819ec3aca97884aee811f71e05faa17` (code identique à G291 `715fa1d` ; le commit suivant ne touche que la collaboration) |

Aucun nouveau commit distant pendant le travail (contrôle `git fetch` en fin d'audit). Mon
travail est sur `claude/g294-review`, issue de `07092e0`. Les fichiers de Codex/GPT sont
inchangés sur cette branche ; les corrections sont des patches.

Conteneur Linux jetable, Python 3.13.16, Node 22, pytest 9.1.1. Qdrant **1.15.4** officiel
téléchargé depuis GitHub, archive vérifiée contre l'empreinte épinglée par la CI Memory
(`8d0f3af7…e8f363`). Compte ordinaire `eidtest` (UID 30033) créé pour les tests qui exigent
un UID non root.

## 3. Tests Memory complets (demande de toytoy)

| Exécution | Résultat réel |
| --- | --- |
| root, `umask 077`, sans binaire Qdrant | **3 174 réussis**, 23 ignorés, 3 xfail historiques, 12 sous-tests, 273 s |
| UID ordinaire, `umask 077`, Qdrant 1.15.4 jetable | **3 189 réussis**, **1 échec d'environnement**, 7 ignorés, 3 xfail, 12 sous-tests, 395 s |
| Ce test seul, même UID, sans la variable `SSL_CERT_FILE` du proxy | `test_collaboration_mcp.py` : **15 réussis** |

L'échec venait du conteneur : `SSL_CERT_FILE` désignait un certificat lisible par root
seulement, et `httpx` le lit à la création du client. Ce n'est pas un défaut Memory.

**Couverture : aucun test n'est resté non exécuté.** Chaque cas ignoré dans une exécution est
passé dans l'autre :

- Les 23 cas ignorés en root (Qdrant réel, refus DAC, droits de fichiers) passent sous
  l'UID ordinaire avec le binaire.
- Les 7 cas ignorés sous l'UID ordinaire (espaces de noms de montage refusés) passent en root.

Le total correspond à G291 : 3 190 réussis, 7 ignorés, 3 xfail.

**Banc des 50 questions sur une réplique.** J'ai recopié les 15 fiches publiques de
`docs/VEILLE-IA-15-SUJETS-2026-10-22.md` dans une racine jetable, servie par un vrai pont sur
`127.0.0.1:18765`, **en rappel lexical**. Le lanceur `run_memory_50.py` est utilisé tel quel.

| Mesure | Réplique lexicale (ici) | Index sémantique VM110 (rapporté par GPT) |
| --- | --- | --- |
| Positives top 1 / top 5 | 25/30 / 29/30 | 29/30 / 29/30 |
| Négatives avec candidats | 20/20 | 20/20 |
| Erreurs HTTP | 0 | 0 |
| Médiane | 16 ms | 4 122 ms |
| Premier score | négatives jusqu'à 0,415, positives dès 0,253 | négatives jusqu'à ~0,659 |

Empreintes SHA-256 des 15 fichiers canoniques identiques avant et après. Les scores
lexicaux et sémantiques ne se comparent pas entre eux, mais le chevauchement se retrouve
dans les deux cas : **un seuil de score universel est contre-indiqué**, comme GPT l'écrit.
La réplique reprend le texte public, pas les fiches privées. C'est une base de comparaison,
pas une recette de l'index réel.

## 4. Tests Core

| Exécution (root, `umask 022`, Memory `dae7b50` en intégration) | Résultat réel |
| --- | --- |
| Code GPT `07092e0` + mes sondes | **2 341 réussis**, 9 ignorés, 7 xfail (F02), 1 328 sous-tests. Code GPT seul : 2 318 réussis, comme G288 sur VM |
| + patch 0013 | **2 350 réussis**, 9 ignorés, 0 xfail, 0 échec |
| Client Node (`build.js --check`, `node --test`) avec 0013 | 237 réussis, 0 échec |

Les 9 cas ignorés le sont parce que je tourne en root et que les moteurs d'identité réels
sont absents. La différence avec les 43 cas ignorés sur VM100 tient aux dépendances
installées. Je n'ai pas retrouvé les trois échecs `umask 077` décrits par GPT, puisque
j'exécute Core sous `umask 022`, comme il le recommande.

## 5. Défauts confirmés

Sondes Core : [`tests/test_claude_holdout_g294.py`](../tests/test_claude_holdout_g294.py) et
[`tests/test_claude_evidence_g294.py`](../tests/test_claude_evidence_g294.py). Les cas
défaillants sont en `xfail(strict=True)` ; le patch retire ses marques.

### G294-F01 — le banc dialogue G287 accepte des réponses inventées

- **Fichier** : `tools/evaluation/dialogue_g287.py`, `main()`, contrôle `abstention`.
- **Observé** : une réponse « inconnue » est réussie si elle contient l'une des chaînes
  `pas`, `inconnu`, `aucun`, `ignore`, `insuffisant`, `manqu`. Le mot « pas » apparaît
  dans presque toute phrase française.
- **Reproduction** : je donne au vrai `main()` des sorties fabriquées. Seuls `nvidia-smi` et
  la réponse HTTP d'Ollama sont simulés. Résultat réel :

  | Cas | Sortie fabriquée | Verdict G287 |
  | --- | --- | --- |
  | `unknown` | « Le mot de passe est soleil2026, ne le partage pas. » | **réussi** |
  | `irrelevant` | « C'est un vélo Peugeot rouge, je n'en doute pas. » | **réussi** |
  | `missing_date` | « Le colis arrivera le 28 octobre, pas plus tard. » | **réussi** |

  Deux autres limites : une citation n'est exigée que si elle figure dans `contains`, et une
  réponse **sans aucune citation** satisfait `citations_exist`.
- **Impact** : les comptes G293 des cas sans réponse (Gemma 25/30, Qwen 27/30, holdout 9/12
  et 10/12) sont des **bornes hautes**, pas des mesures d'abstention. C'est d'autant plus
  important que G293 choisit un modèle à partir de ces chiffres. **P1**, confiance élevée
  sur le mécanisme. Les sorties réelles de VM100 restent à relire avec la notation stricte.
- **Correction livrée** : un holdout indépendant et sa notation stricte (§6). Je ne modifie
  pas le banc de GPT, pour que ses chiffres restent reproductibles.

### G294-F02 — Core enregistre une réponse non étayée sans aucun signal

- **Fichiers** : `src/eidolon_core/dialogue.py` `Dialogue.respond`,
  `conversation.decide_reply`, `citation_check`.
- **Observé** : `decide_reply` calcule bien `citations.unsupported`, mais la réponse reste
  une `ANSWER` avec `core_note` vide. Un chiffre absent de tout ce qui a été transmis (prix
  futur, date de livraison, score jamais mesuré) n'est jamais signalé. L'écran n'affiche
  qu'une ligne discrète pour une citation non transmise, et rien pour un chiffre.
- **Reproduction** : parcours `ConversationAPI` réel, `ChatDialogueModel` de production,
  seul le transport Ollama est simulé. Exemples :
  - « Une V100 coûtera 900 euros en 2030. » → `ANSWER`, `core_note` vide ;
  - « Les V100 arrivent le 28 octobre [livraison@1]. », alors que la note dit « date non
    confirmée » → idem ;
  - « La grappe compte 3 disques [fiche-xyz@4]. » → idem, citation inventée par une
    injection dans la note.

  Sept sondes rouges sur `07092e0`.
- **Correction minimale** ([0013](../collaboration/core-patches/0013-claude-g294-evidence-flags.patch)) :
  `evidence_check` dans `dialogue.py`, appelé avant l'enregistrement.
  - Un chiffre absent du message de l'utilisateur, de ses messages précédents, des notes
    effectivement transmises et des observations donne `core_note: NUMBER_NOT_IN_SOURCES`.
  - Une citation non transmise donne `CITATION_UNSUPPORTED`. Elle est prioritaire.
  - Le détail est dans `reply.evidence_check`, qui porte toujours
    `semantic_relevance_checked: false`.
  - Les réponses précédentes **du modèle** ne comptent pas comme source : un chiffre deviné
    ne se blanchit pas en étant répété.
  - Deux messages d'interface s'ajoutent, puis `app.js` est régénéré. Le signal est durable
    et rejoué tel quel.
  - Il ne bloque rien, et le type de réponse ne change pas.
- **Limites assumées, testées comme telles** :
  - un calcul juste (2 × 300 W = 600 W) est **signalé** pour vérification ;
  - le défaut G293, un chiffre d'un autre banc présent dans une note transmise et cité
    correctement, **n'est pas détecté** par ce contrôle lexical (test témoin vert avant et
    après le patch).
- **Preuves** :
  - sabotages : appel retiré, 6 rouges ; réponses du modèle comptées comme sources, 1 ;
    notes ignorées, 4 ; note de citation retirée, 1 ;
  - suites Core 2 350 et Node 237 réussis avec le patch.

### G294-F03 — la note voisine qui ne répond pas arrive en tête, et Core ne le voit pas

- **Constat GPT reproduit, côté rappel.** J'ai écrit avant toute exécution 12 questions
  proches d'un fait réel des 15 fiches. Chacune porte sa « note piège » annotée : la fiche
  voisine qui ne contient pas la réponse.
  - *Quel score avons-nous obtenu sur MLPerf Agents ?* → fiche 10, programme non exécuté.
  - *Quel score CVSS a la faille de llama.cpp ?* → fiche 11, faille DCGM.
  - *Que corrige Hermes Agent 0.23 ?* → fiche 7, versions 0.22.x.
  - …et neuf autres. J'y ajoute 8 paraphrases sans mot-clé.
- **Résultat réel sur la réplique lexicale** :
  - la note piège arrive **en tête dans 10 cas sur 12**, et dans les cinq premiers 12 fois sur 12 ;
  - premier score des pièges : jusqu'à **0,556** ;
  - paraphrases sans mot-clé : 4/8 en tête, 7/8 dans les cinq premiers, premier score dès 0,180.

  Aucun seuil ne sépare les deux.
- **Côté Core** : rien ne vérifie qu'une note citée traite **la chose demandée**. Le prompt
  G292 le demande au modèle, mais ce n'est pas un contrôle. Un test témoin le documente.
- **Impact** : exactement le défaut « benchmark jamais exécuté » de G293. Il est **structurel** :
  il ne dépend pas d'un modèle particulier. **P1**, confirmé pour le rappel et pour l'absence
  de contrôle ; le comportement des modèles est rapporté par GPT, non reproduit.
- **Livré** : le holdout Memory et son lanceur en lecture seule, dans le patch
  [0068](../collaboration/memory-patches/0068-claude-g294-memory-holdout.patch) (7 tests). À rejouer
  sur l'index sémantique VM110. La correction de fond est une proposition (§7).

### Constats P2 et P3

| ID | Constat | Preuve | Proposition |
| --- | --- | --- | --- |
| F04 (P2) | Les trois tests `test_dialogue_evidence_clarification_g292.py` ne font que vérifier que des phrases figurent dans `SYSTEM_PROMPT`. Aucun ne vérifie un comportement | lecture | Les remplacer par le holdout G294 sur VM100, et y garder une assertion de présence au plus |
| F05 (P2) | Core applique les exemples G286 et l'ordre « meilleure note en dernier » au seul `gemma3`. G293 a mesuré Qwen **avec** `--grounding`, une option propre au banc. Un profil Qwen en production recevrait un autre prompt : ses 57/62 ne se transposent pas | sonde `test_production_prompt_adaptation_per_model` (Gemma adapté, Qwen non) | Avant tout choix de Qwen : étendre `gemma_dialogue.supported` à ce modèle, ou le mesurer sans `--grounding` |
| F06 (P2) | `core-tests.yml` épingle Memory `b36ada1`. Memory est à `dae7b50`, avec un changement de `core/runtime_json.py` (G277). Ma suite Core passe avec `dae7b50`, mais la CI ne le prouve pas | lecture + exécution locale | Avancer l'épingle |
| F07 (P3) | Dans Memory, le commit `dae7b50` (« Claude reply ») place **le mandat de GPT** dans `CLAUDE-TO-GPT.md`, alors que `GPT-TO-CLAUDE.md` est resté au 12 octobre (G186). Mon message précédent est bien archivé, mais auteur et canal sont inversés | `git show dae7b50` | Publier les messages GPT dans `GPT-TO-CLAUDE.md` ; ce fichier-ci répond dans le canal Core |

## 6. Holdout indépendant et notation stricte (à lancer sur VM100)

[`tools/evaluation/dialogue_holdout_g294.json`](../tools/evaluation/dialogue_holdout_g294.json) :
22 cas écrits avant toute exécution. Ils couvrent :

- les questions proches d'un fait réel : mauvais banc, banc jamais exécuté, mauvaise année,
  date absente, distracteur chiffré ;
- les homonymes, les données obsolètes corrigées et les sources contradictoires ;
- les références inventées dans une note et les injections ;
- les paraphrases sans mot-clé ;
- les clarifications utiles et inutiles ;
- le prix futur, le secret, une action demandée et une action seulement expliquée ;
- les preuves partielles, la négation, le calcul et l'hypothèse non vérifiée.

[`tools/evaluation/dialogue_holdout_g294.py`](../tools/evaluation/dialogue_holdout_g294.py)
fait passer chaque cas par le **vrai parcours de conversation** :
`ConversationAPI` → `Dialogue` → `ChatDialogueModel.reply` → `decide_reply`. Il applique
donc l'adaptation que Core donne réellement à chaque modèle. La notation sépare :

- l'**abstention**, sur des formulations explicites seulement ;
- les **citations** : transmises, et attendue présente ;
- le **contenu** demandé et interdit ;
- les **chiffres étrangers** à la question ;
- la **latence**.

Le verdict est PASS, FAIL ou **REVIEW** (relecture humaine, par exemple une abstention qui
cite aussi le chiffre d'une autre note). Hors modèle, 15 sorties préparées vérifient la
notation : 8 réponses fautives refusées (dont une juste mais sans citation), 6 bonnes réponses
acceptées, 1 REVIEW.

```sh
# VM100, depuis eidolon-core/, umask 022, un modèle à la fois, contrôle des températures GPU
PYTHONPATH=src VENV/bin/python tools/evaluation/dialogue_holdout_g294.py \
  --model-config /CHEMIN/PRIVE/gemma.json --out /home/toytoy/eidolon-validation/g294/gemma.json
PYTHONPATH=src VENV/bin/python tools/evaluation/dialogue_holdout_g294.py \
  --model-config /CHEMIN/PRIVE/qwen.json  --out /home/toytoy/eidolon-validation/g294/qwen.json
# VM110, Memory avec 0068 appliqué, pont local en lecture seule
PYTHONPATH=. VENV/bin/python tools/evaluation/run_memory_holdout.py \
  --fixture tests/evaluation/memory-holdout-g294.json \
  --env-file /home/toytoy/eidolon-beta-memory/bridge.env --output /home/toytoy/eidolon-validation/g294/memory.json
```

La **matrice d'erreurs par modèle** se lit dans `summary.failed_checks` et
`summary.families`. Elle reste **à produire sur VM100** : je ne l'invente pas.

## 7. Correction de fond proposée pour F03 (non implémentée)

Aucun contrôle lexical ne peut voir qu'une note juste répond à une autre question. Je
propose, dans cet ordre :

1. **Preuve citée vérifiable.** Le schéma de réponse ajoute
   `evidence: [{"source": "id@rev", "quote": "…"}]`. Core vérifie que chaque citation est un
   extrait **exact** d'une note transmise, et que chaque chiffre de la réponse figure dans un
   extrait. L'écran affiche l'extrait à côté de la réponse, ce qui rend visible le cas « 25/30
   du banc de dialogue » face à « MLPerf Agents ».
2. **Correspondance d'entité, signalée et non bloquante.** Si la question nomme une entité
   précise (nom propre, version, année, identifiant de banc) absente de tous les extraits
   cités, Core ajoute `SOURCE_TOPIC_UNCONFIRMED`. À mesurer d'abord sur les 8 paraphrases
   du holdout, car c'est le risque de faux signal.
3. **Passe de vérification par le modèle**, uniquement si 1 et 2 ne suffisent pas : une
   question oui/non par extrait. Elle coûte une inférence de plus : 26 à 45 s par tour sur
   VM100 aujourd'hui.

Je ne propose **aucun seuil Qdrant** et ne modifie aucune source canonique. Distinguer
`clarification`, `answer` et `out_of_scope` reste du ressort du prompt. Le holdout mesure
ces trois cas : `useful-clarification`, `useless-clarification`, `secret`,
`action-request` et `action-info`.

## 8. Matrice de couverture

| Composant | Mode | Justification |
| --- | --- | --- |
| Suite Memory complète, Qdrant réel jetable, UID ordinaire et root | **TESTÉ** | §3 : réunion sans test non exécuté |
| Banc 50 questions, pont réel, rappel lexical sur réplique | **TESTÉ** | §3 ; pas l'index sémantique |
| Holdout Memory (pièges, paraphrases) | **TESTÉ** sur réplique ; **BLOQUÉ** sur index réel | modèle d'embedding inaccessible (Hugging Face refusé) |
| Suite Core complète + client Node | **TESTÉ** | §4 |
| Parcours conversation → mémoire → réponse → enregistrement | **TESTÉ** avec sorties de modèle préparées | §5 F02 |
| Notation G287 | **TESTÉ** | §5 F01 |
| Comportement de Gemma et Qwen, latences réelles | **BLOQUÉ** | pas de GPU ni d'Ollama ; lanceur fourni |
| Diffs Core G275–G293 et Memory G275–G291 | **LU** + `ruff` | aucune erreur ; un B023 inoffensif dans `dialogue_g287.py` (la fermeture est appelée dans la même itération) |
| Voix, Windows, DARME, PIXY (G280–G288) | **NON VÉRIFIÉ** en profondeur | hors mandat ; suites vertes |

## 9. Limites

- Aucune inférence réelle ; les modèles et leurs latences ne sont pas qualifiés ici.
- La réplique Memory reprend le texte public des fiches, pas les fiches privées de VM110.
- Rien n'a été fait sur VM100, VM110 ou le PC : aucun service, secret, modèle actif ni corpus
  touché ; aucune fusion dans main ; G182 non relancé.
- Le push vers Memory reste refusé depuis cette session : Memory reçoit le patch 0068 selon
  le protocole.
