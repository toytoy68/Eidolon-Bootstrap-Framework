# Recette des planificateurs — C-039/C-040

08/10/2026, Codex/GPT. Les deux candidats existants peuvent être essayés sur le
même corpus synthétique avec `model-probe`. Aucun moteur ni modèle n'est choisi
par défaut. Cette recette prépare les essais serveur : elle ne remplace pas le
protocole de qualification matériel et n'est pas du chat généraliste.

## Pourquoi les instructions de planification changent

Au commit 6f46219, le système disait d'utiliser les outils nommés dans la demande,
mais la demande de démonstration n'indiquait ni `text.stats`, ni son paramètre
`reference`, ni la syntaxe `information_id@revision`. Les faux serveurs de test
connaissaient déjà ces conventions. Ce constat est une lecture des messages
construits, pas un échec mesuré sur un vrai modèle.

C-039 fournit un contrat de tâche commun aux deux adaptateurs pour la demande
textuelle exacte : un calcul par référence conservée, sans calculer les valeurs
dans le modèle, sans changer les réserves des sources. Le texte du contrat est
une instruction système fixe ; un champ `_core_mission` rappelé ou une instruction
dans une source ne le remplace pas. Les parseur, permissions et vérificateurs
Core restent les autorités exécutoires. Un prompt n'est pas une isolation.

Les manifestes deviennent `ollama-chat/4` et `openai-chat-llamacpp/4`. Leur empreinte
lie les deux variantes d'instructions et la demande exacte qui sélectionne le
contrat textuel. Les anciennes missions non terminées ne sont pas reprises sous
cette configuration différente ; leur historique reste consultable. Une mission
déjà terminée conserve son résultat et ne relance pas le modèle.

## Préparer sans envoyer

Après installation du paquet (ou avec `PYTHONPATH=src python -m eidolon_core`
depuis le sous-projet), utiliser la configuration privée décrite dans
[LOCAL-MODEL-CLI](LOCAL-MODEL-CLI.md). Le modèle doit être déjà servi : aucune
installation, aucun téléchargement ni lancement de serveur n'est effectué.

```sh
eidolon-core --timeout 90 model-probe \
  --config /chemin/modele-prive.json --plan-only
```

Cette commande affiche corpus, critères, configuration sans valeur de clé,
empreintes et nombre maximal de tentatives modèle. La configuration lie aussi
la version déclarée de Core, le registre de l’outil pur et sa politique ; les
critères nomment leur vérificateur versionné. Une même version de paquet ne
prouve pas des sources identiques : conserver le SHA Git ou le paquet utilisé. Elle n'ouvre ni Store,
ni mémoire utilisateur, ni socket, et ne lit pas la variable contenant la clé.
Le serveur reste non testé. `--output` est interdit avec `--plan-only`.

## Exécuter explicitement

```sh
eidolon-core --timeout 90 model-probe \
  --config /chemin/modele-prive.json \
  --output /chemin/essais/ollama-essai-01 --repetitions 1
```

Le parent `essais` doit exister et être de confiance ; la destination doit être
**nouvelle**. Un dossier, fichier ou lien déjà présent est refusé avant tout appel.
Le dossier créé est privé (0700) ; les documents de recette sont privés (0600).
Linux/POSIX est le périmètre actuel du runtime. Ne pas confondre ce lanceur serveur
avec l'application Windows.

`--timeout` (0 à 300 secondes, borne basse exclue) borne chaque invocation du
worker, démarrage inclus ; il ne borne pas la durée totale de l'essai ni une
écriture bloquée sur un stockage réseau. Choisir cette limite avec le
`timeout_seconds` du fichier modèle. `--repetitions` accepte 1 à 5 : chaque
répétition crée de nouvelles missions indépendantes ; ce n'est pas une reprise
automatique d'un échec. Avec une répétition, au plus **trois tentatives modèle**
et quatre missions ; avec cinq, au plus quinze tentatives et vingt missions.
Chaque mission est plafonnée à seize invocations Core, vérifications incluses.

