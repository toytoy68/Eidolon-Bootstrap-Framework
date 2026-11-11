# G321 — Sondes C319 : le format C ne passe pas le test préalable

Auteur : Codex/GPT, 11 novembre2026, Europe/Paris. Base examinée `77fe23a2d84da70afe6bae5a25dda8fe5a9a702f`, après C319 `7f0415799eed33cc1ba84ee1b72038e185f45786`.
Nature : mesures réelles X399, sans entraînement. Statut : clos pour ces sondes.

**FC obtient15/44, contre27/44 pourFA et28/44 pourFB. Le critère FC≥FA échoue ; aucun E4c n'est lancé.**
Le parent cycle5 et tous les poids restent inchangés.

## Protocole réellement exécuté

[Protocole G320](../probes-C319-G320/PROTOCOL-G320.md).
Les12 tests Claude passent avec le corpusG304. Les sources Claude sont copiées inchangées, empreintes Git conformes.
156anciennesquestions sont strictement conservées ;44FC ajoutées :44problèmes connus×ZS/FA/FB/FC +24SG =**200 générations**, toutes réalisées.
DeuxV100200W,FP16/NF4doublequant,greedy384tokens,mêmeSYSTEM,unprocessus indépendant et un chargementbase parGPU,parent gelé.
Lot16 fixe,groupes de paires et GPU parquestion appariés. **Nouveau régime exploratoire** : aucune équivalence affirmée avec les anciennes sondes lot1.
Qualification supplémentaire avant les sondes :**192 réponses parent exactement identiques** à la baselineE4a, sur les mêmesGPU/lots.
SG strict24/24,doncFB autorisé ;valeur+signe+unité, booléens refusés.
CopiesRAM2x avec12compteurs nuls parpassage,doublesSHA source/parent,preuve memtester4GiB du mêmeboot,gardes inchangées. Pas de certification128GiB ni disparition démontrée du défaut historique.
Aucun optimizer/backward/DDP/NCCL ;contrôle AST et paramètres gelés.

## Scores appariés

| Variante | JSON heure+jours juste /44 | Juste et aucune affirmation fausse détectée | Tronquée | Compteurs explicites corrects, quand nécessaires /34 |
| --- | ---: | ---: | ---: | ---: |
| ZS, sans exemple |19|19|0|0|
| FA, format A |27|27|0|28|
| FB, format B |28|27|8|34|
| **FC, format C** |**15**|**15**|**0**|**20**|

FC contreFA :**2 gains/14 pertes**,p exact exploratoire0,0041809.
FC contreFB :3/16,p0,0044250 ;contreZS :10/14,p0,541256.
Plusieurs comparaisons sur44cas connus, pas200cas indépendants ni une validation générale.
FB a8troncatures à384tokens ;son unique bonne réponse avec une affirmation fausse est distinguée de sa justesse finale.
FC a0troncature :son recul n'est pas expliqué par une réponse coupée.

| Strate | N | ZS | FA | FB | FC |
| --- | ---: | ---: | ---: | ---: | ---: |
|1440-dessous|8|8|3|1|1|
|1440-dessus|8|6|8|8|6|
|1440-exact−1|2|1|1|1|0|
|1440-exact|2|2|1|2|0|
|1440-exact+1|2|2|2|2|0|
|2880-dessous|8|0|0|2|1|
|2880-dessus|8|0|8|8|5|
|2880-exact−1|2|0|0|0|1|
|2880-exact|2|0|2|2|1|
|2880-exact+1|2|0|2|2|0|

## Point nouveau : C ne préserve pas forcément la conversion initiale

Contre-lecture des44réponsesFC et audit des opérandes écrits :
première égalité littérale a+b=c dont b est la durée demandée. Indicateur lexical explicite, pas un oracle complet du raisonnement.

| Variante | Égalités repérées | Premier opérande et total attendus |
| --- | ---: | ---: |
|ZS|44|44|
|FA|44|44|
|FB|44|44|
|FC|42|29|

FC contient **13 premiers opérandes faux**, plus2réponses se limitant à parler de JSON.
Une analyse initiale exigeait le suffixe « minutes » :41repérées/28justes ;la version élargie ajoute une égalité sans suffixe (3+1436=1439),d'où42/29. Les deux traces sont conservées.

Exemples vérifiés :

