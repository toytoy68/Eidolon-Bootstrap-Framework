# G304 — Sondes C303 exécutées : exemples utiles, arrêt de boucle encore faux

Codex/GPT,10/11/2026,Europe/Paris. Base examinée : `01046a6e08081d0b75f73554366847ed937dc082`, branche `feat/eidolon-core-v0.1`. Suite de C303, sondes sans entraînement. Lot documentaire pris et livré ; canal Claude préservé.

## Résultat principal

Les deux exemples résolus améliorent fortement la justesse sur ce petit jeu, mais ne prouvent pas la maîtrise complète. L'amorce seule ne suffit pas. Les312 réponses complètes et les grades sont publiés.

| Sondes (notation JSON originale) | Parent cycle5 | E2 |
| --- | ---: | ---: |
| S1 heure→minutes | 20/24 | 23/24 |
| S2 soustraire1440 | 24/24 | 24/24 |
| S3 jours+reste | 23/24 | 20/24 |
| S4 minutes→HH:MM | 14/24 | 17/24 |
| ZS complet sans aide | 7/20 | 7/20 |
| FS complet avec2exemples | 16/20 | 17/20 |
| PF complet avecamorce | 5/20 | 7/20 |

FS vs ZS :parent10 gains/1perte,E2 10gains/0perte. PF vs ZS :parent0gain/2pertes,E2 0/0. Échantillon exploratoire :4questions par strate complète,une graine. Aucune comparaison exhaustive de variantes de prompt,aucun gain d'entraînement démontré par ce test en contexte.

| Questions complètes (4cas par cellule) | Parent ZS | Parent FS | Parent PF | E2 ZS | E2 FS | E2 PF |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| jour0 court | 4 | 3 | 3 | 4 | 4 | 4 |
| jour1 court | 3 | 4 | 2 | 3 | 4 | 3 |
| jour1 long | 0 | 4 | 0 | 0 | 4 | 0 |
| jour2 court | 0 | 1 | 0 | 0 | 1 | 0 |
| jour2 long | 0 | 4 | 0 | 0 | 4 | 0 |

Total jour2 :0/8 ZS,5/8 FS,0/8 PF pour chacun. Les cas « jour2 court » restent difficiles malgré les exemples.

## Où ça casse réellement

