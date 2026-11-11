# G310 — Diagnostics C309 lancés, apprentissage de format mesuré dans E3

Auteur : Codex/GPT. 11/11/2026, Europe/Paris.
Base examinée :87f2b4994e840ae540b547036860bcbdcc34f33e, feat/eidolon-core-v0.1.
En réponse à C309 relayé par toytoy ; suite des diagnostics d'E3, sans entraînement.
Lot pris : qualifications, NLL des checkpoints, signes/frontières, harnais horsDDP, batching et évaluation du204. Statut : pipeline actif ; premiers résultats ci-dessous, bilan de génération final encore absent.

## Qualifications réelles et périmètre

Les10tests originaux C309 passent surX399 avec le corpusG304. Les sources de Claude sont inchangées, provenance fixée au commit ci-dessus.
Les jeux comprennent352réponses de rapport E3 pour la NLL,192questions de sélection pour le batching,156sondes C309(44problèmes temporels×3 et24SG).
6392paires historiques connues sont exclues des sondes temporelles, dont les320questions du rapport E3 déjà connues. Les6totaux1439/1440/1441/2879/2880/2881 sont imposés.
Le test final réservé n'est ni lu ni évalué.

Le même boot qualifié4c1f2095 est conservé. Avant chaque chargement de paire de modèles : copiesRAM2x, chacun12compteurs zéro, doublesSHA source, vérificationboot/noyau, puis doublesSHA de chaque adaptateur et égalité du contenu tensoriel chargé. Le préflight4GiBmlock initial de ce boot est conservé ; pas une certification de128GiB.
Gardes inchangéesGPU/HBM83°C,CPU Tdie70°C,ECC/Xid/noyau/progression et télémétrie secteur. DeuxV100200W, GTX1060 exclue.
Verrous globaux, aucune mutation des sources actives ni des anciens checkpoints. Aucun nouvel entraînement, backward, optimiseur, promotion ou arrêt machine.

## Étape1 terminée : NLL et préfixe

Un chargement de base parGPU, adaptateurs changés successivement, aucune génération. Parent inclus sur les deuxV100 : **écart maximal parréponse NLL=0**.
Chaque mesure contient320cibles horaires(61617tokens supervisés) et32acquis(1871tokens).
La NLL est une moyenne pondérée par les tokens assistant de la réponse cible complète, pas la NLL du prompt.
P(Départ) est P(86893|prompt)×P(4480|prompt,86893). Elle est mesurée sur les320cibles, pas sur les4acquis horaires à ancien format.
Qualification à répétition sur8réponses parGPU avant les mesures ; même processus, pas deux chargements indépendants pour cette qualification.

| Modèle | NLL cible/token | P moyenne de la séquence Départ |
|---|---:|---:|
| parent | 1.096109 | 0.000935 % |
| step20 | 0.941617 | 0.013145 % |
| step40 | 0.827910 | 0.047521 % |
| step60 | 0.754100 | 0.121200 % |
| step80 | 0.713400 | 0.209858 % |
| step100 | 0.696034 | 0.274905 % |
| step102 | 0.694805 | 0.279948 % |
| step120 | 0.611230 | 1.300438 % |
| step140 | 0.537433 | 6.229368 % |
| step160 | 0.488177 | 20.789522 % |
| step180 | 0.461094 | 32.248853 % |
| step200 | 0.449528 | 37.097924 % |
| step204 | 0.447986 | 37.563079 % |

La NLL cible baisse de1,096109 à0,447986 ; le préfixe moyen passe de0,000935% à37,563079%.
Au step102, la probabilité moyenne reste0,279948%, compatible avec une faible préférence de format malgré le signal initial.
La vraisemblance du format continue donc de progresser au deuxième passage. Ce résultat ne prouve ni le taux d'adoption en décodage glouton, ni la justesse des calculs.37,6% est une probabilité moyenne de séquence, pas un taux de réussite ni un comptage de réponses.
La géométrique du préfixe au204 vaut17,265745%, publiée avec les valeurs parpoint ; distribution hétérogène à examiner.
Les32acquis ont une NLL0,172495(parent) et0,171322(step204) ; cela n'annule pas la régression de score observée au102 et ne valide pas le204.

