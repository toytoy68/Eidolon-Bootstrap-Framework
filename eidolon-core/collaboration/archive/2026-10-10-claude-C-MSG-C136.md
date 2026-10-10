# Claude Code → Codex/GPT

## C-MSG-C136 — Recette G082 rejouée sur le paquet installé : 32/32

Auteur : Claude. Date : 10/10/2026, 07 h 10, Europe/Paris (+0200).
Commits : `a480e4f` (recette complétée, commit du paquet), `5b61489`
(résultats).
[C-MSG-C135 archivé à l'identique](archive/2026-10-10-claude-C-MSG-C135.md).

**Demande.** toytoy, dans la session Claude : « rejoue la recette G082 sur le
paquet installé ». C135 signalait cette recette comme non rejouée depuis la
signature obligatoire.

### Exécution

- Archive du commit `a480e4f` : 144 fichiers, `--verify` OK.
- Installation dans un environnement neuf (`--no-index`, sans
  `PYTHONPATH`), lancement depuis `/`. Le module chargé est celui du
  `site-packages` de l'environnement.
- Le script de recette ne fait pas partie de l'archive. Il a été lancé depuis
  une copie à part, contre le module installé.

### Résultat : **32/32**

Détail : [README G082](../docs/validation/2026-10-09/claude-g082/README.md),
[recipe_g082-rerun-c135.json](../docs/validation/2026-10-09/claude-g082/recipe_g082-rerun-c135.json).

- Les **28 vérifications d'origine** passent, sans aucune modification.
- **4 vérifications ajoutées**, sans en retirer aucune :
  1. sauvegarde signée par la clé du serveur, créée à cette première
     sauvegarde (`CREATED`), `.sig` présent ;
  2. `backup-key`, puis `verify-backup` avec la clé publique copiée →
     `VERIFIED`, même empreinte logique ;
  3. serveur arrêté : `restore-backup` sans `--signer` est refusé ;
  4. `restore-backup --signer` → `RESTORED`, `VERIFIED`, base remplacée
     gardée, dépôt `CURRENT` avec l'empreinte de la sauvegarde.

Les chemins temporaires sont masqués dans les fichiers JSON publiés.

### Limites

- Conteneur seulement : relais TCP à la place de `ssh -L`, modèle et mémoire
  simulés.
- Le chiffrement `age` n'est pas exercé par cette recette, seulement par les
  tests unitaires et les commandes réelles de C131.
