# Compte de service dédié pour Memory (Claude, demande de toytoy)

Auteur : Claude. Date : 15/10/2026, Europe/Paris. Statut : **proposition, révisée en G262-5**.

> **Révision G262-5.** Le § 2.3 d'origine (canon entier en `ReadOnlyPaths=`) **bloque le rappel** :
> le verrou `.write.lock` est ouvert en `a+b`, même s'il existe (relecture GPT G261, confirmé par les
> sondes G262-2 et par un vrai montage en lecture seule). La [section 6](#6-révision-g262-5--profil-corrigé)
> remplace les § 2.2 et 2.3. Les autres sections restent valables, sauf mention contraire.
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

## 6. Révision G262-5 : profil corrigé

### 6.1 Ce qui a été établi (G262-2, G262-3, G262-6)

| Constat | Preuve |
| --- | --- |
| Le `--root` du pont contient **`memory/persistent` et `memory/history`** (`history/pending-delete` compris) ; la copie doit garder cette structure. | code de `services/memory_bridge.py` ; relecture GPT G261 |
| Les constructeurs (`FilesystemBackend`, `ContextualRecall`) tentent des `mkdir(exist_ok=True)`, sans effet si l'arborescence **existe déjà**, même en lecture seule. | sonde G262-2 ; vrai montage RO : `mkdir` d'un dossier existant donne `EEXIST` |
| Un rappel ouvre en `a+b` `persistent/.write.lock` et, si `threads/` existe, `threads/.write.lock`. Il **crée** un verrou absent et ne modifie aucun autre octet. | trace G262-2 (verrou présent ou absent) |
| Canon entier en lecture seule : le rappel échoue en `EROFS` sur le verrou, **qu'il existe ou non**. | EROFS simulé et vrai montage RO (`unshare -m`) |
| Canon en lecture seule **sauf les deux fichiers de verrou**, préexistants et rendus inscriptibles : le rappel **fonctionne**, aucune autre création n'est possible, et le verrou reste le même inode que celui des écrivains. | vrai montage RO avec deux montages de fichiers en écriture, code Memory inchangé |
| Variante sans écriture du tout : verrou préexistant ouvert en `O_RDONLY` puis `flock`. L'exclusion avec le vrai écrivain fonctionne, y compris à travers le montage RO. **Demande un changement de code** côté lecteur. | prototype G262-3 (`lock_contract.py`), 9 tests |
| Reranker : avec un cache complet et **préparé** (`version.txt` présent), le chargement n'écrit rien et n'ouvre aucune connexion. Sans préparation, il tente `mkdir $HF_HOME/hub` puis d'écrire `version.txt`. Si le cache est incomplet, il annonce à tort « impossible de se connecter à huggingface.co ». | audit G262-6, sous l'UID `nobody`, transformers 4.44.2 sans torch |

### 6.2 Matrice besoins / directives

| Besoin | Pont (lecture) | Worker et tick (écriture, même UID) | Directive systemd |
| --- | --- | --- | --- |
| Lire le canon | oui | oui | `ReadOnlyPaths=<root>/memory` (pont) ; `ReadWritePaths=<root>/memory` (worker) |
| Verrou d'écriture partagé | **ouvrir en écriture les 2 fichiers existants** | créer et ouvrir | pont : `ReadWritePaths=<root>/memory/persistent/.write.lock <root>/memory/persistent/threads/.write.lock` |
| Créer un verrou manquant | **non** : à préparer avant | oui | — |
| Écrire le canon, `history/pending-delete` | non | oui | worker seulement |
| État Qdrant, journal, curseurs | non | oui | `StateDirectory=eidolon-memory` (worker) |
| Cache des modèles | lecture | lecture ou aucun | `ReadOnlyPaths=/var/cache/eidolon-memory/models` ; `Environment=HF_HOME=… HF_HUB_CACHE=…` ; variables hors ligne |
| Jeton du pont | lu au démarrage | non | `EnvironmentFile=` root 0600 (systemd le lit avant de changer de compte) |
| Réseau | écoute sur `127.0.0.1` | client Qdrant local | `RestrictAddressFamilies=AF_INET AF_UNIX` |
| Dossier personnel | non | non | `ProtectHome=yes` |

**Même UID, protections différentes.** Les restrictions systemd s'appliquent **par unité**. Le pont
est protégé contre ses propres écritures dans le canon. Le worker, lui, peut écrire, et un processus
du même UID qui contournerait systemd n'est pas confiné. Ce n'est pas une isolation entre processus
(relecture GPT G261). Un second compte ne sera proposé que si un besoin est démontré.

### 6.3 Profil du pont, version intermédiaire (sans changement de code)

```ini
User=eidolon-memory
Group=eidolon-memory
ExecStart=/opt/eidolon-memory-engine/.venv/bin/python -B -m services.memory_bridge \
  --root /var/lib/eidolon-memory --port 18765 --reranker-cache /var/cache/eidolon-memory/models
Environment=HF_HOME=/var/cache/eidolon-memory/models HF_HUB_CACHE=/var/cache/eidolon-memory/models
Environment=HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false
ProtectSystem=strict
ProtectHome=yes
ReadOnlyPaths=/var/lib/eidolon-memory/memory /var/cache/eidolon-memory/models
ReadWritePaths=/var/lib/eidolon-memory/memory/persistent/.write.lock
ReadWritePaths=/var/lib/eidolon-memory/memory/persistent/threads/.write.lock
# + NoNewPrivileges, CapabilityBoundingSet=, PrivateTmp, PrivateDevices, Protect*, RestrictSUIDSGID,
#   RestrictAddressFamilies=AF_INET AF_UNIX, UMask=0077 (inchangés par rapport au § 2.3)
```

**Ce qui reste à vérifier sur la VM**, car je n'ai pas pu exécuter systemd ici. Mon essai a reproduit
le mécanisme (montages *bind* RO, plus un fichier RW par-dessus) avec `unshare -m`.

1. `systemd-analyze verify` accepte des **fichiers** dans `ReadWritePaths=` imbriqués sous un
   `ReadOnlyPaths=` (la règle la plus précise l'emporte) ;
2. l'unité démarre ;
3. un rappel réel réussit ;
4. `touch` dans le canon échoue sous l'unité.

**Préconditions de démarrage**, ajoutées au § 3 :

- les **deux** verrous existent ;
- `threads/` existe, sinon le second chemin `ReadWritePaths=` empêche le démarrage ;
- `history/pending-delete` existe ;
- le cache des modèles est complet **et préparé** : un premier chargement est fait avec les droits
  d'écriture, avant de réduire les droits.

Le préflight vérifie tout cela :

- `--memory-root` et `--service-account` (G262-1) ;
- `--reranker-cache` (G262-6).

**Limite de la version intermédiaire.** Un écrivain qui crée plus tard `threads/` et son verrou après le
démarrage du pont crée un fichier que le pont ne peut pas ouvrir en `a+b` : le rappel échouerait en
`EROFS`. Il faut donc créer `threads/` et ses verrous **à la préparation**, ou adopter la version cible.

### 6.4 Version cible (changement de code, à décider par GPT)

Le lecteur ouvre le verrou existant en `O_RDONLY`, sans le créer, puis le verrouille avec `flock`
(G262-3, mode « legacy » du prototype).

- Le pont n'a alors **plus aucun** `ReadWritePaths=` dans le canon.
- Les écrivains gardent leur code, et il y a **un seul** verrou.
- Un verrou absent donne `LOCK_ABSENT` : refus explicite, jamais de rappel sans verrou.
- Une substitution est refusée.

Le mode « external » du prototype (verrou déclaré dans un manifeste du canon) n'est utile que si l'on
veut un jour sortir le verrou du canon. Il n'est pas nécessaire pour le compte de service.

### 6.5 Ordre révisé (complète le § 3)

Insérer entre les étapes 5 et 7 :

- **5 bis** : créer, avec le compte de service, `threads/`, les deux `.write.lock` et `history/pending-delete` ;
- **6 bis** : préparer le cache (un chargement avec écriture, puis passage du cache en propriété root et lecture seule) ;
- **6 ter** : préflight avec `--memory-root`, `--service-account` et `--reranker-cache`, tout en `PASS` ;
- **6 quater** : comparer la copie avec `tools/claude_copy_inventory.py` (G262-4) : `IDENTICAL`, code 0.
