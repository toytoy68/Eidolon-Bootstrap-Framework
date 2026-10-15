# Compte de service dédié pour Memory (Claude, demande de toytoy)

Auteur : Claude. Date : 15/10/2026, Europe/Paris. Statut : **proposition**.
Rien n'est exécuté par ce document. Les commandes sont à relire par GPT et à
lancer par toytoy sur la VM, **après** une sauvegarde vérifiée.

Bases :

- Memory `a0cc112` : unité `deployment/vm-profile/eidolon-memory-bridge.service` ;
- Core `6bcbafa` : modèle DARME (`deployment/darme-install.py`,
  `deployment/eidolon-darme.service`).

## 1. Constat

Le pont Memory validé le 12/10 tourne **sous le compte personnel** :

```ini
User=toytoy
ExecStart=/home/toytoy/eidolon-hybrid-lab/.venv/bin/python -m services.memory_bridge \
  --root /home/toytoy/eidolon-corpus-factual-v2-test --port 18765 \
  --reranker-cache /home/toytoy/eidolon-hybrid-lab/models
```

Conséquences :

1. Un défaut ou un piège dans le pont a **tous les droits de toytoy** :
   fichiers personnels, clés SSH, autres services, dépôt Git.
2. Inversement, **tout programme lancé par toytoy** peut modifier le canon
   Markdown sans passer par Memory, donc sans verrou, sans journal et sans
   preuve.
3. L'environnement Python, les modèles et le corpus sont dans `/home/toytoy`.
   On ne peut donc pas activer `ProtectHome=` : le service a besoin du
   dossier personnel.

DARME montre déjà le bon modèle :

- compte système sans shell ni dossier personnel ;
- l'installateur refuse un compte privilégié ;
- unité durcie : `ProtectSystem=strict`, `ProtectHome=yes`, aucune
  capacité.

## 2. Proposition

### 2.1 Comptes

| Compte | Rôle | Création |
| --- | --- | --- |
| `eidolon-memory` | **propriétaire** des données Memory : canon, journal, index local, sauvegardes de travail | `useradd --system --user-group --home-dir /nonexistent --shell /usr/sbin/nologin eidolon-memory` |
| `toytoy` | administration humaine ; **plus** propriétaire des données | inchangé |

- Mêmes garde-fous que DARME : on refuse de continuer si l'UID vaut 0, et
  le compte n'a ni mot de passe ni shell.
- Le pont, qui ne fait que lire, tourne sous `eidolon-memory`, mais avec le
  canon monté **en lecture seule** par systemd (`ReadOnlyPaths=`, § 2.3).
  Cela évite un second compte tout en prouvant que le rappel n'écrit rien.
  C'est déjà un critère de G221 : « Memory ne réécrit pas le corpus pendant
  un rappel ».
- Si l'essai montre que le rappel a besoin d'écrire, par exemple un fichier
  de verrou, on le saura immédiatement (erreur `EROFS`). On décidera alors
  d'un dossier d'exécution séparé, **sans** rouvrir l'écriture du canon.

### 2.2 Emplacements et droits

| Chemin | Propriétaire | Mode | Contenu |
| --- | --- | --- | --- |
| `/opt/eidolon-memory-engine` | root:root | 0755, fichiers 0644 | code, en lecture seule pour le service |
| `/opt/eidolon-memory-engine/.venv` | root:root | 0755 | environnement Python, hors de `/home` |
| `/var/lib/eidolon-memory/canonical` | eidolon-memory | 0700 | canon Markdown (le `--root` actuel) |
| `/var/lib/eidolon-memory/state` | eidolon-memory | 0700 | journal, index, verrous |
| `/var/cache/eidolon-memory/models` | root:root | 0755, fichiers 0644 | modèles de reranking, lecture seule |
| `/etc/eidolon-memory-bridge/environment` | root:root | 0600 | jeton du pont. systemd le lit **avant** de changer de compte, et le service ne peut pas le relire |

Le secret **côté Core**, celui que le client du pont lit, reste la propriété
du compte qui exécute Core. Le préflight vérifie déjà : dossier 0700,
fichier 0600, même propriétaire que le processus, un seul lien.

### 2.3 Unité systemd proposée