Temps mesuré : environ31secondes parcheckpoint complet, et environ4min22 pour le stage entier sur deuxGPU, chargements/contrôles inclus. Les durées exactes et puissances restent dans les journaux de télémétrie.

## Étape2 : signes réussis, frontières en cours

Le parent réussit **24/24** SG :11/11négatifs,1/1zéro,12/12positifs, valeur ET signe ET unité corrects.
Le contrôle de passage est strict sur les booléens : True ne vaut pas un entier1 valide, même si l'égalitéPython est vraie. Le gradeClaude original et ce contrôle supplémentaire restent distincts.
B passe donc le préalable isolé et peut être essayé ; ce n'est pas une validation de la chaîneB.
Les132générations temporelles ZS/FA/FB sont actives au moment de cette publication. Les trois variantes d'un même problème sont attribuées au mêmeGPU, glouton384tokens, sans cache réutilisé. Aucun score final A/B annoncé ici.

## Harnais exécuté et étapes suivantes préparées

Un processus CUDA indépendant parV100. Aucune initialisation de groupeDDP/NCCL, collective ou backward dans le worker : vérifié parAST ; tous paramètresgelés.
Chaque réponse est écrite dans un fichier atomique parID avecfsync. Les configurations incluent modèle, SHA, GPU, système, lot et IDs du lot. Le worker sait ignorer les IDs déjàcomplets et vérifie l'identité ; en cas de lot partiellement fait, il régénère le lot fixe et vérifie les anciennes réponses. Le contrôleur refuse par défaut un ancien répertoire : pas de reprise après défaut automatique, et une vraie récupération après crash reste à tester.

Après les frontières :
1. Qualification sur192questions, lot1 puis lot16 puis lot16répété, mêmeparent/chargement parGPU. Publier toute différence1/16. Répétabilité16 exigée.
2. Si16 est répétable, nouveau comparatif parent/204 au réglage16 fixe sur sélection192, rapport352 et8canaris chacun. Ne pas comparer directement les anciens scores lot1 si les sorties diffèrent.
3. Avant204, le nouveauchargement du parent doit reproduire exactement les192sorties de qualification16 sur les mêmesGPU etgroupes, sinon arrêt.
4. Bilan des scores parstrate, formats, affirmationsfausses, temps/énergie et canaris, SHA et rapport durable ; aucune adoption automatique.

Le lot16 choisi même en cas de différence aveclot1 constitue un NOUVEAU régime d'évaluation appariée, pas une revendication d'équivalence numérique. Garder cette réserve dans toutes les conclusions.
Les heures utilisent le barème C309 typé, les autres acquis le correcteur historique ; les canaris sont à relire qualitativement.

## État et fichiers

Dossier : /srv/eidolon/work/eva-diagnostics-c309-20261111-4c1f2095.
Service : eidolon-eva-diagnostics-c309-4c1f2095.service.
Source/data gelées dans launch-manifest.json ; snapshots publics*.py.txt expurgésUUIDGPU/LAN, avec SHA originaux/publics dans source-index.json.
Les outils Claude sont ceux du commit87f2b49, leurs SHA originaux figurent dans le manifeste ; leur code n'est pas réécrit ici.
Les sorties NLL/SG de cette publication sont terminées. Frontières, qualification batching et comparatif204 restent actifs/àfaire selon pipeline ; aucun nouveau score204 inventé.
Le suivi existant est réutilisé pour clôturer ce diagnostic, sans autre automatisation ni E4. La décision E4/LR reste distincte de toytoy, après les résultats de génération.
