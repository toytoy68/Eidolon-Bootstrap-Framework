# Moteurs d'inférence pour 2 × V100 SXM2/NVLink — étude et protocole

Auteur : Claude, 05/10/2026 (Europe/Paris). Fiche
[C-CLAUDE-002, étape 1](../collaboration/tasks/C-CLAUDE-002.md). Complète la
[note matérielle de Codex/GPT](INFERENCE-2XV100-2026-10-05.md), sans la remplacer.
Statut : **étude documentaire**. Aucun moteur installé, aucun poids téléchargé,
aucune machine contactée. Toutes les performances sont **NON MESURÉES**.
Aucun moteur ni modèle n'est choisi par ce document.

**Révision du 05/10, fiche [C-TASK-G003](../collaboration/tasks/C-TASK-G003.md)** :
Codex/GPT a relevé quatre formulations qui dépassaient leurs preuves. Elles
sont corrigées ci-dessous (« seul moteur » pour NVLink, rôle de NVLink selon
le mode, isolation de panne, précision FP32). La version d'origine reste
lisible dans l'historique Git (`ec7582b`). Les réponses de Codex/GPT à G1 et G2
sont intégrées au protocole (§ 6) ; ce sont ses réponses, pas une décision de toytoy.

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
| Un chemin de llama.cpp passe en FP32 sur V100 | doc : `build.md`, option `GGML_CUDA_FORCE_CUBLAS` : pour les **multiplications matricielles des modèles quantifiés passées par cuBLAS FP16**, V100 « use FP32 compute type by default » ; code : `ggml-cuda.cu` (commit `8f9ae20`, l. 1511), `prefer_f32_output` vrai pour Volta dans le chemin cuBLAS FP16 | Vaut pour ce chemin seulement, pas pour tous les calculs d'une V100. Le choix entre ce chemin et les noyaux MMQ dépend du type de poids et de la taille de lot ; **non vérifié** pour un modèle donné. À relever dans les journaux du moteur pendant la recette |
| **CUDA Toolkit 13 n'inclut plus Volta** | code : `CMakeLists.txt` n'ajoute `70-virtual` que si la version du toolkit est inférieure à 13 ; **déduction** : CUDA 13 ne cible plus sm_70 | Construire et figer avec un **CUDA 12.x**. Toute image ou roue compilée seulement pour CUDA 13 est à exclure pour la V100 |
| Pilote | doc : Ollama exige le pilote 550 ou plus récent ; doc vLLM : CUDA 13 exige R580 ou plus récent | Choisir une branche de pilote qui gère la V100 et CUDA 12.x. Volta est en fin de support chez NVIDIA ; **non vérifié** ici faute d'accès aux pages NVIDIA. Prévoir un miroir local des paquets figés |

## 3. Matrice des moteurs

| Critère | Ollama | llama.cpp (`llama-server`) | LMDeploy (TurboMind) | vLLM | TensorRT-LLM |
| --- | --- | --- | --- | --- | --- |
| V100 | **Listée** (cc 7.0, pilote 550+) — doc | Cible `70` tant que CUDA < 13 ; chemins dédiés à Volta — code | **Listée** : « Volta (sm70): V100 » — doc ; CUDA Toolkit 12.0+ | **Exclue** : « compute capability 7.5 or higher » — doc | Aucune mention de Volta ; matrice inaccessible — **non vérifié** |
| Un modèle sur un GPU | Automatique si le modèle tient sur un GPU — doc FAQ | `--split-mode none`, `--device` — doc | `tp=1` | — | — |
| Un modèle sur deux GPU | Réparti sur tous les GPU s'il ne tient pas sur un seul ; `OLLAMA_SCHED_SPREAD` force la répartition — doc et code ; mode de découpage non documenté | `layer` (pipeline, par défaut) ou `tensor` (**expérimental**, exige FlashAttention et un cache KV non quantifié) — doc | Parallélisme de tenseur annoncé — doc README ; **sur V100 : non vérifié** | — | — |
| NVLink dans la doc lue | Non documenté (absence de documentation, pas preuve d'impossibilité) | `tensor` + NCCL (par défaut à la compilation) + `GGML_CUDA_P2P=1` (opt-in ; « may cause crashes or corrupted outputs » avec certains BIOS ou l'IOMMU) — doc | Non documenté dans les fichiers lus ; non vérifié | — | — |
| Deux rôles, un GPU chacun | `CUDA_VISIBLE_DEVICES` par instance — doc | Une instance par GPU avec `--device` — doc | Une instance par GPU | — | — |
| Sortie JSON contrainte | `format` (schéma JSON) — doc | `json_schema` et `response_format` sur `/v1/chat/completions` — doc | Non lu | — | — |
| API | `/api/chat` (adaptateur Core existant) | API compatible OpenAI, `/metrics` Prometheus — doc | Serveur d'API documenté (non lu en détail) | — | — |
| Format de poids | GGUF | GGUF | HF, AWQ (W4A16), MXFP4 « starting from V100 » — doc README | — | — |
| Verdict de l'étude | **Candidat** : le plus simple pour les profils 1 et 3 | **Candidat** : parmi les fichiers lus, le seul dont la documentation décrit un partage par tenseurs avec NCCL et P2P. Cela ne prouve pas qu'un autre moteur ne pourrait pas utiliser NVLink ; aucun test matériel n'a été fait | **Comparaison documentaire secondaire** : parmi les moteurs orientés débit lus ici, le seul qui liste la V100 ; pas d'installation avant le premier protocole GGUF (G2) | **Écarté** sans version ancienne qualifiée | **Écarté** faute de preuve |

