# Préparer une restauration pour revue — C-008d

Auteur : Codex/GPT, 06/10/2026, Europe/Paris. Base `1489898`.
Statut : copie locale isolée implémentée et testée, Python 3.11+/POSIX,
bibliothèque standard. **Ce lot ne réactive pas une sauvegarde.** Il produit
une copie historique bloquée pour permettre son examen avant une future reprise.

## Usage

Depuis eidolon-core/ :

```sh
PYTHONPATH=src:. python -m examples.recovery_demo --format human
PYTHONPATH=src:. python -m examples.recovery_demo
PYTHONPATH=src:. python -m unittest tests.test_recovery -v
```

La démo crée un accord APPROVED pour un redémarrage fictif, prépare une copie,
y retrouve cet accord historique puis vérifie que Core refuse de démarrer sur
la copie. Source inchangée et zéro redémarrage fictif. Aucun effet externe.

Pour une base de mission existante, sur une destination **neuve**, en dehors
du répertoire source, dont le parent existe déjà :

```sh
PYTHONPATH=src python -m eidolon_core recovery-prepare --source /tmp/eidolon-source/missions.sqlite3 --destination /tmp/eidolon-review --actor operateur-local --reason "Examen avant reprise"
PYTHONPATH=src python -m eidolon_core --state /tmp/eidolon-review recovery-inspect
PYTHONPATH=src python -m eidolon_core --state /tmp/eidolon-review recovery-inspect --mission-id m-ID
```

JSON par défaut. --format human réutilise la présentation ECT et ATTENTION.
Code 0 signifie copie/inspection terminée, jamais autorisation d'exécution.
Code 2 indique refus/erreur. Après une réponse perdue, inspecter la destination ;
ne pas écraser son contenu ni réémettre automatiquement la préparation.

## Copie cohérente et publication

prepare_review(source_database, destination, actor=..., reason=...) ouvre la
source SQLite en mode ro/query_only et épingle une transaction de lecture. Il
valide user_version=1, les quatre tables de cette tranche, l'identité du Store
et l'absence de marqueur de restauration antérieur. Les bases anciennes sans
command_receipts ne sont pas migrées en place : elles sont refusées ici.

La copie utilise l'API SQLite backup, **pas une copie brute de missions.sqlite3**.
Les pages du WAL présentes dans la capture sont donc incluses. Une écriture
concurrente commise après l'ouverture de la capture reste hors de cette copie,
sans mélanger les générations de lignes. Ce comportement est testé sous WAL.
Sans WAL, une lecture peut retarder un écrivain ; aucun arrêt automatique du
processus source n'est tenté. L'outil n'effectue aucune mutation SQL sur la
source et ne prétend pas figer les effets de ses outils ou les autres bases.

La destination est créée avec des droits 0700. Un fichier
RECOVERY-REVIEW-ONLY y bloque immédiatement les accès Core ordinaires pendant
la préparation. Le fichier SQLite se nomme d'abord review.pending.sqlite3.
Après backup, contrôle quick_check et empreinte SHA-256, une transaction :

- remplace store_id par une nouvelle identité s-UUID ;
- ajoute recovery_mode=REVIEW_ONLY ;
- conserve un rapport de provenance avec source_store_id, horodatage,
  recovery_id, acteur/motif et empreinte de la capture avant ces changements.

Les lignes missions, events et command_receipts restent intactes. Un ancien
accord ne devient pas PENDING ou APPROVED de nouveau ; il reste simplement une
observation historique. Aucune proposition sans décision n'expire et aucune
interprétation mémoire n'est promue en fait. Aucun moteur mémoire n'est copié.

Le fichier est fermé et synchronisé, puis publié sous missions.sqlite3 par
lien dur atomique refusant une destination existante. Le nom temporaire est
ensuite retiré et le dossier synchronisé. Tout échec peut laisser un répertoire
incomplet pour diagnostic ; aucun nettoyage destructif automatique n'est fait.
Avant publication, le marqueur de dossier interdit d'y créer un Store neuf.
Après publication, le marqueur **et** la garde inscrite en base interdisent
l'ouverture ordinaire. Une perte de réponse après publication laisse une copie
consultable via recovery-inspect et toujours bloquée.

