# G170-C/D — Moteurs locuteur et visage, contrat de sortie (revue, avant tout code)

Auteur : Claude. Date : 12/10/2026, Europe/Paris.
Cadre : [contrat G170 de Codex](USER-PROFILES-SPEAKER-RECOGNITION-G170.md), répartition G171.

**Statut** :
- revue et proposition **seulement** ;
- aucun modèle téléchargé ni installé, aucun code de moteur écrit ;
- la mesure et le choix final se feront avec Codex et toytoy.

## 1. Rappel des règles qui ne changent pas

- La reconnaissance **propose** un profil. Elle n'ouvre aucune session,
  ne change aucun rôle, ne donne accès à aucun souvenir privé et n'autorise
  aucune action.
- La clé du terminal et la connexion manuelle restent la base ; une action
  sensible demande une authentification explicite.
- Le score est **propre au moteur**. Ce n'est pas une probabilité d'identité.
  Les seuils sont **mesurés**, jamais choisis au hasard.
- Le LLM de vision (Gemma) ne sert **jamais** à reconnaître une personne.

## 2. Moteurs candidats : ce qui est vérifié

**Sources** :
- lues le 12/10/2026 : dépôts GitHub officiels ;
- **non lues** : Hugging Face et le site VoxCeleb d'Oxford sont injoignables
  depuis mon conteneur. Leur ligne porte la mention « à vérifier ».

### Locuteur (G170-C)

| Moteur | Code | Poids | Exécution | Constat |
| --- | --- | --- | --- | --- |
| **WeSpeaker** ResNet34 ou ECAPA (VoxCeleb) | Apache-2.0 (vérifié) | « suit la licence du jeu de données », soit **CC BY 4.0** pour VoxCeleb d'après WeSpeaker ; page VoxCeleb **à vérifier** | ONNX publié pour ResNet34, CAM++ et ECAPA (vérifié) ; dossier `runtime` | **Candidat principal** : petit modèle, ONNX sur processeur sans PyTorch ; entraîné en anglais, à mesurer sur des voix françaises |
| **SpeechBrain** `spkrec-ecapa-voxceleb` | Apache-2.0 (vérifié) | fiche Hugging Face **à vérifier** | PyTorch | Alternative de référence ; dépendance lourde (torch) sur le processeur de la VM |
| WeSpeaker multilingue (VoxBlink2, SimAMResNet) | Apache-2.0 | licence de VoxBlink2 **à vérifier** | ONNX publié | À regarder si l'anglais seul donne de mauvais résultats en français |

### Visage (G170-D)

| Moteur | Code | Poids | Constat |
| --- | --- | --- | --- |
| **OpenCV YuNet** (détection) + **SFace** (reconnaissance) | MIT (YuNet) et Apache-2.0 (SFace) : « tous les fichiers du dossier », vérifié | idem ; données d'entraînement de SFace **non précisées** | **Candidat principal** : ONNX par `opencv-python`, léger sur processeur, alignement sur 5 points |
| dlib `face_recognition_resnet_model_v1` | Boost (dlib) | **CC0** (vérifié), mais entraîné sur FaceScrub, VGG et des images collectées sur le web | **Gardé en secours** (décision de toytoy, 12/10/2026) ; différé pour la v0.1 (G172) |
| InsightFace (`buffalo_l`…) | MIT | **recherche non commerciale seulement**, ou licence à demander (vérifié) | **Écarté** pour l'instant |

### Rejeu et voix synthétique

- Aucun détecteur open source de rejeu retenu.
- Le jeu ASVspoof 2019 est **CC BY-NC-ND**, donc non commercial.
- Parades proposées, qui ne demandent aucun modèle :
  1. la reconnaissance de voix est **ignorée pendant que la voix d'Eidolon
     parle**, et 1 s après ;
  2. un enregistrement diffusé ne peut **rien** autoriser, puisque la
     biométrie n'autorise rien (§1) ;
  3. la recette mesure le rejeu, sans le déclarer bloqué.

## 3. Contrat de sortie proposé `eidolon-identity-proposal/1`

Une proposition par modalité :

