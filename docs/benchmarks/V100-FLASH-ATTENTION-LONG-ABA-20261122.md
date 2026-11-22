# V100 SXM2 16 Go — confirmation A/B/A longue durée de Flash Attention

Date : 2026-11-22. **Résultat expérimental reproductible sur GPU1 à 200 W, pas encore validé en production.**

## Configuration

- Eidolon-OS, pilote NVIDIA 550.163.01, Ollama 0.32.15 ; Tesla V100 SXM2 16 Go GPU1 sélectionnée par UUID (PCI 0C:00.0).
- Plafond électrique 200 W **inchangé**, Ollama principal laissé actif.
- Instances expérimentales successives sur port local distinct, Flash Attention **OFF / ON / OFF**. Une génération de chauffe exclue par variante.
- Qwen2.5 Coder 7B Q4_K_M, num_ctx 8192, num_predict 384, temperature 0, seed 42 ; préfixe ID variable. Tous les résultats de décodage sont normalisés par le nombre réel de tokens.
- Lots **125 à 128 secondes**, 33–36 requêtes par variante, compteur énergie Shelly lu avant/après, puissance au repos mesurée modèle chargé.
- **Réserve cache** : un préfixe commun peut encore être réutilisé par Ollama ; les temps de prompt processing ne sont pas considérés comme indépendants. Le résultat concerne le débit de **décodage**.

## Résultats vérifiés

| Série | Flash Attention | Requêtes | Tokens | Durée (s) | Médiane tok/s | Wh Shelly bruts | Wh nets estimés | Wh bruts / 1 000 tokens |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| A1 | OFF | 33 | 12 672 | 128,00 | 104,934 | 15,003 | 8,994 | 1,184 |
| B | **ON** | 36 | 13 824 | 125,37 | **113,392** | **14,360** | 8,475 | **1,039** |
| A2 | OFF | 33 | 12 672 | 128,14 | 104,875 | 15,003 | 8,820 | 1,184 |

**Gain de décodage B vs moyenne des médianes OFF : +8,09 %.** Références OFF remarquablement proches (104,934 et 104,875 tok/s).

**Efficacité énergétique brute :** 1,184 → 1,039 Wh / 1 000 tokens, soit environ **12,2 % de réduction** pour ce banc et cette charge. La mesure inclut le Threadripper, RAM et reste de la plateforme, et doit être interprétée dans ce périmètre. Énergie nette calculée avec un repos modèle chargé ~169–174 W, estimation sensible à l'échantillonnage et aux charges de fond.

Températures maximales relevées : A1 34 °C, B 35 °C, A2 35 °C. **Attention :** le script prélève nvidia-smi après chaque requête et non en continu ; ces températures sont des maxima *échantillonnés*, pas une garantie de pic réel. De même, la moyenne GPU W obtenue par ces points de mesure **n'est pas une moyenne fiable sous charge**.

## Conclusions et réserves

- **Candidat confirmé pour ce scénario** : Flash Attention améliore le décodage Qwen 7B à 200 W sur V100 GPU1 d'environ 8 %, avec baisse des Wh bruts par 1 000 tokens.
- Pas de preuve d'un gain universel, notamment sur long contexte, multi-GPU, autres modèles ou génération d'images.
- Pas encore de validation qualité, Xid/ECC exhaustifs ni watchdog thermique 1 Hz ; **ne pas déployer en production**.
- À confirmer avec llama-bench sans cache de préfixe, scénarios longs, puis GPU0 sous fenêtre de maintenance autorisée.

## État après campagne

- Instances expérimentales terminées.
- Ollama principal toujours actif.
- V100 GPU0 et GPU1 : plafonds **200 W**, VRAM au repos.
- Aucun événement Xid/ECC correspondant trouvé dans le journal noyau interrogé (cela ne remplace pas un contrôle ECC complet avant/après).

## Traçabilité

Données brutes sur Eidolon-OS :
- /srv/eidolon/work/v100-optimization/long-A1.json
- /srv/eidolon/work/v100-optimization/long-B.json
- /srv/eidolon/work/v100-optimization/long-A2.json
- /srv/eidolon/work/v100-optimization/long-aba.log
- /srv/eidolon/work/v100-optimization/long-aba.py

**Revue Claude demandée avant toute activation sur le service Ollama principal.**
