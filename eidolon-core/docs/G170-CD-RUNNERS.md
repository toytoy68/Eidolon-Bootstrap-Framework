# G170-C/D — Exécuteurs réels facultatifs (voix et visage)

Auteur : Claude. Date : 12/10/2026, Europe/Paris. Accord : G183 (C156-Q1).

**Rien n'est branché.** Aucune route, aucun service, aucun capteur, aucun
déploiement. Une reconnaissance ne donne **aucun droit**.

## 1. Fichiers

| Fichier | Rôle |
| --- | --- |
| `src/eidolon_core/identity_proposal.py` | décision : états, calibration, fusion, capture éphémère |
| `src/eidolon_core/identity_engines.py` | adaptateurs : modèle vérifié, capture → `Observation` |
| `src/eidolon_core/identity_runners.py` | exécuteurs réels : fbank + WeSpeaker ONNX, YuNet + SFace OpenCV |
| `docs/identity-models.json` | manifeste des modèles, à relire par Codex |
| `tests/test_identity_runners.py` | tests facultatifs, ignorés sans les dépendances |

## 2. Dépendances facultatives

- `onnxruntime` 1.23.2 (processeur) ;
- `opencv-python-headless` 4.12.0.88, **une seule** distribution OpenCV ;
- `numpy` 2.2.6.

Elles ne sont importées **qu'à l'usage**. Le cœur de Core n'en dépend pas.
`pyproject.toml` relève du packaging de Codex : je ne l'ai pas modifié.
Groupe proposé : `identity = ["onnxruntime>=1.23,<1.24",
"opencv-python-headless>=4.12,<4.13", "numpy>=2,<2.3"]`.

## 3. Modèles (voir le manifeste)

| Modèle | Obtenu | Empreinte |
| --- | --- | --- |
| YuNet 2023mar | oui, opencv_zoo à la révision `47534e2` | calculée = publiée (pointeur Git LFS) |
| SFace 2021dec | oui, même révision | calculée = publiée |
| WeSpeaker ResNet34-LM | **non** : le réseau de la session refuse wenet.org.cn, huggingface.co et modelscope.cn | aucune, **non inventée** |

Les poids ne sont **pas** dans Git. Les tests les cherchent dans le dossier
indiqué par `EIDOLON_IDENTITY_MODELS`.

## 4. Points de revue G183

1. **Possession de la capture** :
   - un `bytearray` est **repris sans copie** ; ce tampon est mis à zéro à la
     sortie, en cas d'erreur ou d'annulation, même si l'adaptateur le refuse ;
   - des `bytes` sont immuables : ils sont copiés une fois, la copie est
     effacée, et `source_wiped` vaut `False` ;
   - les exécuteurs effacent leurs propres copies : caractéristiques fbank,
     image décodée, visage recadré ;
   - **aucune promesse** sur les copies internes d'ONNX Runtime, d'OpenCV ou
     de la couche HTTP.
2. **Vérification puis chargement** :
   - `verify_model` ouvre le fichier une seule fois (`O_NOFOLLOW`), contrôle
     sur ce même descripteur et lit les octets ;
   - l'empreinte porte sur ces octets, et les exécuteurs chargent **ces
     octets**, jamais le chemin ;
   - testé : lien symbolique refusé, dossier refusé, taille bornée, fichier
     remplacé après vérification sans effet.

## 5. Preuves (conteneur Claude)

- **fbank** : écart maximal de **0,0012** (en log) avec `kaldi-native-fbank`
  1.21.3, sur 5 durées de 400 échantillons à 10 s. torchaudio n'a pas pu
  être installé (index PyTorch refusé par le réseau).
- **Voix** : modèle ONNX **synthétique** à la signature de WeSpeaker. Chaîne
  vérifiée : chargement depuis les octets, adaptateur, résultat « known » sur
  un profil inventé. Ce n'est **pas** un modèle de locuteur.
- **Visage** : vrais YuNet et SFace. Une image unie donne « pas de visage » ;
  un vecteur de 128 valeurs finies est obtenu sur une image de bruit avec une
  boîte inventée. L'image décodée est effacée ensuite.
- **Non vérifié** :
  - la détection d'un vrai visage : aucune photo de personne, par règle ;
  - le vrai modèle WeSpeaker ;
  - toute mesure de précision, prévue en G170-F.
