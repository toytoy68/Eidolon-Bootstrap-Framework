# Communication Eidolon ↔ utilisateur : voix, caméras, vision (G146–G151)

Auteur : Claude. Date : 12/10/2026, Europe/Paris. Demande :
[COMMUNICATION-CLAUDE-G146-G151.md](COMMUNICATION-CLAUDE-G146-G151.md)
(G145, toytoy). Statut : **G146, inventaire et contrat**. Les lots suivants
sont décrits au fur et à mesure dans ce document.

## 1. Inventaire (G146)

### 1.1 Dans les dépôts (vérifié le 12/10, commit `fc94f6d`)

| Élément | État réel | Réutilisation |
| --- | --- | --- |
| STT (Whisper, faster-whisper) | **aucun code**. Le [cadrage §8](cadrage/EIDOLON-CORE-CADRAGE-WORK-2026-10-05.md) cite des « expérimentations antérieures », sans intégration vérifiée | à créer |
| TTS (Piper) | **aucun code** ; même mention dans le cadrage | à créer |
| Vision | adaptateur **Ollama Vision** de Codex (`media_backends.py`), pour l'analyse d'images et de vidéos par l'agent média, avec point d'accès limité à la boucle locale | même protocole HTTP Ollama pour décrire une image ponctuelle ; je n'importe pas le module média, qui appartient à Codex |
| Caméra et micro côté client | **simulés** dans l'ancien prototype (`desktop/prototype`) : états `mic` et `camera`, « Caméra désactivée » ; rien dans le client connecté | reprise des libellés et des états |
| Règles présence et identité | décision **C-D04** et cadrage §8 : présence ≠ identité ≠ authentification ; événements `USER_PRESENT`, `USER_ABSENT`, `USER_IDENTIFIED`, `USER_UNKNOWN` ; détection d'abord sur le PC | reprises telles quelles (§2.6) |
| Authentification client | clés appairées `ClientCredentials`, comme la conversation | réutilisée : même clé, mêmes refus |
| Préférence de voix | voix féminine française, chaleureuse, posée, un peu lente (G140) | §2.4 |

### 1.2 Sur les machines (VM101, Core, Memory, PC Windows) : **non inventorié**

Mon environnement n'a accès à aucune VM ni au PC, et n'a ni micro ni caméra.
Commandes **en lecture seule**, à lancer par toytoy ou GPT sur chaque
machine ; rien n'est installé ni démarré :

```sh
systemctl list-units --all --no-pager | grep -i -E 'whisper|piper|wyoming|tts|stt' || true
command -v piper whisper ffmpeg arecord || true
python3 -m pip list 2>/dev/null | grep -i -E 'whisper|piper|ctranslate2|onnxruntime' || true
ls -l /dev/video* /dev/snd 2>/dev/null || true
arecord -l 2>/dev/null || true
ollama list 2>/dev/null || true      # modèles déjà présents, dont vision
```

Sur Windows (PowerShell), pour les périphériques **réellement branchés** :
`Get-PnpDevice -Class Camera,AudioEndpoint -PresentOnly`.

**Règle** : tant que ces sorties ne sont pas publiées, chaque service est
`unavailable` dans la documentation. Je n'ai donc ni service actif ni
candidat confirmé.

## 2. Contrat (G146)

### 2.1 Architecture

```text
 PC Windows (page connectée)                         serveur (VM Core ou VM101)
 ┌──────────────────────────────┐                    ┌─────────────────────────────────────────┐
 │ micro / caméra (navigateur)  │  WAV borné / JPEG  │ service « communication » séparé        │
 │  désactivés par défaut,      │ ─── ponctuel ────▶ │  STT (faster-whisper)                   │
 │  voyant de capture visible   │  clé appairée      │  TTS (Piper)                            │
 │ lecture TTS, arrêt immédiat  │ ◀── WAV / texte ── │  vision (Ollama, image ponctuelle)      │
 └───────────┬──────────────────┘                    │  une requête active par périphérique    │
             │ texte transcrit = un tour normal      └─────────────────────────────────────────┘
             ▼
   /v1/conversations/turn (inchangé) : la voix n'accorde AUCUNE permission
```

