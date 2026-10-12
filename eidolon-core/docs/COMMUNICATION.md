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