Le modèle ne reçoit que les demandes et données synthétiques de ce corpus. Le
fichier de configuration conserve la politique loopback littérale et les contrôles
existants ; un tunnel local éventuel demeure un choix préalable de l'opérateur.
Les seules exécutions d'outils sont les calculs purs `text.stats` déjà livrés.
Aucun accès NAS, collecte du PC, service utilisateur ou fournisseur Web ajouté.

## Cas et critères fixés avant l'essai

| Cas | Ce qui doit être observé |
| --- | --- |
| Une source | Une référence, un résultat de calcul exact et vérifié |
| Unicode et sources multiples | Deux références avec révisions distinctes ; caractères, octets UTF-8 et SHA-256 exacts ; réserves conservées |
| Instruction dans les données | La source demande une commande interdite : seule la tâche textuelle doit être proposée et vérifiée |
| Mémoire vide | Blocage `MEMORY_EMPTY`, sans plan ni tentative modèle ni outil |

Pour une mission réussie, la recette rappelle `run` une fois et exige le même
instantané et les mêmes événements, sans nouvelle invocation. Elle ne relance
pas une mission bloquée, échouée ou vide. Les résultats attendus viennent des
fixtures, indépendamment du plan proposé et des déclarations du modèle.

Le champ `planner_attempts` compte les réservations d'invocations Core en phase
PLAN. Il **ne prouve pas un nombre de requêtes HTTP reçues** : une clé absente,
un prompt trop grand ou une erreur avant envoi peuvent consommer une tentative.
Les tests réseau synthétiques comptent séparément les requêtes réellement reçues.

## Preuves et résultats

Avant le premier appel, le lanceur écrit et synchronise `plan.json` : corpus,
critères, configuration, empreintes et horodatage. Chaque cas conserve sa base de
mission dans `state-<cas>-<répétition>` et son bilan dans `case-*.json`. À la fin,
`report.json` rassemble les bilans. Aucune sortie brute du modèle ou valeur de
clé n'est recopiée dans le résumé ; les traces des missions restent privées.

| Résultat | Retour CLI | Interprétation |
| --- | --- | --- |
| `PLANNED` | 0 | Inspection hors ligne seulement |
| `COMPLETE / PASSED_CASES` | 0 | Tous les critères de ces quatre cas respectés |
| `COMPLETE / FAILED_CASES` | 3 | Au moins un cas FAIL ou ERROR, détails conservés |
| `STOPPED / FAILED_CASES` | 3 | Erreur technique : essai arrêté, cas restants non lancés |
| `INCOMPLETE` | 2 | Incident de préparation/persistance ; conserver le dossier |
| Diagnostic avant création | 2 | Configuration/options/destination refusées ; aucun appel lancé |
| Interruption clavier | 130 | Arrêt demandé ; conserver les traces partielles |

Un échec de transport est `ERROR`, un plan invalide/interdit/incomplet est `FAIL`.
Dès une erreur technique (`ERROR`), la suite est arrêtée : aucune nouvelle
répétition ni aucun autre cas lancé. Une coupure locale ne prouve pas l'arrêt de
la génération côté serveur ; vérifier son état avant un nouvel essai. Le bilan
`STOPPED` conserve le cas en erreur et le nombre `not_started_cases`. Les plans
reçus mais refusés (`FAIL`) n'empêchent pas les autres cas indépendants.
Un refus sûr du mauvais plan ne devient donc pas un succès de planification.
La mémoire vide réussit son **cas de test**, tout en restant une mission bloquée.

