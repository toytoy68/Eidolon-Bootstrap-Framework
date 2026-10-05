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
un texte peut être fourni, mais le modèle simulé refuse toute demande différente
de la mission documentée. Ce n'est pas encore un assistant généraliste.

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
PYTHONPATH=src:. python -m unittest tests.test_core -v
```

Refus, paramètres invalides, sortie modèle mal formée, mémoire absente/vide,
délais mémoire/modèle/outil/vérification, sortie fausse, annulation, concurrence,
processus interrompu et reprise sont couverts. Les scénarios d'interruption
utilisent `os._exit` dans un processus distinct, avant/après l'appel et autour
de l'enregistrement/vérification du reçu. Ils ne simulent pas une coupure disque.

## Intégration optionnelle avec le vrai Memory Engine

Base testée : `refactor/architecture-v1`, commit
`3a86ef0707d24f8126df385e462f911c52891d3e`.
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
  --decision no-effect --actor toytoy --reason 'Exécutant arrêté, absence d’effet vérifiée'
PYTHONPATH=src python -m eidolon_core --state /tmp/eidolon-core-demo run m-ID
```

`no-effect` autorise une nouvelle tentative, avec le même identifiant d'appel
et un numéro de tentative incrémenté. `observed-result --result resultat.json`
enregistre un résultat observé ; il passe ensuite au même vérificateur que
l'outil, avec une origine `human_reconciliation` explicite. Une simple affirmation
« réussi » est refusée. Auteur/motif/décision restent dans le journal.
La réconciliation ne lance aucun outil ; `run` est une étape distincte.
Une annulation déjà demandée reste active après réconciliation.

La configuration de reprise doit correspondre à celle de création (modèle,
mémoire/racine, politique, versions outils/vérificateurs, délai). Utiliser les
mêmes options CLI ; sinon le système bloque. Un reçu présent est revérifié
sans refaire l'appel. Les missions FAILED sont terminales : nouvelle mission
après diagnostic. Les propositions bloquées n'expirent jamais automatiquement.

Codes CLI : 0 succès de commande (`show/create/reconcile`) ou mission réussie ;
2 bloqué/revue/erreur d'entrée ; 3 mission échouée ; 4 annulée ; 130 interruption.
`cancel` pendant un appel actif persiste la demande ; `show` expose sa progression.
Le délai `--timeout` est **par appel**, démarrage du processus compris, 10 s par
défaut. Ce n'est pas encore un budget global de mission.

## Documents et limites

- [Architecture et garanties](docs/ARCHITECTURE.md)
- [Bilan de validation](docs/VALIDATION-2026-10-05.md)
- [TODO Core et prochaine tranche](TODO.md)

Les fournisseurs et outils Python sont du code de confiance. Le sous-processus
permet arrêt/délai, **pas un bac à sable de sécurité**. Aucune extension non fiable,
commande shell, réseau ou effet externe n'est exposé. Les permissions sont
indépendantes du contenu du modèle et des sources ; cela ne constitue pas une
qualification générale contre les injections pour un futur LLM.
