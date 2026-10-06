# G035 — recette bêta : ce qui a été exécuté ici

Auteur : Claude, 06/10/2026. Fiche [C-TASK-G035](../../../../collaboration/tasks/C-TASK-G035.md).
Livrable : [BETA-ACCEPTANCE.md](../../../BETA-ACCEPTANCE.md). Base : `a9dc5e3`
(branche Claude, incluant C-009c `a8ae8fa`).

[linux-sequence.sh](linux-sequence.sh) exécute, dans le conteneur Linux de
Claude, les commandes **serveur** de la recette (S2 à S9). Elles sont copiées
du document ; seul `HOME` pointe vers un dossier temporaire.
[Sortie](linux-sequence-output.txt).

```sh
HOME=<dossier temporaire> REPO=<racine du dépôt> bash docs/validation/2026-10-06/claude-g035/linux-sequence.sh
```

| Étape | Résultat ici |
| --- | --- |
| S2 état synthétique + jeton | codes 0 ; jeton en `600` |
| S3 diagnostic `--check --format human` | 4 × `[OK]`, code 0 ; bundle à jour |
| S5 page / health / sans jeton | 200 / `eidolon-http-read/1 read_only`, `authorizes_execution = False` / 401 |
| Écoute | `127.0.0.1:8765` seulement (lu dans `/proc/net/tcp`, `ss` absent ici), pas d'IPv6 |
| S6 mission créée par la CLI pendant le service | NEW |
| S8 arrêt | `kill -INT` **sans effet** sur un serveur lancé en arrière-plan par un script (SIGINT hérité ignoré) ; `kill` (TERM) l'arrête |
| Journal du serveur | jeton absent |
| S9 retrait | dossier supprimé, rien d'autre créé |

Constat **R-G035-1** : l'arrêt d'un serveur en arrière-plan doit se faire par
`kill <PID>`, pas par Ctrl+C. C'est utile pour le lanceur G040. Rien à
corriger dans `http_api.py` : c'est le comportement de bash pour les tâches
en arrière-plan d'un shell non interactif.

## Non exécuté ici (pas de PASS fictif)

- Tunnel SSH : ni `ssh` ni `sshd` dans le conteneur.
- Windows, Edge, PowerShell.
- Debian 13 / Python 3.13 : seul Python 3.11.15 est essayé.
- Le parcours navigateur (W2 à W9) a été vérifié **sans tunnel**, en Chromium
  Linux headless, par les tests G031 et G034. Le rechargement de page (W9)
  n'est pas testé.
