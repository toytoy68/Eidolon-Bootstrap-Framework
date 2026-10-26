# Mot d'appel « Eidolon » — plan v3 et validation sur voix humaines (G296)

Claude, 27/10/2026 (C199). Ce plan est écrit **avant** tout entraînement v3. Les critères
sont dans [`gate-v3.json`](gate-v3.json) : leur empreinte sha256 est recopiée dans chaque
fiche de provenance et dans chaque banc. Les modifier exige une note datée ici.

## 1. Ce que disent les mesures v2 (exécutées par GPT sur VM100, 26/10)

Au seuil 0,5 :

- rappel 0,859 ;
- 0,374 FP/h sur les 11 h ordinaires ;
- 4 clips pièges déclenchés sur environ 2 000 ;
- latence p95 de 150 ms.

| Cause | Constat | Statut |
| --- | --- | --- |
| « Eilledolon » : 128 ratés sur 287 (55 % de rappel), contre 88 à 93 % pour les six autres graphies | C'est la seule graphie que les voix lisent **sans accent sur la première syllabe** : /ɛjdolˈɔ̃/, contre /ˈɛjdolɔ̃/ pour les autres. | Phonèmes : **exécuté** (phonémiseur de Piper 1.3.0, voix `fr`). Effet acoustique, une première syllabe avalée, **à vérifier à l'oreille** (`diagnose`). |
| Voix UPMC (Jessica et Pierre) : 753/1000, contre 98 % (Siwis) et 95 % (Tom) | Déjà la plus faible en v1 (845/1000). | Cause inconnue : on ne sait pas encore si elle tient à un des deux locuteurs, à une graphie ou à la durée. Le diagnostic croise graphie × voix × locuteur. |
| Chute générale du rappel entre v1 et v2 | `train.py` (368c037) double `max_negative_weight` avant les séquences 2 et 3 dès que les FP/h bruts dépassent `target_false_positives_per_hour` = 0,2. C'est plus sévère que notre critère de 0,5. | Code **lu** ; le journal v1 montre deux doublements. |
| Les FP/h « 11 h » ne sont pas un test tenu à l'écart | `train.py` sélectionne et fusionne les checkpoints sur ce même fichier. | Code **lu**. Les 0,374 FP/h de la v2 sont donc optimistes. |
| Le test synthétique n'est pas tenu à l'écart par locuteur | Les 3 voix comptent moins de 20 locuteurs : le générateur emploie les mêmes locuteurs en entraînement et en test. | Code **lu**. Seules des voix humaines donnent une vraie épreuve. |

## 2. Critères (`gate-v3.json`), écrits avant la v3

### Banc synthétique

Il autorise seulement les essais humains, pas l'activation.

- **Rappel** :
  - au moins 0,95 au total ;
  - au moins 0,90 **pour chaque graphie et pour chaque voix**, pour qu'une moyenne ne cache
    pas une graphie ou une voix cassée.
- **Faux déclenchements** :
  - au plus 0,5 FP/h sur la **moitié B** des négatifs openWakeWord, que `train.py` n'a jamais
    vue ;
  - le modèle doit avoir été sélectionné sur la moitié A seulement ; sinon le verdict est
    `GENERAL_AUDIO_NOT_HELD_OUT`.
- **Mots pièges** :
  - au plus 1 % des clips pièges qui déclenchent au total, et au plus 3,5 % par mot ;
  - c'est une **proportion de clips**, pas des « FP/h » : les pièges sont lus bout à bout, et
    les ramener à l'heure mesurait leur densité, pas un risque réel ;
  - le plafond de 0,5 FP/h reste appliqué là où il a un sens : le son ordinaire tenu à
    l'écart, puis les enregistrements domestiques.
- **Latence** : p95 d'au plus 500 ms.

Appliqué à la v2 au seuil 0,5, le banc rejette le modèle pour : `RECALL`,
`GENERAL_AUDIO_NOT_MEASURED`, `SPELLING:Eilledolon`, `SPELLING:Eïdolon` (0,898),
`SPELLING:Heïdolon` (0,882) et `VOICE:fr_FR-upmc-medium`. Les pièges passent (4 sur 2 000).
Ce n'est pas un assouplissement : il y a plus de planchers qu'avant, et un critère de plus,
la tenue à l'écart.

### Critères humains

Ils conditionnent l'activation. Mesure avec `wake_eval_g296.py` sur des enregistrements
annotés, jamais utilisés pour entraîner :

- un rappel d'au moins 0,95 **pour chaque personne** ;
- au plus 0,5 FP/h sur **au moins 8 h** d'ambiance domestique (télévision, repas,
  conversations, musique) ;
- **zéro** faux déclenchement pendant qu'Eidolon parle (écho) ;
- une latence p95 d'au plus 500 ms.

## 3. Ordre v3, avec une règle de décision écrite d'avance

1. **Diagnostic de la v2**, environ 15 min, sans entraînement :
   ```sh
   cd ~/eidolon-validation/g296/core && git pull -q && cd eidolon-core
   bash tools/wake_training/run_vm100.sh bench      # banc C199 : critères, croisements, détail par clip
   bash tools/wake_training/run_vm100.sh diagnose   # tableau graphie × voix, durées, phonèmes, extraits
   ```
   toytoy écoute `models/<v2>.diagnostic/a-ecouter/` (8 ratés et 8 réussis des trois pires
   cases) et répond à une question : « ces ratés disent-ils bien Eille-do-lon ? ».
