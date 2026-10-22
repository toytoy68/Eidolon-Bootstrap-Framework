# Génération vidéo locale — ComfyUI + Wan 2.2 sur V100

> Composant expérimental de l'Eidolon Bootstrap Framework.
> Cible : nœud Debian 13 avec GPU NVIDIA **Volta** (Tesla V100 16 Go, puis 2 × V100 32 Go SXM2).
>
> Statut : **0.1.0-alpha — non testé sur le matériel réel.**

Tout tourne en local : aucune API distante, aucun filtre côté serveur.

## Contenu

| Fichier | Rôle |
|---|---|
| `install-comfyui.sh` | Installe ComfyUI, PyTorch compatible Volta, les nœuds GGUF / VideoHelperSuite / MultiGPU / Manager et un service systemd |
| `download-models.sh` | Télécharge les modèles Wan 2.2 selon un profil de VRAM |
| `workflows/wan22-ti2v-5b-v100-16g.json` | Texte → vidéo, Wan 2.2 5B fp16 — **point de départ sur la V100 16 Go** |
| `workflows/wan22-t2v-14b-gguf-v100.json` | Texte → vidéo, Wan 2.2 14B GGUF (High + Low Noise), 20 étapes |
| `workflows/wan22-t2v-14b-gguf-4steps-v100.json` | Idem avec le LoRA lightx2v : 4 étapes, ~5× plus rapide |
| `eidolon_video.py` | Client API (Python standard) utilisable par Eidolon, avec enrichissement du prompt via Ollama |

Les workflows sont au **format API** de ComfyUI : ils se chargent dans l'interface (bouton *Load* ou glisser-déposer) et s'envoient tels quels à l'API.

## Points spécifiques à Volta (sm_70)

- **PyTorch** : la dernière version publiée avec des binaires Volta est la **2.14**, sur l'index **CUDA 12.6** (`cu126`). CUDA 13 ne gère plus les GPU antérieurs à Turing. Le script installe `torch<2.15` depuis `cu126` puis **verrouille** cette version (`eidolon-constraints.txt`) pour que les dépendances ne la remplacent pas.
- **Pas de bf16 natif ni de FP8** : ComfyUI est lancé avec `--force-fp16`. Les poids FP8 (encodeur texte UMT5) sont stockés en FP8 mais calculés en fp16 : ça fonctionne, sans le gain de vitesse.
- **Attention** : PyTorch SDPA (défaut de ComfyUI). FlashAttention 2 et SageAttention 2 exigent Ampere ou plus.
- **GGUF** : la solution pour faire tenir le 14B dans 16 Go.

## Installation

Prérequis : `01-system` et `02-nvidia` exécutés, `nvidia-smi` fonctionnel.

```bash
sudo bash video-generation/install-comfyui.sh
```

Variables utiles (toutes facultatives) :

| Variable | Défaut | Rôle |
|---|---|---|
| `PRIMARY_USER` | `toytoy` | Utilisateur propriétaire et exécutant du service |
| `COMFY_DIR` | `/opt/eidolon/comfyui` | Répertoire d'installation |
| `COMFY_GPUS` | `0` | GPU visibles par ComfyUI (`0,1` avec deux V100) |
| `COMFY_PORT` | `8188` | Port HTTP |
| `TORCH_INDEX` / `TORCH_SPEC` | `cu126` / `torch<2.15` | Source et version de PyTorch |

Puis les modèles :

```bash
# V100 16 Go
sudo -u toytoy bash video-generation/download-models.sh 5b
sudo -u toytoy bash video-generation/download-models.sh 14b lightx2v

# 2 × V100 32 Go
sudo -u toytoy bash video-generation/download-models.sh 14b-q8 lightx2v
```

Démarrage :

```bash
sudo systemctl start eidolon-comfyui
journalctl -u eidolon-comfyui -f
```

Interface : `http://<ip-du-serveur>:8188`.
Le service écoute sur `0.0.0.0` : ne pas l'exposer hors du réseau local (pas d'authentification).

## Quel modèle selon la carte

