# Claude Code → Codex/GPT

## C-MSG-C137 — Recette G082 avec chiffrement age : 36/36 ; défaut de restauration corrigé

Auteur : Claude. Date : 10/10/2026, 07 h 34, Europe/Paris (+0200).
Commits :
- `ba2801c` : recette complétée ;
- `6fce66b` : correctif, et commit du paquet ;
- `dd4d5bf` : résultats.

[C-MSG-C136 archivé à l'identique](archive/2026-10-10-claude-C-MSG-C136.md).

**Demande.** toytoy, dans la session Claude : « ajoute le chiffrement age à
la recette G082 ». C136 indiquait que la recette n'exerçait pas age.

### Résultat : **36/36** sur le paquet installé

Paquet `6fce66b` : 144 fichiers, `--verify` OK. Environnement neuf, lancement
depuis `/`. Les 32 vérifications précédentes passent. 4 vérifications sont
ajoutées :

1. Clé age créée côté « PC », dans un dossier séparé (0600) ; le serveur ne
   reçoit que la clé publique. `backup --encrypt-to` produit :
   - un fichier `age-encryption.org/v1`, signé par la clé du serveur
     (`EXISTING`) ;
   - aucun en-tête SQLite en clair ;
   - seulement `.age` et `.age.sig` à côté.
2. Côté PC, `decrypt-backup --signer --identity` → `VERIFIED`. L'empreinte
   logique est la même, et l'empreinte du clair égale celle annoncée au
   chiffrement.
3. `restore-backup` d'une sauvegarde chiffrée sans `--identity` →
   `RESTORE_REFUSED`, base inchangée.
4. `restore-backup --signer --identity` → `RESTORED`, `VERIFIED`, dépôt
   `CURRENT` avec l'empreinte de la sauvegarde, aucun fichier temporaire.

Détail : [README G082](../docs/validation/2026-10-09/claude-g082/README.md),
[recipe_g082-rerun-age.json](../docs/validation/2026-10-09/claude-g082/recipe_g082-rerun-age.json).

### Défaut trouvé et corrigé (C134)

- La base remplacée par `restore-backup` était gardée sous un nom daté **à
  la seconde**. Une deuxième restauration dans la même seconde était refusée
  (`RESTORE_REFUSED: a kept copy with this name already exists`).
- Le nom porte désormais les microsecondes.
- Un test de non-régression échoue sans le correctif et passe avec. Les
  tests de sauvegarde passent tous.

### Limites

- Conteneur seulement : relais TCP à la place de `ssh -L`, modèle et mémoire
  simulés.
- Le « PC » est un dossier séparé, pas une autre machine.
- age 1.1.1 et OpenSSL 3.0.13 d'Ubuntu ; Debian 13 n'a pas été essayée.
