# Proposition G057 — rotation explicite de la garde de recherche

Auteur : Claude, 07/10/2026. Fiche [C-TASK-G057](../../../collaboration/tasks/C-TASK-G057.md).
Traite G051-1 (plafond de 256 recherches sans sortie) et G051-2 (verrou
absent). Statut : **prototype isolé**.

- `research_guard.py` et le reste de Core ne sont pas modifiés.
- Le prototype [rotation.py](rotation.py) n'est importé par rien.
- Il est testé sur des journaux synthétiques de schéma 2, créés par la garde
  actuelle (C-019, avec `cleaned_queries`) et contenant un lien
  `operation_id` (C-021).

```sh
python3 docs/proposals/2026-10-07-research-retention/probes_g057.py <copie>/eidolon-core/src
```

Sortie : [probes.txt](probes.txt), sur une copie de `8c5f649`.

## Contrat proposé

### Ce que fait une rotation

1. Elle prend le **verrou de la garde**, sans attendre. S'il est tenu :
   `WEB_RESEARCH_IN_FLIGHT`. S'il est absent : `RESEARCH_LOCK_MISSING`. Le
   verrou n'est **jamais recréé** automatiquement (G051-2 : la reprise reste
   un geste documenté de l'opérateur).
2. Elle **vérifie** les archives existantes (voir plus bas), puis valide le
   journal avec la garde **inchangée**, sur une copie fantôme. Toute
   incohérence du journal ou de l'historique nettoyé → refus.
3. Elle refuse s'il reste une intention (`INTENT`) : `WEB_RESEARCH_UNCERTAIN`.
4. Elle choisit les **K plus anciennes** recherches terminées (`COMPLETED`
   ou `RESOLVED_UNKNOWN`), K étant donné explicitement par l'opérateur.
   - **Aucune règle d'âge et aucune durée de rétention** : la décision
     revient à toytoy.
   - Une recherche liée à une mission (`operation_id`) est **exclue**, sauf
     si l'opérateur libère cet identifiant explicitement. C'est
     nécessaire : C-021 relit `report_sha256` pour vérifier un résultat
     `RETURNED` après une reprise. L'âge ne dit pas si la mission est
     finie.
5. Elle écrit **un** fichier d'export privé (0600, dans un dossier 0700
   distinct du journal), en trois temps :
   - un fichier `.partial` est créé, écrit, puis synchronisé (`fsync`) ;
   - il est publié par `link()`, qui **échoue si le nom existe déjà** ;
   - le dossier est synchronisé.

   L'export contient, **octet pour octet**, chaque recherche choisie : sa
   fiche, ses événements d'audit et sa ligne `cleaned_queries`. Le lien du
   descripteur (`query_history_sha256`, `operation_id`) reste donc
   vérifiable.
6. **Une transaction SQLite** retire exactement ces lignes et ajoute une
   entrée de chaîne dans la table `archives` :
   - numéro ;
   - nom et SHA-256 de l'export ;
   - empreinte de la chaîne précédente ;
   - empreinte des identifiants retirés.

   Le journal passe en **schéma 3**. La garde actuelle le refuse
   (`UNSUPPORTED_RESEARCH_GUARD`) : il n'y a pas de rétrogradation
   silencieuse. L'intégration du schéma 3 revient à Codex.

Elle ne fait **rien d'autre** :

- aucun appel réseau (`request_sent=false`) ;
- aucune libération de pause ;
- aucune relance ;
- aucune suppression du journal actif.

### Vérification (copie, restauration, altération)

| Situation | Résultat |
| --- | --- |
| Export modifié | `ARCHIVE_ALTERED` |
| Export supprimé | `ARCHIVE_MISSING` |
| Recherche archivée revenue dans le journal | `ARCHIVED_RUN_REAPPEARED` |
| Un seul export inconnu, qui prolonge la chaîne | `UNCOMMITTED_EXPORT` : panne entre publication et validation, ou journal revenu **une** rotation en arrière (indiscernables) |
| Plusieurs exports inconnus, ou qui ne prolongent pas la chaîne | `JOURNAL_ROLLED_BACK` |
| Fichier `.partial` restant | `PARTIAL_EXPORT_PRESENT` |

`resume_uncommitted` termine une rotation interrompue. Il ne valide
**que si** l'export prolonge la chaîne **et** correspond octet pour octet au
journal. Il ne réexporte jamais.

## Résultats des sondes

