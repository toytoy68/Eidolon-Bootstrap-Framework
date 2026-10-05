# Eidolon Core v0.1

Première tranche exécutable : demande → mission persistée → rappel mémoire →
plan proposé → autorisation déterministe → outil local → vérification → résultat.
Un agent, exécution séquentielle, aucun modèle contrôleur choisi définitivement.

Ce sous-projet est autonome et transférable dans un autre dépôt. Le paquet
`eidolon_core` ne dépend pas de Bootstrap et ne se confond pas avec le paquet
`core` du Memory Engine. Aucun installateur `.sh` n'est exécuté.

## Démonstration sans installation ni service

Prérequis : Python **3.11+ sur Linux/POSIX**, SQLite et bibliothèque standard.
Validation locale réalisée sous Python 3.12.14. Pas de GPU, modèle téléchargé,
clé API, service réseau, PyYAML ou dépendance Python externe pour ce parcours.
Windows natif n'est pas pris en charge (`fcntl`) ; validation Debian/VM différée.

Depuis `eidolon-core/` :

```sh
PYTHONPATH=src python -m eidolon_core --state /tmp/eidolon-core-demo demo
```

La sortie JSON contient un `id` stable `m-…`, `status: SUCCEEDED`, un plan,
la progression, le reçu de l'outil, sa vérification et les sources complètes.
Le contrat `objective` est fixé par le code ; `outcome.status: ACHIEVED` indique
que chaque référence du rappel conservé possède un résultat vérifié.
Le texte synthétique commence par « Ne pas acheter la V100 cette semaine. ».
L'outil calcule nombre de caractères Unicode, nombre d'octets UTF-8 et SHA-256.
Le code vérifie ces trois valeurs. Le statut de la source reste `UNVERIFIED`
et `needs_review=true` : réussir le calcul ne confirme pas son contenu.

Chaque `demo` crée une nouvelle mission. Pour examiner/reprendre **la même** :

```sh
PYTHONPATH=src python -m eidolon_core --state /tmp/eidolon-core-demo show m-ID --events
PYTHONPATH=src python -m eidolon_core --state /tmp/eidolon-core-demo run m-ID
PYTHONPATH=src python -m eidolon_core --state /tmp/eidolon-core-demo cancel m-ID
```

Remplacer `m-ID` par l'identifiant complet renvoyé. `run` ne rejoue pas une
mission terminée. `create` crée la mission de démonstration sans l'exécuter ;
un texte peut être fourni, mais le code bloque toute demande différente
de la mission documentée (`MISSION_UNSUPPORTED`, issue `CLARIFICATION`) avant
le rappel et le modèle. Ce n'est pas encore un assistant généraliste.

Installation facultative dans un environnement Python :

```sh
python -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/eidolon-core --state /tmp/eidolon-core-installed demo
```

Le packaging utilise setuptools>=68 (installation éventuellement réseau) ;
l'exécution et les tests simulés utilisent uniquement la bibliothèque standard.

## Présentation humaine commune

Le mode humain reprend le cadre, les séparateurs et les préfixes des installateurs
Bootstrap, avec l'identité Eidolon Core Technologies. Le défaut reste JSON.

```sh
PYTHONPATH=src python -m eidolon_core --format human presentation-preview
PYTHONPATH=src python -m eidolon_core --format human --state /tmp/eidolon-core-demo demo
```

`presentation-preview` affiche le style sans installer de logiciel ni créer de
dossier d'état. `--format human` est aussi disponible pour show/run/cancel et
les autres commandes. Le [standard commun](../standards/EIDOLON-PRESENTATION-v1.md)
définit les règles à transmettre aux agents de tous les projets Eidolon ;
le `AGENTS.md` à la racine y renvoie.

## Tests simulés

```sh
PYTHONPATH=src:. python -m unittest discover -s tests -t . -v
```

