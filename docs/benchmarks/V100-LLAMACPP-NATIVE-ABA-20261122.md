# llama.cpp b12246 — A/B/A Flash Attention natif sur Tesla V100

Date : 2026-11-22. Statut : benchmark microkernels contrôlé, pas encore validation production.

- Source llama.cpp officielle tag b12246, SHA 78ffbaa18533c2ed51eab2ef5ae0702330efc3e9.
- Compilé sm_70 avec CUDA Toolkit 12.4.131 et GCC 13.3 sous Ubuntu 24.04 isolé via Bubblewrap sur Eidolon-OS Debian 13.
- GPU1 Tesla V100 SXM2 16 Go par UUID, limite de puissance 200 W inchangée.
- Modèle GGUF Qwen2.5 Coder 7B Q4_K_M, blob SHA-256 60e05f2100071479f596b964f89f510f057ce397ea22f2833a0cfe029bfc2463.
- llama-bench, 5 répétitions par configuration, séquence A1 Flash Attention OFF / B ON / A2 OFF ; cache KV f16, offload GPU complet.

| Mesure | A1 OFF tok/s | B ON tok/s | A2 OFF tok/s | Gain B vs moyenne OFF |
| --- | ---: | ---: | ---: | ---: |
| Prompt 512 tokens | 2793,85 | 2915,83 | 2804,39 | +4,17 % |
| Prompt 4096 tokens | 2330,49 | 2725,08 | 2326,96 | **+17,02 %** |
| Décodage 128 tokens | 114,54 | 122,50 | 114,37 | +7,03 % |
| Décodage 384 tokens | 113,02 | 120,99 | 112,94 | +7,09 % |

**Interprétation :** Flash Attention apporte un gain reproductible dans ce moteur à 200 W, surtout pour le traitement des prompts longs. Le gain +17 % porte sur un prompt de 4096 tokens, et non une conversation complète avec 4096 tokens de contexte accumulé. Les résultats llama-bench ne doivent pas être comparés directement aux mesures Ollama précédentes.

**Réserves :** microbenchmark sans comparaison des textes générés, stabilité 30 minutes et ECC avant/après non encore validés ; pas de surveillance thermique continue à 1 Hz pendant ce lot. Ne pas déployer en production sur cette seule preuve.

**Sécurité :** Ollama principal toujours actif, GPU0/GPU1 à 200 W, cartes revenues au repos ; aucun Xid détecté dans les journaux consultés.

**Données brutes** : /srv/eidolon/work/v100-optimization/llama-cpp/aba-A1.json, aba-B.json, aba-A2.json. Script : run-native-aba.sh.