Limites de volume : 256 Mio physiques/logiques avant backup, vérification de
la taille annoncée pendant backup ; budget de 30 secondes vérifié aux rappels
par blocs de 256 pages. Ce budget est coopératif, pas une échéance dure pour
l'ensemble de l'opération (intégrité, hash, fsync et inspection inclus).

## Garde d'exécution et consultation historique

Store.connection vérifie à chaque ouverture le marqueur de dossier, puis la
présence de recovery_mode en base **avant sa migration additive**. Toute
valeur de ce champ bloque, y compris une valeur inconnue. Un Store déjà construit
qui pointe vers une copie gardée est également refusé à sa prochaine connexion.

Cela bloque les chemins Core ordinaires : création, run, décision, annulation,
réconciliation, lecture ClientSync et consultation de reçu. Une commande avec
l'ancienne **ou la nouvelle** identité ne peut pas muter cette copie. Le CLI
refuse avant de construire ActionRuntime et son monde synthétique. Le protocole
client-sync/1 reste inchangé : aucune nouvelle capture à consommer dans G012.
Le client ne reçoit pas un historique maquillé en état vivant.

inspect_review et recovery-inspect ouvrent exclusivement en lecture seule,
sans Store ni Runtime. Le rapport eidolon-recovery-review/1 indique :

- historical_only=true, execution_authority=false,
  external_effects_reconciled=false et artifacts_restored=[mission_sqlite_only] ;
- identités source/nouvelle, empreinte de la capture, provenance de préparation ;
- nombres de missions, événements et reçus ; répartition des statuts historiques ;
- sur demande d'une mission : statut/phase/révision/annulation/accord/appels
  **au moment de la capture**, sans requête, contexte mémoire ni résultat brut.

Les reçus historiques ne sont pas servis comme accusés de commandes de la
nouvelle identité. Ils restent dans les lignes SQLite conservées, pour une
future revue plus détaillée. Le rapport n'est ni une signature ni une preuve
contre un opérateur pouvant modifier directement la base.

## Diagnostics de stockage

La CLI traite désormais les exceptions SQLite par STORAGE_UNAVAILABLE,
code 2, sans traceback ni message SQL brut. Le nom de classe d'erreur reste
présent pour diagnostic. Le texte conserve l'incertitude et demande une
consultation d'état/reçu avant réémission : une erreur n'est pas une preuve
que le commit n'a pas eu lieu. Cette protection couvre aussi les CLI de
commandes des tranches précédentes. Les API Python internes conservent leurs
exceptions SQLite d'origine.

## Ce qui reste à faire

- Aucun mécanisme de réactivation ni d'exception à cette garde. Préparer un
  protocole explicite de revue des missions, accords consommés/anciens, effets
  externes et reçus manquants avant un futur retour en exploitation.
- La copie couvre une seule base de missions, pas simulation.sqlite3, les baux
  et reçus des enfants, fichiers joints, index ou Memory Engine. Elle ne constitue
  pas une sauvegarde complète de Core et ne réconcilie aucun effet.
- Aucun détecteur universel de rollback. Recopier manuellement une ancienne
  base sans passer par cet outil n'ajoute pas cette garde. Une copie lancée avec
  un ancien binaire peut ignorer les marqueurs ; ne jamais l'utiliser ainsi.
- Ancien runtime/ouvrier ailleurs potentiellement encore actif : l'outil ne
  le contacte et ne l'arrête pas. La revue doit en tenir compte avant reprise.
- Stockage local POSIX seulement : pas de qualification des liens durs/fsync
  sur NAS, de coupure électrique ou de recette VM/Windows. Le dossier cible
  doit être réservé à cette opération, pas utilisé simultanément par un autre
  programme. Les manipulations SQL brutes sont hors des interfaces protégées.

[Preuves](validation/2026-10-06/codex-recovery-review/README.md).
