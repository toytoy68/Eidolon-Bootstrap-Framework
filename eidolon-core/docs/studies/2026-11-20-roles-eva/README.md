# Modèles par rôle et Eva E5 — 20 novembre 2026
Eidolon Core Technologies (ECT).

Cette étude remplace une qualification par simple chargement ou débit par des contrats de rôle. Les décisions de contrôle et de sécurité restent hors LLM. Aucun modèle de production n’est remplacé.

[Protocole et amendements](PROTOCOL.md) · [Catalogue par utilité](ROLE-CATALOG.md) · [Apprentissage Eva](EVA-E5.md)

## Contrats texte
Cellules : strict libre / JSON contraint, sur 12. Les réponses ouvertes sont relues séparément dans chat-review.json. La seconde passe est exploratoire.

| Modèle | Robot | Darme | Système | Calcul/dates |
| --- | --- | --- | --- | --- |
| LFM2.5-1.2B-Instruct-Q4_K_M | 4 / 4 | 5 / 5 | 2 / 2 | 0 / 3 |
| SmolLM3-Q4_K_M | 4 / 7 | 2 / 4 | 5 / 6 | 2 / 5 |
| Phi-4-mini-instruct-Q4_K_M | 6 / 6 | 5 / 8 | 8 / 8 | 0 / 6 |
| Falcon3-3B-Instruct-q4_k_m | 7 / 7 | 3 / 5 | 2 / 2 | 0 / 1 |
| LFM3-1.7B | 9 / 10 | 3 / 6 | 7 / 7 | 0 / 4 |
| Prism-Ternary-2B-Q2_0 | 4 / 4 | 2 / 3 | 4 / 4 | 1 / 3 |
| Qwen2.5-1.5B | 5 / 5 | 0 / 3 | 0 / 2 | 0 / 4 |
| Eva-source-Q4_K_M | 10 / 10 | 7 / 7 | 8 / 8 | 4 / 6 |
| Qwen3-14B | 10 / 10 | 9 / 9 | 10 / 10 | 7 / 8 |
| Gemma4-12B | 9 / 10 | 9 / 9 | 6 / 6 | 0 / 10 |

Le tag qwen3:30b contient Thinking 2507. Le test adapté à 8192 tokens donne 12/12 robot, 10/12 Darme, 12/12 système et 6/12 calcul/dates stricts. La relecture confirme 12/12 valeurs correctes, avec six clés JSON incorrectes. Deux injections Darme restent mal traitées. Les passages à 512 tokens sont des diagnostics de budget inadapté, pas une qualification complète.

## Compression et perception
Prism PTQ1_0, PQ2_0 et Q2_0 exécutés sur le fork cec7baeffba70dcf52890069aa8588d4a71006dd, compilé sm70 avec CUDA12.9 isolé. Mêmes scores fermés ; PQ2 reproduit 52/52 textes Q2, PTQ1 48/52. Les fichiers prism-perf-clean donnent la répétition après libération des GPU et arrêt du lecteur de métadonnées CPU. Le premier passage reste conservé. Les mesures CPU restent indicatives : services ordinaires actifs et contrôle SHA bref concomitant ; aucune hiérarchie CPU strictement isolée revendiquée.
WeVisOne : comptage, localisation, absence et OCR réussis sur une scène synthétique. Segmentation FP16 : NaN ; décodeur seul FP32 : encore NaN. Chaîne entière FP32 : masques finis, IoU1 sur forme initiale, déplacée et répétée. Prototype uniquement ; dépendances différentes des pins auteur.

## Reproduction et preuve
Code de banc dans code/, cas et oracles dans cases.json, identités GGUF, révisions et SHA des téléchargements conservés. Runtime texte : llama.cpp b1b770d90d94cad9e9ea5b993bdbc383a522fb28, CUDA12.9 privé avec correction noexcept glibc2.41 décrite dans le lot backlog précédent. Source et poids complets restent sur X399.
Les JSONL publics conservent la réponse finale, les scores et durées ; seul le nombre de caractères du raisonnement est exporté. Adresses LAN et UUID GPU sont masqués. SOURCE-INDEX.json identifie les fichiers publiés ; les manifestes sources identifient les originaux avant assainissement. Les fichiers de configuration exportés sont documentaires, à adapter avant exécution.
Le code Eva exporté conserve sa logique complète ; corpus, pack-plan, checkpoints, RNG et optimiseur sont dans le dossier local de campagne. Les données historiques E4b restent référencées par source-manifest.json et lineage.json.

## Conservation et suites
Dossiers locaux : /srv/eidolon/ssd/work/roles-eva-20261120 et /srv/eidolon/work/eva-learning-cycle13-lowdose-20261120.
P0 : chaîne Darme indépendante de bout en bout. P1 : confirmation Eva inédite, corpus de rôles élargi, N6000 réel et hors réseau. P2 : vision terrain et mémoire avec dates/ACL. Projecteur Prism, autres tailles, code et voix restent non qualifiés dans ce lot.