```json
{"schema": "eidolon-identity-proposal/1",
 "modality": "voice",
 "state": "known",
 "profile_id": "profil-fictif-a",
 "candidates": [{"profile_id": "profil-fictif-a", "score": 0.71}, {"profile_id": "profil-fictif-b", "score": 0.42}],
 "score_kind": "cosine/wespeaker-resnet34/1",
 "threshold_id": "mesure-2026-10-xx/1",
 "observed_at": "2026-10-12T10:00:00+00:00", "valid_until": "2026-10-12T10:00:30+00:00",
 "engine": {"name": "wespeaker", "model": "resnet34-voxceleb", "sha256": "…"},
 "grants": [], "authorizes_execution": false}
```

**États** :

| État | Quand | `profile_id` |
| --- | --- | --- |
| `known` | un seul profil au-dessus du seuil **mesuré**, avec un écart suffisant sur le suivant | ce profil |
| `ambiguous` | plusieurs profils proches, ou désaccord voix/visage | `null` (candidats listés) |
| `unknown` | aucun profil au-dessus du seuil | `null` |
| `too_short` | parole utile inférieure à la durée minimale mesurée | `null` |
| `silence` | sous le seuil d'énergie (même règle que G164) | `null` |
| `several_people` | plusieurs visages, ou paroles simultanées détectées | `null` |
| `no_face` | aucun visage détecté | `null` |
| `stale` | `valid_until` dépassé | `null` |
| `unavailable` | moteur absent ou en erreur | `null` |
| `not_enrolled` | aucun gabarit pour cette modalité | `null` |

**Règles de forme** :
- `grants` est **toujours vide** et `authorizes_execution` toujours `false`
  (vérifié côté serveur) ;
- `profile_id` n'est **jamais** lu depuis le navigateur ni le LLM : seul le
  moteur le produit, et seul le serveur le compare aux profils.

**Fusion voix + visage** (G170-D, fonction pure) :

| Voix | Visage | Résultat |
| --- | --- | --- |
| `known` A | `known` A | `known` A, les deux à jour |
| `known` A | `known` B | **`ambiguous`**, sans aucun changement de profil |
| `known` A | autre état | `known` A, voix seule (un seul capteur suffit) |
| `stale` ou `unavailable` des deux côtés | | `unavailable` |

Le résultat reste une **proposition**. Le changement de profil se fait par
G170-B (Codex) : confirmation, annulation des réponses en vol, contexte
vidé.

## 4. Enrôlement local (proposé)

- Sur le PC, la personne est présente et volontaire, la capture est
  visible, et un bouton « Arrêter » est toujours disponible.
- Voix : 3 phrases de 5 à 8 s. Visage : 3 vues de face, avec un éclairage
  normal.
- Le serveur calcule les gabarits (vecteurs), puis **efface les prises
  brutes** dès le calcul fait. Aucune conservation par défaut.
- Stockage privé (0600) lié au profil confirmé de G170-A. Effacement et
  réenregistrement possibles, avec un test d'effacement réel.
- Rien dans Git, rien dans le chat ; les tests utilisent des vecteurs
  synthétiques et des noms fictifs.

## 5. Mesures nécessaires avant de fixer les seuils (G170-F)

| Mesure | Comment |
| --- | --- |
| Faux acceptés et faux rejets (voix, visage) | Enrôlement des trois personnes réelles, puis essais croisés au PC |
| Bruit, distance, micro de la webcam ou micro USB | Même protocole que G164 |
| Rejeu d'un enregistrement, voix d'Eidolon | Le résultat attendu est **noté**, pas « bloqué » |
| Ressources | Processeur et mémoire de la VM, durée par décision, contention avec Whisper (G167 : `Nice`) |

## 6. Questions pour Codex et toytoy

1. Moteurs principaux : WeSpeaker en ONNX pour la voix, et OpenCV
   YuNet + SFace pour le visage. D'accord pour les mesurer ?
2. Peux-tu vérifier depuis la VM les fiches non lues (VoxCeleb, carte
   SpeechBrain, VoxBlink2) ?
3. Le contrat `eidolon-identity-proposal/1` (§3) te va-t-il avant que
   j'écrive l'adaptateur isolé et ses tests synthétiques ?
4. dlib : **réglé**. toytoy le garde en secours (12/10/2026), et il est
   différé pour la v0.1 (G172).
