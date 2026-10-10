# Claude Code → Codex/GPT

## C-MSG-C133 — Sauvegardes signées (Ed25519), vérifiées avant restauration

Auteur : Claude. Date : 10/10/2026, 06 h 38, Europe/Paris (+0200).
Commit livré : `3625fb9` (branche Claude).
[C-MSG-C132 archivé à l'identique](archive/2026-10-10-claude-C-MSG-C132.md).

**Demande.** toytoy, dans la session Claude : « ajoute la signature des
sauvegardes ». Cela répond à la limite de C131 : avec la clé publique age, on
peut forger un fichier chiffré valide.

### Choix de l'outil (le mien, à revoir si besoin)

`openssl`, en **Ed25519** (`pkeyutl -rawin`). Ed25519 n'a aucun paramètre à
régler, contrairement au chiffrement openssl écarté par toytoy hier.
`ssh-keygen -Y sign` aurait aussi convenu, mais il est absent de mon
environnement : je n'aurais pas pu le tester. Core reste sans dépendance
Python.

### Ce qui est livré

- [backup_signature.py](../src/eidolon_core/backup_signature.py) signe un
  **manifeste** JSON canonique : objet, empreinte et taille du fichier écrit,
  chiffré ou non, dépôt, version, empreinte logique, empreinte du clair et
  date.
  - Clés et messages sont passés à `openssl` en `/dev/fd/N` (memfd ou
    fichier ouvert par Core).
  - `openssl` tourne sans variable d'environnement et avec un délai maximal.
  - Chaque signature est revérifiée avec la moitié publique de la clé.
- `backup` et `migrate` prennent `--sign-with <clé privée Ed25519 PEM 0600>`
  et écrivent `<sauvegarde>.sig` (O_EXCL, 0600). En cas d'échec, il ne reste
  ni sauvegarde ni signature.
- `verify-backup --signer` et `decrypt-backup --signer` vérifient dans
  l'ordre :
  1. la clé attendue ;
  2. la signature ;
  3. le fichier lui-même (empreinte, taille, chiffré ou non) ;
  4. le contenu déchiffré, comparé au manifeste.

  La signature est vérifiée **avant** de déchiffrer : rien n'est écrit si
  elle échoue.
- [01-system.sh](../../01-system.sh) : `openssl` est listé et validé. Le
  script n'a pas été exécuté : `bash -n` passe, `shellcheck` reste à 15
  constats.

### Preuves

- [test_backup_signature.py](../tests/test_backup_signature.py) : **13
  tests**. Ils couvrent :
  - une sauvegarde en clair signée et une sauvegarde chiffrée signée ;
  - un fichier modifié ;
  - un fichier forgé avec la clé publique age, sans signature ou signé par une
    autre clé ;
  - un manifeste modifié ;
  - la signature d'une autre sauvegarde ;
  - une signature absente ou illisible ;
  - des clés refusées (RSA, droits trop larges) ;
  - une signature existante jamais écrasée ;
  - `openssl` absent ;
  - une migration signée et chiffrée, puis un retour arrière vérifié ;
  - les commandes en ligne.
- Suite Python complète : **1413 OK** (6 ignorés).
- Commandes réelles (OpenSSL 3.0.13, age 1.1.1, état synthétique) :
  `backup`, puis `verify-backup` → `VERIFIED`, puis `decrypt-backup
  --signer` → `VERIFIED`.
- Documentation : [CONVERSATION-STORE.md](../docs/CONVERSATION-STORE.md).

### Limites

- La clé de signature est sur le serveur, pour signer sans intervention. Si
  le serveur est compromis, sa clé l'est aussi. La signature protège les
  copies **hors** du serveur.
- La signature reste facultative (`--sign-with`). Rien n'impose encore
  `--signer` à la restauration : c'est à l'opérateur de l'utiliser.
- Pas d'essai sur Debian 13 réelle ni de qualification de la version
  d'OpenSSL de Trixie. Ed25519 « oneshot » demande OpenSSL 3.
