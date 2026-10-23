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
| `workflows/wan22-t2v-14b-gguf-4steps-v100.json` | Idem avec le LoRA lightx2v : 4 étapes, accélération à mesurer sur V100 |
| `eidolon_video.py` | Client API (Python standard) utilisable par Eidolon, avec enrichissement du prompt via Ollama |

Les workflows sont au **format API** de ComfyUI : ils se chargent dans l'interface (bouton *Load* ou glisser-déposer) et s'envoient tels quels à l'API.

## Points spécifiques à Volta (sm_70)

- **PyTorch** : la dernière version publiée avec des binaires Volta est la **2.14**, sur l'index **CUDA 12.6** (`cu126`). CUDA 13 ne gère plus les GPU antérieurs à Turing. Le script fixe `torch==2.14.0+cu126`, puis enregistre les versions résolues de torch/torchvision/torchaudio dans `eidolon-constraints.txt`. Ces contraintes sont appliquées aux installations du script, aux futurs appels pip de ce venv (`venv/pip.conf`) et au service (`PIP_CONSTRAINT`). Elles ne sont pas une protection contre une modification volontaire de la configuration.
- **Pas de bf16 natif ni de FP8** : ComfyUI est lancé avec `--force-fp16`. L’encodeur UMT5 est stocké en FP8 ; son chemin de conversion et de calcul sur Volta reste à valider par une vraie génération. Le seul test de multiplication fp16 ne valide pas cet encodeur.
- **Attention** : PyTorch SDPA (défaut de ComfyUI). FlashAttention 2 et SageAttention 2 exigent Ampere ou plus.
- **GGUF** : réduit le stockage des poids. La tenue dans 16 Go dépend aussi des activations, du VAE et des transferts vers la RAM ; les profils ne constituent pas une garantie sans mesure.

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
| `TORCH_INDEX` | `https://download.pytorch.org/whl/cu126` | Index proposant le build fixé `torch==2.14.0+cu126` |

ComfyUI et les quatre extensions sont fixés à des commits dans `sources.lock`.
Une réinstallation reprend ces commits, sans `git pull` implicite, et refuse les
modifications locales suivies par Git. Les autres dépendances Python restent résolues
par pip : l’environnement complet n’est pas encore verrouillé avec des hashes.
`pip check` et le calcul fp16 sur **chaque GPU visible** doivent réussir avant la
création/activation du service. Celui-ci n’est pas lancé par l’installateur, mais
sera lancé au prochain démarrage une fois activé. Un service préexistant n’est pas
arrêté ni désactivé automatiquement en cas d’échec de réinstallation.

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

**Deux V100** : les trois workflows fournis utilisent un seul GPU. Installer MultiGPU ou définir `COMFY_GPUS=0,1` ne distribue pas ces graphes et ne crée pas automatiquement un espace de 64 Go. Deux options à configurer et valider séparément :
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
Les noms distants doivent être de simples noms de fichiers : chemins, liens symboliques
et écrasements de fichiers existants sont refusés. Utiliser un dossier `--out` distinct
par génération si plusieurs serveurs produisent les mêmes noms.
Les téléchargements sont copiés par blocs ; les fichiers partiels sont supprimés en cas d’erreur.
Un dépassement du délai client **n’annule pas** le travail sur ComfyUI.
`--dry-run` effectue les contrôles locaux (dimensions, images, étapes, liens) et affiche
le JSON ; il ne valide ni les nœuds installés sur le serveur ni les modèles disponibles.
Avec `--enhance`, il appelle néanmoins Ollama pour préparer le prompt.

### Enrichissement du prompt par un LLM local

Wan 2.2 donne de bien meilleurs résultats avec un prompt détaillé en anglais (sujet, action, décor, lumière, caméra, style). L'option `--enhance` transforme une idée courte en prompt complet via **Ollama** :

```bash
python3 video-generation/eidolon_video.py -w ... -p "un renard dans la neige" \
  --enhance --ollama-url http://<ip>:11434 --ollama-model qwen3:14b
```

Modèles conseillés :
- `qwen3:8b` / `qwen3:14b` : modèles officiels ;
- `huihui_ai/qwen3-abliterated:8b` / `:14b` : variantes sans refus, si le modèle officiel refuse de reformuler certaines idées.

**VRAM** : le client envoie désormais `keep_alive: 0` par défaut pour demander à Ollama de décharger le modèle après enrichissement, y compris lors du repli sans `think`.
Sur un GPU séparé, `--ollama-keep-alive 5m` permet de le conserver. Ce réglage ne décharge
pas les autres modèles déjà présents et n’empêche pas une requête concurrente d’Eidolon
de recharger un LLM : réserver le GPU vidéo pour la recette. Sur la GTX 1060 6 Go,
choisir la quantification et le contexte en fonction de la mémoire réellement disponible.

## Validation

```bash
python3 -m unittest discover -s video-generation/tests -v
```

La suite est hors GPU : régressions du client, faux serveur HTTP, installation simulée
et dépôts Git temporaires. Elle ne télécharge aucun modèle et n’installe aucun service.
Voir [le rapport de validation](VALIDATION-2026-10-23.md).

Pour la première recette matérielle, utiliser le 5B et un clip court :

```bash
python3 video-generation/eidolon_video.py \
  -w video-generation/workflows/wan22-ti2v-5b-v100-16g.json \
  -p "A red fox walking slowly in snow, static camera" \
  --width 512 --height 320 --length 17 --steps 10 --seed 42 \
  --out ./outputs/recette-5b
```

C’est un test de fonctionnement, pas une mesure représentative de qualité. Relever
le temps total, le pic VRAM, la RAM et le swap, vérifier le MP4 avec `ffprobe` et regarder
les images pour détecter un résultat noir ou corrompu. Ensuite seulement, tester les
réglages du tableau, puis le 14B. Le passage de 20 à 4 étapes ne garantit pas un temps
total divisé par cinq : chargement, transferts et décodage restent nécessaires.

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