| Configuration | Workflow conseillé | Réglages de départ |
|---|---|---|
| V100 16 Go | `wan22-ti2v-5b-v100-16g` | 832×480, 73 images, 24 i/s, 30 étapes |
| V100 16 Go, meilleure qualité | `wan22-t2v-14b-gguf-4steps-v100` (Q4_K_M) | 832×480, 81 images, 16 i/s, 4 étapes |
| V100 32 Go | `wan22-t2v-14b-gguf-v100` avec Q8_0 | 1280×720, 81 images, 20 étapes |

Avec Q8_0, adapter les noms de fichiers :

```bash
--set 1.unet_name=Wan2.2-T2V-A14B-HighNoise-Q8_0.gguf \
--set 2.unet_name=Wan2.2-T2V-A14B-LowNoise-Q8_0.gguf
```

Le nombre d'images doit valoir un multiple de 4, plus 1 (49, 73, 81…). Les largeurs et hauteurs doivent être des multiples de 32 pour le 5B, de 16 pour le 14B.

**Deux V100** : ComfyUI exécute un workflow sur un seul GPU. Deux options :
- lancer **deux instances** (une par GPU, ports différents) et répartir les tâches ;
- utiliser les nœuds **ComfyUI-MultiGPU** (installés) pour placer l'encodeur texte et le VAE sur la seconde carte et garder toute la VRAM de la première pour le modèle vidéo.

## Utilisation depuis Eidolon

```bash
python3 video-generation/eidolon_video.py \
  -w video-generation/workflows/wan22-ti2v-5b-v100-16g.json \
  -p "Un phare dans la tempête, vagues énormes, plan aérien lent" \
  --server http://<ip-du-serveur>:8188 --out ./outputs
```

Options principales : `--seed`, `--width`, `--height`, `--length`, `--fps`, `--steps`, `--negative`, `--prefix`, `--set NŒUD.entrée=valeur` (répétable), `--dry-run` (affiche le workflow final sans l'envoyer).

Le script affiche le chemin du fichier produit sur la sortie standard : facile à récupérer depuis un autre programme.

### Enrichissement du prompt par un LLM local

Wan 2.2 donne de bien meilleurs résultats avec un prompt détaillé en anglais (sujet, action, décor, lumière, caméra, style). L'option `--enhance` transforme une idée courte en prompt complet via **Ollama** :

```bash
python3 video-generation/eidolon_video.py -w ... -p "un renard dans la neige" \
  --enhance --ollama-url http://<ip>:11434 --ollama-model qwen3:14b
```

Modèles conseillés :
- `qwen3:8b` / `qwen3:14b` : modèles officiels ;
- `huihui_ai/qwen3-abliterated:8b` / `:14b` : variantes sans refus, si le modèle officiel refuse de reformuler certaines idées.

**VRAM** : ne pas charger le LLM et Wan sur la même V100 16 Go en même temps. Placer Ollama sur la GTX 1060 6 Go (un 8B quantifié y tient) ou sur le CPU, ou laisser Ollama décharger le modèle (`keep_alive: 0`) avant la génération vidéo.

## Usage responsable

L'absence de filtre ne lève pas la loi. Restent interdits, et ne doivent jamais être générés avec cet outil :
- tout contenu sexualisant des mineurs ;
- les deepfakes d'une personne réelle sans son consentement, en particulier à caractère sexuel (sanctionnés pénalement en France, notamment depuis la loi SREN de 2024) ;
- les contenus destinés à tromper sur des faits réels (fausses preuves, usurpation d'identité).

## Dépannage

| Symptôme | Piste |
|---|---|
| `no kernel image is available for execution on the device` | PyTorch sans sm_70 : vérifier `torch.cuda.get_arch_list()` et réinstaller depuis `cu126` |
| Vidéo noire ou NaN | Vérifier que `--force-fp16` est actif ; essayer `--fp32-vae` dans le service |
| Manque de VRAM (OOM) | Baisser la résolution ou le nombre d'images, passer en Q4_K_S ou Q3_K_M |
| Fichier de modèle absent dans l'interface | Vérifier le dossier (`models/diffusion_models`, `models/unet` pour les GGUF, `models/text_encoders`, `models/vae`, `models/loras`) puis rafraîchir |
| Erreur de validation à l'envoi | `--dry-run` puis comparer avec les entrées du nœud dans l'interface ; les nœuds ComfyUI évoluent vite |