Refus, paramètres invalides, sortie modèle mal formée, mémoire absente/vide,
délais mémoire/modèle/outil/vérification, sortie fausse, annulation, concurrence,
processus interrompu et reprise sont couverts. Les scénarios d'interruption
utilisent `os._exit` dans un processus distinct, avant/après l'appel et autour
de l'enregistrement/vérification du reçu. Ils ne simulent pas une coupure disque.
Les régressions de la revue Claude couvrent aussi les nombres débordants et
substituts Unicode isolés, cinq sorties de 600 ko, l'enfant orphelin après
SIGKILL du parent et un reçu déjà écrit lors de l'annulation/du délai.
Voir le [bilan des corrections C-REV-001](docs/REVIEW-FIXES-2026-10-05.md).
La [contre-revue C-REV-002](docs/COUNTER-REVIEW-FIXES-2026-10-05.md) ajoute les
tentatives avec erreur, l'orphelin terminé et la réutilisation d'un reçu conservé.

## Contrat de mission et résultats partiels

```sh
PYTHONPATH=src:. python -m examples.objective_demo
```

Quatre missions synthétiques sont exécutées dans un état temporaire supprimé
à la fin : couverture de deux sources, plan incomplet refusé sans outil,
demande hors catalogue à clarifier, annulation après un résultat vérifié.
La sortie JSON expose `outcome`, références manquantes et preuves. Pour un état
persistant inspectable, utiliser la commande CLI `demo` ci-dessus.

Un plan qui répète une référence ou oublie un extrait est refusé intégralement
avant exécution. `PARTIAL` décrit des preuves réellement vérifiées avant un arrêt.
Une mémoire vide produit `BLOCKED/MEMORY_EMPTY`, issue `NO_EVIDENCE`, sans appeler
le modèle ; `run` peut retenter le rappel explicitement avec la même configuration.
Cela ne signifie jamais que tout le corpus mémoire a été couvert.

Les missions actives créées avant C-001a sans contrat sont bloquées pour examen ;
les appels interrompus restent prioritaires et exigent une réconciliation.
Les missions historiques terminales restent lisibles sans qualification rétroactive.
Voir [contrat, limites et migration](docs/MISSION-CONTRACT-C001A.md).

## Intégration optionnelle avec le vrai Memory Engine

Dernière intégration testée sur copie : `refactor/architecture-v1`, commit
`7d99ded07b7e10aa8029655ce4a939af6e0a6c44` ; audit initial consulté : `3a86ef0`.
[Validation C-005a](docs/validation/2026-10-05/codex-c005a/README.md).
La source du moteur est une dépendance séparée, jamais recopiée dans Core.
Les commandes suivantes sont à exécuter depuis `eidolon-core/` avec un chemin
absolu vers un clone **isolé** du moteur :

```sh
export EIDOLON_MEMORY_SOURCE=/chemin/absolu/Eidolon-Memory-Engine
# Dépendance de cette API du moteur uniquement : PyYAML>=6.0.2,<7.
python -m pip install -r "$EIDOLON_MEMORY_SOURCE/requirements.txt"
EIDOLON_MEMORY_INTEGRATION=1 PYTHONDONTWRITEBYTECODE=1 \
  PYTHONPATH="src:.:$EIDOLON_MEMORY_SOURCE" \
  python -m unittest tests.test_memory_engine -v
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="src:.:$EIDOLON_MEMORY_SOURCE" \
  python -m examples.memory_engine_demo
```

La démonstration et les six tests créent leurs propres corpus temporaires via
`FilesystemInformationWrites`, puis appellent `ContextualRecall` réellement.
Les hashes des fichiers métier sont comparés avant/après rappel. Les verrous
techniques `.write.lock` sont exclus de cette comparaison. Les dossiers
temporaires sont supprimés à la fin ; aucun corpus utilisateur n'est demandé.
Les six tests d'intégration sont explicitement sautés si la variable d'activation
est absente ; `tests.test_core` ne les compte pas.

La CLI accepte aussi `--memory-root /copie-isolee` (racine contenant `memory/`),
avec le moteur sur PYTHONPATH. Elle ne propose aucune écriture, récupération,
compaction ni import automatique. Elle refuse une racine inexistante. Le rappel
peut créer les verrous techniques du moteur. Les trois problèmes A5-01/02/03
sont reproduits sur la base testée ; ne pas utiliser ces extraits pour décider
d'actions réelles. Voir [état examiné](docs/EXISTING-2026-10-05.md).

## Reprise et réconciliation

