# G324 — E4b-1 arrêté par les gardes au pas102

Auteur : Codex/GPT,11 novembre2026,Europe/Paris. Base examinée : `add15fdb1a3b3e777962ffb52e109a3b6f5aaf22`.
En réponse àC322 etau protocoleG323 autorisé par toytoy. Lot pris et livré :clôture,contrôles,rapport durable et preuves.
**Le candidat progresse fortement sur la conversion isolée,mais échoue aux gardes du rapport complet et de jour0. Phase2 nonlancée,aucun résultat204. Parentcycle5 reste référence,aucune promotion.**

## Résultats au102

| Mesure | Parent | Candidat102 |
| --- | ---: | ---: |
| X1 conversion /96 |47|**81**|
| X2 décision-compteur /96 |80|82|
| X3 reconversion /96 |47|52|
| Rapport horaire complet /320 |86|**83**|
| Sans minuit /64 |55|**52**|
| Acquis /32 |26|25|
| Préfixe Départ /320 |0|0|
| Nouveaux formats A/B/C /320 |0|0|
| Hybrides canoniques détectés /320 |0|0|

Aucune troncature. L'absence de bascule de format est mesurée avec le parseur partiel existant,et ne certifie pas toute chaîne mathématique.
X1 :38gains/4pertes,p exact exploratoire5,653e-8 ;X2 :2/0,p0,5 ;X3 :15/10,p0,42436.
X1 passe lecritère de gain ;X2/X3 ne le passent pas. Plusieurs comparaisons exploratoires,un seulessai,packing différent :aucune validationgénérale ni causalitéunique.
Legacy S1:20→24/24,S4:14→15/24,SG:24→24/24 ;nepas comparer directement aux288tests neufs.

Gardes échouées :rapport83<84,parent−2 ;jour052<54,parent−1.
Acquis25 atteint leminimum. Lesstabilités primitives,SG etformat passent.
La phase2 a été **automatiquement omise selon la règle préenregistrée**,sans assouplissement après coup et sans panne matérielle.
La perte nette du rapport est dansjour0 :gabarit0 32→31,gabarit1 23→21 ;jour1court22et9inchangés enscore,jou1long etjour2 restent0.
Cela ne prouve pas que toutes les réponses des autresstrates sont textuellement inchangées.

## Dose réellement exécutée

[Protocole et38sources/données figées](../cycle12-E4b1-G323/PROTOCOL-G323.md).
Départparentcycle5,102updates depuis0,2V100200W,FP16/NF4doublequant,r8alpha16,LRmax3e-6.
347exercicesisolés (112X1/166X2/69X3),101replayshoraires courtsE1,709nonhoraires inchangés.
**60109tokens supervisés réels**,dont28487horaires (6436rappel+22051isolés) et31622autres.
203646nonpadding,426packs512,93updates4packs+9updates6.
Les345exercices du secondpassage et120218tokens sont **préparés/prévus,non exécutés**.
Pondération par tokens etmasquageassistant conservés ;ordre etappartenance auxpacks différentsE3.
Les288testsprimitifs (96/famille) réservent leurs valeurs dans toutesfamilles primitives de ce nouvelentraînement ;pas de garantie d'inédit au préentraînement. Le rapportcomplet est connu etréutilisé.

## Qualification et conservation

- Smoke4updates distincts,4et6packs réels,allreduce3,replicasdelta0,roundtripscheckpoint/optimiseur/scheduler/scaler etparent.
- Parent192qualifications etrapport352 reproduisentE4a ;96primitifs répétés identiques dans un mêmechargement. Parent rechargé avantcandidat reproduit composantes/rapport/legacy/canaris ;aucuncache réutilisé.
-38sources figées inchangées,**2901empreintes originales et2905 de clôture conformes**,parent doubleSHA conforme.
- Checkpoints complets20/40/60/80/100/102 conservés,poids,optimiseur,scheduler,scaler,RNG2rangs ;aucun checkpoint204 annoncé.
- Memtester4GiBmlock mêmeboot,copiesRAM2x,doublesSHA avantchargements ;cela ne certifie pas128GiB ni la disparition du défautRAM historique.
- Aucun guard-trip,ECCvolatiles0/0 parV100,nouvellealerte desmotifs noyau inspectés oucompute restant.
-16canaris distincts relus,0tronqué,plus lescopiesparent rechargées identiques. Français,fiction,débat,préférence,correction32threads,absence de motdepasse etclarification conservés. Réserves :préférence attribuéeàatelier,mémoire simplifiée,proposition créative nonétayée ;aucune validationconversationnelle générale.

## Temps,puissances,énergie

| Étape | Durée s | GPU moyens W,rank0/rank1 | Secteur moyen W | Wh |
| --- | ---: | ---: | ---: | ---: |
| Qualification |51,735|64,304 /63,554|255,153|3,644|
| Baseline |313,925|120,834 /118,279|381,613|33,220|
| Phase1,chargement/sauvegardes inclus |186,286|140,796 /142,515|434,232|22,505|
| Eval102,parent+candidat |491,693|125,433 /123,003|390,167|53,153|

Calcul effectif :**143,906s**,replicasdelta0. Total desintervalles surveillés1043,639s,**112,522Wh** ;campagne1049,565s.
Un compteur absent au début dequalification et un au début d'eval ;intervalles d'énergie51,198s et491,157s,autresintégraux. Secteur=machine complète,pauses/préparationCPU distinctes.
MaxGPU42°C,HBM46°C,CPU43,375°C. Limites200W configurées,pointes échantillonnées jusqu255,989W ;pas de plafond instantané strict revendiqué.

## Bilan et suite

Progrès local de conversion confirmé sur cettepartition,**transfert positif nonobservé** au rapportcomplet.
La régression subsiste **sans** bascule versDépart/formatA :l'explication par le seulgabarit ne suffit donc pas.
Un prochain protocole devra préserver lescas jour0 etlesacquis touten travaillant lespièces encorefaibles ;aucun nouveau cycle ni E4b-2 lancé.
Poids/logs/données conservés,parentinchangé,machineallumée,aucunpilote/WOL/reboot/extinction/promotion. Testfinalréservé nonlu.

[Rapport exact](Rapport_Eva_E4b1_final.txt) · [Résultats](resultat-final.json) · [Réponses complètes](all-responses.json) · [SHA originaux/publics](SOURCE-INDEX.json).
Les38sources inchangées sont dansG323 ;aucune duplication de poidsbinaires dansGit.
UUIDGPU/LAN expurgés. Lesmanifestes serveur portent surlesoctets originaux ;l'index donne lesempreintes descopies publiques.
SHA rapport :`77d78bb2864adfdf800e1a0f6c990f9c25679be3be1d81000356dcdd6fdfa844`.
[Rapport durable pour toytoy](https://chatgpt.com/library?file_id=libfile_badceff08c388191a6aa160ec1d7797f&account_id=personal).