À ce commit, Ollama s'appuie sur `llama-server`, compilé à partir d'une version
figée de llama.cpp (code : `CMakeLists.txt` d'Ollama, « GGML backend for
inference is provided by llama-server … from the pinned llama.cpp source »).
Les noyaux Volta sont donc les mêmes ; ce qui change, c'est le placement,
automatique chez Ollama, et la version de llama.cpp, qu'Ollama choisit. Les deux
peuvent charger les mêmes fichiers GGUF, ce qui permet de comparer leur
placement avec des poids identiques.

## 4. Les trois profils et le rôle attendu de NVLink

Les colonnes « trafic » et « rôle attendu » sont des **déductions** tirées du
principe de chaque mode. Aucune n'est mesurée ; ce ne sont pas des propriétés garanties.

| Profil | Placement | Trafic entre GPU attendu | Rôle attendu de NVLink |
| --- | --- | --- | --- |
| 1 — un modèle, un GPU | Contrôleur sur GPU0 | Aucun pour l'inférence | Aucun ; sert de **référence** |
| 2a — un modèle, deux GPU, `layer` | Couches réparties, cache KV suivant ses couches | Activations à la frontière des couches : à chaque jeton en génération, en volume plus important pendant le traitement du prompt | Contribution attendue plus faible qu'en 2b, mais pas nulle : elle dépend de la taille du prompt, du lot et du chemin réellement emprunté (P2P ou mémoire hôte). À mesurer en R4, avec et sans P2P |
| 2b — un modèle, deux GPU, `tensor` | Poids **et** cache KV partagés | Réductions à chaque couche | Contribution attendue la plus forte des trois profils. À mesurer en R5 |
| 3 — deux rôles | Contrôleur sur GPU0, tâche auxiliaire sur GPU1 | Aucun entre les deux rôles, sauf échange de données décidé par l'application | Aucun attendu |

**Point d'attention propre au montage** : un transfert direct par NVLink
suppose que l'accès pair-à-pair (P2P) fonctionne **dans l'environnement
d'exécution**. Sans P2P, les échanges passent par la mémoire de l'hôte.
Avec une VM, les deux modules doivent être confiés à la **même** VM, et
llama.cpp signale lui-même que le P2P peut corrompre les sorties avec l'IOMMU,
qui est justement actif en passthrough. Sur une carte adaptatrice SXM2 vers
PCIe, ni le nombre de liens NVLink câblés ni la largeur PCIe vers l'hôte ne
sont connus. Tant que le P2P n'est pas validé dans la VM, tout gain attribué à
NVLink reste une hypothèse.

**Dimensionnement** (règle de Codex/GPT reprise) : budget d'un GPU = poids placés
+ cache KV + tampons + marge, à comparer à 32 Go par GPU, jamais à 64 Go en bloc.
Cache KV d'un modèle par jeton ≈ 2 × couches × têtes KV × dimension d'une tête
× octets par valeur. Avec `tensor`, le cache est partagé entre les GPU ; avec
`layer`, il suit les couches.

