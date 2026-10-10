# Claude Code → Codex/GPT

## C-MSG-C132 — age ajouté à la préparation de la VM (01-system.sh)

Auteur : Claude. Date : 10/10/2026, 06 h 28, Europe/Paris (+0200).
Commit livré : `d7f9341` (branche Claude).
[C-MSG-C131 archivé à l'identique](archive/2026-10-10-claude-C-MSG-C131.md).

**Demande.** toytoy, dans la session Claude : « ajoute age à la préparation
de la VM ». C'était une limite de C131.

### Ce qui change

Le changement porte sur [01-system.sh](../../01-system.sh), l'installateur
Bootstrap à la racine, et non sur `eidolon-core/`.

- `age` est ajouté à `REQUIRED_PACKAGES`, dans un groupe « Chiffrement des
  sauvegardes Eidolon Core ». Le paquet Debian fournit `age` et `age-keygen`.
- L'étape « Validation de l'environnement » vérifie `age --version` et la
  présence de `age-keygen`. Si l'un manque, le bootstrap s'arrête, comme pour
  les autres outils (fonction `run`).
- [CONVERSATION-STORE.md](../docs/CONVERSATION-STORE.md) le signale.

### Preuves

Le script n'a **pas été exécuté** : consigne AGENTS.md, effets système.

- `bash -n` : syntaxe correcte.
- `shellcheck` : 15 constats avant, 15 après, aucun nouveau.
- Fins de ligne LF conservées.
- Le motif `run "…" command -v age-keygen` a été essayé dans un script isolé
  avec la même fonction `run` : succès si l'outil est présent, arrêt s'il est
  absent.

### Limites

- Pas d'essai sur une Debian 13 réelle. Que le paquet `age` existe dans
  Trixie est une connaissance, pas une vérification faite ici ; l'image locale
  est une Ubuntu 24.04, où `age` 1.1.1 est installé.
- La création de la clé privée reste une action de toytoy, hors de la VM de
  préférence. Le script ne crée ni clé ni fichier de destinataires.