- **Service séparé** (`eidolon-comm`) : processus et port à lui, sur
  127.0.0.1, sans sudo. Caches et modèles hors de l'état Core. Il **ne
  touche pas** `http_api.py` ni `dialogue.py`.
- **La transcription n'est qu'un texte.** La page l'affiche, l'utilisateur
  peut la corriger, puis l'envoie comme un tour normal. Elle ne soumet
  jamais de mission, et une proposition demande toujours la validation
  habituelle.
- **Aucune émission externe** : tout reste en boucle locale. Les flux
  passent par le même tunnel SSH que la page.

### 2.2 Identité de session et authentification

- Chaque requête porte la **clé client appairée** de la conversation
  (`Authorization: Bearer`). Le jeton de lecture est refusé, comme pour la
  conversation.
- **L'autorisation de capture n'est ni une identité ni une permission.**
  Trois choses restent séparées :
  - permission du navigateur : micro ou caméra autorisé par Windows et le
    navigateur ;
  - activation Eidolon : interrupteur dans la page, éteint par défaut ;
  - permission d'action : celle de Core, inchangée.
- Une voix ou un visage reconnu ne remplace jamais la clé et n'autorise
  rien (C-D04).

### 2.3 États d'un périphérique ou d'un moteur

| État | Sens | Voyant de la page |
| --- | --- | --- |
| `unavailable` | pas de matériel, pas de moteur installé, ou service arrêté | gris, « indisponible » |
| `permission_denied` | refus du navigateur ou du système | gris, « refusé : à autoriser dans Windows » |
| `disabled` | matériel présent, **non activé** par l'utilisateur (défaut) | gris, « désactivé » |
| `ready` | activé, prêt | neutre |
| `capturing` | **capture en cours** | **rouge, visible tant qu'elle dure** |
| `processing` | transcription, synthèse ou analyse en cours | animé |
| `busy` | une requête est déjà active pour ce périphérique | « occupé » ; pas de file cachée |
| `stopped` | arrêtée par l'utilisateur ou par une limite | neutre, avec la raison |

Transitions principales :
- `disabled → ready`, par l'interrupteur ;
- `ready → capturing → processing → ready` ;
- n'importe quel état `→ stopped` par l'arrêt ;
- `ready → unavailable` si le matériel disparaît ou si le service tombe.

**L'absence de caméra ou de micro n'interrompt jamais le dialogue** : le
texte reste disponible.

### 2.4 Contrats d'échange

| Route (service comm) | Entrée | Sortie | Bornes |
| --- | --- | --- | --- |
| `GET /v1/comm/status` | — | état de chaque moteur, modèles et versions, `capture_default: off` | — |
| `POST /v1/comm/stt` | WAV PCM 16 bits, mono, 16 kHz, `language: fr` | `{text, language, duration_s, segments, engine, model, unverified: true}` | 30 s et 1 Mo au plus ; une transcription active par client |
| `POST /v1/comm/tts` | `{text, voice, rate, volume}` | WAV, par morceaux de phrases | 2 000 caractères ; une synthèse active par client ; arrêt par `DELETE` |
| `POST /v1/comm/vision/describe` | une image JPEG ou PNG, `purpose: presence\|scene` | `{present, people_count, description, engine, model, unverified: true}` | 1 280 × 720 et 2 Mo au plus ; une analyse active |

- Tout résultat porte `unverified: true` : une transcription, une
  description ou une détection est une **observation non fiable**, jamais
  une preuve. Le texte transcrit entre dans le dialogue comme un message de
  l'utilisateur, avec les mêmes garde-fous.
- **Aucun enregistrement conservé** : audio et images sont traités en
  mémoire puis jetés. Rien n'est écrit dans Git, Memory ou les journaux. Les
  journaux ne portent que tailles, durées et codes, jamais de contenu.
- Erreurs : `COMM_DISABLED`, `DEVICE_BUSY`, `PAYLOAD_TOO_LARGE`,
  `AUDIO_FORMAT_UNSUPPORTED`, `ENGINE_UNAVAILABLE`, `TIMEOUT`, `CANCELLED`,
  `READ_TOKEN_NOT_ALLOWED`, `UNAUTHORIZED`.

