# C-042 — Identité et migration des pauses de recherche

Codex/GPT, 08/10/2026. Suite de la contre-revue Claude G064.

## Garantie livrée

Chaque nouvelle base de pauses porte une identité `pd-…` (schéma SQLite 2).
Le Store des missions lie cette identité et celle de la garde dans sa propre
transaction. L'ouverture du runtime refuse une autre base valide, même vide.
Un runtime déjà construit vérifie aussi l'identité avant d'entrer dans le
coordinateur ; chaque connexion d'un objet ResearchPauses vérifie son identité
dans la même transaction que sa lecture ou son écriture.

Les pauses actives ne sont ni levées ni supprimées par une migration. Les
révisions, délais, lignes d'audit, missions et configurations restent inchangés.
Les manifestes de missions conservent leur version : la liaison au Store protège
l'identité sans invalider artificiellement une mission historique compatible.

Une identité est un repère local, pas une signature ni une preuve de fraîcheur.
Une ancienne copie portant la même identité, ou une réécriture cohérente du Store
et des bases, reste hors détection. Le répertoire d'état demeure un périmètre
local de confiance ; ce mécanisme ne protège pas contre un écrivain SQL arbitraire.

## Bases existantes : revue explicite

Une base de schéma 1 reste consultable, mais le runtime exige désormais une
migration explicite avant de l'utiliser. Un ensemble entièrement créé puis
interrompu avant sa première liaison exige lui aussi cette revue ; sa simple
présence n'est pas interprétée comme une autorisation d'adoption.

Arrêter les utilisateurs de cet état, conserver une copie cohérente de l'ensemble
et examiner son origine, les pauses et les missions interrompues. Ne pas supprimer
un dossier incomplet pour faire disparaître un refus : conserver les preuves.

Depuis `eidolon-core/`, ou avec les mêmes arguments du binaire installé :

```sh
PYTHONPATH=src python -m eidolon_core --state /chemin/etat --profile research-sim research-pauses
PYTHONPATH=src python -m eidolon_core --state /chemin/etat --profile research-sim research-pauses-migrate \
  --actor operateur --reason 'Origine des trois bases et pauses conservées examinées'
PYTHONPATH=src python -m eidolon_core --state /chemin/etat --profile research-sim research-pauses
```

La migration enregistre acteur/motif dans les métadonnées des pauses et dans
la liaison du Store. Ces libellés sont déclaratifs, pas une identité humaine
authentifiée. `BOUND` signifie liaison enregistrée : `request_sent`,
`authorizes_execution` et `pauses_released` restent faux. Aucun modèle, outil,
fournisseur ou runtime de mission n'est exécuté par cette commande.

Le mode `--profile research-sim` désigne `research-fixture/pauses.sqlite3`.
Le profil `text`, conservé pour le coordinateur autonome, désigne l'ancien
emplacement `research-pauses.sqlite3`. L'inspection ouvre la base existante sans
création de schéma. La commande de migration exige `research-sim`, un Store et
un ensemble garde/pauses déjà présents ; elle n'est pas un réparateur.

## Coupures et concurrence

SQLite rend atomiques les changements **dans chaque base** ; les deux bases
ne partagent pas une transaction distribuée. L'ordre est : verrou d'écriture
Store, validation de garde, commit de l'identité et de l'audit dans les pauses,
puis commit de leur liaison dans le Store.

| Interruption | Résultat à la réouverture |
| --- | --- |
| Pendant le changement de schéma des pauses | Transaction annulée, ancien schéma et pauses conservés ; revue toujours requise |
| Après commit des pauses, avant commit Store | Identité et premier audit conservés ; runtime bloqué, même commande explicite à relancer après examen |
| Après commit Store, avant affichage du résultat | Liaison retrouvée ; répétition sans réécriture de l'audit ni des pauses |
| Création initiale partielle, garde ou pauses manquantes | Refus sans recréation automatique |

Les constructeurs et migrations concurrents sont sérialisés par le Store.
Une migration répétée ne crée pas de seconde identité. Les intents incertains
de la garde et les missions interrompues restent soumis à leur propre revue ;
migrer la base ne les réconcilie pas.

## Diagnostics

| Code | Interprétation |
| --- | --- |
| `RESEARCH_PAUSES_MIGRATION_REQUIRED` | Ensemble non encore lié, revue et migration explicites nécessaires |
| `RESEARCH_PAUSES_CHANGED` | Identité différente de celle retenue ; ne pas remplacer la liaison pour contourner le refus |
| `RESEARCH_PAUSES_MISSING` | Élément absent ; retrouver la copie cohérente, ne pas créer une base vide |
| `INVALID_RESEARCH_PAUSE_BINDING` | Métadonnée de liaison mal formée |
| `RESEARCH_BINDING_BUSY` | Écrivain concurrent ; aucune reprise ni absence d'effet déduite |
| `RESEARCH_BINDING_SCAN_TIMEOUT` | Balayage de l'historique interrompu par sa limite coopérative |
| `RESEARCH_BINDING_UNAVAILABLE` | Stockage/structure illisible ; détails SQL non reproduits dans le message public |

Les refus gardent un code 2 et ne transmettent pas de texte SQL brut. Une erreur
de commit doit toujours être examinée via l'état conservé avant toute répétition.
Les délais restent coopératifs ; aucun test de ce lot ne qualifie un disque réel,
une coupure électrique, Windows, une VM ou un fournisseur Internet.

## C-043/C-044 — parcours opérateur

`research-release` avec `--profile research-sim` vérifie désormais les deux
liaisons avant la levée : une base étrangère ou non migrée est refusée sans
modifier la pause. Le Store reste verrouillé pendant cette courte opération.
La révision et les délais continuent à être vérifiés ; aucun runtime n'est lancé.

Pour distinguer liaison correcte, migration à examiner, identité différente et
fichier manquant sans écrire dans l'état :

```sh
PYTHONPATH=src python -m eidolon_core --state /chemin/etat research-binding-inspect
PYTHONPATH=src python -m eidolon_core --state /chemin/etat --format human research-binding-inspect
```

Ce diagnostic lit les identités en mode SQLite `ro` et `query_only`, avec valeurs
bornées et vérification des fichiers. Les trois bases sont des captures séparées,
relues pour détecter les changements observables ; elles ne sont pas une capture
atomique. `BOUND` (code 0) décrit uniquement leurs identités, jamais la cohérence
de l'historique ou la possibilité de reprendre. Les autres états rendus donnent
le code 2 ; une structure illisible est refusée sans détails SQL ou chemin privé.

Depuis C-045, l'inspection de liaison et `research-pauses` refusent aussi une
base passée extérieurement en WAL, avant la connexion SQLite. Le diagnostic ne
peut ainsi créer les fichiers annexes d'un WAL fermé. Les états Core ordinaires
restent en journal classique ; aucun changement automatique de journalisation
n'est effectué. Les commandes de migration et de levée sont des opérations
d'écriture explicites, distinctes de ce contrat de consultation sans mutation.
