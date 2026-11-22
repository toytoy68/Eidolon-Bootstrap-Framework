# Tesla V100 — contrôle de stabilité Flash Attention 30 minutes (22 novembre 2026)

**Verdict : VALIDATION DE STABILITÉ SUR CETTE CHARGE ET CETTE CARTE, avec réserves.** Le test a couvert les 1 800 secondes exigées sans erreur enregistrée, sans nouveau compteur ECC, sans Xid détecté, sans dépassement thermique. **Ce résultat ne valide pas la qualité fonctionnelle ni un déploiement de production.**

## Périmètre, provenance

- Hôte : Eidolon-OS (X399 Debian 13), contrôle direct à **21:07:40 CET**.
- GPU testé : **GPU1 Tesla V100 SXM2 16 Go** `GPU-c9d9173f-6303-6998-7a60-a379b9a0d60b`, PCI `0000:0c:00.0`.
- Ollama expérimental 0.32.15, `127.0.0.1:11436`, modèle Qwen2.5 Coder 7B Instruct Q4_K_M, contexte 8 192, génération 768 tokens, température 0, seed 42, 1 génération à la fois.
- **Flash Attention effectivement activée**, prouvée par `OLLAMA_FLASH_ATTENTION:true` et argument du `llama-server --flash-attn on` dans `stability-server.log`.
- Limite GPU NVIDIA réglée à **200 W** (sans modification) sur les deux cartes.
- Service : `eidolon-v100-stability30.service`, désormais `inactive`, `Result=success`, `ExecMainStatus=0`.

## Chiffres bruts

| Contrôle | Mesure | Appréciation |
|---|---:|---|
| Début de charge | 20:30:57 CET | |
| Fin de charge | 21:00:58 CET | |
| Durée enregistrée | **1 800,677 s** | Conforme >=1 800 s |
| Requêtes terminées | **259 / 259** | Conforme |
| Tokens de décodage | **198 912** | 768 par requête |
| Débit agrégé sur durées de décodage | **112,17 tokens/s** | Indicatif, hors chargement |
| Erreurs watchdog/applicatives | **0** | Conforme |
| Échantillons GPU | **1 754** | Surveillance nominale ~1 Hz |
| Intervalle entre échantillons | médiane **1,026 s** ; max **1,044 s** | ~0,975 Hz effectif ; aucun trou > 2 s |
| Température GPU | **28–38 °C**, moyenne **36,73 °C** | Sous seuil d'arrêt 85 °C |
| Puissance GPU lue | moyenne **193,99 W**, p95 **201,66 W**, pic **228,18 W** | Voir réserve sur transitoires |
| Power cap rapporté | **200 W** à chaque échantillon | Aucun changement de réglage |

Les **259 requêtes atteignent toutes la limite `num_predict=768`** (`done_reason=length`) ; il s'agit d'un test de charge et non d'un contrôle de qualité ou de complétude des réponses.

**Réserve puissance importante :** malgré une limite configurée de 200 W constante, la télémétrie NVML présente **159/1754 échantillons >200 W**, dont **7 >210 W et 4 >220 W** (pic 228,18 W). Cela peut provenir d'une fenêtre d'échantillonnage et de transitoires/régulation ; ne pas affirmer que la consommation n'a jamais dépassé 200 W. Recommander une comparaison électrique externe et, si nécessaire, une surveillance plus fine.

## Intégrité matérielle et reprise

- ECC **activé**. Comparaison `stability-before-ecc.txt` du **20:30:55** et `stability-after-ecc.txt` du **21:00:58** : **identique à l'horodatage près**.
- Compteurs ECC volatile et aggregate (simple et double bit) : **0 → 0**.
- Pages retirées simple/double bit : **0 → 0** ; `Pending Page Blacklist: No`.
- Aucun message **NVRM/Xid/ECC** dans le journal noyau consulté sur l'intervalle.
- Le service expérimental a quitté normalement ; aucun processus `stability-30min.py`, `quality-compare.py`, `llama-bench` ni listener expérimental sur `127.0.0.1:11436` constaté après le test.
- **Ollama principal actif**, deux V100 au repos (27–28 °C environ, 1 MiB VRAM chacune, cap 200 W).
- Aucune activation de Flash Attention en production.

## Limites et suites

1. Cette campagne valide une charge soutenue de 30 minutes sur **GPU1 uniquement**, pas l'endurance de plusieurs heures, GPU0, NVLink ou les modèles plus volumineux.
2. Les requêtes en sortie sont **tronquées à 768 tokens** : le contrôle d'identité sémantique/fonctionnelle des réponses Flash Attention ON vs OFF reste ouvert. Le test précédent de qualité (3 prompts de 384 tokens) avait produit 1 réponse identique sur 3, sans preuve de dégradation mais sans validation suffisante.
3. La surveillance était nominalement à 1 Hz mais effective à **~0,975 Hz** ; l'affirmer telle quelle, sans arrondir en fréquence stricte.
4. Confidentialité stricte : le modèle et le runner étaient locaux, `llama-server --offline`, mais le serveur Ollama rapporte `OLLAMA_NO_CLOUD=false`. Aucune activité cloud n'est démontrée par les mesures, mais le mode sans cloud n'est **pas techniquement forcé** dans cette instance. Paramétrer `OLLAMA_NO_CLOUD=true` et/ou isoler le réseau lors des essais futurs.
5. **Ne pas activer en production** avant une campagne de qualité à réponses complètes et une revue croisée.

### Fichiers sources sur Eidolon-OS

- `/srv/eidolon/work/v100-optimization/stability-30min.json`
- `/srv/eidolon/work/v100-optimization/stability-30min.log`
- `/srv/eidolon/work/v100-optimization/stability-before-ecc.txt`
- `/srv/eidolon/work/v100-optimization/stability-after-ecc.txt`
- `/srv/eidolon/work/v100-optimization/stability-server.log`
- `/srv/eidolon/work/v100-optimization/stability-30min.py`

**Décision proposée :** stabilité 30 minutes **validée sur GPU1 / Qwen2.5 Coder 7B / 200 W configurés**. Optimisation de production **NON VALIDÉE** tant que la qualité des réponses et les réserves d'énergie/confidentialité ne sont pas levées.
