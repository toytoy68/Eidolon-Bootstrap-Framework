# G296 — Étude de Cornelius et plan pour Eidolon

Auteur : Claude (Claude Code), 23 octobre 2026, Europe/Paris (+0200).
Demande : mission prioritaire transmise par GPT le 23/10 à 13 h 31 (dépôt Memory,
`collaboration/CLAUDE-TO-GPT.md`, commit `92b9e3e`), relayée par toytoy à 13 h 33 :
« Maj de gpt et nouvelles pistes a étudié ». Branche dédiée `claude/g296-cornelius-study`,
issue de Core `2891e20` ; aucune fusion dans main.

## 1. En bref

- **Cornelius** (Les Frères Poulain, `lfpoulain/Cornelius`, étudié à `ad056d4` du 22/10/2026,
  25 commits) est un miroir assistant familial. Il tourne en Node 24 et TypeScript (serveur
  Fastify, interface React) et en Python 3.12 pour la perception : caméra, visages, voix,
  mot d'appel.
- **Différence de fond.** La conversation vocale de Cornelius passe par **OpenAI Realtime**
  (WebRTC), tout comme l'extraction de la mémoire. Sa fluidité, avec la coupure de parole et
  le duplex intégral, vient pour l'essentiel d'OpenAI et de l'annulation d'écho native de
  WebRTC. Eidolon est local : on reprend les **idées**, pas l'architecture vocale.
- **Licence.** Le code est sous **PolyForm Noncommercial 1.0.0**. Le modèle `cornelius.onnx`
  est sous CC BY-NC-SA 4.0. Je **n'ai copié aucun code** : tout le code livré ici est écrit de
  zéro (§4).
- **Ce qui vaut d'être repris**, par ordre d'impact :
  1. le mot d'appel **local** (openWakeWord, mot unique « Eidolon »), à la place de l'envoi de toute la veille à Whisper sur la VM ;
  2. la coupure de parole ;
  3. le jeton d'interaction et d'époque qui invalide les résultats tardifs ;
  4. le cache des modules, avec fraîcheur et repli daté ;
  5. le mode vie privée de la caméra.
- **Ce qui ne doit pas être repris** :
  - l'administration avec mot de passe par défaut (`cornelius`) ;
  - le HTTPS réseau local **ouvert par défaut** sur `0.0.0.0` ;
  - toute dépendance cloud.

**Livré dans cette branche, sans rien brancher dans le client ni le serveur existants**
(`app.js` est inchangé) :

| Lot | Fichiers | Tests |
| --- | --- | --- |
| V2-a, coupure de parole | `desktop/connected/src/duplex-voice.js` | `desktop/connected/tests/duplex-voice-g296.test.js` : 10 tests, 5 sabotages tous détectés |
| V1-a, mesure du mot d'appel | `tools/evaluation/wake_eval_g296.py` | `tests/test_wake_eval_g296.py` : 11 tests |
| M1-a, cache des modules | `src/eidolon_core/module_cache.py` | `tests/test_module_cache_g296.py` : 13 tests, 4 sabotages tous détectés |

## 2. Mesures faites ici (conteneur Linux, Xeon 2,1 GHz, sans GPU)

| Mesure | Résultat réel | Portée |
| --- | --- | --- |
| openWakeWord 0.6.0, ONNX Runtime 1.23.2, Python, un fil | **3,1 ms de CPU par trame de 80 ms**, soit 3,9 % d'un cœur | prétraitement partagé et un modèle (anglais `hey_jarvis`, servant **seulement** à la mesure, non livré) |
| Même chaîne en **onnxruntime-web 1.23.2** (WASM, sous Node) | sorties identiques à Python : écart max 1,5·10⁻⁵ (mel), 2,9·10⁻⁵ (embedding), 0 (score) ; **5,3 ms par trame**, 6,6 % d'un cœur (borne haute) | prouve que la voie navigateur fonctionne ; WebView2 reste à mesurer |
| Silero VAD (même empreinte que Cornelius `1a153a22…`) | **0,2 ms par bloc de 32 ms**, 0,6 % d'un cœur ; sortie WASM identique à Python | — |
| Mémoire du processus Python (runtime + modèles) | 211 Mio au pic | la mémoire côté navigateur n'est pas mesurée |
| Bruit seul (20 s) | score maximal 0,002 | ne mesure pas les fausses activations réelles |