```ini
[Service]
Type=simple
User=eidolon-memory
Group=eidolon-memory
WorkingDirectory=/opt/eidolon-memory-engine
EnvironmentFile=/etc/eidolon-memory-bridge/environment
Environment=PYTHONPATH=/opt/eidolon-memory-engine
Environment=HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false
ExecStart=/opt/eidolon-memory-engine/.venv/bin/python -B -m services.memory_bridge \
  --root /var/lib/eidolon-memory/canonical --port 18765 \
  --reranker-cache /var/cache/eidolon-memory/models
Restart=on-failure
RestartSec=5
UMask=0077
NoNewPrivileges=yes
CapabilityBoundingSet=
AmbientCapabilities=
ProtectSystem=strict
ProtectHome=yes
ReadOnlyPaths=/var/lib/eidolon-memory/canonical
PrivateTmp=yes
PrivateDevices=yes
ProtectKernelTunables=yes
ProtectKernelModules=yes
ProtectControlGroups=yes
RestrictSUIDSGID=yes
RestrictAddressFamilies=AF_INET AF_UNIX
```

- `RestrictAddressFamilies` autorise IPv4, parce que le pont écoute sur
  `127.0.0.1` (son code refuse toute autre adresse).
- Je ne propose pas de limites de mémoire ni de CPU tant que le modèle de
  reranking n'est pas mesuré sur la VM : aucune valeur inventée.
- Le worker J2 et le tick de maintenance, quand ils auront leur unité,
  utiliseront le **même compte**, avec `ReadWritePaths=` limité à
  `/var/lib/eidolon-memory`.

## 3. Ordre des opérations (pour toytoy, sur la VM)

Arrêt au premier écart. Chaque étape se vérifie avant de passer à la
suivante.

| # | Opération | Vérification |
| --- | --- | --- |
| 1 | Sauvegarde du corpus actuel et du dossier des modèles | sauvegarde **relue** : liste et empreintes identiques (`VM-OPERATIONS-ACCEPTANCE.md`) |
| 2 | `systemctl stop eidolon-memory-bridge` | `systemctl is-active` répond `inactive` |
| 3 | Création du compte (§ 2.1) | `id eidolon-memory` : UID différent de 0, shell `nologin` |
| 4 | **Copie** du corpus vers `/var/lib/eidolon-memory/canonical` (l'original reste en place) | même nombre de fichiers, empreintes `sha256sum` identiques |
| 5 | `chown -R eidolon-memory:eidolon-memory /var/lib/eidolon-memory` puis droits du § 2.2 | `find … ! -user eidolon-memory` vide ; aucun fichier lisible par les autres |
| 6 | Code, venv et modèles vers `/opt` et `/var/cache`, propriété root | le service ne peut pas les modifier (`touch` refusé sous `eidolon-memory`) |
| 7 | Nouvelle unité (§ 2.3), puis `systemd-analyze verify` | aucune erreur |
| 8 | `systemctl daemon-reload && systemctl start eidolon-memory-bridge` | `ps -o user= -p <PID>` affiche `eidolon-memory` |
| 9 | Un rappel de recette (B02) depuis Core | même réponse et mêmes références qu'avant la migration |
| 10 | Le compte `toytoy` essaie d'écrire dans le canon | refusé |
| 11 | `systemd-analyze security eidolon-memory-bridge` | score noté dans le journal de recette |

**Retour arrière** : arrêter le service, remettre l'ancienne unité et
redémarrer. Le corpus d'origine n'a pas été touché (étape 4 : copie). On ne
supprime l'ancien corpus qu'après une recette complète, et sur décision
explicite de toytoy.

## 4. Ce que le code doit encore garantir (pour GPT)

1. **Installateur** sur le modèle de `darme-install.py` : compte créé s'il
   manque, refus de l'UID 0, sauvegarde avant installation, fichiers du code
   possédés par root, `systemd-analyze verify` avant le démarrage.
2. **Préflight** : ajouter une vérification « propriétaire du canon =
   compte de service, et différent du compte qui lance la recette ». Le
   résultat est `UNKNOWN` si le compte n'existe pas. Je peux l'écrire dans
   `tools/claude_offline_preflight.py`.
3. **Test** : le rappel fonctionne sur un canon en lecture seule. Je peux
   l'écrire en sonde synthétique (dossier `chmod 0500`, ou montage en
   lecture seule simulé).

## 5. Ce que cette proposition ne fait pas

- Elle ne touche à aucune VM et ne crée aucun compte.
- Elle ne change pas les comptes des autres services (Core, tunnels,
  tableau de bord) : ce sera une décision séparée, sur le même modèle.
- Elle ne supprime aucune donnée.