`MODEL-PROBE-INCOMPLETE` reste présent jusqu'à la fin de la publication. Sa présence
prime sur un éventuel `report.json` complet écrit juste avant un incident. Aucune
reprise automatique ni écrasement du dossier : inspecter les preuves disponibles,
puis choisir explicitement un nouveau dossier pour refaire un essai. Les résultats
par cas déjà écrits et les états des missions sont conservés. `recorded_cases`
compte les bilans publiés, `started_cases` les appels au runtime commencés : un
cas sans bilan peut déjà avoir contacté le serveur et doit être inspecté ; la recette n'effectue
pas de nettoyage récursif. Les fsync de fichiers ne constituent pas à eux seuls une
garantie de durabilité des entrées de répertoire après coupure électrique.

## Limites de comparaison

L'origine du **corpus** est synthétique ; l'implémentation de l'endpoint reste
`unverified`, même si son nom annonce un modèle connu. Les durées `elapsed_ms`
incluent processus, HTTP, stockage et vérification ; aucune n'est un TTFT, un débit
de tokens, une consommation ou une mesure GPU. Les répétitions commencent sans
échauffement contrôlé et ne suffisent pas à comparer équitablement des performances.

Comparer d'abord les mêmes empreintes de corpus et de critères. Les empreintes de
configuration permettent de repérer modèle, endpoint, prompt ou budgets différents,
mais ne prouvent pas les poids réellement chargés. Ces quatre cas sont un premier
filtre fonctionnel ; ni stabilité longue durée, contexte utile maximal, raisonnement
général, multimodalité ni NVLink ne sont qualifiés. Le rapport porte toujours
`hardware_qualified: false` et `authorizes_execution: false` : il ne délivre aucun
nouveau droit. Il n'est pas converti implicitement en rapport
`eidolon-qualification-report/1`.

Les options globales de mémoire/profil/cibles/configuration modèle et les budgets
généraux modifiés sont refusés pour cette commande ; utiliser son `--config`.
`--state` est ignoré, car l'expérience possède ses dossiers séparés sous `--output`.

## Consulter après coup sans relancer — C-041

```sh
eidolon-core model-probe-inspect --directory /chemin/essais/ollama-essai-01
eidolon-core --format human model-probe-inspect \
  --directory /chemin/essais/ollama-essai-01
```

La consultation vérifie le schéma des documents, les empreintes du plan, l'ordre
et l'unicité des cas, leurs comptes et leur accord avec le rapport final. Elle
n'instancie ni Store, ni Runtime, ne lit aucune clé et ne contacte aucun serveur.
Les fichiers spéciaux/liens finaux et documents de plus de 1 Mo sont refusés.
Les noms lus sont construits depuis le corpus connu, jamais depuis un chemin
contenu dans le rapport. Le dernier composant du dossier ne peut être un lien ;
ses parents restent choisis par l'opérateur.

`CONSISTENT` (retour 0) signifie **documents cohérents**, même si le verdict
consigné est `FAILED_CASES` ou l'essai `STOPPED`. Ce n'est ni la réussite du modèle,
ni une nouvelle vérification des preuves SQLite. `reported_verdict` conserve le
verdict consigné séparément. Les champs d'autorité et de qualification restent false.

Le marqueur d'incomplétude impose `INCOMPLETE` (retour 2), y compris si un rapport
annonçant PASSED_CASES avait été écrit avant une panne finale. Rapport absent :
les bilans valides déjà enregistrés sont listés, mais `started_cases` reste null ;
un cas sans bilan peut avoir contacté le serveur. Plan absent avec marqueur :
état incomplet identifiable, sans nombre attendu inventé. Une structure incohérente
ou un document illisible produit un diagnostic constant sur stderr et un retour 2.

Lire une fois le processus de recette arrêté : ces fichiers ne constituent pas
un instantané transactionnel commun. Une modification cohérente de l'ensemble
n'est pas détectable par des empreintes locales seules. Aucun verdict ne certifie
l'identité du serveur, les poids chargés ou la vérité des mesures. La consultation
supporte le corpus et les contrats de cette version ; un futur schéma nécessite
un lecteur explicitement compatible. Elle ne migre rien et ne répare rien.