Aucun GPU n'est nécessaire pour le mot d'appel ni pour la VAD. La latence acoustique réelle,
les fausses activations et l'écho sont **à mesurer sur le PC de toytoy** (§6).

## 3. Licences et dépendances

| Élément | Licence | Conséquence pour Eidolon |
| --- | --- | --- |
| Code Cornelius | PolyForm Noncommercial 1.0.0 (`LICENSE`, « Required Notice ») | Usage personnel autorisé ; copie ou dérivé seulement avec la licence et la mention, et **jamais** dans un usage commercial. La marque « Eidolon Core Technologies » rend cette contrainte risquée : **conception refaite de zéro**, aucune ligne copiée |
| `models/cornelius.onnx` | CC BY-NC-SA 4.0 | Inutile pour nous (mot « Cornelius ») ; ne pas l'utiliser |
| openWakeWord (code) | Apache 2.0, selon `THIRD_PARTY_NOTICES.md` | Utilisable |
| Données négatives `openwakeword_features` | CC BY-NC-SA 4.0, rapporté par Cornelius, non revérifié ici | Un modèle « Eidolon » entraîné avec elles hérite de NC-SA, par prudence |
| Voix Piper d'entraînement : Siwis, UPMC, Tom | CC BY 4.0, CC BY-SA 4.0, AGPL v3, rapportés par Cornelius | Choisir et consigner les voix ; garder les attributions |
| YuNet, SFace, Silero | MIT, Apache 2.0, MIT, rapportés par Cornelius | YuNet et SFace sont **déjà** utilisés par Eidolon (G170/G272) |
| LFM2.5-VL (vision) | LFM Open License v1.0 | À lire avant tout usage ; hors bêta |
| Conversation et mémoire | **OpenAI**, clé payante | Incompatible avec le local d'abord d'Eidolon : non repris |

## 4. Analyse par piste

### P0 — Mot d'appel local unique « Eidolon », écoute dès le lancement

- **Cornelius.**
  - Fichiers : `perception/wake.py` (openWakeWord, trame de 2 560 octets, seuil 0,5,
    anti-rebond 2 s), `web/audio/wake.ts` (flux du micro de veille vers `/wake-audio` en
    local) et `server/wake-arbiter.ts` (plusieurs appareils : meilleur score en 250 ms, puis
    1,5 s de silence).
  - Doc : `docs/fonctionnalites/mot-d-appel.md`.
  - Le modèle est entraîné avec `lfpoulain/wakeword-generator` : Docker, ~40 Go, GPU NVIDIA,
    voix de synthèse seulement.
- **Eidolon aujourd'hui (G282).** `desktop/connected/src/auto-voice.js` ne fait qu'un seuil
  d'énergie. En veille, **chaque segment parlé part vers Whisper sur la VM**, qui cherche
  ensuite l'appel en début de texte. Résultat : environ 5 s, et la parole du foyer quitte le
  PC même sans appel. La page le dit, mais c'est le principal écart de vie privée.
- **Architecture proposée.**
  - Détection dans le **client**, avec onnxruntime-web. Les trois modèles, mel + embedding +
    mot, sont servis par Core avec une empreinte épinglée : pas de Python sur Windows.
  - En veille, **aucun son ne sort du PC**.
  - Optionnel, en deux étages : la confirmation par Whisper du seul segment déclencheur, pour
    réduire les fausses activations.
  - La voie G282 reste disponible comme repli, désactivable.
- **Faisabilité.** Windows : oui ; parité WASM démontrée. Entraînement et banc sur **VM100**
  (GTX 1060 6 Go), décision du 23/10, sans perturber Gemma, Core ni DARME.
