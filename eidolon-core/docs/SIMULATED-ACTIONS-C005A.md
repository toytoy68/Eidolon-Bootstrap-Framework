# Approbation et action simulée — C-005a

Auteur : Codex/GPT. Date : 05/10/2026. Base fonctionnelle précédente : `e54823d`.
Intégration documentaire/qualification Claude : `a273f3c`.
Cette tranche fonctionne sur un **service fictif dans une base SQLite locale**.
Elle ne dispose d'aucun accès à la VM100, au NAS, à Windows ou à un vrai service.

## Parcours livré

1. `restart nas` crée une intention typée `service_restart.simulated`.
2. Le catalogue résout la cible et la capacité ; le rappel conserve ses réserves.
3. Le fournisseur local observe le service fictif DOWN, avec identité de base et
   révision. Une observation récente est vérifiée avant de construire le plan.
4. Le modèle déterministe propose l'appel, puis le code contrôle outil, cible,
   révision, identifiant d'opération et permissions.
5. La mission reste BLOCKED/APPROVAL_REQUIRED. La proposition est persistante,
   visible dans `show`, et **n'expire pas automatiquement**.
6. `decide` enregistre l'accord, le refus ou la révocation. Cette commande
   n'exécute pas l'outil. `actor` est une trace libre, pas une identité authentifiée.
7. Un `run` explicite après accord observe à nouveau la cible. État, révision et
   identité doivent toujours correspondre à la proposition. Sinon la mission
   bloque, conserve la proposition et exige un examen ; créer une nouvelle
   mission pour une action différente. Aucun nouvel accord n'est supposé.
8. La consommation de l'accord et CALL_STARTED sont enregistrés ensemble.
   L'exécutant reçoit ensuite l'autorisation selon le protocole durable existant.
9. Dans la base de simulation, une transaction compare DOWN et la révision
   attendue, passe à UP, incrémente le compteur et écrit le reçu de l'opération.
10. Le vérificateur contrôle la sortie contre ce reçu et les paramètres attendus.
    SUCCEEDED exige ce résultat vérifié et l'accord consommé pour cette tentative.

UP et UNREACHABLE ne produisent pas de proposition de redémarrage dans ce
prototype. La simulation représente une transition instantanée DOWN → UP,
pas un cycle système réel avec démarrage, dépendances ou erreurs matérielles.

## Modules et persistance

| Module | Responsabilité |
| --- | --- |
| `simulation.py` | Base synthétique, état/révision, transaction de redémarrage et reçu |
| `approvals.py` | Empreinte de l'action, décision, consommation et historique des accords |
| `actions.py` | Runtime spécialisé, politique limitée à la simulation et vérification des préconditions |
| `runtime.py` | Points d'extension avant plan/lancement/réconciliation ; protocole d'exécutant commun |
| `store.py` | Persistance atomique de la consommation avec CALL_STARTED ; garde du succès |

Les missions/propositions restent dans `missions.sqlite3`, JSON version 1,
sans migration SQL. Les services fictifs et reçus sont dans `simulation.sqlite3`
sous le même `--state`. Une identité UUID de cette base entre dans la configuration ;
la remplacer empêche la réutilisation d'une ancienne approbation. Les fichiers
canoniques du Memory Engine ne sont jamais une destination de ces écritures.

La proposition couvre : mission, appel, tentative, paramètres exacts, plan,
objectif, configuration, contexte mémoire, observation initiale et condition
cible/identité/révision/état. Une décision nomme son SHA-256 complet. Une décision
pour une autre mission, une autre tentative ou un plan modifié ne convient pas.

États de proposition : PENDING → APPROVED ou REJECTED ; APPROVED → REVOKED ou
USED. Un refus/révocation n'est pas réversible dans cette tranche : nouvelle
mission après examen. Une tentative réouverte après réconciliation sans effet
obtient une nouvelle proposition ; l'ancienne reste dans `proposal_history`.
L'ancien accord n'autorise pas la tentative suivante.

La politique par défaut conserve son refus des mutations. `action-sim` utilise
une politique dédiée à `service.restart.simulated`, avec permissions distinctes
pour observer et agir sur la cible. Elle n'est pas un droit général de mutation
locale ou distante. Les implémentations Python restent du code de confiance ;
ce mécanisme n'est ni un bac à sable ni une frontière d'identité authentifiée.

## Concurrence et interruption

L'observation juste avant l'appel réduit le risque de condition périmée ; la
comparaison **dans la transaction d'action** couvre le changement entre ce
contrôle et la modification. Même une séquence DOWN → UP → DOWN change la révision
et bloque l'action approuvée sur l'ancienne version. Deux missions approuvées
sur la même révision ne peuvent pas toutes deux modifier le service fictif.