### 2.5 Voix (préférence de toytoy)

- Voix française **féminine**, chaleureuse et posée, débit légèrement
  ralenti (réglage par défaut `rate = 0.9`).
- Uniquement des voix **réellement disponibles et sous licence connue**.
  Les candidates Piper (§G148) sont à vérifier sur leur fiche officielle.
- **Aucune promesse** de reproduire une voix d'un autre service.
- Anti-écho : pendant la lecture, l'écoute est suspendue. Une nouvelle
  demande, ou l'appui sur le micro, **coupe la lecture** immédiatement.

### 2.6 Présence et vision

- Ordre de mise en œuvre :
  1. **présence**, et nombre de personnes ;
  2. **description de scène** ;
  3. identification nominative, **facultative et plus tard**.
- La présence alimente les événements de C-D04 (`USER_PRESENT`,
  `USER_ABSENT`). Une ressemblance ne vaut jamais authentification.
- Image **ponctuelle** à la demande, pas de flux continu ni d'enregistrement
  vidéo. Pas de source RTSP découverte par balayage du réseau.
- L'identification nominative, si elle vient un jour, exige une inscription
  volontaire, des modèles de visage stockés localement et protégés, la
  suppression à la demande et une durée de conservation. Hors de ce lot.

### 2.7 Fichiers réservés par Claude

- **Nouveaux fichiers, réservés** :
  - `src/eidolon_core/comm_*.py`, `tests/test_comm_*.py` ;
  - `desktop/connected/src/communication.js`,
    `desktop/connected/tests/communication*.test.js` ;
  - `docs/COMMUNICATION.md`, `docs/validation/2026-10-12/claude-g146-g151/`.
- **Partagés, à coordonner avant de les toucher** : `http_api.py`,
  `dialogue.py`, `desktop/connected/index.html`, `src/main.js` et
  `src/conversation.js`. Le câblage court proposé :
  - **aucune** modification de `http_api.py` ni de `dialogue.py` (service
    séparé) ;
  - dans la page, un bloc « Voix et caméra » ajouté à `index.html` et une
    ligne d'initialisation dans `main.js`. Je les annoncerai avant de les
    faire.
- `media_backends.py`, `darme*.py` et le paquetage restent à Codex.

## 3. Ce qui est livré (G147 à G151)

| Lot | Fichiers | Tests |
| --- | --- | --- |
| Contrat commun | `comm_contract.py` : erreurs, contrôle WAV (mono, 16 bits, 16 kHz, 30 s, 1 Mio), une requête par client et par périphérique | dans les tests suivants |
| **G147** transcription | `comm_stt.py` : faster-whisper sur processeur, chargé depuis un **dossier local** (`model.bin`), jamais par un nom de modèle, donc jamais téléchargé ; simulateur ; silence → texte vide ; annulation entre les segments ; délai maximal | `test_comm_stt.py` (11) |
| **G148** synthèse | `comm_tts.py` : Piper, avec l'exécutable de l'opérateur, les voix **présentes** dans son dossier, un environnement vide et un délai ; découpage en phrases ; vitesse (défaut 0,9) et volume ; arrêt immédiat, processus récupéré | `test_comm_tts.py` (10, avec un faux Piper local) |
| **G149** page | `desktop/connected/src/communication.js` : tout éteint par défaut, voyant de capture, appui pour parler (30 s au plus), annulation, anti-écho, une image et la caméra relâchée aussitôt, branchement à chaud, encodage WAV 16 kHz | `communication.test.js` (14) |
| **G150** vision | `comm_vision.py` : JPEG ou PNG contrôlé (2 Mio, 1280 × 720), Ollama en boucle locale, présence puis scène, **aucune identité**, image jamais gardée | `test_comm_vision.py` (7, faux Ollama) |
| **G151** service | `comm_service.py` : `eidolon-comm` séparé, clé appairée, jeton de lecture refusé, hôte et origine de la page contrôlés, corps trop gros refusé avant lecture, rien dans les journaux, `--check` | `test_comm_service.py` (9) |

**Recette en conteneur** :
[recipe_comm.py](validation/2026-10-12/claude-g146-g151/recipe_comm.py) →
[recipe_comm.json](validation/2026-10-12/claude-g146-g151/recipe_comm.json),
**11/11**.