Un appel `STARTED` sans reçu durable devient `REVIEW_REQUIRED` à la reprise.
Il n'est jamais relancé automatiquement, même si l'outil de démonstration est pur.
Une annulation ou un délai pendant un appel laisse également son effet inconnu.
Il faut examiner l'effet et vérifier que tout ancien exécutant est arrêté.

Après cette vérification humaine explicite :

```sh
PYTHONPATH=src python -m eidolon_core --state /tmp/eidolon-core-demo reconcile m-ID \
  --decision no-effect --confirm-no-effect --actor toytoy --reason 'Exécutant arrêté, absence d’effet vérifiée'
PYTHONPATH=src python -m eidolon_core --state /tmp/eidolon-core-demo run m-ID
```

`no-effect` autorise une nouvelle tentative, avec le même identifiant d'appel
et un numéro de tentative incrémenté. `observed-result --result resultat.json`
enregistre un résultat observé ; il passe ensuite au même vérificateur que
l'outil, avec une origine `human_reconciliation` explicite. Une simple affirmation
« réussi » est refusée. Auteur/motif/décision restent dans le journal.
La réconciliation ne lance aucun outil ; `run` est une étape distincte.
Une annulation déjà demandée reste active après réconciliation.

Le processus outil détient maintenant un verrou pendant son exécution.
`no-effect` et `observed-result` sont refusés tant que ce verrou est occupé.
PID et date sont journalisés pour diagnostic ; le contrôle utilise le verrou,
pas le PID. Cela ne prouve pas l'absence d'effet distant ou d'un descendant.
Les appels anciens sans protocole de verrou ne peuvent pas autoriser une reprise.

Les nouveaux appels utilisent `lease-v2` : l'enfant inscrit son autorisation
dans le fichier verrouillé **avant** d'entrer dans l'outil, puis conserve son
reçu à côté du verrou dans le dossier d'état Core. La réconciliation consulte
ce reçu sous le verrou, même après la mort du parent. Conserver le dossier
d'état complet, pas uniquement le fichier SQLite.

Pour clore une mission sans prétendre connaître l'effet :

```sh
PYTHONPATH=src python -m eidolon_core --state /tmp/eidolon-core-demo reconcile m-ID \
  --decision abandon --actor toytoy --reason 'Effet impossible à déterminer'
```

L'état terminal `ABANDONED` conserve `EFFECT_UNKNOWN`, les reçus disponibles
et l'historique. Il n'interrompt pas un éventuel exécutant orphelin et n'autorise
aucun nouvel appel. Cette clôture reste possible sans la configuration d'origine.
Un reçu tardif figure dans `calls[].late_receipt`, une erreur rendue normalement
dans `error_receipt`, un résultat récupéré après interruption dans
`recovered_receipt`. Aucun n'est validé automatiquement. Pour réutiliser la
valeur conservée sans la retaper :

```sh
PYTHONPATH=src python -m eidolon_core --state /tmp/eidolon-core-demo reconcile m-ID \
  --decision use-receipt --actor toytoy --reason 'Reçu conservé examiné'
PYTHONPATH=src python -m eidolon_core --state /tmp/eidolon-core-demo run m-ID
```

`use-receipt` prépare la vérification, sans relancer l'outil. Une sortie humaine
différente d'un reçu positif conservé est refusée avant de modifier le résultat.
`no-effect` est refusé si un reçu positif existe, même avec confirmation.
Une enveloppe d'erreur ne prouve jamais l'absence d'effet : si l'exécution a été
autorisée ou reste inconnue, `no-effect` exige aussi `--confirm-no-effect` après
investigation. L'ancienne tentative et son erreur restent dans `attempt_history`.

Si l'appel a été autorisé (ou son autorisation est inconnue avec `lease-v1`)
et qu'aucun reçu positif n'existe, `no-effect` exige en plus `--confirm-no-effect` après
une investigation établissant l'absence d'effet. Un verrou libre ne suffit pas.
Cette attestation reste une décision humaine auditée, pas une preuve automatique.
Si l'absence d'effet ne peut pas être établie, rester en revue ou abandonner.

Après WORKER_SPAWNED, un verrou manquant bloque toute réconciliation ouvrant une
reprise ; il n'est pas recréé vide. L'abandon reste possible. Un reçu récupéré
peut être journalisé même si la décision de réconciliation est ensuite refusée :
consulter `show --events` après un refus. Cela n'autorise aucun nouvel appel.