Un appel interrompu/dépassant son délai reste REVIEW_REQUIRED tant que son effet
est inconnu. Aucun rejeu automatique. Un résultat sauvegardé RETURNED reprend
la vérification ; un état terminal ne relance rien. Si l'exécutant disparaît
après la transaction mais avant son reçu de transport, le reçu du simulateur
permet une réconciliation explicite `observed-result`, puis une revérification.
Le fournisseur refuse `no-effect`, même confirmé, si son reçu prouve une
transaction déjà effectuée. Le verrou d'exécutant est contrôlé avant ce constat.

Le reçu local est consultable par `runtime.world.receipt(mission_id)` via l'API
Python ; son champ `result` est la sortie à soumettre à la réconciliation.
Une affirmation humaine seule échoue au vérificateur si ce reçu n'existe pas.
`abandon` conserve la possibilité de clore une mission à effet inconnu.

La base synthétique écrit effet et reçu dans sa propre transaction : c'est une
propriété spécifique de ce simulateur. **Aucune garantie « exactement une fois »
n'est étendue à un outil externe arbitraire.** Missions et services occupent deux
bases distinctes ; le protocole de revue traite la coupure entre leurs commits.
Une vérification réussie prouve une transition passée, pas la santé actuelle.

L'annulation est durable, distincte de la révocation. `decide` partage le verrou
de mission avec `run` : une révocation pendant un appel actif peut répondre Busy ;
utiliser `cancel` pour demander l'arrêt. Une annulation ne défait pas un effet
commis. Aucun contenu mémoire ne passe à « confirmé » après une approbation.

## Commandes sans GPU ni service

Depuis `eidolon-core/`, Python 3.11+ Linux/POSIX et bibliothèque standard :

```bash
PYTHONPATH=src:. python -m examples.action_demo
PYTHONPATH=src python -m eidolon_core --profile action-sim --state /tmp/eidolon-actions --format human restart nas
```

La première commande vérifie six scénarios dans des dossiers temporaires :
attente, accord/exécution, refus, révocation, état changé, annulation. La seconde
crée une mission persistante, présente sa proposition et retourne **2** (attente).
Remplacer `m-ID` et `SHA` ci-dessous par les valeurs affichées après inspection :

```bash
PYTHONPATH=src python -m eidolon_core --profile action-sim --state /tmp/eidolon-actions show m-ID --events
PYTHONPATH=src python -m eidolon_core --profile action-sim --state /tmp/eidolon-actions decide m-ID --proposal-sha SHA --decision approve --actor demo-operateur --reason "Essai explicite sur service fictif"
PYTHONPATH=src python -m eidolon_core --profile action-sim --state /tmp/eidolon-actions run m-ID
PYTHONPATH=src python -m eidolon_core --profile action-sim --state /tmp/eidolon-actions fixture sim-nas
```

`decide` retourne 0 lorsque la décision est enregistrée, sans annoncer un succès
métier. Les décisions `reject` et `revoke` utilisent les mêmes arguments.
`--allow-target` remplace la liste des cibles permises à la simulation.

Contrôle **opérateur du banc fictif**, jamais exposé au modèle :

```bash
PYTHONPATH=src python -m eidolon_core --profile action-sim --state /tmp/eidolon-actions fixture sim-nas --set-state UP
```

Cette commande permet de provoquer un changement pendant l'attente. Elle change
uniquement la fixture, incrémente sa révision et ne compte pas comme un redémarrage
par mission. Elle est volontairement distincte de la politique d'action des
missions. Ne pas l'interpréter comme une commande d'administration réelle.
Le profil C-004a `service-sim` garde ses fixtures statiques indépendantes ;
inspecter la simulation avec `action-sim fixture`, pas avec `service-sim diagnose`.

## Limites et suite

[Preuves exécutées](validation/2026-10-05/codex-c005a/README.md).
Le scénario C simulé est livré. L'identité humaine authentifiée, l'autorisation
distante, le cycle d'un vrai redémarrage, les secrets et connecteurs réels restent
à construire et à qualifier. C-BRAIN-G008 n'est pas transformé en politique
générale : le choix local de ce prototype est de bloquer tout changement de
précondition. Aucun TTL de proposition ou d'accord n'est ajouté.

Prochaine tranche indépendante : premiers contrats/lectures de ressources
synthétiques (Internet/LAN/Windows), budgets de contenu et artefacts. L'adaptateur
chat candidat de Claude (C-TASK-G004) reste séparé. Le retry métier de D conserve
son lot C-006 ; FAILED demeure terminal. Budget global, rétention des bases et
reçus, restauration physique et recette VM restent différés.
