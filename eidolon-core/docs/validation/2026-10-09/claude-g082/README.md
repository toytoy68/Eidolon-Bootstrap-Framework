# G082 — Plan de bêta serveur et PC actualisé (recette opérateur synthétique)

Auteur : Claude. Date : 09/10/2026, Europe/Paris. Fiche : C-TASK-G082.
Commit du paquet : `aa245e11692e5e974d98c7d5445766bbcdbed776`. Archive de 131
fichiers, `--verify` OK ([construction](bundle-build.json),
[vérification](bundle-verify.json)). Installée dans un environnement neuf
(`--no-index`, sans `PYTHONPATH`), recette lancée depuis `/`.
**Conteneur seulement : ni VM100, ni Windows, ni vrai SSH.**

## Résultat exécuté

[recipe_g082.py](recipe_g082.py) → [recipe_g082.json](recipe_g082.json) : **28/28**.

| Étape | Vérifié dans le conteneur |
| --- | --- |
| S2 état et jeton | mission de démonstration `SUCCEEDED` avec rappel mémoire **simulé** (`synthetic-note@1`, non vérifié) ; jeton 0600 jamais affiché |
| S2 conversation | appairage ; profil de dialogue `recette` choisi explicitement (G098) ; dépôt `CURRENT` (G099) ; sauvegarde vérifiée |
| S3 | diagnostic sans démarrage : code 0 |
| W tunnel | page, santé en lecture seule, 401 sans jeton, missions listées, mission lue ; jeton de lecture refusé sur la conversation |
| C conversation | proposition avec le modèle nommé ; mission créée **non lancée** ; annulation **demandée**, pas confirmée |
| L coupure | tunnel fermé : plus de réponse côté PC ; aucune mission changée ; l'opérateur crée une mission pendant la coupure ; au retour, état neuf, seule cette mission s'ajoute |
| S7 redémarrage | arrêt sur SIGTERM ; après redémarrage, **reçus anciens** retrouvés (validation, annulation, aussi par l'API de lecture) ; même validation renvoyée = même reçu, aucune 2ᵉ mission |
| S8 arrêt | port fermé ; bases intactes (`integrity_check`, dépôt `CURRENT`) ; ni clé ni jeton dans les sorties |

## Rejeu du 10/10/2026 (après C-130 à C-135) : 32/32

Demande de toytoy : rejouer la recette sur le paquet installé, après la
signature obligatoire des sauvegardes.

- **Paquet** : archive du commit `a480e4f262da5d657f0620d3f8269356fd1d283f`,
  144 fichiers, `--verify` OK ([construction](bundle-build-c135.json),
  [vérification](bundle-verify-c135.json)).
- **Installation** : environnement neuf (`--no-index`, sans `PYTHONPATH`),
  lancement depuis `/`. Le script de recette n'est pas dans l'archive : il a
  été lancé depuis une copie à part, contre le module installé.
- **Résultat** : [recipe_g082-rerun-c135.json](recipe_g082-rerun-c135.json),
  **32/32**.
  - Les **28 vérifications d'origine** passent toutes, sans changement.
  - **4 vérifications ajoutées** passent aussi :

| Étape | Ajout vérifié |
| --- | --- |
| S2 | la sauvegarde est **signée** par la clé du serveur, créée à cette première sauvegarde (`CREATED`) ; `.sig` présent |
| S2 | `backup-key` donne la clé publique (sans clé privée) ; `verify-backup` avec cette copie → `VERIFIED`, même empreinte logique |
| R | après l'arrêt (S8), `restore-backup` **sans** `--signer` est refusé (code 2) |
| R | `restore-backup --signer` → `RESTORED`, `VERIFIED` ; base remplacée gardée (`conversations.sqlite3.before-restore-…`) ; dépôt `CURRENT` avec l'empreinte logique de la sauvegarde |

Limites inchangées : conteneur seulement, relais TCP à la place de `ssh -L`,
modèle et mémoire simulés. Le chiffrement `age` n'est pas exercé par cette
recette ; il l'est par les tests unitaires.

## Rejeu avec chiffrement age (10/10/2026) : 36/36

Demande de toytoy : ajouter le chiffrement age à la recette.

- **Paquet** : archive du commit `6fce66be05350c242edd83a856affef4f17ecd12`,
  144 fichiers, `--verify` OK ([construction](bundle-build-age.json),
  [vérification](bundle-verify-age.json)).
- **Installation et lancement** : même procédure que le rejeu précédent.
- **Résultat** : [recipe_g082-rerun-age.json](recipe_g082-rerun-age.json),
  **36/36**, soit les 32 vérifications précédentes et 4 nouvelles.

| Étape | Ajout vérifié |
| --- | --- |
| S2 | clé age créée côté « PC » (dossier séparé, 0600) ; le serveur ne reçoit que la clé **publique** ; `backup --encrypt-to` → fichier `age-encryption.org/v1`, **signé** (clé du serveur `EXISTING`), sans en-tête SQLite en clair ; à côté, seulement `.age` et `.age.sig` |
| S2 | côté PC : `decrypt-backup --signer --identity` → `VERIFIED`, même empreinte logique, et empreinte du clair égale à celle annoncée au chiffrement |
| R | `restore-backup` d'une sauvegarde chiffrée **sans** `--identity` → `RESTORE_REFUSED`, base inchangée |
| R | `restore-backup --signer --identity` → `RESTORED`, `VERIFIED`, dépôt `CURRENT` avec l'empreinte de la sauvegarde chiffrée, aucun fichier temporaire restant |

**Défaut trouvé et corrigé en préparant ce rejeu** (commit `6fce66b`) :
- La base remplacée était gardée sous un nom daté **à la seconde**. Une
  seconde restauration dans la même seconde était refusée (`RESTORE_REFUSED`).
- Le nom porte maintenant les microsecondes.
- Un test de non-régression échoue sans la correction et passe avec.

## Deux constats pour la vraie bêta

1. **Le tunnel doit garder le même numéro de port des deux côtés.** Les routes
   de conversation vérifient l'en-tête `Host` (protection contre le DNS
   rebinding). Un PC qui ouvre le tunnel sur un **autre** port local (par
   exemple `-L 127.0.0.1:9000:127.0.0.1:8765`) lit les missions, mais la
   conversation répond `HOST_REFUSED`. La recette le vérifie. Consigne : `ssh
   -N -L 127.0.0.1:8765:127.0.0.1:8765 …`. Si le port 8765 est pris sur le PC,
   changer **les deux** (`--port` du serveur et le tunnel).
