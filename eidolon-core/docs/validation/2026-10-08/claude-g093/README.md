# Compléments G093 — contre-vérification C-045 (G067) et C-042 (G064)

Auteur : Claude. Date : 08/10/2026, Europe/Paris. Base : `86fc533` (sources figées
par `git archive`, dont `590b7e2` pour Core). Données synthétiques, dossiers
temporaires, aucun service réel.

Les sondes de G067 et G064 ont été relancées **sans modification** sur la base
actuelle. Les fichiers ci-dessous comparent leurs sorties à celles de G067/G064.

## C-045 (G067) — confirmé, avec une limite mémoire

Sortie : [probes_g067.txt](probes_g067.txt).

| Cas G067 | Avant | Maintenant |
| --- | --- | --- |
| WAL au repos | liste OK, **crée** `-shm` et `-wal` | `READ_ONLY_WAL_UNSUPPORTED`, aucun fichier créé ni modifié |
| WAL avec écrivain | liste OK | `READ_ONLY_WAL_UNSUPPORTED` |
| Corps 16, 64, 256 Mio | liste et capture OK | `MISSION_SIZE_LIMIT` (liste et capture) |
| Corps en BLOB UTF-16 | liste et capture OK | `INVALID_MISSION_STORAGE_TYPE` |
| Détail d'événement en BLOB | `ContractError` générique | `INVALID_EVENT_STORAGE_TYPE` |
| Date d'événement vide | liste OK | `INVALID_EVENT_REFERENCE` |
| Corps 1 Mio, 100 × 2 Mio, 10⁶ événements | OK | OK, inchangé |

La **réponse** est bornée, mais pas la **lecture**. `read_mission_row` utilise
`substr(CAST(body AS BLOB),1,16 Mio + 1)` : SQLite charge le corps entier avant
de le couper.

Mesure propre ([probe_body_memory.py](probe_body_memory.py),
[résultat](probe_body_memory.txt)) : corps TEXT de 256 Mio, SQLite 3.45.1, un
processus neuf par expression.

| Expression | Pic mémoire |
| --- | --- |
| `substr(CAST(body AS BLOB),1,16777217)` (actuel) | 297 Mio |
| `length(body)` | 265 Mio |
| `octet_length(body)` | **12 Mio** |
| `typeof(body)` | 12 Mio |

Proposition, à décider par Codex (`client_sync.py` est réservé) : lire d'abord
`octet_length(body)` et refuser au-delà de la limite **avant** le `substr`.

- `octet_length` existe depuis SQLite 3.43. Le SQLite fourni avec Python sous
  Windows n'a pas été vérifié ; une version plus ancienne refuserait la
  requête.
- La même remarque vaut pour `MAX_EVENT_BYTES`.

**Correction de ma propre preuve G067.** Les colonnes `max_rss_mib` de la série B
sont faussées. Ce pic est hérité du processus parent, qui venait d'écrire le
corps de test : `ru_maxrss` se conserve à travers fork/exec. Elles ne mesurent
pas la lecture. La mesure ci-dessus remplace ces chiffres.

## C-042 (G064) — confirmé

Sortie : [probes_g064.txt](probes_g064.txt).

| Cas G064 | Avant | Maintenant |
| --- | --- | --- |
| I5 pauses remplacées par une base vide valide | **construit** (pause perdue) | `RESEARCH_PAUSES_CHANGED` |
| I6 arrêt avant la liaison | réouverture construite, liaison faite en silence | `RESEARCH_PAUSES_MIGRATION_REQUIRED`, liaison toujours absente |
| I9 balayage historique trop long | `OperationalError interrupted` | `RESEARCH_BINDING_SCAN_TIMEOUT` |
| L8 texte de liste.md | « Cohérence vérifiée » | « Cohérence vérifiée **à la génération** » |
| L5 8 index simultanés | 8 OK | 1 `ARCHIVE_INDEX_BUSY`, 7 OK ; `liste.md` complet |

L5 vient du verrou non bloquant de l'index. Le refus est explicite et le fichier
reste complet. Ce n'est pas une régression, mais l'appelant doit réessayer
lui-même.

I6 était le seul cas sans issue montrée. La sonde
[probe_i6_migration.py](probe_i6_migration.py) en donne le
[résultat](probe_i6_migration.txt) :

1. sans migration : `RESEARCH_PAUSES_MIGRATION_REQUIRED` ;
2. migration sans motif : `INVALID_PAUSE_REVIEW` ;
3. migration avec opérateur et motif : `BOUND`, avec `authorizes_execution` à
   faux, aucune requête envoyée, aucune pause levée ;
4. la réouverture fonctionne ensuite, et une mission synthétique se termine en
   `SUCCEEDED` ;
5. une seconde migration répond `BOUND` sans rien réécrire. L'opérateur et le
   motif de ce second appel ne sont **pas** enregistrés. C'est acceptable, mais
   à documenter.

Note de méthode : l'outil de recherche tourne dans un processus « spawn » qui
réimporte le script appelant. Une sonde sans garde `__main__` se rejoue dans
chaque exécutant. Ma première exécution de `probe_i6_migration.py` l'a montré,
et elle a été corrigée.

## Limites

- Linux, root, SQLite 3.45.1. Windows et les versions de SQLite plus anciennes ne
  sont pas testés.
- La migration adopte toute base de pauses présente dans un Store non lié. Le
  contrôle repose sur la revue de l'opérateur, comme le prévoit C-042.
- Les temps de L5 et de D dépendent de l'ordonnancement.
