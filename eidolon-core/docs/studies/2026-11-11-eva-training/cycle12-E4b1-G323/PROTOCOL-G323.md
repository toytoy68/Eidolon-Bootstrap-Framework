# G323 — E4b-1 autorisé : apprendre les pièces séparément

Auteur : Codex/GPT. Date :11 novembre2026,Europe/Paris. Base examinée :`9914b3db89b52f6f8ffa8f7804b7bb322f3a6684`.
En réponse àC322 età l'accord direct de toytoy « accord ok ! ». Nature :protocole exécuté,essai borné en cours.
Aucun E4b-2,autreessai,promotion,pilote,WOL,reboot ouextinction automatique.

## Hypothèse et limites

Apprendre X1conversion,X2décision+compteur,X3reconversion en exercices isolés,avec rappel complet au format court d'origine.
L'apprentissage de pièces ne garantit pas leur transfert vers une question complète.
La série précédente affaiblit l'explication par la seule répétition ;elle ne démontre pas que tout changement de format échouerait nécessairement.
La lectureC32228/44 conversions justes correspond au parseur exigeant « minutes » ;l'audit élargi G32129/42 tient aussi une égalité sans ce suffixe. Aucun désaccord sur les13premiersopérandes faux,ni sur15/44 réponses finales.

## Départ et matériel

Parent **cycle5**,pasE3/E4a, SHA256`c600d531e36d65b30c36b84bc65f6a44c0175550581b8ea5a1f1c224a27d5b30`,état tensoriel`0883c80e45904bdcb85aa6a27d20e921eea7a6bf5574990375e51835d4163a52`.
Base nightmedia/Qwen3-4B-Element8-Eva-Hermes-Heretic,r3497c4c82493fabf3ee118e9865b047d8aecccf2.
DeuxV100200W,GTX1060exclue,FP16/NF4doublequant,LoRAr8alpha16.
LRmax3e-6,calendrier102 répété ;**204updates maximum depuis leparent**.
Évaluations dans desprocessusCUDAindépendants,horsDDP.

## Données concrètes et budgets

101replays horaires courts originauxE1,avant réécritureE2 ;709nonhoraires identiques à E1/E3 parpassage.
Les101réponses courtes ont été vérifiées contre l'oracle(question→heure/jours),zéroerreur.
Aucun texte de question complète au format time_steps dans letrain.

| Mesure | Passage1 | Passage2 |
| --- | ---: | ---: |
| Exemples isolés nouveaux |347|345|
| X1 / X2 / X3 |112 /166 /69|111 /164 /70|
| Replay horaire /nonhoraire |101 /709|101 /709|
| Total exemples |1157|1155|
| Tokens supervisés X1 |4760|4723|
| Tokens supervisés X2 |12985|12998|
| Tokens supervisés X3 |4306|4330|
| Replay horaire supervisé |6436|6436|
| **Horaires supervisés total** |**28487**|**28487**|
| Nonhoraires supervisés |31622|31622|
| Tokens nonpadding |203646|203398|
| Packs512 |426|428|
| Updates4packs /updates6packs |93 /9|92 /10|

**120218 tokens supervisés cumulés**,dont56974 horaires(47,392237%),comme E3-204. Tous les nouveaux exercices sont distincts entrepassages.
X1 etX3 n'utilisent pas lesmêmes valeurs d'entraînement.
Les valeurs des**288tests neufs (96parfamille)** sont exclues de **toutes** lesfamilles primitives d'entraînement.
Cela ne garantit pas l'inédit face au préentraînement du parent ni face aux autres tâches anciennes.

X2 :N0–4319 ;86/166 puis83/164 sont à±60minutes de1440/2880,au-delà du tiers requis.
Répartition jours0/1/2 :55/56/55 puis36/88/40,asymétrie du secondpassage publiée.
Bornes1439/1440/1441/2879/2880/2881 etX3(0/59/60/1380/1439) enseignées unefois,premierpassage ;pas de duplication pour les remettre au second.
Les testsprimitifs réservés excluent cesvaleurs ;S1/S4/SGhistoriques sont desdiagnostics distincts,nonaveugles.

### Différence de packing explicitée

Plus de prompts courts implique plus de tokens non supervisés et de packs qu'E3.
Le packing408 initial était infaisable ;la préparationCPU a été corrigée **avant toutgel/lancement**.
Un premier poolX2 insuffisant enfrontières a aussi été corrigé avantlancement ;traces souspreparation-history.
Aucun contrôle d'intégrité matériel n'a été contourné.

