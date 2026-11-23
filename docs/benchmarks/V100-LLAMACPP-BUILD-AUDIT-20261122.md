## Audit de compilation llama.cpp Volta — 2026-11-22

Code officiel llama.cpp b12246, SHA 78ffbaa18533c2ed51eab2ef5ae0702330efc3e9, cloné sur Eidolon-OS dans un dossier de travail isolé.

Tentative de configuration CMake : GGML_CUDA=ON, CMAKE_CUDA_ARCHITECTURES=70. **Échec** : compilateur nvcc introuvable, CUDA Toolkit not found.

Le paquet Debian candidat est nvidia-cuda-toolkit 12.4.131 ; la simulation APT annonce environ 160 paquets à installer. **Aucune installation effectuée** pour éviter de modifier le système de production. Ollama fournit des bibliothèques CUDA précompilées, mais pas nvcc.

**Aucun benchmark GPU de llama.cpp récent n'a encore été réalisé.** Le gain de +8,09 % mesuré précédemment concerne Flash Attention dans Ollama 0.32.15 et ne doit pas être attribué à une mise à jour de llama.cpp.

Prochaine étape : obtenir une toolchain CUDA 12.x isolée, sans remplacer le pilote, compiler sm_70 et exécuter llama-bench pp/tg avec un modèle GGUF et des paramètres figés. Garder la V100 n°1 à 200 W, le service Ollama principal actif, et utiliser A/B/A avant toute conclusion.
