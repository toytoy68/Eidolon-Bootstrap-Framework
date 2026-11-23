# Baseline V100 n°1 — 22 novembre 2026

Statut : mesure réelle préliminaire, **pas une comparaison d'optimisation A/B**.

## Conditions
- Eidolon-OS, Debian 13, pilote NVIDIA 550.163.01, Ollama 0.32.15.
- Tesla V100 SXM2 16 Go GPU1 (PCI 0C:00.0), sélection par UUID, CUDA_DEVICE_ORDER=PCI_BUS_ID.
- Power cap 200 W inchangé, instance Ollama isolée sur 127.0.0.1:11436 ; service principal conservé.
- Modèle qwen2.5-coder:7b-instruct-q4_K_M, référence locale dae161e27b0e.
- num_ctx 8192, num_predict 384, temperature 0, seed 42.
- Warmup exclu, 6 requêtes de 384 tokens, préfixe d'identification unique pour réduire le risque de réutilisation du cache.

## Résultats mesurés
| Essai | Débit de décodage (tok/s) |
| --- | ---: |
| 1 | 102,867 |
| 2 | 102,800 |
| 3 | 102,887 |
| 4 | 102,692 |
| 5 | 102,050 |
| 6 | 101,467 |
| **Médiane** | **102,746** |

Total : 2 304 tokens. Tous les prompt_eval_count = 87 et done_reason = length. Aucune fin anticipée. Dispersion 101,467 à 102,887 tok/s.

Shelly plateforme entière : **3,429 Wh bruts**, soit **1,488 Wh/1 000 tokens bruts**. Le lot n'a duré qu'environ 24 secondes : cette mesure énergétique est **indicative, non qualifiée** par le protocole exigeant des lots >= 2 minutes et un repos chargé mesuré.

Après le test : instance isolée arrêtée, Ollama principal actif, les deux GPU à 200 W, VRAM GPU1 libérée.

## Référence historique NON COMPARABLE
Ancien résultat GPU1 Qwen 200 W : 104,59 tok/s. Nouvelle médiane : 102,746 tok/s, soit environ -1,8 %. Le prompt et la politique de cache diffèrent : **ce n'est pas une régression démontrée**.

## À faire avant une conclusion d'optimisation
1. Instrumentation continue Xid/ECC/température/horloges et mesure Shelly >=2 minutes avec baseline idle.
2. Vérification du hash complet du modèle et de l'absence d'interférences.
3. Installation isolée de llama-bench, baseline pp/tg, puis A/B/A sur commit figé.
4. Aucun changement de power cap 150/250/300 W sans réservation GPU ou fenêtre autorisée.

Sources locales : /srv/eidolon/work/v100-optimization/baseline-200w-gpu1.json et baseline.py. Aucun secret ni IP privée inclus dans ce rapport.