- `FC-1440-dessous-7` :départ09:37,durée811. Il faut **577+811=1388**. Eva écrit **937+811=1748**,puis05:08/jour1. Les opérations écrites sont cohérentes entreelles, mais l'opérande de départ est faux.
- `FC-2880-exact-1-0` :1089+1790=2879,puis reste1439 correct ;la réponse est00:39 au lieu de23:59. La reconversion finale casse encore.
- `FC-2880-exact+0-0` :2880→1440→0,jour1 puisjour2,00:00/jour2 correct. C peut fonctionner,ce qui ne démontre pas sa robustesse.

`format_of` détecteC dans33/44réponses,contre8courtes et3autres. L'imitation de la forme ne garantit pas le contenu.
Le validateur d'affirmations ne recroise pas tous les opérandes avec la question :le premier exemple peut donc avoir zéro affirmation fausse détectée tout en étant faux. Aucun nouveau correcteur n'a changé les scores après coup.
L'hypothèse d'une conversion trop implicite dans les exemplesC est plausible, **non démontrée**. Aucun nouveau prompt ni autre essai lancé pour la tester.

## Correction de l'interprétation C319

Reproduit sur les352réponses G318 :
parent/102 identiques261 ;102/E3-204 identiques34,donc318changées ;
**102/E4a identiques36,donc316changées** ;E3/E4a identiques290.
La répétition seule est fortement affaiblie à cette dose ;cela n'isole pas le gabarit comme cause unique parmi les éléments communs.
La promesse « même début, donc pas de transition problématique » n'est pas établie ;le testC montre même des erreurs nouvelles en amont avec ces exemples en contexte.
L'effet d'un prompt et celui d'un apprentissage restent distincts.

## Temps, puissances et énergie

Durées =fenêtre allant du début de la première génération du groupe à la dernière réponse des deuxGPU.
Les GPU peuvent chevaucher deuxgroupes adjacents :les énergies de fenêtres ne doivent pas être additionnées.

| Groupe | Durée s | Secteur moyen W | Énergie de fenêtre Wh | Tokens produits |
| --- | ---: | ---: | ---: | ---: |
|Qualification192|55,877|406,910|6,430|11970|
|Signes24|8,323|400,647|0,857|1080|
|ZS44|17,922|383,806|1,929|2898|
|FA44|59,411|490,898|7,930|7839|
|FB44|108,615|498,608|14,789|10494|
|FC44|38,813|473,348|4,930|4309|

Intervalle surveillé total,préflight/chargement/qualification inclus :**324,961s**,secteur moyen**435,857W**,énergie**39,436Wh**,aucun relevé compteur absent.
GPU moyens145,494/142,304W ;limites200W,pointes échantillonnées212,295/245,046W ;secteur max551,2W.
MaxGPU42°C,HBM49°C,CPU41,75°C ;aucun guard-trip,ECCvolatiles0/0 parV100,aucune nouvelle alerte des motifs noyau vérifiés,aucun compute restant.

## Conservation et limites

**466 empreintes finales conformes**,23sources/données figées inchangées,parent vérifié deuxfois.
Poids/checkpoints précédents et toutes nouvelles données/réponses/logs conservés sur X399.
Les fichiers originaux et leur manifeste restent intacts ;clôture et audit d'opérandes séparés.
Aucun testfinalréservé lu ;aucun entraînement,E4c,promotion,pilote,WOL,reboot ou extinction.
La machine reste allumée.

[Réponses complètes](responses.json) · [Scores](resultat-final.json) · [Audit des opérandes](closure/initial-addition-audit.json) · [Profils pargroupe](closure/stage-profiles.json) · [Sources/SHA originaux et publics](SOURCE-INDEX.json).
UUIDGPU et LAN expurgés,groupes/rangs conservés ;les SHAoriginaux portent sur les octets serveur,les publics sur les copies expurgées.
[Rapport texte exact](Rapport_Eva_sondes_C319_final.txt), SHA256 `c8039d1af5b14912bea192af31ce9d6548e23b6d9d86230f51dbe0ad6c9361da`.
[Rapport durable toytoy](https://chatgpt.com/library?file_id=libfile_396b2611aeb08191823a336a2050a05a&account_id=personal).

Suite proposée :petits exercices isolant conversion HH:MM→minutes,décision de poursuivre,compteur accolé à la soustraction et reconversion finale. Mesurer chaque étape et les acquis avant un nouveau cycle complet. Ce curriculum n'est pas lancé et ses seuils/dose restent à définir ;aucune session Claude présumée.
