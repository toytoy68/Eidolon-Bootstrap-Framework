# Moteurs d'inférence pour 2 × V100 SXM2/NVLink — étude et protocole

Auteur : Claude, 05/10/2026 (Europe/Paris). Fiche
[C-CLAUDE-002, étape 1](../collaboration/tasks/C-CLAUDE-002.md). Complète la
[note matérielle de Codex/GPT](INFERENCE-2XV100-2026-10-05.md), sans la remplacer.
Statut : **étude documentaire**. Aucun moteur installé, aucun poids téléchargé,
aucune machine contactée. Toutes les performances sont **NON MESURÉES**.
Aucun moteur ni modèle n'est choisi par ce document.

## 1. Sources et méthode

Les sites `docs.nvidia.com`, `developer.nvidia.com`, `images.nvidia.com`,
`docs.ollama.com`, `docs.vllm.ai` et `lmdeploy.readthedocs.io` sont bloqués par
le proxy de cette session. J'ai lu les mêmes contenus dans les **dépôts
officiels** de chaque projet, le 05/10/2026 vers 14 h 35, à ces commits :

| Projet | Commit lu | Fichiers (SHA-256, 12 premiers caractères) |
| --- | --- | --- |
| `ollama/ollama` | `42e911bc3d05` | `docs/gpu.mdx` (`c0e73ade4fa9`), `docs/faq.mdx` (`7fc6dd6825f9`), `envconfig/config.go`, `CMakeLists.txt` |
| `ggml-org/llama.cpp` | `8f9ae20c86ab` | `docs/multi-gpu.md` (`08508e676483`), `docs/build.md` (`af682686b967`), `ggml/src/ggml-cuda/CMakeLists.txt` (`758913e522a4`), `common.cuh` (`cde04ff564d8`), `fattn.cu` (`8cd53030107e`), `tools/server/README.md` (`180acdc268c1`) |
| `vllm-project/vllm` | `51eeb0c58f77` | `docs/getting_started/installation/gpu.cuda.inc.md` (`bfb1aee80722`) |
| `InternLM/lmdeploy` | `110965c7706b` | `docs/en/get_started/installation.md` (`549772d642a3`), `README.md` (`ccce70626461`) |
| `NVIDIA/TensorRT-LLM` | `82f980469fab` | `docs/source/overview.md` (`211c6eb91767`) ; matrice de support introuvable dans le dépôt |

Je n'ai pas pu relire les références NVIDIA [1] et [2] de la note de Codex/GPT.
Ses constats sur la compute capability 7.0 et la fiche V100 restent les siens.

