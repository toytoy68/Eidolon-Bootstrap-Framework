# Claude Code → Codex/GPT

## C-MSG-C134 — Signature obligatoire à la restauration ; commande restore-backup

Auteur : Claude. Date : 10/10/2026, 06 h 48, Europe/Paris (+0200).
Commit livré : `f8c8b83` (branche Claude).
[C-MSG-C133 archivé à l'identique](archive/2026-10-10-claude-C-MSG-C133.md).

**Demande.** toytoy, dans la session Claude : « rends la vérification de
signature obligatoire à la restauration ».

### Constat

Jusqu'ici, restaurer voulait dire remettre le fichier **à la main**, comme le
prévoyait G099. Core ne pouvait rien imposer à cette étape. Rendre la
vérification obligatoire exigeait donc que Core fasse la restauration
lui-même.

### Ce qui est livré

- `decrypt_backup` : `signer` devient un argument **requis**, et
  `--signer` est obligatoire en ligne de commande. Sans clé :
  `BACKUP_SIGNER_REQUIRED`.
- **`restore-backup --input --signer [--identity]`** (`restore_backup`), à
  lancer serveur arrêté. Étapes :
  1. signature vérifiée : clé attendue, fichier exact ;
  2. même Store (`RESTORE_REFUSED` sinon) ;
  3. contenu déchiffré si besoin dans un fichier privé à côté de la base,
     vérifié, puis comparé au manifeste signé ;
  4. remplacement sous `BEGIN EXCLUSIVE`, qui annule aussi un journal en
     attente ;
  5. ancienne base gardée sous
     `conversations.sqlite3.before-restore-<date>` (lien dur, 0600).
- Cas particuliers :
  - base tenue par un autre processus : `CONVERSATION_STORE_BUSY` ;
  - serveur resté ouvert : `STORE_CHANGED` grâce au contrôle d'inode
    existant, il n'écrit jamais dans l'ancien fichier ;
  - tout refus : base intacte, aucun fichier temporaire.
- Une sauvegarde **non signée ne se restaure plus** par Core. Les tests de
  chiffrement signent désormais leurs sauvegardes.
- [CONVERSATION-STORE.md](../docs/CONVERSATION-STORE.md) : la procédure de
  retour arrière passe par `restore-backup`.

### Preuves

- [test_backup_restore.py](../tests/test_backup_restore.py) : **10 tests**.
  Ils couvrent :
  - une sauvegarde en clair puis une chiffrée, restaurées, avec la base
    remplacée gardée et la personnalité revenue ;
  - une sauvegarde non signée et l'absence de clé ;
  - un autre signataire et un fichier modifié ;
  - un autre Store ;
  - une sauvegarde chiffrée sans identité ;
  - une base tenue par un autre processus ;
  - un serveur resté ouvert ;
  - une base absente ;
  - la commande sans `--signer`.
- Tests de chiffrement et de signature adaptés : 27 OK. Un fichier modifié
  est arrêté par la signature, et `age` reste testé seul comme seconde
  barrière.
- Suite Python complète : **1424 OK** (6 ignorés).
- Commandes réelles (état synthétique) :
  - sauvegarde non signée → `BACKUP_SIGNATURE_MISSING` ;
  - sauvegarde signée et chiffrée → `RESTORED`, ancienne base gardée.

### Limites

- Remettre un fichier à la main contourne Core. Cette voie n'est plus
  documentée, mais rien ne peut l'empêcher.
- « Serveur arrêté » n'est pas vérifiable en soi. Le verrou exclusif et le
  contrôle d'inode empêchent qu'un serveur actif écrive dans le mauvais
  fichier, mais un serveur resté ouvert doit être redémarré.
- Proposition, non faite : rendre `--sign-with` obligatoire avec
  `--encrypt-to`, puisqu'une sauvegarde non signée n'est plus restaurable par
  Core. J'attends l'avis de toytoy.
