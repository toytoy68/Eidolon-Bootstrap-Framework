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
source SQLite en mode ro/query_only et valide dans une courte transaction de
lecture, libérée avant la copie incrémentale. Il
valide user_version=1, les quatre tables de cette tranche, l'identité du Store
et l'absence de marqueur de restauration antérieur. Les bases anciennes sans
command_receipts ne sont pas migrées en place : elles sont refusées ici.

La copie utilise l'API SQLite backup, **pas une copie brute de missions.sqlite3**.
Les pages du WAL présentes dans la capture sont donc incluses. Une écriture
concurrente peut faire recommencer la copie : la capture finale est cohérente,
mais n'est plus promise à l'instant de la validation initiale. Des commits
postérieurs à cette validation peuvent donc y figurer. L'identité, le schéma,
la garde et la taille logique sont revérifiés dans la copie terminée, avant sa
publication. Une identité différente donne RECOVERY_SOURCE_CHANGED.

Suivi G017 : la transaction épinglée précédente pouvait faire échouer un écrivain
après ses cinq secondes d'attente, en mode DELETE. Elle est maintenant libérée
avant backup. Les verrous de lecture sont ceux des étapes SQLite, pas de toute
la copie ; aucune garantie de latence dure ni d'absence de contention sur un
vrai disque n'est annoncée. Une activité continue peut empêcher la copie de
finir : son budget coopératif reste appliqué et la destination reste bloquée.
Le mode de journal source est conservé ; aucun arrêt automatique du processus
source n'est tenté. L'outil n'effectue aucune mutation SQL sur la
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
Avant publication, le marqueur de dossier et la présence du fichier
review.pending.sqlite3 interdisent chacun d'y créer un Store neuf. Retirer
manuellement le marqueur ne suffit plus à ouvrir un état vide à côté de la
copie incomplète. Cela ne protège pas contre une manipulation arbitraire de tous
les fichiers ni le renommage manuel d'une copie avec un ancien binaire.
Après publication, le marqueur **et** la garde inscrite en base interdisent
l'ouverture ordinaire. Une perte de réponse après publication laisse une copie
consultable via recovery-inspect et toujours bloquée.

Limites de volume : 256 Mio physiques/logiques avant backup, vérification de
la taille annoncée pendant backup ; budget de 30 secondes vérifié aux rappels
par blocs de 256 pages. Ce budget est coopératif, pas une échéance dure pour
l'ensemble de l'opération (intégrité, hash, fsync et inspection inclus).

## Garde d'exécution et consultation historique

Store.connection vérifie à chaque ouverture le marqueur de dossier ou le fichier
review.pending.sqlite3, puis la présence de recovery_mode en base **avant sa migration additive**. Toute
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
- pour les nouvelles copies, capture_semantics=sqlite-online-backup : la capture
  peut inclure des commits après validation initiale (anciens rapports conservés) ;
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

Un dossier de préparation sans missions.sqlite3 mais avec marqueur ou fichier
en attente donne désormais RECOVERY_INCOMPLETE lors de l'inspection. Aucun
fichier n'est créé, supprimé ou réactivé par ce diagnostic.

## Références et validation du suivi G017

Documentation officielle SQLite consultée le 06/10/2026 :
[Online Backup API](https://www.sqlite.org/c3ref/backup_finish.html),
[verrous et redémarrages](https://www.sqlite.org/backup.html#file_and_database_connection_locking).
Les étapes libèrent leur verrou source entre appels ; un commit concurrent peut
relancer la copie. Le test utilise un véritable écrivain séparé lancé entre
étapes, sous DELETE et WAL. Il vérifie mission et événement liés dans la copie,
la garde persistante, l'identité modifiée pendant copie et la borne de reprise.
Les délais de progression sont simulés ; aucune mesure de disque réel.
[Preuves du suivi](validation/2026-10-06/codex-recovery-followup/README.md).

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


## C-025 — validation du lecteur et bornes d’inspection

Le lecteur exige désormais les invariants du rapport avant de l’afficher :
`REVIEW_ONLY`, historique uniquement, autorité false, effets non réconciliés,
artefacts limités à la base de missions. Un rapport incohérent, de mauvais type
ou avec champs inattendus est refusé par code constant, sans réémettre ses
valeurs. Les anciens rapports sans `capture_semantics` restent lisibles.
Les JSON dupliqués, non finis et non UTF-8 sont refusés.

L’inspection parcourt au plus 10 000 missions, 16 Mio par corps, 32 Kio pour
les métadonnées de rapport et 256 Mio logiques pour la base. Un budget de deux
secondes couvre coopérativement la VM SQLite et les passages Python ; l’attente
sur verrou SQLite est limitée à deux secondes. Le stockage physique peut encore
bloquer hors de cette garantie. Dépassement : `RECOVERY_INSPECTION_LIMIT`, sans
rapport partiel. Aucun changement de la copie ni autorisation de reprise.

Une préparation peut déjà avoir publié sa copie avant que son inspection finale
échoue : conserver le dossier gardé, ne pas répéter la préparation sur lui.
L’indisponibilité du rapport n’invalide pas la garde de restauration et n’autorise
pas sa suppression. Les grands historiques nécessiteront un futur inventaire
paginé ; ce lot ne tronque pas leurs comptes pour paraître réussi.
Les annotations acteur/raison et identifiants d’appel restent des textes fournis ;
la validation ne les authentifie pas et n’en fait pas un rapport public anonymisé.
[Preuves et limites](validation/2026-10-07/codex-recovery-inspection/README.md).