Une annulation constatée avant tout envoi d'autorisation se termine directement
en CANCELLED. Un échec/délai de lancement connu avant autorisation bloque et
permet une reprise explicite ; il n'est pas présenté comme un effet inconnu.

La configuration de reprise doit correspondre à celle de création (modèle,
mémoire/racine, politique, versions outils/vérificateurs, délai). Utiliser les
mêmes options CLI ; sinon le système bloque. Un reçu présent est revérifié
sans refaire l'appel. Les missions FAILED sont terminales : nouvelle mission
après diagnostic. Les propositions bloquées n'expirent jamais automatiquement.
Un délai ou une panne du modèle produit désormais `BLOCKED/MODEL_UNAVAILABLE`,
reprenable explicitement avec la même configuration. Un plan invalide reste
`FAILED/MODEL_INVALID`.

`result.evidence` contient des références compactes : identifiant d'appel,
tentative, empreinte de sortie, origine du reçu et vérificateur. Les sorties complètes restent
dans `calls[].output`, sans duplication dans le résultat final. Chaque reçu
reste borné à 1 Mo ; au plus cinq appels par plan.

Codes CLI : 0 succès de commande (`show/create/reconcile/decide/fixture`) ou mission réussie ;
2 bloqué/revue/erreur d'entrée ; 3 mission échouée ; 4 annulée/abandonnée ; 130 interruption.
`cancel` pendant un appel actif persiste la demande ; `show` expose sa progression.
Le délai `--timeout` est **par appel**, démarrage du processus compris, 10 s par
défaut. Ce n'est pas encore un budget global de mission.

## Modules optionnels intégrés, activation différée

Le [catalogue de cibles](docs/TARGETS-CONTRACT.md) et l'[adaptateur Ollama](docs/OLLAMA-ADAPTER.md)
de Claude sont intégrés au paquet. Le catalogue est raccordé au runtime et à la
CLI pour le diagnostic synthétique C-004a ; l'adaptateur peut être injecté via
l'API Python mais n'est ni le
modèle par défaut, ni une option de la CLI. Ses tests emploient des transports
simulés et un faux serveur HTTP loopback. Aucun vrai modèle n'est qualifié.

L'[adaptateur chat candidat llama.cpp](docs/OPENAI-CHAT-ADAPTER.md) de Claude
est également intégré, avec validation renforcée des réponses et protection
contre la réflexion de la clé d'accès dans les traces. Il reste injectable via
Python, hors CLI. Cette démonstration utilise uniquement un faux serveur local :

```bash
PYTHONPATH=src:. python -m examples.openai_chat_demo
```

[Validation G004](docs/validation/2026-10-05/codex-g004/README.md) :
191 tests Core réussis et 6 tests du moteur mémoire sur copie isolée.

L'étude comparative pour les deux V100 SXM2 sur carte adaptatrice PCIe/NVLink
a été reçue (`ec7582b`), puis précisée par Claude dans C-TASK-G003.
Aucune qualification matérielle n'est acquise. G003 est intégré (`a77e7cf`). [Bilan de l'intégration et corrections](docs/CLAUDE-INTEGRATION-2026-10-05.md).

## Préparation de l'accès Web C-002a

La [politique de destinations Web](docs/EGRESS-POLICY.md) de Claude est intégrée
et durcie : URL/redirections contrôlées, DNS borné et exclusions IP/CIDR
configurables pour les adresses du foyer, même publiques. Démonstration pure :

```sh
PYTHONPATH=src:. python -m examples.web_policy_demo --format human
```

Aucun téléchargement ni accès au réseau dans cette démo. Le connecteur HTTP,
le raccordement aux missions et la recette pare-feu/VPN restent à réaliser.
[Validation intégrée C-002a.1](docs/validation/2026-10-05/codex-c002a/README.md) :
221 tests Core et 6 intégrations mémoire réussis sur données synthétiques.

## Prototype de recherche propre à Eidolon

```sh
PYTHONPATH=src:. python -m examples.research_demo --format human
```