La séquence reste512 ;packingdense d'exemples entiers,split pour unnombrepair.
102updates/pass conservées,avec4ou6packs globaux,donc2ou3microsteps égaux surchaquerang.
La formule validée de pondération par tokens `WORLD*n/global_supervised` reste inchangée.
Masques assistant produits par la fonctionencode antérieure,réutilisés sans modification.
L'ordre et l'appartenance auxpacks changent ;l'attention causale peut traverser desexemples,comme avant.
**Ce nouvelessai ne prétend pas isoler un seul facteur causal.**

## Contrôles réalisés avant lancement

-7200oracles X1/X2/X3 vérifiés,y compris bornes ettypes booléens refusés.
-Couverture exacte desexemples/packs,tokens supervisés60109 parpassage,masquesPAD ettests disjoints.
-GradientCPUglobal vsDDPpondéré vérifié pour4et6packs.
-Smoke réel4updates sur les2V100 :4ET6packs exercés,allreduce=3,replicas delta0,parent etcheckpoint/optimiseur/scheduler/scaler roundtrip passés.
-38fichiers figés,manifeste`6d8091c8699836ce68afbc01cf483005bb213a792b26039084b62222fb8dc715`.
-Dataset SHA`477c08b25b11290bb9405bb3da31c0ba023e2b4ea1660469ba7fc8ca22bc86a6`.
-Train.py SHA`11b78a08d1a8202001f8489e4d2f9c3e938a5ab4a035d9e7cb00cd629150fa27`.

[Securité des sources/SHA originaux et publics](SOURCE-INDEX.json).
train.py,audit_worker.py,campaign.py sont lesexécutables ;train-source.py/audit-source.py sont destemplates historiques conservés,nonexécutés.

## Pipeline en cours

Service unique`eidolon-eva-c12-components-4c1f2095.service`.
Dossier`/srv/eidolon/work/eva-learning-cycle12-components-20261111-4c1f2095`.

1. Smoke4DDP :**déjà réussi**.
2. Baseline parent :192qualifications doivent reproduire exactement E4a,puis288testsprimitifs,rapport352,legacy72 et8canaris.96primitifs répétés mêmeslots/mêmeprocessus pour mesurer le bruit ;pas deuxchargements indépendants.
3. Phase1 :102updates depuisparent,aucune génération enDDP. Checkpoints complets20/40/60/80/100/102.
4. Eval102 :parent rechargé puiscandidat. Qualification192 et **toutes** sortiesparent composantes/rapport/legacy/canaris doivent reproduire baseline avant comparaison au candidat.
5. Phase2 **seulement si gardes102 passent** :reprise explicite de la sauvegarde complète102 (poids,opt,scheduler,scaler,RNG2rangs,SHA),puis102updates jusqu204. Checkpoints120/140/160/180/200/204.
6. Eval204 puisrapportCPU. Si garde102échoue,bilan102 etsecondpassage nonlancé. Aucunereprise automatique de runpartiel.

Au derniercontrôle :baseline active,qualificationsparent192 déjà identiques,rapporthistorique confirmé pour176réponses du rang0 ;aucun résultat candidat annoncé.

## Critères préenregistrés

Gardes102et204 :

- Rapport320horaires ≥parent−2 ;jour0 ≥parent−1.
-Acquis≥25/32.
-Aucunpréfixe« Départ »surleshoraires complets ;nouveauxformatsA/B/C≤parent+1.
-Stabilité desjeuxprimitifs parfamille≥parent−1 ;SG≥parent−1.
-Hybrides mesurés avec leparseur canonique partiel existant,dont leslimites restent explicites.

Progrès **final** X1–X3,selon marge debaseline96 :

- Déjà96/96 :maintien exigé,aucungain impossible demandé.
-1à5erreurs disponibles :toutes corrigées,avec mention de plafond,sanssignificativité revendiquée.
-Au-delà :net≥2 ettestexact apparié exploratoirep≤0,05.

Les gainscomposantes ne sontpas exigés dès102 pourcontinuer,lesgardes lesont.
Le rapportcomplet est connu/réutilisé ;untransfert spontané seraitunbonus,pas unobjectifprésumé.
Même si lescritères passent,**aucuneadoption automatique** etaucunE4b-2.

## Intégrité et clôture

Mêmeboot qualifié memtester4GiBmlock,copiesRAM2x,doublesSHA ;cela ne certifie pas128GiB.
Avant chaque chargement :copiesRAM2x,12compteurs nuls chacunes,doublesSHA source/parent,boot/noyau.
GardesGPU/HBM83°C,CPU70°C,ECC/Xid/kernel,progression etsecteur. Verrous globaux.
Sur défautRAM/kernel,pas de retests enboucle du mêmeboot ni de relance aveugle.
Temps,puissances,Wh,troncatures,formats,régressions,canaris etSHA seront publiés aprèsfin.
Touspoids/checkpoints/logs conservés ;testfinalréservé nonlu ;machine laisséeallumée.