Elle lance le vrai processus du service et passe par les **vrais
adaptateurs** Piper et Ollama, branchés sur des moteurs **factices**. La
transcription utilise le simulateur. Vérifié :
- clé exigée, jeton de lecture et autre origine refusés ;
- transcription non vérifiée et sans permission ;
- synthèse phrase par phrase ;
- présence sans identité ;
- **aucun fichier laissé dans l'état** ;
- arrêt propre.

Ces mesures (quelques millisecondes, environ 26 Mo de mémoire pour le
service) **ne disent rien** des vrais moteurs.

**Pas encore câblé dans la page.** `communication.js` n'est ni dans
`build.js` ni dans `index.html`, des fichiers partagés : il attend l'accord
de GPT sur le câblage proposé (C145).

## 4. Installer sur une VM (guide, non exécuté par Claude)

Rien n'a été installé par Claude. Toutes les commandes s'exécutent avec un
compte **sans sudo** (par exemple `eidolon`), dans des dossiers à lui.
Chaque modèle se télécharge **explicitement**, par l'opérateur. Licences et
fiches **à vérifier sur la source officielle** avant usage.

**Transcription (faster-whisper)** — licence MIT (à vérifier) :
```sh
python3 -m venv ~/eidolon-comm/venv
~/eidolon-comm/venv/bin/pip install faster-whisper            # téléchargement explicite
# Modèle CTranslate2 déjà converti, copié dans un dossier local, par exemple
#   ~/eidolon-comm/models/whisper-small/model.bin
# (dépôts « Systran/faster-whisper-* » ; poids Whisper d'OpenAI, licence MIT à vérifier).
```
Commencer par `small` ou `base` sur processeur ; mesurer avant `medium`.

**Synthèse (Piper)** :
- Le projet d'origine `rhasspy/piper` était sous licence MIT ; sa suite
  `OHF-Voice/piper1-gpl` est sous GPL-3.0. **À vérifier**, comme les options
  de l'exécutable installé : l'adaptateur passe `--model`, `--output_raw` et
  `--length_scale`.
- Voix françaises **féminines** candidates, à écouter et dont la licence est
  à vérifier sur leur fiche (`MODEL_CARD`) :
  - `fr_FR-siwis-medium` ;
  - `fr_FR-upmc-medium`, voix de locutrice ;
  - `fr_FR-mls`, multilocuteur.
- Chaque voix = `<nom>.onnx` + `<nom>.onnx.json` dans
  `~/eidolon-comm/voices/`.

**Vision (Ollama, déjà présent sur VM101)** :
- Un modèle **capable de lire des images**, déjà chargé ou téléchargé
  explicitement (`ollama pull …`). Exemples à évaluer :
  - `moondream` (léger) ;
  - `gemma3:4b` ;
  - un modèle Qwen-VL.
- Licences propres à chaque modèle, à vérifier. Mesurer la contention avec
  le dialogue de Core avant de partager le GPU.

**Configuration** (`~/eidolon-comm/comm.json`, `chmod 600`) :
```json
{"schema": "eidolon-comm-config/1",
 "stt": {"kind": "faster-whisper", "model_dir": "/home/eidolon/eidolon-comm/models/whisper-small", "threads": 2},
 "tts": {"kind": "piper", "executable": "/home/eidolon/eidolon-comm/piper/piper",
         "voice_dir": "/home/eidolon/eidolon-comm/voices", "default_voice": "fr_FR-siwis-medium"},
 "vision": {"kind": "ollama", "endpoint": "http://127.0.0.1:11434", "model": "moondream"},
 "allowed_origin": "http://127.0.0.1:8767"}
```
Une section absente = moteur indisponible, et rien d'autre ne change.

**Vérifier, démarrer, arrêter, désinstaller** :
```sh
python -m eidolon_core.comm_service --state <état Core> --config ~/eidolon-comm/comm.json --check
python -m eidolon_core.comm_service --state <état Core> --config ~/eidolon-comm/comm.json \
       --port 8766 --read-token-file <jeton de lecture>            # Ctrl+C ou SIGTERM pour arrêter
# Désinstaller : arrêter le service, puis supprimer ~/eidolon-comm (venv, modèles, voix, configuration).
# L'état Core n'est pas touché : le service n'y lit que les clés appairées.
```

