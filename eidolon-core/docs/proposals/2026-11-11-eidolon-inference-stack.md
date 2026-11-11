# Eidolon Inference — pile figée multi-GPU et routeur

Auteur : Claude. Date : 11/11/2026, Europe/Paris.
Base : `feat/eidolon-core-v0.1`, `b108ae2`.
Demande de toytoy (11/11, 15 h 18) : « ajoute un fichier pour le moteur d'inférence
au dépôt ». Idée de toytoy (13 h 39) : une version « Eidolon » d'un moteur d'inférence
pour gérer les V100 et les autres GPU qu'il installe, les moteurs récents gérant mal
les V100.
Statut : **PROPOSITION**. Rien n'est installé, aucun moteur choisi, aucune mesure
faite par ce document. Il complète, sans les remplacer,
[INFERENCE-2XV100-2026-10-05.md](../INFERENCE-2XV100-2026-10-05.md) (GPT) et
[INFERENCE-RUNTIME-COMPARISON.md](../INFERENCE-RUNTIME-COMPARISON.md) (Claude),
écrits quand le matériel était encore prévu et non installé.

## 1. Principe

Ne pas écrire un moteur d'inférence (noyaux GPU, attention, quantification) :
c'est un travail d'équipes entières et il faudrait le maintenir seul.
« Eidolon Inference » est plutôt :

1. **une pile figée et qualifiée** : un moteur existant par type de GPU, compilé
   pour ses architectures, versions verrouillées, jamais mises à jour sans
   requalification ;
2. **des groupes de GPU par rôle**, pas un modèle étalé sur des cartes différentes ;
3. **un routeur Eidolon**, seule partie à développer : une API unique devant les
   moteurs, qui aiguille, surveille et journalise.

Core n'en dépend pas directement : il garde son contrat `contracts.Model` et ses
adaptateurs interchangeables ([Ollama](../OLLAMA-ADAPTER.md),
[OpenAI chat / llama-server](../OPENAI-CHAT-ADAPTER.md)).

## 2. Matériel visé (rapporté par toytoy, 11/11/2026)

| Élément | État actuel | Évolution annoncée |
| --- | --- | --- |
| Plateforme | X399 « Eidolon-OS », ASUS Prime X399-A, BIOS à jour | — |
| CPU | Threadripper 1950X | 2950X si l'occasion se présente |
| RAM | 128 Go, 8 × 16 Go de références mélangées, à 2400 MT/s, 1,2 V ; pas d'ECC | remplacement de la barrette Corsair par une Crucial |
| GPU de calcul | 2 × V100 SXM2 16 Go sur un adaptateur PCIe double, NVLink NV6, PCIe 3.0 ×4 par GPU | 2 × V100 SXM2 32 Go (même adaptateur) |
| GPU auxiliaire | GTX 1060 6 Go (Pascal) | — |
| Alimentation | MSI 1 000 W | — |

Mesure rapportée par GPT dans l'inventaire du 11/11 : NVLink ≈ 144,7 Go/s
unidirectionnel, ≈ 288,2 Go/s bidirectionnel. Non remesurée par Claude.

## 3. Ce qui a changé depuis l'étude du 05/10

