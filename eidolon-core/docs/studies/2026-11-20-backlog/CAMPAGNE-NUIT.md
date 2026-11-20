# ECT — Eidolon-OS — Campagne du 20 novembre 2026

Campagne bornée terminée. Les éléments bloqués restent NON TESTÉS ; aucun déploiement en production.

- Liste récupérée : CANDIDATE-QUEUE-G332, commit c74f1f64780a93fbf894537d121d7cbffb27182c ; complément REPRISE-2026-11-17.
- CPU llama.cpp : 8 passages ABBAABBA, 3 répétitions internes chacun. v0.8.0 génération 40.2102 tok/s ; v1.0.0 34.9134 tok/s, -13.17 %. Pas de conclusion GPU.
- Hindsight / Graphiti : 3/3 faits synthétiques attendus en première position ; pas de validation de production.
- Garak : 50 sondes Base64, aucun échec détecté ; périmètre limité. AgentDojo : 0/3 tâches normales réussies, donc essai de sécurité non interprétable.
- Vidéo : 11 workflows ComfyUI terminés. Répétitions SVD-XT et Wan T2V14B identiques en pixels, sans nœuds réutilisés depuis le cache. Wan I2V720 et plusieurs autres recettes rejetés visuellement ; voir visual-review.json.
- AnimateDiff : trois diagnostics FP16/sliced, FP16/SDPA, FP32/SDPA, tous exécutés mais textures sans scène reconnaissable. Cause non résolue.
- Blocages : accès FLUX protégé (HTTP401), intégrations Qwen/FLF/VACE manquantes, VFIO IVRS, compilation CUDA12.8.1/glibc, DCGM non installé.
- Les résultats image antérieurs sont HISTORIQUES et n'ont pas été régénérés cette nuit.
- Contrôle final : Core/Darme/tunnel/Ollama actifs ; Memory-engine production actif ; deux VM de laboratoire arrêtées ; services temporaires arrêtés. Compteurs ECC tous zéro, aucun Xid du démarrage. X399 laissée allumée, Shelly final 160 W.

Sources, scripts, modèles, journaux et sorties conservés dans ce dossier. Aucun résultat ne vaut promotion automatique ou validation exhaustive de la file.
