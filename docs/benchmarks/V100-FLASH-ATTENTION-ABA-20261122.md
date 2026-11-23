# Résultat expérimental V100 — Flash Attention A/B/A (2026-11-22)

**Première optimisation mesurée : Flash Attention dans Ollama 0.32.15.** Test sur GPU1 V100 SXM2 16 Go à **200 W constants**, sans changement de pilote ni service principal.

## Conditions contrôlées

- Trois instances successives sur un port localhost isolé : A1 = OLLAMA_FLASH_ATTENTION=0, B = 1, A2 = 0.
- Même Ollama 0.32.15, même modèle Qwen2.5 Coder 7B Q4_K_M, num_ctx=8192, num_predict=384, temperature=0, seed=42.
- Sélection GPU par UUID et CUDA_DEVICE_ORDER=PCI_BUS_ID.
- Une chauffe exclue et **six générations de 384 tokens par variante**.
- Identifiant distinct au début du prompt de chaque répétition ; le log llama-server indique toutefois des tokens de préfixe commun mis en cache (par exemple 33). **Le cache n'est donc pas intégralement éliminé**, et les mesures de prompt processing ne doivent pas être interprétées comme indépendantes. Le débit de décodage reste la métrique principale.
- Logs vérifiés : flash_attn=disabled en A2 et enabled en B.
- Les deux GPU sont restés à 200 W de limite ; service Ollama principal actif ; instances isolées arrêtées après campagne.

## Débit de décodage (tok/s, médiane de 6 répétitions)

| Séquence | Flash Attention | Médiane | Minimum–maximum |
| --- | --- | ---: | ---: |
| A1 | désactivée | 102,746 | 101,467–102,887 |
| B | **activée** | **113,000** | 112,753–113,439 |
| A2 | désactivée | 104,650 | 104,207–105,012 |

**Gain B vs A1 : +9,98 % ; B vs A2 : +7,98 % ; B vs moyenne des deux références A : +8,97 %.**

La répétition A2 retrouve une performance inférieure à B, ce qui renforce l'hypothèse d'un gain réel sur cette charge. **Résultat préliminaire**, pas encore validation finale : essais courts, un seul GPU, un seul prompt et aucune étude qualité/numerique exhaustive.

## Énergie Shelly brute (plateforme complète)

| Variante | Wh relevés |
| --- | ---: |
| A1 | 3,429 |
| B | 2,572 |
| A2 | 3,000 |

**NE PAS comparer ces Wh comme des économies prouvées** : chaque lot dure ~21–24 secondes, sans mesure de repos chargé ni normalisation des transitoires. Les tests énergétiques du protocole exigent >= 2 minutes et un repos mesuré.

## Sécurité et suite

- Aucun changement de power cap ; 200 W sur chaque carte avant/après.
- Aucune modification du service Ollama principal ; toujours actif.
- Pas de conclusion sur SDXL, llama.cpp récent, NVLink, ni sur le GPU0.
- Prochaine étape : automatiser la surveillance ECC/Xid/horloges, puis confirmer sur GPU1 avec séries longues >=2 min et plusieurs tailles de contexte ; reproduire sur GPU0 dans une fenêtre autorisée.
- Ne pas activer Flash Attention en production sans validation de stabilité, exactitude et revue.

**Données brutes locales** :
/srv/eidolon/work/v100-optimization/baseline-200w-gpu1.json
/srv/eidolon/work/v100-optimization/flash-attention-200w-gpu1.json
/srv/eidolon/work/v100-optimization/baseline-repeat-200w-gpu1.json

Scripts locaux : baseline.py, flash-attention.py, baseline-repeat.py. Aucun secret inclus.
