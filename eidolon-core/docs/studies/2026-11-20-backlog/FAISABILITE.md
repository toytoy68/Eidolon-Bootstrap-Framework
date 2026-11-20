# Faisabilité des pistes matérielles et modèles - 20 novembre 2026

Les annonces fournisseur sont séparées des mesures réalisées sur Eidolon. Aucun achat proposé ni effectué.

| Piste | État vérifié | Décision |
|---|---|---|
| Basalt | Dépôt officiel : GPU principal Blackwell sm_120. Les V100 sont sm_70. | Écarté du banc V100 comme moteur principal. Les extensions de pairs d'autres architectures ne prouvent pas un support Volta autonome. |
| Intel D270 | Intel annonce 160 Go LPDDR5X sur sa carte, jusqu'à 480 Go chez des partenaires, 1,5 To/s et 350 W. Le gain 5,9x concerne Monte Carlo, pas les LLM en général. Chiffres Intel sur présérie. | Veille P3 ; prix livré, disponibilité et benchmarks indépendants équivalents non établis ici. Aucun remplacement justifié. |
| Leo / CXL | CXL 2.0 emploie PCIe 5.0 et exige une plateforme hôte compatible. Leo 2 ajoute CXL 3.2. | Pas d'extension de RAM CXL sur X399/1950X. Les modes PCIe spécialisés de Leo X ne rendent pas la RAM système CXL compatible par magie. |
| Lisuan | Un paquet pilote Linux officiel est référencé, mais sa page n'a pas répondu à la vérification. | Support Debian, PyTorch, ECC et SR-IOV non qualifiés ; ne pas assimiler pilote graphique à moteur IA compatible. |
| BC250 / Dell R220 | Aucun exemplaire connecté pour ces essais. | Les chiffres de vidéos restent des hypothèses. Exiger coût total et consommation mesurée face au matériel déjà possédé. |
| LFM3 | LiquidAI/LFM3-1.7B-GGUF identifié ; Q4_K_M 1,10 Go vérifié par SHA256. Licence LFM 1.0. | Banc GPU puis évaluation française et matériel Wall-E. Pas de conclusion N6000. |
| Prism | Ternary-Bonsai-2-2B Q2_0 identifié, Apache 2.0, 547 Mo. L'amont récent doit contenir la rotation Hadamard. PTQ1/PQ2 demandent un fork spécifique. | Ne pas appeler cette mesure un benchmark 1-bit. Comparatif 1-bit et qualité étendue restent ouverts. |
| WeVisOne-VL | tencent/WeVisOne-VL-2B identifié, Apache 2.0, métadonnées et accès public vérifiés. | Grounding, faux positifs et runtime spécialisé non qualifiés ; contrôle moteur hors LLM. |
| Phonon FR | Gradium phonon-40m-fr identifié ; accès au config obtenu avec HTTP401. Licence annoncée CC BY-NC 4.0, distincte du petit modèle anglais Apache 2.0. | Pas de contournement des conditions ; aucun benchmark vocal FR déclaré réussi. |

Sources primaires consultées :
- https://github.com/jesdga95/basalt
- https://www.intel.com/content/www/us/en/newsroom/news/data-center/why-intel-gpu-d270-belongs-in-the-hpc-conversation.html
- https://www.intel.com/content/www/us/en/products/details/discrete-gpus/data-center-gpu/d-series.html
- https://www.asteralabs.com/products/leo--smart-memory-controllers/
- https://www.lisuantech.com/driving-center/download/9
- https://huggingface.co/LiquidAI/LFM3-1.7B-GGUF
- https://huggingface.co/prism-ml/Ternary-Bonsai-2-2B-gguf
- https://huggingface.co/tencent/WeVisOne-VL-2B
- https://huggingface.co/gradium/phonon-40m-fr