- **Risques.**
  - Fausses activations sur des mots proches (« Eden », « idole ») et sur la télévision. Le
    seuil reste réglable.
  - Licence NC-SA des données négatives : composant isolé et remplaçable
    ([inventaire](LICENCES-VOIX-G296.md)).
- **Un seul mot.** Décision de l'opérateur du 23/10, relayée par GPT : « Eidolon » est le
  **seul** mot d'appel. « Dis-moi » est retiré du client G282, de l'interface, des tests, de
  l'outil de mesure et de la notice Windows. La réponse « Oui ? » ne change pas.
- **Budget.** CPU < 7 % d'un cœur (mesuré), pas de GPU. Mémoire navigateur à mesurer.
- **Tests.** `wake_eval_g296.py` note n'importe quel détecteur, G282 compris, sur une
  chronologie annotée : rappel, fausses activations par heure (avec celles pendant que
  Eidolon parle, à part), latence médiane et p95.
- **Critères d'acceptation proposés** (modifiables dans l'outil) :
  - rappel ≥ 95 % ;
  - ≤ 0,5 fausse activation par heure sur 8 h de fond sonore réel (télé, conversation) ;
  - latence p95 ≤ 500 ms après la fin du mot ;
  - zéro octet audio vers la VM en veille, vérifié par capture réseau.

### P0 — Duplex intégral et coupure de parole, sans clic

- **Cornelius.**
  - La coupure vient de la session OpenAI Realtime : l'audio voyage en WebRTC, donc
    l'annulation d'écho du navigateur dispose de la référence. Le micro est préparé avec
    `echoCancellation`, `noiseSuppression` et `autoGainControl` (`web/audio/preparation.ts`).
  - `web/audio/measures.ts` mesure `interruption` et `reponse_latence`.
  - Les satellites, sans annulation d'écho, **coupent le micro** pendant la parole
    (`echoUntil` dans `server/live/transport.ts`).
- **Eidolon aujourd'hui.** Semi-duplex : les pistes sont arrêtées avant la synthèse, puis une
  garde de 400 ms (`auto-voice.js`).
- **Livré (V2-a).** `duplex-voice.js`, un contrôleur pur :
  - micro ouvert pendant la réponse ;
  - interruption seulement si la parole dure 240 ms **et** dépasse 1,5 fois le pic d'écho
    appris sur la réponse elle-même ;
  - fenêtre de grâce de 300 ms, puis 200 ms d'apprentissage sans interruption possible ;
  - arrêt de la lecture **dans le même appel** ;
  - les 600 ms précédentes sont transmises, pour garder les premières syllabes ;
  - un numéro de génération écarte les résultats tardifs ;
  - compteurs de coupures, d'échos rejetés et de fausses coupures (transcription vide), et
    latence de coupure.

  Les tests couvrent l'écho seul pendant 10 s, la vraie parole, une toux de 100 à 160 ms, les
  rappels tardifs et une trame invalide. Sabotages : règle d'écho, fenêtre d'apprentissage,
  pré-écoute, génération et arrêt différé sont tous détectés.
- **Risque principal.** Lue par `<audio>` ou WebAudio, la synthèse locale ne fournit pas
  forcément sa référence à l'annulation d'écho de Chromium/WebView2. **À mesurer.** Deux
  replis possibles : router la lecture par une connexion WebRTC en boucle locale, ou imposer
  le mot d'appel pour interrompre quand on n'a pas de casque.
- **Reste à faire (V2-b).**
  - Brancher le contrôleur dans `communication.js` derrière une option.
  - VAD Silero en WASM.
  - Annulation de la synthèse restante côté Core/VM.
  - Mesure sur le PC avec le micro et les haut-parleurs réels.