| Point | 05/10 | 11/11 |
| --- | --- | --- |
| Matériel | prévu, non installé | installé ; NVLink mesuré par GPT |
| vLLM | écarté : exige compute capability 7.5+ | toujours vrai pour vLLM officiel (≥ 0.20 sans sm_70 d'après le forum vLLM [2]) ; **mais** un fork dédié Volta existe : **1Cat-vLLM** [1] |
| Pilote | « fin de support Volta non vérifiée » | NVIDIA annonce la branche **R580** comme dernière pour Maxwell, Pascal et Volta [3] ; CUDA 13 les abandonne [4] |

### 1Cat-vLLM (lu le 11/11/2026 sur son dépôt, non testé)

Fork de vLLM « V100 / SM70-focused » (`1CatAI/1Cat-vLLM`, Apache-2.0, en cours de
renommage 1Cat-LLM), dernière version publiée v1.5.1 du 03/10/2026 [1].
D'après son README :
- noyaux d'attention réécrits pour Volta (FlashAttention-V100), décodage spéculatif ;
- quantifications AWQ/W4A16, NVFP4, MXFP4, cache KV FP8, GGUF partiel ;
- configurations TP4, TP8, PP2×TP4 ; profil validé sur **4 × V100-SXM2 32 Go**
  reliées en pair-à-pair ;
- prérequis v1.5.1 : Python 3.12, PyTorch 2.10, CUDA 12.8 (toolkit et compilateur
  requis), glibc ≥ 2.38, pilote ≥ 570 recommandé ;
- LoRA non mentionné.

**Déductions à vérifier** : 2 GPU (TP2) et des modules de 16 Go ne sont pas dans
son profil validé ; la compatibilité avec la R580 est probable (570+ demandé)
mais à constater ; l'API compatible OpenAI de vLLM est présumée conservée par le
fork, ce qui permettrait de réutiliser l'adaptateur `openai_chat_model.py`.

## 4. Pile figée proposée

| Couche | Choix proposé | Raison |
| --- | --- | --- |
| Pilote | branche **R580**, version exacte figée | dernière branche qui gère à la fois V100 (Volta) et GTX 1060 (Pascal) [3] ; une mise à jour au-delà rendrait ces cartes inutilisables |
| CUDA | **12.8** (toolkit et runtime) | dernière famille qui cible sm_70 et sm_61 ; requise par 1Cat v1.5.1 |
| Groupe V100 | **1Cat-vLLM**, version et commit figés, environnement isolé | seul moteur trouvé optimisé Volta avec TP sur NVLink |
| Groupe V100, repli | **llama.cpp** (`llama-server`), `CMAKE_CUDA_ARCHITECTURES=70` | déjà étudié et adapté par Core ; `--split-mode layer/tensor` |
| GTX 1060 | **llama.cpp**, `CMAKE_CUDA_ARCHITECTURES=61` | Pascal hors de vLLM et de 1Cat ; modèles GGUF quantifiés |
| Nouvelle carte | son propre groupe et son propre build, qualifié avant usage | ne pas mélanger les architectures dans un même modèle |
| Miroir | paquets, roues, sources et poids archivés localement avec SHA256 | rester reconstructible quand les dépôts amont abandonnent Volta |

**Entraînement d'Eva : hors de cette pile.** L'entraînement et la comparaison
de checkpoints restent sur Transformers + PEFT (NF4), pour évaluer exactement le
modèle entraîné. La pile d'inférence sert Eva une fois retenue (adaptateur
fusionné), ou un autre modèle.

## 5. Groupes et rôles

| Groupe | GPU | Rôle proposé |
| --- | --- | --- |
| `v100-nvlink` | 2 × V100 16 Go (puis 32 Go), TP2 | modèle principal ; Eva en service quand elle est retenue |
| `pascal-core` | GTX 1060 6 Go | petit LLM système Core |

Profils hérités de l'étude du 05/10 : profil 1 (un GPU), 2a/2b (un modèle sur
deux GPU, couches ou tenseurs), 3 (un rôle par GPU). Avec le NVLink mesuré, le
profil 2b devient testable sur le groupe V100.

Dimensionnement (règle GPT reprise) : par GPU, poids placés + cache KV + tampons
+ marge, comparés à 16 Go aujourd'hui, 32 Go demain, jamais au total en bloc.
**Déduction** : un modèle d'environ 27 milliards de paramètres quantifié en 4 bits
(~15 Go de poids) tient en TP2 sur 2 × 16 Go avec un contexte modéré ; les très
longs contextes annoncés par 1Cat supposent 4 × 32 Go.

## 6. Routeur Eidolon (à développer)

Responsabilités :
1. **API unique** compatible OpenAI chat pour Core et les clients ; un nom de
   modèle logique (`eidolon-main`, `eidolon-core`) résolu vers un groupe.
2. **Registre des groupes** : moteur, version figée, modèle et SHA256 des poids,
   GPU, état (qualifié, en test, hors service).