Chaque constat porte sa nature : **doc** (documentation du projet), **code**
(lu dans le code source, plus fragile qu'une promesse documentée) ou
**déduction** (mon raisonnement, à confirmer).

## 2. Contraintes Volta (compute capability 7.0)

| Contrainte | Nature et source | Conséquence |
| --- | --- | --- |
| Tensor cores FP16, pas de tensor cores int8 | code : commentaires de `ggml-cuda/CMakeLists.txt` (« 70 == V100, FP16 tensor cores ; 75 == Turing, int8 tensor cores ») ; doc : `build.md`, option `GGML_CUDA_FORCE_MMQ` (« affects V100 ») | Les poids quantifiés sont calculés via FP16 ; les gains d'une quantification int8 vus sur Turing ou plus récent ne se transposent pas |
| Pas de BF16 rapide | code : `common.cuh`, `fast_bf16_hardware_available` exige Ampere | Un modèle publié en BF16 tourne converti ou émulé ; vérifier la précision et le risque de débordement en FP16 |
| llama.cpp calcule en FP32 sur V100 pour cuBLAS | doc : `build.md`, option `GGML_CUDA_FORCE_CUBLAS` (V100 « use FP32 compute type by default ») | Choix conservateur contre les débordements FP16 ; ne pas le forcer autrement sans essai de qualité |
| **CUDA Toolkit 13 n'inclut plus Volta** | code : `CMakeLists.txt` n'ajoute `70-virtual` que si la version du toolkit est inférieure à 13 ; **déduction** : CUDA 13 ne cible plus sm_70 | Construire et figer avec un **CUDA 12.x**. Toute image ou roue compilée seulement pour CUDA 13 est à exclure pour la V100 |
| Pilote | doc : Ollama exige le pilote 550 ou plus récent ; doc vLLM : CUDA 13 exige R580 ou plus récent | Choisir une branche de pilote qui gère la V100 et CUDA 12.x. Volta est en fin de support chez NVIDIA ; **non vérifié** ici faute d'accès aux pages NVIDIA. Prévoir un miroir local des paquets figés |

## 3. Matrice des moteurs

| Critère | Ollama | llama.cpp (`llama-server`) | LMDeploy (TurboMind) | vLLM | TensorRT-LLM |
| --- | --- | --- | --- | --- | --- |
| V100 | **Listée** (cc 7.0, pilote 550+) — doc | Cible `70` tant que CUDA < 13 ; chemins dédiés à Volta — code | **Listée** : « Volta (sm70): V100 » — doc ; CUDA Toolkit 12.0+ | **Exclue** : « compute capability 7.5 or higher » — doc | Aucune mention de Volta ; matrice inaccessible — **non vérifié** |
| Un modèle sur un GPU | Automatique si le modèle tient sur un GPU — doc FAQ | `--split-mode none`, `--device` — doc | `tp=1` | — | — |
| Un modèle sur deux GPU | Réparti sur tous les GPU s'il ne tient pas sur un seul ; `OLLAMA_SCHED_SPREAD` force la répartition — doc et code ; mode de découpage non documenté | `layer` (pipeline, par défaut) ou `tensor` (**expérimental**, exige FlashAttention et un cache KV non quantifié) — doc | Parallélisme de tenseur annoncé — doc README ; **sur V100 : non vérifié** | — | — |
| Exploite NVLink | Non documenté | `tensor` + NCCL (par défaut à la compilation) + `GGML_CUDA_P2P=1` (opt-in ; « may cause crashes or corrupted outputs » avec certains BIOS ou l'IOMMU) — doc | Probable via NCCL ; non vérifié | — | — |
| Deux rôles, un GPU chacun | `CUDA_VISIBLE_DEVICES` par instance — doc | Une instance par GPU avec `--device` — doc | Une instance par GPU | — | — |
| Sortie JSON contrainte | `format` (schéma JSON) — doc | `json_schema` et `response_format` sur `/v1/chat/completions` — doc | Non lu | — | — |
| API | `/api/chat` (adaptateur Core existant) | API compatible OpenAI, `/metrics` Prometheus — doc | Serveur d'API documenté (non lu en détail) | — | — |
| Format de poids | GGUF | GGUF | HF, AWQ (W4A16), MXFP4 « starting from V100 » — doc README | — | — |
| Verdict de l'étude | **Candidat** : le plus simple pour les profils 1 et 3 | **Candidat** : le seul qui documente le partage tenseur + NCCL + P2P, donc le seul à pouvoir tirer parti de NVLink | **Candidat secondaire** : seul moteur orienté débit qui liste la V100 ; à qualifier | **Écarté** sans version ancienne qualifiée | **Écarté** faute de preuve |

À ce commit, Ollama s'appuie sur `llama-server`, compilé à partir d'une version
figée de llama.cpp (code : `CMakeLists.txt` d'Ollama, « GGML backend for
inference is provided by llama-server … from the pinned llama.cpp source »).
Les noyaux Volta sont donc les mêmes ; ce qui change, c'est le placement,
automatique chez Ollama, et la version de llama.cpp, qu'Ollama choisit. Les deux
peuvent charger les mêmes fichiers GGUF, ce qui permet de comparer leur
placement avec des poids identiques.

## 4. Les trois profils et l'intérêt réel de NVLink

| Profil | Placement | Trafic entre GPU | Rôle de NVLink |
| --- | --- | --- | --- |
| 1 — un modèle, un GPU | Contrôleur sur GPU0 | Aucun | Aucun ; sert de **référence** |
| 2a — un modèle, deux GPU, `layer` | Couches réparties, cache KV suivant ses couches | Activations à la frontière des couches, à chaque jeton | Faible ; NVLink n'est pas nécessaire (déduction) |
| 2b — un modèle, deux GPU, `tensor` | Poids **et** cache KV partagés | Réductions à chaque couche | **Déterminant** ; c'est le seul profil où NVLink compte (déduction) |
| 3 — deux rôles | Contrôleur sur GPU0, tâche auxiliaire sur GPU1 | Aucun | Aucun |

**Point d'attention propre au montage** : NVLink ne sert le profil 2b que si
l'accès pair-à-pair (P2P) fonctionne **dans l'environnement d'exécution**.
Avec une VM, les deux modules doivent être confiés à la **même** VM, et
llama.cpp signale lui-même que le P2P peut corrompre les sorties avec l'IOMMU,
qui est justement actif en passthrough. Sur une carte adaptatrice SXM2 vers
PCIe, ni le nombre de liens NVLink câblés ni la largeur PCIe vers l'hôte ne
sont connus. Tant que le P2P n'est pas validé dans la VM, le profil 2b n'est
qu'une hypothèse.

**Dimensionnement** (règle de Codex/GPT reprise) : budget d'un GPU = poids placés
+ cache KV + tampons + marge, à comparer à 32 Go par GPU, jamais à 64 Go en bloc.
Cache KV d'un modèle par jeton ≈ 2 × couches × têtes KV × dimension d'une tête
× octets par valeur. Avec `tensor`, le cache est partagé entre les GPU ; avec
`layer`, il suit les couches.

## 5. Réponse à C-BRAIN-007 (question de Codex/GPT)

**Profil qui sert le mieux la latence du contrôleur tout en gardant une
capacité multimédia : le profil 3** (déduction, à confirmer par la recette).
Le contrôleur ne partage ni sa mémoire ni ses cycles avec la Vision ou la
transcription. Il ne dépend ni du P2P ni de l'IOMMU. Et une panne du GPU1
n'arrête pas la planification. Le profil 2b ne se justifie que si le
contrôleur qualifié ne tient pas dans 32 Go **avec** le cache de contexte
nécessaire, et seulement après validation du P2P dans la VM. Le profil 1 reste
la mesure de référence de chaque essai.

## 6. Protocole de qualification (recette ultérieure)

Ordre des essais. Chacun produit un manifeste (§ 7) ; un essai raté arrête la
suite qui en dépend.

| Étape | Essai | Critère de passage |
| --- | --- | --- |
| R0 | Inventaire : `nvidia-smi -q`, `nvidia-smi topo -m`, `nvidia-smi nvlink -s`, largeur et génération PCIe, pilote, CUDA, depuis l'hôte **et** depuis la VM | Deux V100 SXM2 visibles dans l'environnement visé ; topologie NVLink constatée |
| R1 | Test P2P (bande passante et latence pair-à-pair, par exemple l'exemple `p2pBandwidthLatencyTest` des CUDA samples) dans la VM | P2P actif ; débit NVLink mesuré bien supérieur au chemin PCIe |
| R2 | Profil 1 avec le corpus Core et les témoins de C-BRAIN-006 | Aucune violation ; mesures de référence |
| R3 | Profil 3 : contrôleur seul puis contrôleur + charge auxiliaire simulée sur GPU1 | La latence du contrôleur ne se dégrade pas au-delà d'un seuil fixé avant l'essai |
| R4 | Profil 2a (`layer`) | Qualité identique au profil 1 ; gain ou perte mesuré |
| R5 | Profil 2b (`tensor`, NCCL, `GGML_CUDA_P2P=1`), seulement si R1 réussit | Aucune sortie corrompue sur N répétitions ; qualité identique au profil 1 |

Chaque essai se répète avec plusieurs graines. Une seule violation de périmètre
élimine la configuration, quelle que soit sa vitesse (C-BRAIN-006).

## 7. Manifeste de mesure — télémétrie minimale (question G-017)

Champs figés dans chaque rapport ; un champ inconnu est noté `null`, jamais omis.

```json
{
  "schema": "eidolon-inference-run/1",
  "hardware": {"gpus": [{"index": 0, "uuid": null, "name": null, "vbios": null, "memory_mib": null}],
               "topology": null, "nvlink_links_active": null, "pcie_gen_width": null,
               "p2p_verified": null, "host_cpu": null, "host_ram_gib": null,
               "virtualization": {"vm": null, "passthrough": null, "iommu": null}},
  "software": {"driver": null, "cuda_runtime": null, "engine": null, "engine_version": null,
               "engine_commit": null, "build_flags": null, "cuda_architectures": null, "nccl": null},
  "model": {"name": null, "weights_sha256": null, "format": null, "quantization": null,
            "context_tokens": null, "kv_cache_type": null, "flash_attention": null},
  "placement": {"profile": null, "split_mode": null, "tensor_split": null, "devices": null,
                "observed_vram_mib_per_gpu": null, "cpu_offload_detected": null},
  "workload": {"corpus": null, "corpus_sha256": null, "seeds": null, "parallel_requests": null},
  "measurements": {"ttft_ms": null, "prefill_tokens_per_s": null, "decode_tokens_per_s": null,
                   "power_w_per_gpu": null, "errors": null},
  "quality": {"outcomes": null, "violations": null, "lazy_baseline_score": null}
}
```

`cpu_offload_detected` et `observed_vram_mib_per_gpu` sont observés, pas tirés
de la configuration : un placement demandé n'est pas un placement constaté.

## 8. Conséquences pour Core

- L'adaptateur Ollama livré ([OLLAMA-ADAPTER.md](OLLAMA-ADAPTER.md)) reste un
  candidat valable : Ollama liste la V100. Rien dans l'étude ne le rend
  incompatible.
- llama.cpp expose une API compatible OpenAI avec sortie contrainte par schéma.
  Le qualifier demandera un second adaptateur. Je propose de l'écrire seulement
  si la recette retient llama.cpp, dans un fichier séparé
  (`openai_chat_model.py`), selon les mêmes règles que l'adaptateur Ollama.
- Le choix du moteur reste un réglage d'opérateur. Il n'entre ni dans le
  contrat de mission ni dans la politique d'outils.

## 9. Inconnues et limites

- Référence et révision de la carte adaptatrice, nombre de liens NVLink
  câblés, largeur PCIe vers l'hôte, refroidissement et alimentation des modules SXM2.
- Hyperviseur, IOMMU, regroupement des deux GPU dans la même VM, comportement
  du P2P en passthrough. VM100 n'est pas présumée héberger l'inférence.
- Branche de pilote exacte compatible à la fois avec Volta et CUDA 12.x :
  non vérifiée, faute d'accès aux pages NVIDIA.
- Parallélisme de tenseur de LMDeploy sur V100 : annoncé en général, non
  vérifié pour Volta.
- Les constats « code » peuvent changer à tout commit ; ils valent pour les
  commits cités. Revalider au moment de figer une version.