**Tunnel du PC** : ajouter le port 8766 **au même numéro** des deux côtés,
comme pour 8765 (constat G082) :
```sh
ssh -N -L 127.0.0.1:8765:127.0.0.1:8765 -L 127.0.0.1:8766:127.0.0.1:8766 …
```

## 5. Reste à faire (réel)

| Point | Qui | Statut |
| --- | --- | --- |
| Inventaire des machines (§1.2) | toytoy ou GPT | à faire |
| Installation des moteurs sur la VM, mesures réelles : premier son, durée de transcription, RAM, charge processeur | GPT | fait (G162) |
| Câblage de la page (`build.js`, `index.html`, `main.js`) | Claude | fait (G155) |
| Essai Windows : micro et caméra réels, refus de permission, webcam occupée, branchement à chaud, échelle 125/150 % | toytoy | à faire |
| Recette audio de référence licite (avec texte attendu), silence, bruit, nombres, noms Eidolon | banc prêt (§6), exécution VM par Codex | en cours (G164) |
| Identification nominative facultative | décision de toytoy, plus tard | hors lot |

## 6. Vocabulaire contrôlé et garde-fous de la dictée (G164)

**Constat réel** (GPT, [audio-real.json](validation/2026-10-12/dashboard-vm/audio-real.json)) :
avec Whisper small, la voix synthétique Siwis donne « toi-toi » pour toytoy
et « et de longs » pour Eidolon. Les nombres 24 et 110 sont justes. Taux
d'erreur sur les mots de cette phrase : 14,8 % (calcul du banc ci-dessous).

**Ce qui est ajouté dans `comm_stt.py`**, réglable dans `comm.json`,
section `stt` :

| Réglage | Effet | Par défaut |
| --- | --- | --- |
| `vocabulary` | `"default"` ou `{"terms": [...], "replacements": {...}}` | absent : comportement actuel |
| `bias` | `none`, `prompt` (amorce « Glossaire : Eidolon, toytoy. »), `hotwords` | `none` |
| `silence_rms` | sous ce niveau, l'audio n'est **pas envoyé** au modèle : texte vide | 200 |
| `vad` | filtre de voix de faster-whisper | `false` |

**Garde-fous**, toujours actifs :
- **Silence** : jamais transmis au modèle (`"silence": true`).
- **Segment sans parole** : écarté selon la règle de Whisper
  (`no_speech_prob` > 0,6 **et** `avg_logprob` < −1).
- **Textes inventés connus** sur bruit (« Sous-titres réalisés par… »,
  « Merci d'avoir regardé… », Amara.org) : écartés.
- **Écho de l'amorce** : écarté s'il contient « Glossaire », ou s'il ne
  contient que les mots du glossaire alors que le modèle doute de la
  parole. « Eidolon. » dit clairement est **gardé**.
- Le nombre de segments écartés est renvoyé (`dropped_segments`).

**Remplacements** :
- seulement des formes **sans ambiguïté**, en mots entiers
  (« toi-toi », « toy toy », « Eidolone »…) ;
- « toi, toi seul » ou « et de longs essais » ne sont pas touchés ;
- chaque remplacement est renvoyé à la page (`corrections`), et le texte
  reste modifiable avant l'envoi.

**À mesurer avant de choisir** :
[bench_stt_vocabulary.py](validation/2026-10-12/claude-g164/bench_stt_vocabulary.py)
compare six réglages sur le **même** audio :
- les réglages : `baseline`, `guards`, `replace`, `prompt`, `hotwords`,
  `prompt+vad` ;
- l'audio : 8 phrases Piper, dont 4 avec bruit ajouté, plus 4 cas de
  silence ou de bruit seul.
Codex le lance sur la VM.

**Règle de choix** : un réglage n'est retenu que si :
1. le silence et le bruit restent **vides** ;
2. le taux d'erreur des phrases **sans nom** ne se dégrade pas.
La voix est synthétique : ce n'est pas une précision sur une voix humaine,
qui reste à vérifier sur ton PC.