2. **Le contenu rappelé de la mémoire n'est pas exposé par l'API de lecture.**
   À distance, on voit l'objectif `recalled_text_statistics` et le statut,
   pas le texte. C'est un constat ; je ne dis pas si c'est voulu.

## Ce qui est testé ici et ce qui reste à faire

| Point | Conteneur (09/10) | VM100 Debian | PC Windows |
| --- | --- | --- | --- |
| Paquet construit, vérifié, installé sans réseau | PASS | À EXÉCUTER | — |
| Démarrage, diagnostic, arrêt | PASS | À EXÉCUTER | — |
| Tunnel | **relais TCP local** à la place de `ssh -L` | à exécuter avec le vrai `sshd` | **`ssh -L` OpenSSH Windows** |
| Page et client | appels HTTP (Chromium déjà couvert en G095) | — | **navigateur et WebView réels**, échelle 125/150 % |
| Coupure et retour | PASS (relais fermé puis rouvert) | — | fermer puis rouvrir la fenêtre SSH, veille du PC, Wi-Fi coupé |
| Reçus anciens après redémarrage | PASS | À EXÉCUTER | lecture dans la page |
| Rappel mémoire | **simulé** (note synthétique) | vrai Memory Engine : hors de cette recette | — |
| Modèle de dialogue | **simulé** (profil `recette`) | vrai modèle : qualification séparée | — |

## Commandes reproductibles (préparées, NON exécutées sur VM100 ni Windows)

Serveur, session SSH 1. Les chemins sont temporaires, rien n'est installé en
dehors d'eux :

```sh
BETA="$(mktemp -d "$HOME/eidolon-beta-XXXXXX")"
# Archive vérifiée du commit choisi, puis environnement isolé
python3 tools/build_beta_bundle.py --verify <archive>.tar.gz
tar -xzf <archive>.tar.gz -C "$BETA"
python3 -m venv --system-site-packages "$BETA/venv"
(cd "$BETA"/eidolon-beta-*/eidolon-core && SETUPTOOLS_USE_DISTUTILS=stdlib "$BETA/venv/bin/pip" install --no-deps --no-build-isolation --no-index .)
PY="$BETA/venv/bin/python"; WEB="$(echo "$BETA"/eidolon-beta-*/eidolon-core/desktop/connected)"
"$PY" -m eidolon_core --state "$BETA/state" demo > "$BETA/demo.json"
"$PY" -m eidolon_core.access_token --output "$BETA/read-token" --format human
"$PY" -m eidolon_core.conversation_api --state "$BETA/state" pair --client-id pc-toytoy --actor toytoy   # clé affichée une fois
printf '%s' '{"schema":"eidolon-dialogue-profiles/1","profiles":{"recette":{"kind":"simulated"}}}' > "$BETA/profiles.json"; chmod 600 "$BETA/profiles.json"
"$PY" -m eidolon_core.conversation_api --state "$BETA/state" profile select --name recette --actor toytoy --profiles "$BETA/profiles.json"
"$PY" -m eidolon_core.conversation_api --state "$BETA/state" inspect-store
"$PY" -m eidolon_core.http_api --state "$BETA/state" --token-file "$BETA/read-token" --web-root "$WEB" --port 8765 --check --format human
"$PY" -m eidolon_core.http_api --state "$BETA/state" --token-file "$BETA/read-token" --web-root "$WEB" --port 8765 \
  --conversations profiles --dialogue-profiles "$BETA/profiles.json"
```

PC Windows, PowerShell (fenêtre à laisser ouverte) :

```powershell
ssh -N -L 127.0.0.1:8765:127.0.0.1:8765 <utilisateur>@<serveur>   # MÊME port des deux côtés
# Navigateur : http://127.0.0.1:8765/  — jeton de lecture, puis clé de conversation
```

Coupure : fermer la fenêtre SSH, attendre, la rouvrir. La page doit
retrouver un état neuf sans rien renvoyer. Pendant la coupure, sur le
serveur : `"$PY" -m eidolon_core --state "$BETA/state" create "mission de recette synthétique"`.
Arrêt : Ctrl+C dans la session 1. Retrait : comme S9 de
[BETA-ACCEPTANCE.md](../../../BETA-ACCEPTANCE.md).

## Limites

- Le relais TCP n'est pas SSH : pas de chiffrement, pas d'empreinte d'hôte,
  pas de reconnexion automatique d'OpenSSH.
- Aucune commande n'a été lancée sur VM100 ni sur le PC. Aucun accès
  personnel.
- Modèle et mémoire simulés.
