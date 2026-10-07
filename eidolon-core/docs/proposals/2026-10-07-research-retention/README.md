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