[Audit d'invariants](invariant-audit.json) et [son code](sources/invariant_audit.py.txt). Dans les deux modèles,les trois échecs FS jour2-court rédigent une comparaison fausse :
-1421+1485=2906,puis2906−1440=1466,mais «1466 < 1440» ; attendu deuxième soustraction et2jours.
-2915−1440=1475,puis «1475 < 1440».
-2918−1440=1478,puis «1478 < 1440».

La soustraction isolée S2 passe24/24,mais la condition de continuation n'est pas correctement appliquée ici. Les réponses gardent parfois la bonne heure en reconvertissant24hXX en00hXX,tout en perdant un jour.

Important :l'outil original step_errors retourne une liste VIDE sur ces réponses. Il contrôle notamment la soustraction et le nombre d'étapes écrites,mais pas la vérité de «reste < 1440». Son test d'addition utilise aussi le premier motif trouvé ; ce n'est pas un validateur exhaustif. Les8tests originaux passent sur X399,ce qui ne prouve pas cette exhaustivité. Les sources Claude et scores originaux ne sont pas réécrits.

S3 nécessite une distinction format/contenu :
-Parent S3-17 calcule correctement2881=2×1440+1,mais met «1 minute(s)» au lieu de «1» dans resultat :faux strictement pour une raison de sortie.
-E2 S3-1 etS3-9 calculent correctement1349 et79,mais ajoutent jours/texte dans resultat.
-E2 S3-17 écrit une décomposition correcte,puis un JSON au reste faux1440 ; incohérence explication/réponse.
-E2 S3-21 calcule2999=2040+959 etrend1jour,959 :erreur réelle.

Il serait donc faux d'interpréter23→20/24 comme trois pertes arithmétiques supplémentaires. Les scores stricts restent publiés sans remplacement par une renotation opportuniste.

S1 etS4 comportent de vraies erreurs :parent transforme10:30 en1030+30 ; S4 invente parfois une heure de départ et réutilise l'ancien schéma d'addition,par exemple581minutes→600+81=681→11:21. E2 améliore certains cas,mais conserve plusieurs de ces confusions.

## Adoption de time_steps

| Mesure | Parent ZS/FS/PF | E2 ZS/FS/PF |
| --- | --- | --- |
| Début du format reconnu | 0/20,19/20,0/20 | 0/20,19/20,0/20 |
| Structure complète selon filtre supplémentaire | 0/20,12/20,0/20 | 0/20,14/20,0/20 |

Le filtre supplémentaire exige les sections et le nombre attendu de soustractions ; il n'est pas un oracle de toute la chaîne. Il reste distinct de la justesse du JSON final. Une réponse correcte peut aussi être concise et ne pas satisfaire ce filtre.

[Analyse CPU des réponses complètes E1/E2](cpu-analysis.json) :324 réponses horaires par état (320cibles+4acquis),début time_steps0/324 avant/après dans les deux essais. Ceci étend le constat de Claude au-delà des seules six réponses changées,et reste distinct de ses48échecs historiques de l'audit8.

## Protocole et intégrité

156sondes uniques par candidat,S1–S4×24 etZS/FS/PF×20 ;653paires E1/E2 exclues. PF concatène assistant_prefix après le gabarit puis le remet dans response. Même SYSTEM qu'E1/E2,décodage glouton384tokens,V100 seule200W,FP16/NF4doublequant. Zéro sortie à384tokens ; aucune sonde manquante ni IDdoublonné. Les IDs correspondent dans l'ordre et chaque identité candidat est vérifiée.

Un chargement de base etdeuxadaptateurs successifs,parentcycle5 puisE2 ; ne pas présenter ces sondes comme deux chargements indépendants. Binaries hashés deux fois,statehashes vérifiés. Nouveau contrôle copiesRAM2x tous compteurs zéro etsourceSHA2x avantchargement ; preuve dans [live-integrity.json](live-integrity.json). Garde indépendante CPU/GPU/HBM,ECC/Xid,noyau,progression etsecteur,verrouglobal. Aucun optimizer/backward,aucun entraînement ou modèle promu.

Boot `f006076b-6010-48c7-8104-046b21152e0f` inchangé ; qualification antérieure memtester4GiBmlock complet. Aucune nouvelle alerte noyau Oops/BUG/Hardware Error/Xid/Machine check détectée sur ce boot à clôture ; aucune preuve que le défaut intermittent de RAM est réparé. Anciennes preuves d'erreurs conservées. Pas de changement BIOS ni d'intervention matérielle.

Service terminé/succès,inactif ; aucun calcul GPU restant. Six empreintes du manifeste [run/result-saved.json](run/result-saved.json) recalculées conformes,312réponses présentes. Rapport serveur exact enregistré séparément pour toytoy. Touslogs,données,poids etcheckpoints historiques conservés. Aucune extinction ni reboot.

Le final-test-reserved n'a pas été lu ni évalué pour ces sondes. Les exclusions viennent des jeux E1/E2 ; le lot réservé n'est pas nécessaire.

## Suite proposée, non lancée

La forte amélioration FS rend plausible un problème d'adoption du format,mais n'établit pas que le LR est la seule cause. S2 réussi etFS élevé peuvent motiver un E3a borné ; les comparaisons fausses etla reconversion fragile justifient d'abord un diagnostic contrôlé de l'arrêt de boucle (reste>=1440),du compte des jours etde la restitution HH:MM. Éviter d'augmenter simultanément LR,dose etnombredepasses. Conserver une mesure explicite de format,de justesse etde validité des étapes,etdes acquis/canaris. Aucun passage automatique à3e-5,aucun E3 lancé.

## Publication

Sources Claude citées à C303 restent inchangées dans claude-review/. Le harnais exact [sources/probe_worker.py.txt](sources/probe_worker.py.txt),les [questions](probes.jsonl),les réponses complètes avec grades originaux etla preuve de préparation sont joints. Les UUIDGPU/LAN sont expurgés des copies publiques. source-index.json distingue SHA256 des originaux serveur etdes copies publiques ; ne pas appliquer les hashes serveur aux copies expurgées.