2. **v3a**, environ 30 à 40 min, sans régénérer un seul clip : recette
   [`eidolon-training-v3.yml`](eidolon-training-v3.yml) (mêmes clips que la v2).
   - `target_false_positives_per_hour` passe à 0,25 sur la moitié A, soit environ 0,5 FP/h
     bruts réels, puisque `train.py` suppose 11,3 h ;
   - 100 000 étapes au lieu de 50 000.
   ```sh
   WAKE_ACTIVITY=/home/toytoy/eidolon-beta/profile-services/activity.json WAKE_GPU=0 \
   WAKE_CONFIG=eidolon-training-v3.yml nohup bash tools/wake_training/run_vm100.sh \
     > ~/eidolon-validation/g296/lancement-v3a.log 2>&1 &
   ```
   Le lanceur met de côté `output/eidolon_v2.onnx` (archivé avec son empreinte dans `models/`),
   puis entraîne ; le banc mesure sur la moitié B, avec les critères. Comparaison **appariée**
   avec la v2 : mêmes clips de test.
3. **Décision**, selon le résultat de la v3a :

   | Résultat de la v3a | Suite |
   | --- | --- |
   | passe le banc | essais humains (§4) |
   | échoue seulement sur `SPELLING:Eilledolon`, **et** l'écoute confirme une première syllabe avalée | **v3b** : retirer cette graphie (nouveau `model_name`, environ 2 h 30 de régénération). Ce défaut vient de la synthèse, pas de la prononciation de toytoy. |
   | échoue sur `VOICE:fr_FR-upmc-medium` malgré tout | décision à prendre par toytoy et GPT : ajouter une voix française à beaucoup de locuteurs (`fr_FR-mls-medium`, licence à vérifier). Le générateur fixe ses voix dans le code, donc il faudrait **modifier l'outil**, ce que notre règle « outil externe non modifié » interdit aujourd'hui. Le seul tenu à l'écart par locuteur viendrait aussi de là. |
   | autre échec | analyse avant tout nouvel entraînement ; jamais d'ajustement à l'aveugle |

## 4. Validation sur voix humaines (Windows)

Rien ne quitte la machine sans accord. Les enregistrements restent chez toytoy et ne servent
**jamais** à entraîner tant qu'ils servent d'épreuve.

1. **Consentement** de chaque personne enregistrée. Ni prénom ni voix dans Git.
2. **Enregistrement** en WAV 16 kHz mono :
   - par personne, 50 « Eidolon » dits naturellement, en 3 pièces et à 3 distances (1, 2 et
     4 m), à des moments différents de la journée ;
   - au moins 8 h d'ambiance domestique ordinaire, sans le mot ;
   - 30 min où Eidolon parle par les haut-parleurs du PC pendant qu'on lui coupe la parole :
     c'est l'écho, le lot V2-b.
3. **Annotation** `eidolon-wake-annotation/1` : début et fin de chaque « Eidolon », et
   intervalles où Eidolon parle (`playback`).
4. **Détection et score.** Le client Windows n'a pas de Python, par décision G296. Le score se
   fait donc dans le conteneur du kit sur VM100. toytoy y copie les enregistrements, sur son
   réseau local et avec l'accord des personnes enregistrées, sous
   `~/eidolon-validation/g296/humain/`, puis les efface après le rapport :
   ```sh
   H=~/eidolon-validation/g296/humain; W=~/eidolon-validation/g296/wake
   docker run --rm -v "$H:/humain" -v "$W/models:/models:ro" -v "$PWD/tools:/kit:ro" \
     --entrypoint python3.10 eidolon-wake-generator:1cc2c42 /kit/wake_training/detect_recording.py \
     --model /models/<modèle>.onnx \
     --melspec /opt/openWakeWord/openwakeword/resources/models/melspectrogram.onnx \
     --embedding /opt/openWakeWord/openwakeword/resources/models/embedding_model.onnx \
     --recording /humain/piece.wav --threshold <seuil du banc> --out /humain/piece.det.json
   python3 tools/evaluation/wake_eval_g296.py --annotation "$H/piece.json" --detections "$H/piece.det.json"
   ```
   Le seuil vient du banc (`gate.operating_threshold`), fixé **avant** l'écoute des
   enregistrements humains.
5. **Comparaison** sur les mêmes enregistrements avec le chemin actuel G282, en mettant les
   journaux côte à côte (`wake_eval` accepte n'importe quel détecteur).
6. Les critères humains (§2) décident. Sinon, pas d'activation : V1-c reste fermé.

## 5. Limites

- Je n'ai accès ni à VM100 ni au PC Windows. Tout le code est testé dans mon conteneur, et
  le pipeline banc → diagnostic a tourné de bout en bout sur un faux modèle exporté comme
  `train.py`, avec le vrai `pipeline.py` du générateur.
- Les durées de v3a sont estimées d'après la v2, pas mesurées.
- La correction du facteur de `train.py` (0,25 sur la moitié A) suppose que les négatifs
  sont répartis uniformément entre les deux moitiés.
