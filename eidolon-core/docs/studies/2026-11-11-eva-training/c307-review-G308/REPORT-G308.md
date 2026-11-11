# G308 — Contre-vérification CPU de C307

Auteur : Codex/GPT.11/11/2026,Europe/Paris.
Base examinée :1984bda3e5d6f294d9b68d74e59452ed110e4620,feat/eidolon-core-v0.1.
En réponse à C-MSG-C307 relayé par toytoy.
Lot pris : revue CPU du validateur, des cas frontière et de la mesure de format. Aucun chargement des poids, génération, entraînement ou changement de source historique.

## Résultats reproduits

Les trois fichiers Claude ont été copiés inchangés dans /srv/eidolon/work/eva-review-c307-20261111.
Les9tests originaux passent sur X399 avec le corpus G304, sans test sauté.
Le nouveau validateur retrouve les6comparaisons fausses et la septième incohérence de compte de jours annoncées par Claude.
Le source C303 historique reste inchangé. Les sources Claude et son message C307 restent inchangés.

## Le format B introduit une branche non qualifiée par S2

Les24cas S2 G304 ont tous un résultat strictement positif : minimum162,maximum2818.
Aucun résultat négatif, aucun zéro. Le score24/24 ne couvre donc pas le dernier calcul négatif du formatB ni la classification du signe.
B remplace la comparaison à1440 par une soustraction ET une décision sur le signe ; il ne supprime pas toute comparaison.

Complément proposé avant choix du format : cas ciblés N−1440 donnant −1,0,+1, nombres négatifs supplémentaires et classification explicite négatif/zéro/positif. Cela ne nécessite aucun entraînement.

## Trois contre-exemples reproductibles au validateur

À partir de time_steps_b(1421,1485), dont la bonne réponse est00:26,jour2 :

1. Remplacer «1466, positif ou nul» par «1466, négatif» : invalid_claims=[] et JSON toujours correct.
2. Remplacer «−1414, négatif» par «−1414, positif ou nul» : invalid_claims=[] et JSON toujours correct.
3. Remplacer l'Arrivée ET le JSON par00:27 alors que le reste calculé est26 : invalid_claims=[], même si le correcteur final indépendant refuse la réponse.

Le troisième ne fausse pas le score final grâce à _correct ; il contredit seulement une lecture trop large de «cohérence du JSON avec le dernier reste». Les deux premiers sont des affirmations fausses centrales au nouveau format, invisibles même quand le score final est juste.
Ces sorties sont des mutations synthétiques de contrôle, pas de nouvelles générations Eva.
La correction des anciennes comparaisons est réelle ; le validateur demeure partiel. Ajouter les contrôles de signe et l'égalité heure_en_minutes=reste avant la comparaison FA/FB.

## Taille et couverture du futur jeu

build(seed3070,per8) donne96générations sur32problèmes distincts, chacun déclinéZS/FA/FB. Il y a8problèmes par cellule frontière/côté ; ne pas compter96observations indépendantes.
Avec ce seed sans exclusions, aucun des32totaux n'est exactement1440ou2880, et aucun n'est à±1minute.
Offsets réels :
1440-dessous :−2,−60,−22,−52,−38,−40,−43,−10.
1440-dessus :54,33,13,36,13,9,17,29.
2880-dessous :−19,−15,−53,−29,−29,−45,−53,−52.
2880-dessus :57,53,15,3,22,12,10,57.
Ce constat dépend du seed et des exclusions. Forcer les cas exacts et±1 tout en conservant des cas aléatoires ; ne pas supposer leur présence dans un tirage au hasard.

## Signal NLL et probabilité de Départ

Un contrôle CPU du tokenizer réel, sur le premier item du rapport E3 et son SYSTEM/chat template, donne :
- Dé :token86893 ;
- part :token4480 ;
- le préfixe du chat est bien commun à l'entrée et la réponse forcée.

Il faut mesurer la probabilité conditionnelle de la séquence86893,4480, pas nommer P(Dé) «P(Départ)».
P(Départ|prompt)=P(86893|prompt)×P(4480|prompt,86893).
Pour comparer les12checkpoints, garder les mêmes questions, réponses cibles, masques assistant, précision et configuration ; inclure le parent comme référence. NLL forcée et probabilité du préfixe sont des signaux de format, pas des preuves de bonne réponse en génération.
La durée «quelquessecondes parcheckpoint» et les gains de batching doivent être mesurés, pas annoncés comme acquis.

## Suite proposée et état réel

L'ordre général de C307 est pertinent : signal sans génération sur les checkpoints existants ; frontière A/B avec les contrôles complétés ; évaluateurs indépendants du DDP, persistance parréponse et batching qualifié ; évaluation du204 ; décision E4 séparée.
Pour le batching, comparer en priorité les réponses et scores au même réglage entre candidats, publier toute divergence lot1/lot16. Ne pas désactiver les gardes ni modifier les sources des essais conservés.
Le résultat few-shot de G304 est un indice limité :16–17/20 et5/8 pourjour2 ne démontrent ni une maîtrise générale ni un unique mécanisme causal.

Cette revue n'a lancé NI les mesures NLL sur les poids, NI les96générations, NI E4. Aucun nouveau serviceGPU, aucune reprise204, aucune promotion, aucun réveil/arrêt/redémarrage. Les tâches suivantes restent à exécuter après qualification des contrôles. L'augmentation du LR reste une décision distincte de toytoy.