| Cas | Résultat |
| --- | --- |
| Rotation de 3 sur 7 | 3 retirées ; export 0600 ; textes nettoyés identiques à `read_history` avant rotation ; vérification OK |
| Rotation « tout le reste » | 3 de plus ; **la recherche liée à la mission reste** |
| Mission libérée explicitement | retirée ; chaîne de 3 exports |
| Intention en cours | refus `WEB_RESEARCH_UNCERTAIN` |
| Verrou tenu par une autre recherche | refus `WEB_RESEARCH_IN_FLIGHT` |
| Verrou absent | refus `RESEARCH_LOCK_MISSING` ; verrou **non** recréé |
| Dossier d'archive en 0755 | refus |
| Journal incohérent (événement supprimé) | refus `INVALID_RESEARCH_AUDIT` ; journal intact |
| Panne après écriture partielle | journal intact ; `.partial` laissé ; toute rotation refusée tant qu'il reste |
| Panne après publication | journal intact ; `UNCOMMITTED_EXPORT` ; **reprise** → validé, vérification OK |
| Panne dans la transaction | rollback SQLite ; même reprise OK |
| Panne après le commit | état final correct, vérification OK |
| Journal restauré d'avant 2 rotations | `JOURNAL_ROLLED_BACK` ; nouvelle rotation refusée |
| Export modifié, puis supprimé | `ARCHIVE_ALTERED`, puis `ARCHIVE_MISSING` |
| Entrée de chaîne supprimée du journal | `UNCOMMITTED_EXPORT` ; reprise refusée `EXPORT_DOES_NOT_MATCH_JOURNAL` |

## Limites et décisions ouvertes

- **Copie du journal sous une autre racine** : non détectée. La chaîne ne
  sait pas *où* vit le journal. C'est la même limite que celle de la garde.
- Restaurer un journal d'**une** rotation en arrière ressemble à une panne :
  la reprise le remet dans l'état archivé, ce qui reste correct.
- Supprimer **ensemble** le journal et les exports n'est pas détectable
  sans référence extérieure (signature, empreinte hors machine).
- Le `.partial` laissé par une panne contient une copie de données
  privées, encore présentes dans le journal. Le prototype exige une
  suppression manuelle. Faut-il une commande dédiée ?
- Les exports sont privés et **non chiffrés**, comme le journal.
- La validation passe par une copie fantôme de schéma 2, faute de schéma 3
  dans la garde. Une intégration réelle validerait directement.
- Décisions pour toytoy/Codex :
  - combien en garder ;
  - où ranger les exports ;
  - si la rotation reste manuelle ;
  - comment une mission déclare qu'elle n'a plus besoin de sa preuve.
- Linux et POSIX seulement, comme la garde.

## Décision reçue le 07/10/2026

toytoy : « Archivage automatique. Garder une centaine de recherche en mémoire .
Archives dans un dossier avec liste.md accessible depuis l'appli bureau ? »
Voir [C-D17](../../CADRAGE-DECISIONS-2026-10-05.md). Conséquences pour ce
prototype :

- le déclenchement devient automatique, par exemple à la fin d'une recherche
  qui dépasse le seuil d'environ 100 ;
- un `liste.md` dans le dossier d'archives, régénéré à chaque rotation ;
- une lecture en consultation seule par Core, pour l'application bureau.

Tous les refus et toutes les garanties ci-dessus restent valables.

## Version 2 du prototype — G062, 07/10/2026

Fiche [C-TASK-G062](../../../collaboration/tasks/C-TASK-G062.md), après la
[contre-revue Codex](../../validation/2026-10-07/codex-g057-review/README.md).
La version 1 reste dans Git (`21d121a`). Toujours isolé : aucun fichier
Core n'est modifié.

```sh
cd docs/proposals/2026-10-07-research-retention
G062_SRC=<copie>/eidolon-core/src python3 -m unittest tests_g062 -v
```

### Corrections

| Défaut (Codex) | Correction | Assertion |
| --- | --- | --- |
| reprise acceptée avec `cleaned_query` nul ou modifié dans l'export | l'export doit être **exactement** les lignes du journal : fiche, événements **et** `cleaned_queries`. Une recherche liée à un historique sans texte exporté est refusée | `EXPORT_DOES_NOT_MATCH_JOURNAL`, rien retiré |
| reprise acceptée avec un `guard_id` étranger | identité de garde comparée à `metadata` | idem |
| reprise acceptée alors qu'une archive précédente manque | **toute la chaîne** est revalidée avant chaque retrait (présence, privé, borne, SHA-256, identité) | `ARCHIVE_MISSING`, ou `ARCHIVE_ALTERED` si modifiée |
| copie brute du fichier SQLite (sans le WAL) | **sauvegarde en ligne** SQLite sous le verrou. Les lignes sont relues dans la transaction de retrait et comparées de nouveau | test WAL : la copie brute voit 7 recherches, la sauvegarde 8 |
| lecture non bornée | export ≤ 32 Mio, ≤ 4096 exports, ≤ 256 recherches par export. JSON strict (clé dupliquée, `NaN`). Pas de lien symbolique, noms de fichiers de la chaîne contrôlés. Descripteurs fermés sur **chaque** refus (vérifié) | 4 assertions |

Les contre-sondes de Codex, rejouées sur la v2, refusent les 3 cas sans
rien retirer : [sortie](codex-counterprobes-v2.jsonl). Les sondes G057
v1 donnent les mêmes états : [sortie](probes-v2.txt). Assertions :
**13/13** ([sortie](tests_g062.txt)).

### Archivage automatique (C-D17)

`auto_rotate(journal, archives, target=100, terminal_operations=…)` :

- **Quand** : juste **après** qu'une recherche est `COMPLETED`, hors de
  `guard.execute`, sous le verrou de la garde. Jamais pendant une
  intention.
