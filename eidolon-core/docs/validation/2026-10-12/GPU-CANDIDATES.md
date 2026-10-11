# Recette V100 et candidats — 12/10/2026

VM101, confirmée par toytoy : 192.168.1.135, Eidolon-Core-Alpha.
V100 SXM2 16 Go, driver 550.163.01, CUDA 12.4, Ollama 0.34.2.
Core cible MCP : 192.168.1.101 ; Memory : 192.168.1.110.
Aucun changement de pilote ou de VM effectué.

Sauvegarde VM101 : code/configuration/services et définitions/manifests des
neuf modèles initiaux, archive vérifiée et SHA-256 enregistré. Les poids
téléchargeables ne sont pas recopiés dans cette archive.

Espace disponible avant téléchargements : 124952002560 octets, soit 116,37 Gio.
Ajouts : gemma4:12b (8021618941 octets) et qwen3.5:9b (6550825550 octets).
Espace restant : environ 110379413504 octets, soit 102,80 Gio.
Aucun modèle initial supprimé. Les deux nouveaux candidats sont conservés :
aucun échec bloquant dans la première recette.
Sources : https://ollama.com/library/gemma4 et https://ollama.com/library/qwen3.5.

## Comparaison préliminaire

Même corpus factual-v2, cinq questions, mêmes budgets, penser désactivé lorsque
le modèle expose cette capacité. Ce sont des appels API Ollama depuis Core ;
le rappel mémoire précède la mesure de temps ci-dessous.

| Modèle | Cas avec réponses attendues sur ce petit lot | Premier appel | Moyenne des quatre appels chauds | Génération moyenne |
|---|---:|---:|---:|---:|
| Qwen3 14B | 5/5 | 7,79 s | 2,50 s | 63,1 tok/s |
| Mistral Small 3.2 24B | 5/5 | 16,03 s | 4,88 s | 24,8 tok/s |
| Gemma4 12B | 5/5 | 8,91 s | 3,01 s | 102,7 tok/s |
| Qwen3.5 9B | 5/5 | 5,86 s | 1,92 s | 87,3 tok/s |

Les cinq cas couvrent GPU utilisé, VM mémoire, installation vs projet, numéro
de série absent et panne mémoire. Évaluation qualitative ponctuelle, pas
une qualification générale ni un taux de réponses correctes sur le corpus.
Les débits portent sur des sorties courtes et ne constituent pas un benchmark
de génération longue. L'ancien prompt Qwen3 14B donnait une action hors sujet
sur le cas installation/projet ; le prompt corrigé répond à la question.

Occupation réelle mesurée par NVIDIA, contexte 4096 :
Qwen3.5 9B environ 6697 Mio ; Gemma4 12B environ 8913 Mio.
La valeur size_vram renvoyée par Ollama pour Gemma4 sous-estime l'occupation
réelle : ne pas l'utiliser seule pour dimensionner la carte.
Mistral 24B utilise un offload partiel selon le runtime et est plus lent.

## Changements Core

think booléen optionnel dans OllamaConfig, manifeste et requêtes du planner
et du dialogue. Le défaut garde le protocole et l'identité précédents.
Les positions des anciens arguments du constructeur restent conservées.
Documentation protocole : https://docs.ollama.com/api/chat.

Le prompt distingue une question factuelle d'une demande explicite d'action,
sépare matériel prévu/installé, garde les sources UNVERIFIED comme déclarations,
et demande une citation information_id@revision présente dans le rappel.
Les vérifications déterministes Core restent l'autorité ; aucun outil exécuté.

Validation du code final : 1460 tests, six ignorés, zéro échec.
58 tests ciblés pour configuration/adaptateur/dialogue, puis 37 ciblés pour
le prompt avec citations et le bridge. Recette HTTP élargie en cours.
