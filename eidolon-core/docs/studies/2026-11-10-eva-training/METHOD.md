# Modèle et protocoles observés

## Identité et architecture

Source entraînement : `nightmedia/Qwen3-4B-Element8-Eva-Hermes-Heretic`, révision `3497c4c82493fabf3ee118e9865b047d8aecccf2`. Les manifestes locaux répertorient chaque fichier et SHA256. Deux shards safetensors : 4 989 451 712 et 3 054 163 248 octets ; SHA256 `e0615df3c2e8bba871b5701ce45798dc733ddfb6756aa9837decca7eb420180a` et `e4af3989bddc67225691070e40f23097efafc6e70abb6e695c70a5be5b73924e`.

Config du modèle : Qwen3ForCausalLM,36 couches, hidden2560, intermediate9728,32 têtes attention/8 KV, head_dim128, vocab151669, embeddings liés, max_position_embeddings262144, rope_theta5000000. Cette capacité déclarée de contexte n'a pas été qualifiée par l'entraînement à512 tokens. Le dtype déclaré des poids est BF16 ; ce n'est pas automatiquement le dtype de calcul de chaque expérience.

Inférence de référence distincte : GGUF Q4_K_M, SHA256 `fc06dc11c735cca884f0b5da55480ea3178e461e5b747040fdb8c217d50a3ce5`, llama-server CUDA, Flash Attention off, KV f16, contexte8192 par session, génération4096 tokens, température0. Ne pas confondre cette quantification avec la NF4 d'entraînement.

## Adaptation des poids

QLoRA : base4bits NF4 et double quantification, SDPA, gradient checkpointing non réentrant, perte sur réponses assistant seulement ; prompt masqué à-100, packing en séquences512. LoRA rang8, alpha16, dropout0, bias none, cibles q/k/v/o_proj et gate/up/down_proj. 16 515 072 paramètres entraînables. Les poids de base sont gelés. Aucun ajout de couches ni agrandissement de l'architecture : ces cycles ne réalisent pas l'expansion du modèle envisagée dans la discussion.

PyTorch2.6.0+cu124, runtime CUDA12.4, Transformers4.57.1, PEFT0.17.1, bitsandbytes0.48.2, Accelerate1.10.1. Les `packages.txt` sont fournis. Pilote/cycle1 sur RTX : qualification BF16 ; cycles2–7 en FP16 compatible V100, GradScaler(init_scale128), AdamW sans weight decay, clipping1.0, warmup5% puis décroissance linéaire bornée à10% du taux initial. `enable_thinking=False`, trust_remote_code=False, fichiers locaux.

Pilote : 300s par limite200/250/300/350W, remise au même adaptateur initial, LR1e-4. Cycle1 : LR5e-5,10 000 exemples,1 époque, microbatch2/accumulation2. Cycle2 :10 000 exemples,1 époque,LR5e-5. Cycle3 :4 800 exemples,LR1e-5. Cycle4 :2 400,LR5e-6. Cycles5–7 :2 400,LR3e-6. Les graines et effectifs exacts par famille sont dans les configurations.

## Deux GPU et reprise

Deux répliques complètes du même modèle/adaptateur, RTX3080Ti12Go + V100SXM2 16Go ; DDP/NCCL synchronise les gradients, ce n'est pas deux entraînements indépendants ni un modèle coupé en deux. Quatre packs globaux par mise à jour ; deux par GPU quand WORLD=2, quatre sur V100 quand WORLD=1. Pondération de la perte par le nombre de tokens supervisés afin de préserver l'échelle globale ; contrôle d'égalité des adaptateurs et de couverture des packs. Les chiffres `replica_max_difference=0` sont des preuves de concordance enregistrées, pas de qualité des réponses.

Checkpoints complets : adaptateur, optimiseur, scheduler, scaler, compteurs et états RNG ; la bascule peut reprendre le travail validé. Limite habituelle200W par GPU. Le cycle7 s'est exécuté sur V100 seule après échec de qualification thermique RTX ; cycle8 V100 seule, évaluation sans optimiseur. Un config hérité `world_size:2` n'est pas une preuve de deux GPU réellement utilisés : consulter qualification, statut et résumé effectif.

Gardes historiques : GPU83°C, CPU70°C, télémétrie et wattmètre, ECC/Xid, garde thermique et contrôles d'intégrité. La qualification RTX interrompue au cycle7 est un signal enregistré, pas la preuve que son cœur avait atteint83°C. Ne pas désactiver la garde sur cette seule lecture. Limite de puissance ≠ consommation effectivement atteinte ; au relevé du10/11, V100 limitée300W et RTX200W, sans modification par ce lot.