- **Seuil** : 100 recherches actives (lecture de « une centaine »). Les plus
  anciennes recherches terminées partent au-delà.
- **Missions** : une recherche liée à une mission n'est archivée que si
  l'appelant déclare cette mission **terminée** (`terminal_operations`,
  fourni par le Store). Si ces recherches protégées gardent le journal
  au-dessus de 100, le dépassement est **rapporté** (`above_target`).
- **Pannes** :
  - un `.partial` restant est supprimé : il n'est jamais référencé et ses
    données sont encore dans le journal ;
  - un export non validé qui prolonge la chaîne est **terminé** selon les
    règles de reprise ;
  - tout autre écart (archive manquante ou modifiée, journal restauré) est
    refusé et rapporté.
- **Refus** : un refus d'archivage **ne dit rien** de la recherche qui
  vient d'avoir lieu. Son résultat et ses effets restent ceux de son
  rapport.

`liste.md` et le lecteur des exports relèvent de **Codex (C-028)**. Le
prototype n'en crée pas de seconde version.

Exigence proposée : `liste.md` porte l'empreinte de tête de chaîne qu'il
décrit. Si elle diffère de celle du journal (panne entre le commit et la
régénération), la liste est **périmée** : elle est régénérée, ou affichée
comme telle, jamais présentée comme à jour.

### Changements de format avant intégration

- l'export gagne `released_operations` (missions libérées par l'appelant) ;
- `verify` exige `guard_src` et renvoie aussi `active` ;
- `resume_uncommitted` prend `operations` ;
- `auto_rotate` est nouveau ;
- le schéma 3 (table `archives`) reste à intégrer par Codex.

## Version 3 du prototype — G063, 07/10/2026

Fiche [C-TASK-G063](../../../collaboration/tasks/C-TASK-G063.md), après la
[seconde contre-revue Codex](../../validation/2026-10-07/codex-g062-followup/README.md).
La v2 reste dans Git (`42d6dde`).

```sh
cd docs/proposals/2026-10-07-research-retention
G062_SRC=<copie>/eidolon-core/src python3 -m unittest -v tests_g063 tests_g062
```

| Défaut | Correction |
| --- | --- |
| écriture courte acceptée (`os.write` ne renvoie que la moitié) : 2 recherches retirées, export illisible | `_write_all` boucle jusqu'au dernier octet. 0 octet écrit ou erreur système (`ENOSPC`…) → `ARCHIVE_WRITE_FAILED` ; seul le partiel **créé par cet appel** (`O_EXCL`) est retiré, et rien n'est touché dans le journal |
| contenu publié non relu | après publication, le fichier est **relu** : les octets doivent être exactement ceux écrits, sinon `ARCHIVE_PUBLISH_MISMATCH`. L'export est gardé pour revue, rien n'est retiré |
| `.partial` inconnu supprimé avant le refus `WEB_RESEARCH_UNCERTAIN` | le refus d'intention passe **avant** tout fichier. Un partiel n'est supprimé que s'il est **prouvé redondant** : notre motif de nom, fichier privé ordinaire, JSON complet et strict, même garde, index suivant de la chaîne, et toutes ses recherches encore présentes octet pour octet dans le journal. Sinon il est gardé, avec le refus `PARTIAL_EXPORT_PRESENT` |
| FIFO : `_read_private` pouvait bloquer | ouverture `O_NONBLOCK`, puis refus avant toute lecture (`NOT_PRIVATE`) ; un partiel FIFO est gardé et refusé, sans attente |

Assertions : **21/21** (8 nouvelles + les 13 de G062), [sortie](tests_g063.txt).
Après **chaque** cas, chaque recherche d'origine se retrouve identique,
soit dans le journal, soit dans un export **lisible** :

- écriture courte complétée, export lisible, vérification OK ;
- 0 octet et `ENOSPC` : rien retiré, ni export ni partiel restant ;
- export publié altéré : refus, rien retiré, la reprise est aussi refusée ;
- partiel inconnu avec intention incertaine : gardé ;
- partiel étranger ou tronqué : gardé, refus ;
- partiel complet et redondant : retiré, puis rotation normale ;
- pannes aux 4 frontières : données conservées, puis deux `auto_rotate`
  successifs **idempotents** (le second ne fait rien) ;
- FIFO comme export ou comme partiel : aucun blocage (délai de 5 s
  vérifié), refus.

Contre-sondes Codex rejouées sur la v3 ([sortie](codex-followup-v3.jsonl)) :

- écriture courte : export **lisible**, les 2 recherches archivées sont
  conservées ;
- partiel inconnu **gardé** ;
- les 3 anciens cas sont toujours refusés sans retrait.

Sondes G057 inchangées par rapport à la v2 ([sortie](probes-v3.txt)).

### Limites restantes

- Un partiel tronqué par une vraie panne pendant l'écriture reste en
  place et bloque l'archivage automatique : sa provenance ne peut être
  établie. Il faut une revue manuelle, puis sa suppression.
- `fsync` et `link` supposent un système de fichiers local POSIX. Ni NFS,
  ni coupure de courant réelle.
- Une réécriture cohérente du journal **et** des exports reste hors
  détection.