3. **Admission et file d'attente** par groupe ; aucune requête envoyée à un
   groupe non qualifié.
4. **Surveillance** reprise des gardes Eva : températures GPU/HBM/CPU, puissance
   par GPU (plafond 200 W configuré), ECC/Xid, journaux noyau, prise secteur.
   Mise hors service automatique d'un groupe sur alerte, sans redémarrage machine.
5. **Journal** par requête : groupe, modèle, durée, tokens, erreurs.
6. **Pas de basculement silencieux** d'un modèle vers un autre : un repli est
   explicite, journalisé et visible du client.

Langage : Python, dans le style de Core (bibliothèque standard autant que
possible), ou Rust si toytoy le préfère. Point ouvert.

## 7. Qualification

Reprendre le protocole R0–R5 de l'[étude du 05/10](../INFERENCE-RUNTIME-COMPARISON.md#6-protocole-de-qualification-recette-ultérieure)
et son manifeste. Ajouts propres à cette pile :

| Essai | Contenu | Critère |
| --- | --- | --- |
| Q0 | Pilote, CUDA, `nvidia-smi topo -m`, NVLink, RAM (qualification mémoire complète, pas seulement 4 Gio) | inventaire consigné ; RAM sans erreur sur un test complet |
| Q1 | llama.cpp sm_61 sur la 1060 : modèle Core, débit, VRAM, stabilité | réponses identiques sur N répétitions, gardes silencieuses |
| Q2 | llama.cpp sm_70 sur une V100 : référence de débit et de qualité | référence chiffrée |
| Q3 | 1Cat-vLLM en TP2 sur les deux V100, même modèle que Q2 si possible | qualité ≥ Q2, débit mesuré, aucune sortie corrompue, températures et puissance dans les gardes |
| Q4 | Routeur devant Q1 + Q3, charge simultanée | latence de `eidolon-core` dégradée de moins d'un seuil fixé avant l'essai |
| Q5 | Après passage à 2 × 32 Go ou au 2950X : Q0 à Q4 de nouveau | même critère qu'à la première qualification |

Les seuils sont fixés par toytoy avant chaque essai. Un échec de Q3 laisse le
groupe V100 sur llama.cpp, sans bloquer Q1 ni le routeur.

## 8. Ordre proposé

1. Q0 (dont un test mémoire complet ; lié au défaut RAM intermittent).
2. Q1 et Q2 (llama.cpp, peu de risques, réutilise l'adaptateur existant).
3. Q3 dans un environnement isolé, sans toucher au pilote s'il est déjà en R570–R580.
4. Routeur minimal (registre, API, journal), puis surveillance.
5. Q4.

Pas en concurrence avec les essais Eva sur les mêmes GPU : une fenêtre à la fois,
décidée par toytoy.

## 9. Décisions ouvertes (à toytoy)

- Lancer Q0–Q3 et dans quelle fenêtre par rapport aux essais Eva.
- Modèle principal visé pour le groupe V100.
- Python ou Rust pour le routeur.
- Seuils de qualification (latence, températures, puissance).
- Version exacte du pilote R580 à figer.

## Références

1. [1CatAI/1Cat-vLLM — GitHub](https://github.com/1CatAI/1Cat-vLLM), README lu le 11/11/2026.
2. [vLLM Forum — Support for V100 (sm 70) on vllm 0.20](https://discuss.vllm.ai/t/support-for-v100-sm-70-on-vllm-0-20/2605) (réponse automatique du forum, à confirmer par les notes de version).
3. [Tom's Hardware — 580 series drivers will be the last to support Maxwell, Pascal and Volta](https://www.tomshardware.com/pc-components/gpu-drivers/nvidia-to-axe-maxwell-pascal-and-volta-gpus-with-end-of-driver-support-580-series-drivers-will-be-the-last-to-support-gtx-900-and-1000-cards).
4. [Tom's Hardware — CUDA support dropped for Maxwell, Pascal and Volta with the next major Toolkit](https://www.tomshardware.com/pc-components/gpus/nvidia-to-drop-cuda-support-for-maxwell-pascal-and-volta-gpus-with-the-next-major-toolkit-release).