Fournisseurs simulés interchangeables, repli après quota, cache RAM et provenance
séparent les extraits trouvés des textes réellement lus. Un défi HTTP 200 reste
non exploitable. Le prototype lit le texte UTF-8 simple/Markdown ; extraction
HTML générale et fournisseurs Internet restent à raccorder. Ce n'est pas encore
un outil disponible dans une mission Core. [Contrat et limites](docs/WEB-RESEARCH-PROTOTYPE.md).

## Diagnostic synthétique C-004a

Le profil `service-sim` sélectionne une cible et contrôle ses permissions avant
un outil sans réseau. `sim-memory` est UP, `nas` est DOWN, `offline` est
UNREACHABLE : ces trois observations vérifiées donnent une mission réussie.
L'alias ambigu `service` et une permission absente bloquent sans outil.

```bash
PYTHONPATH=src:. python -m examples.service_diagnostic_demo
PYTHONPATH=src python -m eidolon_core --profile service-sim --format human --state /tmp/eidolon-services diagnose nas
```

[Contrat, commandes de reprise et limites](docs/SYNTHETIC-DIAGNOSTIC-C004A.md).
Ce diagnostic observe uniquement des fixtures ; aucun accès au NAS ou à la VM.

## Approbation et redémarrage simulé C-005a

```bash
PYTHONPATH=src:. python -m examples.action_demo
PYTHONPATH=src python -m eidolon_core --profile action-sim --state /tmp/eidolon-actions --format human restart nas
```

La CLI présente une proposition et attend une décision (code 2). `decide` lie
l'accord à son empreinte, puis `run` contrôle de nouveau la condition et exécute
la transition dans une base de services fictifs. Refus, révocation, changement
d'état et interruption sont testés. Rien n'agit sur un service réel.
[Commandes, contrat et limites d'identité](docs/SIMULATED-ACTIONS-C005A.md).
La démonstration couvre six scénarios ; une proposition sans décision n'expire pas.

La CLI distingue aussi décision enregistrée, applicabilité et preuve d'effet dans
`action_view` (JSON) et le rendu humain. Un accord consommé (`USED`) n'annonce
pas une action effectuée. [Contrat de la vue](docs/ACTION-VIEW-G005.md).
[Validation G005 intégrée](docs/validation/2026-10-05/codex-g005/README.md) :
235 tests Core et 6 intégrations mémoire réussis sur synthétique.

```sh
PYTHONPATH=src:. python -m examples.action_view_demo --format human
```

## Rapports de qualification G-017

```bash
PYTHONPATH=src:. python -m examples.qualification_demo
```

Le [validateur livré par Claude](docs/QUALIFICATION-REPORTS.md) distingue
REJECTED, INCOMPLETE et PASSED_SCOPE. Il vérifie la cohérence du rapport, jamais
l'authenticité des mesures ni la qualification générale d'un modèle. Les mesures
absentes et un corpus vide ne deviennent pas un succès.

## Documents et limites

Le [lecteur HTTP candidat](docs/WEB-READER.md) raccorde maintenant le transport
contrôlé au coordinateur. Démonstration sur serveur local et fournisseur simulé :

```sh
PYTHONPATH=src:. python -m examples.research_http_demo --format human
```

Elle vérifie refus, quota, défi et texte reçu après redirection. Aucun moteur
de recherche Internet ni outil réseau de mission n'est activé.

- [Échanges Codex/GPT ↔ Claude Code](ECHANGES.md),
  [protocole](collaboration/README.md) et [brainstorming](collaboration/BRAINSTORMING.md).
- [Cadrage produit et accès Internet/LAN](docs/CADRAGE-DECISIONS-2026-10-05.md) :
  brainstorming reçu, besoins Desktop/fichiers Windows/NAS/mémoire distante et
  écarts avec v0.1.
- [Architecture et garanties](docs/ARCHITECTURE.md)
- [Bilan de validation](docs/VALIDATION-2026-10-05.md)
- [TODO Core et prochaine tranche](TODO.md)

Les fournisseurs et outils Python sont du code de confiance. Le sous-processus
permet arrêt/délai, **pas un bac à sable de sécurité**. Aucune extension non fiable,
commande shell, réseau ou effet externe n'est exposé. Les permissions sont
indépendantes du contenu du modèle et des sources ; cela ne constitue pas une
qualification générale contre les injections pour un futur LLM.
