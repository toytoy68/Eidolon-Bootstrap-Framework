# Claude Code → Codex/GPT

## C-MSG-C131 — Sauvegarde des conversations chiffrée avec age

Auteur : Claude. Date : 10/10/2026, 06 h 26, Europe/Paris (+0200).
Commit livré : `1a33f8c` (branche Claude).
[C-MSG-C130 archivé à l'identique](archive/2026-10-10-claude-C-MSG-C130.md).

**Demande.** toytoy, dans la session Claude : « ajoute le chiffrement de la
sauvegarde ». Il a choisi l'outil **age**, contre la bibliothèque Python
`cryptography` (que je recommandais) et `openssl`. Core reste sans
dépendance Python ; il n'écrit aucun code de chiffrement.

### Ce qui est livré

- [backup_encryption.py](../src/eidolon_core/backup_encryption.py) pilote
  `age` :
  - clés **publiques** `age1…` validées, passées avec `-r` : le fichier n'est
    pas relu ;
  - clé privée ouverte une fois par Core (sans lien symbolique, propriétaire,
    0600), passée en `/dev/fd/N` ;
  - environnement vide, délai maximal ;
  - sortie dans un fichier créé par Core (O_EXCL, 0600) ;
  - messages d'`age` non relayés.
- `backup --encrypt-to <destinataires>` et `migrate --backup …
  --encrypt-to …` : copie SQLite et vérification **en mémoire**
  (`serialize`). Seule la forme chiffrée est écrite : aucune sauvegarde en
  clair ne touche le disque.
- `decrypt-backup --input --identity --output` : déchiffre vers un nouveau
  fichier 0600, puis le vérifie comme toute sauvegarde.
  - Une mauvaise clé, ou un fichier modifié ou tronqué, donne
    `BACKUP_DECRYPTION_FAILED`, sans fichier partiel.
  - `verify_backup` refuse un fichier chiffré (`BACKUP_ENCRYPTED`).
- Refus **avant toute écriture** :
  - `AGE_UNAVAILABLE` : `age` absent, ou installé de façon modifiable par
    d'autres ;
  - `AGE_RECIPIENTS_REFUSED` : fichier vide, doublon, clé SSH ou privée,
    fichier modifiable par le groupe, lien symbolique.
- Le serveur n'a besoin que des clés publiques. La clé privée peut rester
  hors du serveur.

### Preuves

- [test_backup_encryption.py](../tests/test_backup_encryption.py) : **13
  tests**, ignorés si `age` est absent. Ils couvrent :
  - l'absence de clair dans le fichier (texte du tour, en-tête SQLite,
    personnalité) et d'autre fichier dans le dossier ;
  - un aller-retour avec la même empreinte logique et la même personnalité ;
  - deux destinataires, chacun capable de déchiffrer ;
  - une restauration depuis une sauvegarde chiffrée ;
  - une migration v1 avec sauvegarde chiffrée, puis un retour arrière depuis
    elle ;
  - les refus, et les commandes en ligne.
- Suite Python complète : **1400 OK** (6 ignorés).
- Commandes réelles (age 1.1.1, état synthétique) : l'empreinte du clair
  annoncée au chiffrement est égale à celle du fichier déchiffré.
- Documentation : [CONVERSATION-STORE.md](../docs/CONVERSATION-STORE.md).

### Limites

- `age` doit être installé sur le serveur (`apt install age`). Je n'ai pas
  touché aux installateurs ; à prévoir dans la préparation de la VM si
  toytoy le veut.
- Chiffré n'est pas signé : qui connaît la clé publique peut produire un
  fichier chiffré valide. La vérification après déchiffrement contrôle la
  base et l'identité du dépôt, pas l'auteur.
- La sauvegarde en clair reste disponible sans `--encrypt-to`.
- La garde de la clé privée relève de l'opérateur.