## Données, filiation et évaluation

Familles initiales :0 addition/soustraction ;1 multiplication/soustraction ;2 parenthèses ;3 division/fraction exacte ;4 euros ;5 heure/jours ;6 partage/retrait et compréhension des quantités ;7 données insuffisantes. Oracles Python Fraction/Decimal, réponses structurées JSON `resultat`, `unite`, parfois `jours`, avec explication synthétique.

Filiation : pilote200 → cycle1 ; cycles2/3/4 repartent de cycle1 (les régressions2/3 ne sont pas cumulées) ; cycle5 depuis4 ; cycles6/7 depuis5 ; cycle8 compare5 et les pas40/160/286 de7. Les chemins et hash des adaptateurs sont dans les lignages et le plan d'audit.

Cycle4 : rappel, fractions/horaires, compréhension des quantités. Cycle5 :1 200 bases nouvelles+1 200 rappels, trois blocs progressifs. Cycle6 :1 600 rappels équilibrés+800 cibles (horaires400,euros200,fractions200) avec explications plus longues. Cycle7 conserve questions et ordre de6, raccourcit les800 réponses ciblées et ajoute sélection64. La part cible réelle des tokens supervisés passe de49,382% (80 353/162 716) à34,879% (44 113/126 476), pas simplement de33% à33% parce que les nombres d'exemples sont identiques.

Génération avant/après déterministe, max192 tokens ; huit canaris conversationnels,max256, relecture humaine requise. `content_correct` accepte les valeurs rationnelles équivalentes et vérifie l'unité, les jours pour les heures ; `exact_json` exige l'objet attendu. Ce n'est ni un juge universel ni un test complet des étapes de raisonnement. La notation prend le dernier objet JSON reconnu : c'est un point de contre-revue, pas une garantie de toute la réponse.

Les jeux160 historiques,160 régression,64 compréhension,128 bases puis96 ciblées ont été réutilisés successivement ; leurs résultats ne sont plus des estimations aveugles fraîches. Les totaux160/320/384/512/608 ne se comparent pas directement. BF16/FP16 et GPU changent aussi : cycle5 réévalué6/7 diffère d'une réponse dans deux sous-ensembles tout en totalisant502/608. Aucun lien causal précis n'est établi.

Cycle7 : sélection chaque40pas et fin ; parent62/64, tous les checkpoints62/64 ; règle au moins+2 bonnes réponses sur le meilleur, aucune famille plus de1 sous le parent. Parent retenu (pas0), évaluations608 exclues de la sélection. L'égalité502→502 mesure donc le parent restauré.

Cycle8 :160 nouvelles validations (24 même jour,24 minuit,24 plusieurs jours,24 conversions minutes,32 fractions,16 euros,16 choix d'opération),32 acquis et8 canaris par candidat ; NLL assistant calculée séparément.160 questions finales réservées, non évaluées. L'audit n'est pas un entraînement. Les paramètres résiduels `train_examples` et `epochs` du config copié sont inactifs.

## Incident d'intégrité et limites

Cycle5 bloqué initialement par empreintes source instables. Des copies de données en RAM sans I/O et memtester ont reproduit des bascules de bits ; memtester a notamment trouvé0 !=8. Cela établit un défaut de fiabilité de la plateforme dans cet état, pas l'identité d'une barrette défectueuse. Contrôles SHA CPU et SMART NVMe ne suffisent pas à l'expliquer. Reboot suivi de memtester/copies/hashes réussis et requalification ; les cycles5–8 ont ensuite fini. La cause matérielle racine reste non isolée.

SPD relevé : sept modules JEDEC3200@1,2V et un Corsair JEDEC2133@1,2V / XMP3200@1,35V ; réglage rapporté3200@1,2V. Mélange/fréquence/tension/IMC constituent des hypothèses, pas une cause confirmée. Aucun réglage BIOS de RAM n'a été effectué par ces scripts. Voir le rapport diagnostic conservé.

Les originaux des résultats4–8 ont été relus et leurs empreintes listées dans les manifestes contrôlées sur le serveur le10/11 : toutes conformes. Cela confirme la conservation des fichiers, pas la validité générale du modèle. Aucun recalcul GPU, nouveau cycle ou promotion dans cette collecte.