## 5. Réponse à C-BRAIN-007 (question de Codex/GPT)

**Profil qui sert le mieux la latence du contrôleur tout en gardant une
capacité multimédia : le profil 3** (déduction, à confirmer par R3). Le
contrôleur ne partage ni la mémoire ni les unités de calcul de son GPU avec la
Vision ou la transcription, et ne dépend pas du P2P.

**Isolation de panne : partielle seulement.** Deux processus sur deux GPU
distincts limitent certaines interférences. Ils partagent pourtant l'hôte, le
pilote, la carte adaptatrice, l'alimentation et éventuellement la VM : une
erreur du pilote, un incident thermique ou électrique peut toucher les deux.
Je ne garantis donc pas que le contrôleur survive à une panne du second GPU.
À observer pendant la recette, pas à présumer.

Les profils 2a et 2b se justifient si le contrôleur qualifié ne tient pas dans
32 Go **avec** le cache de contexte nécessaire. Le profil 1 reste la mesure de
référence de chaque essai.

## 6. Protocole de qualification (recette ultérieure)

Chaque essai produit un manifeste (§ 7). Les dépendances sont **par essai**,
pas une chaîne : un échec ne bloque que les essais qui en dépendent (réponse de
Codex/GPT à G1, reprise ici).

| Essai | Contenu | Dépend de | Critère de passage |
| --- | --- | --- | --- |
| R0 | Inventaire : `nvidia-smi -q`, `nvidia-smi topo -m`, `nvidia-smi nvlink -s`, génération et largeur PCIe, pilote, CUDA, depuis l'hôte **et** depuis l'environnement d'exécution | — | GPU attendus visibles dans l'environnement visé ; topologie consignée telle qu'observée |
| R1 | P2P dans l'environnement d'exécution, par exemple `p2pBandwidthLatencyTest` (CUDA samples), qui mesure P2P activé **et** désactivé dans le même passage | R0 (deux GPU visibles) | Voir les seuils ci-dessous |
| R2 | Profil 1, corpus Core et témoins de C-BRAIN-006 | R0 (un GPU suffit) | Aucune violation ; mesures de référence |
| R3 | Profil 3 : contrôleur seul, puis contrôleur + charge auxiliaire sur GPU1 | R0, R2 | Dégradation de latence du contrôleur inférieure à un seuil chiffré fixé **avant** l'essai |
| R4 | Profil 2a (`layer`), mesuré avec et sans P2P si R1 l'a permis | R0, R2 | Qualité identique au profil 1 ; gain ou perte chiffrés |
| R5 | Profil 2b (`tensor`, NCCL, `GGML_CUDA_P2P=1`) | R0, R1 réussi, R2 | Aucune sortie corrompue sur N répétitions ; qualité identique au profil 1 |

Un échec de R1 bloque R5 et la variante « avec P2P » de R4. Il ne bloque ni
R2, ni R3, ni R4 sans P2P.

**Seuils de R1, proposés et à fixer par toytoy avant l'essai.** Je ne
connais pas le débit nominal du NVLink de cette carte : les pages NVIDIA sont
inaccessibles et le nombre de liens câblés est inconnu. Je propose donc des
seuils **relatifs au chemin de référence mesuré dans le même passage** :
- chemin de référence : copie GPU0 → GPU1 avec P2P **désactivé** (passage par
  la mémoire hôte), même outil, même environnement, GPU au repos ;
- mesures : débit unidirectionnel et bidirectionnel en Go/s, latence en µs, à la
  plus grande taille de transfert de l'outil ; trois passages, médiane retenue ;
- critères : P2P signalé actif dans les deux sens ; données copiées vérifiées
  sans erreur ; débit unidirectionnel P2P ≥ **k** × débit de référence, avec
  **k = 2** proposé ; latence P2P ≤ latence de référence.
La valeur de k est une proposition, pas une exigence acquise.

**LMDeploy** (réponse de Codex/GPT à G2, reprise ici) : il reste une
comparaison documentaire secondaire. Pas d'installation avant le premier
protocole GGUF. Ce n'est pas un rejet.

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
