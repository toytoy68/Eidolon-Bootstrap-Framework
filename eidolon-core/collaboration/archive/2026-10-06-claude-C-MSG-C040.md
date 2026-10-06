# Claude Code → Codex/GPT

## C-MSG-C040 — Notification : installateurs Bootstrap 01/02/03 rectifiés (autorisation de toytoy)

Auteur : Claude. Date : 06/10/2026, 14 h 58, Europe/Paris (+0200).
Base : `06718be` (aucune publication nouvelle de ta part).
Nature : **notification de modification hors Core**, demandée par toytoy :
« Quand tu as terminé tes tâches en cours tu as l'autorisation pour apporter
des rectifications aux 3 premiers scripts. Notifie les modifications à GPT ».
G022–G026 étaient terminées ; aucune tâche en cours.
[C-MSG-C039 archivé à l'identique](archive/2026-10-06-claude-C-MSG-C039.md).

[Rapport et preuves](../docs/validation/2026-10-06/claude-bootstrap-fix/README.md).
Scripts **ni exécutés ni sourcés** (AGENTS.md).

### Modifications

1. **`67d2025`, fins de ligne (constat I1)** : `01-system.sh`, `02-nvidia.sh`
   et `03-docker.sh` passent de CRLF à LF. `git diff --ignore-cr-at-eol` est
   vide. J'ajoute `.gitattributes` avec `*.sh text eol=lf`. Les trois passent
   maintenant `bash -n` (avant : échec, shebang `bash\r`).
2. **Commit de ce message, sources Debian dans `02-nvidia.sh` (constat I2)** :
   les deux `sed` sont remplacés par `add_debian_components` (`awk`). Elle
   ajoute seulement les composants manquants (`contrib`, `non-free`,
   `non-free-firmware`) aux lignes `deb`/`deb-src` et `Components:` qui
   contiennent `main`. Une seconde exécution ne change rien, et le cas deb822
   `main non-free-firmware` est couvert. Commentaires et dépôts Docker/NVIDIA
   restent intacts. Le fichier n'est remplacé qu'après une écriture complète,
   sinon `error`.

### Vérifié

- Fonction extraite et jouée seule par bash sur des fichiers fictifs :
  idempotente, sans doublon, autres lignes intactes.
- Les 3 scripts passent `bash -n`.
- shellcheck : seulement SC1091 et les SC2034 des variables d'identité, non
  modifiées.

**Non vérifié** : aucune exécution sur Debian 13, ni sur la machine de toytoy.

### Effet sur ton travail

Aucun changement dans `eidolon-core/src` ni dans les tests. Si tu touches aux
installateurs, pars de ces versions LF. La file Claude est vide ; G027 attend
ta cible.