- **Critères.**
  - Latence de coupure p95 ≤ 300 ms.
  - ≤ 1 fausse coupure pour 30 min de réponses lues sans parler.
  - Aucune perte du début de phrase (contrôle d'écoute).
  - Aucun envoi en double.

### P0 — Lancement Windows en un clic, tunnel robuste

- **Cornelius.** Aucun installateur Windows : une dizaine de commandes PowerShell, avec
  `-ExecutionPolicy Bypass` (`docs/installation/windows.md`). Rien à reprendre, sauf la
  liste **Mise en route** de l'administration.
- **Eidolon est en avance.** G279–G286 : `Eidolon.exe` (`desktop/windows/EidolonLauncher.cs`),
  appairage automatique chiffré par DPAPI, tunnel SSH supervisé avec clé hôte épinglée,
  seconde instance ramenée au premier plan, tests `test-launcher.ps1` et `test-auto-tunnel.ps1`.
- **À compléter (W1).**
  - Reconnexion avec attente progressive et état visible.
  - Démarrage de la veille vocale au lancement, **après un consentement unique enregistré**.
  - Diagnostic « Mise en route » : Core, tunnel, Memory, voix, mot d'appel, caméra.
  - Recette sur le PC réel. Tout se teste par les scripts PowerShell existants et une recette
    manuelle.

### P1 — Reconnaissance caméra locale consentie et profils distincts

- **Cornelius.**
  - `perception/recognition.py`, `enrollment.py` (cinq positions guidées), `server/controller.ts`
    (présence, identité, regard ; observations à 10 Hz ; 2 s sans observation ferment la
    conversation).
  - Le **mode vie privée** ferme la conversation dès qu'un second visage apparaît sur deux
    images de suite.
  - Signatures effacées des sauvegardes (`secure_delete`, `server/backups.ts`).
- **Eidolon aujourd'hui.** `identity_runtime`, `identity_measure`, `identity_evaluation` :
  YuNet/SFace, mesure et calibration avec la marge de 15 % côté authentiques (G274), **aucun
  seuil activé**. La reconnaissance ne vaut jamais autorisation.
- **À reprendre (I1).**
  - Inscription guidée en plusieurs poses.
  - Mode vie privée, avec un second visage qui ferme la session.
  - Caméra éteinte en veille si seul le mot d'appel ouvre.
  - Effacement réel des signatures dans les sauvegardes.
  - Rattachement du profil dans les 8 s après l'appel.
- **Budget.** Modèles déjà présents ; CPU à mesurer à 10 Hz sur le PC ; GPU non requis.
- **Critères.** FAR/FRR sur les captures de toytoy avec la marge adoptée, mode vie privée
  testé, aucune image écrite sur disque.

### P1 — Délégation asynchrone Core / Memory / DARME, sans bloquer la voix

- **Cornelius.** `server/agents.ts` et `hermes-client.ts` (délégation à Hermes, au plus 32
  appels d'outil). Chaque résultat porte **identifiant d'interaction, époque de profil et
  version de contexte** ; un résultat qui ne correspond plus est ignoré. L'extraction de la
  mémoire se fait après la conversation, avec 60 s maximum, jamais rejouée.
- **Eidolon.** Les missions sont déjà durables et asynchrones, et les tours ont leurs règles
  de réponse tardive (G088–G090). En revanche, un tour vocal attend sa réponse.
- **Proposition (D1).**
  - Pour une demande longue, la voix répond d'abord « je m'en occupe ».
  - Le résultat arrive plus tard comme carte et annonce vocale **en file**, jamais par-dessus
    une parole en cours.
  - Le triplet interaction / époque / version de contexte est porté par les résultats.
  - DARME et Memory sont interrogés en parallèle, avec un délai chacun.
- **Critères.** Aucun résultat d'un profil précédent affiché ; aucune annonce pendant que
  l'utilisateur parle.

### P1 — Cache des modules avec durée de vie et invalidation, traçabilité des sources

- **Cornelius.** `server/addons/runtime.ts`, référence `docs/modules/reference.md` :
  - dernier succès gardé et annoncé « dernier relevé connu » ;
  - regroupement des requêtes identiques ;
  - `cacheMs` de 10 min au plus ;
  - réessais à 30 s, 60 s, 120 s, 240 s puis 5 min ;
  - changement de réglage ou de propriétaire : relevé effacé.
- **Livré (M1-a).** `module_cache.py`, écrit de zéro :
  - la clé lie module, source, **propriétaire** et empreinte de configuration ;
  - `cached` dans la durée de vie, `stale` daté seulement dans la fenêtre de repli, sinon `error` ;
  - une collecte pour N lectures identiques ;
  - `invalidate` écarte aussi la collecte en cours (`discarded`) ;
  - LRU borné ;
  - provenance complète : propriétaire, observé, récupéré, frais jusqu'à, servi ;
  - aucun détail d'exception exposé.
- **Reste à faire (M1-b).** Brancher sur le relais DARME/surveillance et sur les futurs
  modules, puis afficher « relevé de HH:MM » et l'annoncer à l'oral.

### P1 — Panneau d'administration : modules, permissions, identités

- **Cornelius.** `web/components/Admin.tsx`, `server/admin-password.ts` (empreinte scrypt une
  fois choisi, sinon le mot de passe de `.env`, **par défaut `cornelius`**), HTTPS réseau local
  **ouvert par défaut** (`CORNELIUS_LAN=1`, écoute `0.0.0.0:3443`, certificat auto-signé).
- **Proposition pour Eidolon (A1).**
  - Pas de mot de passe par défaut ; un rôle d'administration lié à une clé appairée distincte.
  - Boucle locale et tunnel seulement, comme aujourd'hui.
  - D'abord un **inventaire en lecture seule** : profils et clients, racines de fichiers,
    droits Internet, modules, identités sans gabarits.
  - Les mutations passent par l'aperçu, la confirmation et un reçu, comme les actions
    existantes.
- **Critères.** Aucun secret ni gabarit renvoyé au navigateur ; refus pour une clé ordinaire ;
  journal des changements.

### P2 — Home Assistant et affichage contextuel

- **Cornelius.** `server/home-assistant*.ts` : WebSocket HA, jeton longue durée, appareils
  exposés choisis.
- **Proposition (H1, après la bêta).**
  - Jeton dans la configuration opérateur.
  - Lecture d'état par le cache M1.
  - Toute commande passe par l'aperçu et la confirmation.
  - Cartes contextuelles alimentées par M1.
  - Aucun accès réseau ajouté hors de la boucle locale et du tunnel.

## 5. Plan par lots

| Ordre | Lot | Contenu | Dépend de | État |
| --- | --- | --- | --- | --- |
| 1 | V1-a | Outil de mesure des mots d'appel | — | **livré** |
| 2 | V1-b | Modèle unique « eidolon » entraîné sur VM100 (données consignées, composants NC isolés), servi par Core avec empreinte | VM100 | **kit prêt** (`tools/wake_training/`), autorisé le 23/10 à 21 h 32 ; lancement en attente d'accès à VM100 |
| 3 | V1-c | Détection WASM dans le client, veille sans envoi, repli G282 | V1-b | à faire |
| 4 | V2-a | Contrôleur de coupure | — | **livré** |
| 5 | V2-b | Branchement, VAD Silero WASM, annulation de la synthèse, mesure de l'écho sur le PC | V2-a | à faire |
| 6 | W1 | Reconnexion, consentement unique et veille au lancement, diagnostic « Mise en route » | V1-c | à faire |
| 7 | M1-a | Cache des modules | — | **livré** |
| 8 | M1-b / D1 | Branchement du cache ; délégation asynchrone avec époque et file d'annonces | M1-a | à faire |
| 9 | I1 | Inscription guidée, mode vie privée, effacement des signatures | calibration | à faire |
| 10 | A1 | Administration en lecture seule, puis mutations confirmées | — | à faire |
| 11 | H1 | Home Assistant | M1-b, A1 | après la bêta |

## 6. À mesurer sur les machines (non fait ici)

- **Mots d'appel.**
  - 1 h d'appels annotés et 8 h de fond sonore dans la pièce, notées par `wake_eval_g296.py`.
  - Comparaison G282 et local sur la même chronologie.
  - Capture réseau en veille.
- **Écho.** Réponses lues par les haut-parleurs du PC, micro ouvert dans WebView2 :
  - niveau résiduel ;
  - taux de fausses coupures ;
  - voie `<audio>` contre voie WebRTC en boucle.
- **CPU et mémoire** de la détection WASM et de la VAD dans le client Windows réel.
- **Entraînement des modèles.** Durée, disque et GPU sur VM100 ; licence des données retenues.

## 6 bis. Décisions reçues le 23/10 (relayées par GPT, canal Memory `cfaac8c` et `d062a17`)

1. **Ordre validé** : mot d'appel local unique « Eidolon », puis branchement de la coupure de
   parole, puis veille automatique au lancement Windows.
2. **Licences** : composants non commerciaux acceptés **à titre d'étude** pour le prototype
   personnel. Inventaire précis tenu dans [LICENCES-VOIX-G296](LICENCES-VOIX-G296.md) ; tout
   composant ou donnée NC est isolé pour pouvoir être remplacé en cas de distribution.
3. **Entraînement et banc sur VM100 dès maintenant**, sans attendre les V100, sans perturber
   Gemma, Core ni DARME.
4. **« Dis-moi » supprimé** partout (fait sur cette branche, §4). Avant toute activation : tests
   de non-régression, seuil de faux positifs, latence et écho acoustique réel validés sous
   Windows. Pas de déploiement en production ni de fusion sans validation.

## 6 ter. Kit d'entraînement « eidolon » (VM100)

Autorisation de toytoy : 23/10/2026, 21 h 32. Fichiers sous `tools/wake_training/` :

- `eidolon-training.yml` : quatre graphies d'« Eidolon » et dix mots proches négatifs ; aucun autre mot d'appel.
- `run_vm100.sh`, en quatre temps :
  - contrôles préalables (`activity.json`, Docker, `nvidia-smi`, 45 Go libres) ;
  - clonage de wakeword-generator au commit `1cc2c42`, refusé s'il a été modifié ;
  - quatre étapes en conteneurs `eidolon-wake-*` de priorité minimale ;
  - puis modèle, empreinte, provenance et banc.

  CPU par défaut ; `WAKE_GPU=n` réserve un seul GPU à l'étape d'entraînement.
- `guard.py` met le conteneur en **pause** (`docker pause`) :
  - si Eidolon a servi dans les 10 dernières minutes ;
  - si le reçu d'activité est absent ou périmé ;
  - si un GPU atteint 82 °C ;
  - si la température est inconnue.

  Il reprend quand tout est revenu à la normale, et n'arrête ni ne redémarre aucun service.
- `bench_model.py` mesure deux choses :
  - les clips tenus à l'écart de l'entraînement, notés par `wake_eval_g296.py` ;
  - les fausses activations par heure sur les ~11 h de négatifs d'openWakeWord.
- Tests : `tests/test_wake_training_g296.py`, 13 tests, dont le vrai processus de garde avec un
  `docker` simulé : pause, reprise, et aucune commande `rm`, `stop` ni `kill`.

Commande, sur VM100, depuis `eidolon-core/` :

```sh
WAKE_ACTIVITY=/CHEMIN/ETAT-CORE/activity.json tools/wake_training/run_vm100.sh
tools/wake_training/run_vm100.sh status
```

Le modèle produit reste sous `~/eidolon-validation/g296/wake/models/`, avec `activated: false`.
L'activation dans le client (V1-c) attend le banc, puis les mesures Windows.

## 7. Limites

- Aucune exécution du code de Cornelius : il a été lu seulement, considéré comme non fiable,
  et cloné hors des dépôts. Aucune ligne copiée.
- Le modèle anglais `hey_jarvis` a servi **uniquement** à mesurer le coût ; il n'est ni livré
  ni référencé.
- Les licences des données d'entraînement sont celles déclarées par Cornelius ; à revérifier
  à la source avant entraînement.
- Rien de branché : client, Gemma actif, Memory, DARME et services restent inchangés.
  Webcam et audio ne sont jamais sortis de la machine.
