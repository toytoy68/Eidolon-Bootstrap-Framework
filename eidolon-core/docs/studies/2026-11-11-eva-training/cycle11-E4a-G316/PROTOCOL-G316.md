# G316 — E4a stricte autorisée et campagne lancée sur deux V100

Auteur : Codex/GPT. Date :11/11/2026, Europe/Paris.
Base examinée :`195f776707d86bead722b274c17b28966ad59ce1`, branche`feat/eidolon-core-v0.1`.
En réponse à C315 relayé par toytoy et à son autorisation directe : **« moi je le donne d'office mon feu vert »**.
Lot pris : préparation, qualification et essai E4a borné, enregistrement du résultat et transmission à Claude. Aucun E4b, promotion, pilote, arrêt ou redémarrage inclus.
Statut à publication : service actif, smoke4updates réussi ; références neuves en cours, optimisation réelle pas encore commencée au dernier contrôle.

## Variante stricte : un préfixe commun réellement identique

Le premier passage d'E3 est réutilisé **depuis sa sauvegarde complète au pas102**, avec adaptateur, optimiseur, scheduler, scaler et RNG des deux ranks. Pas de départ du checkpoint204.
Le parent d'origine reste cycle5. E4a hérite102updates et exécutera102updates nouvelles : **204cumulées, pas204nouvelles**.
Cette bifurcation évite de présumer qu'un recalcul du premier passage reproduirait exactement les mêmes poids.

Copie isolée sous `inherited/step-102`, doublesSHA vérifiés contre le manifesteG306 :
- adapter_model.safetensors :`ac55b0a89890520590ef8364f40f601f2e383524cbd3c738211b29d326832142` ;
- training-state.pt :`255759a0ae250d316647a236393f05133ae2e989d88f20e113341326b29c24f2`.
504états optimiseur/16515072paramètres, scheduler last_epoch102, deuxRNG, totaux hérités172484nonpadding/60109supervisés/208896padded vérifiés surCPU.
Le smoke vérifie séparément l'entraînementDDP et le roundtrip parent/adapter/optimiseur/scheduler/scaler. La restauration réelle102 est vérifiée dans le worker avant les nouvelles updates.

## Données réellement préparées, pas une simple intention

[Statistiques](dataset-preparation.json) · [169appariements](matched-replacements.json) · [lignage](lineage.json) · [sources d'exclusion](exclusion-sources.json).

Premier passage :878exemples E3 inchangés, dont169horaires. Second passage :seuls ces169horaires sont remplacés ;709nonhoraires, leurs répétitions, l'ordre et les positions restent identiques.
**338problèmes distincts par(départ,durée)**, pas338paraphrases. Même question-type et même fonction `time_steps`, jours/plage de durée/strate préservés ; bornes4320min conservées.
Chaque remplacement a exactement la même longueur tokenisée complète ET le même nombre de tokens supervisés que son exemple d'origine. Les frontières de packs sont donc préservées.
Recherche déterministe seed111116, bornée ; préparation CPU réussie en20,31s, maximum10798tirages pour un appariement.

| Budget | Parpassage | Cumul2passages |
|---|---:|---:|
| Packs512 | 408 | 816 |
| Updates globales4packs | 102 | 204 |
| Tokens supervisés horaires | 28487 | 56974 |
| Tokens supervisés nonhoraires | 31622 | 63244 |
| Tokens supervisés total | 60109 | 120218 |
| Tokens nonpadding | 172484 | 344968 |

Part horaire **47,392237%**, distincte des21,253% du seul ancien groupe68cibles.
Les exclusions portent sur les jeux connus, données et sondes ; le test final réservé n'a pas été lu.
La nouveauté numérique reste un tirage particulier : un gain éventuel ne démontrerait pas que la répétition était l'unique cause de l'ancien échec.

## Entraînement : seul le second passage varie

DeuxV100200W, FP16/NF4doublequant, LoRAr8alpha16, LRmax3e-6 et calendrier102pas répété, optimiseur hérité sans remiseàzéro. Pondération par tokens identique.
Le worker DDP ne contient **aucun appel generate** ni sélection de checkpoint. Sauvegardes complètes auxpas120/140/160/180/200/204, préfixe102 conservé àpart.
Aucune reprise automatique d'un runpartiel, aucun checkpoint écrasé.
Les évaluations se font dans des processus indépendants, après libération du groupe DDP ; le défaut d'attente de G306 n'est pas reconduit.

## Pipeline concret lancé

Service :`eidolon-eva-c11-e4a-4c1f2095.service`.
Dossier :`/srv/eidolon/work/eva-learning-cycle11-diversity-20261111-4c1f2095`.
Sources/données gelées :[launch-manifest.json](launch-manifest.json),33fichiers.

1. **qualification-dual : passée.**4updates, allreduce connu3, égalité réplicasdelta0, roundtrip adapter/parent etoptimiseur/scheduler/scaler passés.
2. **baseline : active.** Parent, préfixe102 et ancien204, deux évaluateurs indépendants. Sélection192+rapport352+8canaris par candidat, nouvelles générations. Parentlot16 répété doitêtreexact ; parent et ancien204 doivent reproduire les réponses sélection/rapportG312 avant l'optimisation, sinon arrêt. Les mêmes jeux restent connus et exploratoires.
3. **run : préparé, automatique seulement si ces contrôles passent.** Restauration complète102 puis102nouvellesupdates. Vérification finale des120218tokens supervisés et344968nonpadding cumulés.
4. **after : préparé.** Nouveau chargementparent doit reproduire les192sorties du baseline16 ; puis candidatE4a204 sélection/rapport/canaris, mêmesGPU/IDs/lots.
5. **finish CPU : préparé.** Rapport, scores/strates, métriques, temps/énergie, réponses complètes et manifesteSHA. Aucun résultat de gain E4a n'est encore annoncé.

Le démarrageType=notify a attenduREADY alors que le script émettaitWATCHDOG. Un signalREADY explicite auPIDprincipal a achevé l'activation ; le service est désormaisactive/running et son watchdog fonctionne. Aucun worker relancé, aucune source gelée modifiée. [Note conservée](startup-readiness-note.json).
Le suivi existant est réactivé pour cette campagne, sans nouvelle tâche ni enchaînementE4b.

## Qualifications et gardes

Même boot qualifié que les diagnostics :4c1f2095. Préflight initial memtester4GiBmlock et doublesSHA conservé ; ce n'est pas une certification des128GiB.
Avant chaque stage : copiesRAM2x avec12compteurs touszéro parpassage, doublesSHA de tous fichiers source modèle, parent2x, étatboot/noyau et sourcesgelées.
GardesGPU/HBM83°C, CPU Tdie70°C, ECC/Xid/noyau, progression, télémétrieShelly ; GTX1060exclue. Verrous globaux apprentissage etorchestration détenus par la campagne.
Les pointes de puissance instantanées peuvent dépasser200W échantillonnés ; le contrôle porte aussi sur la limite réellement configurée.
Les testsCPU vérifient reprisecomplète102, couverturedespacks, pondérationDDP àtokensinégaux et séparationgénération/entraînement.
Aucune nouvelle alerte matérielle ni guard-trip observés au dernier contrôle.

## Mesures nouvelles et limites explicites

[ContrôlesCPU métriques](metric-self-check.json) :320corrigés canoniques vérifiés,6cas ciblés et conservation d'une réponse courte juste mais nonparsable.
Les spans des valeurs calculées sont annotés par rôle :conversion,total,reste,reconversion,jours,HH:MM ; unionnumérique sans doublecompte. Rôlecontrôle distinct pour comparaisons etcompteurs.
NLL totale etparrôle mesurées sur les352cibles forcées, mêmes lots/GPU parID ; elles ne remplacent pas la justesse en génération.

**Limite de tokenisation conservée sans modification des sources actives :** la règle d'inclusion stricte écarte384tokensfrontière du contrôle, précisément les tokens` jour` incluant l'espace initial. La NLLcontrôle couvre les comparaisons et les chiffres descompteurs, mais **ne mesure pas la vraisemblance du motjour lui-même**. Les rôles numériques n'ont aucun chevauchementfrontière exclu. La présence du mot et du compteur en génération est comptée séparément. Ne pas conclure à l'apprentissage lexical dejour à partir de cette NLLpartielle.
[Constat CPU postérieur au gel](control-span-retention-note.json).

Les métriques de génération séparent préfixeDépart, fragments, comparaisons/compteurs, chaîneArequise etcontenu final. Le parseur ne vérifie que les composants canoniques requis et les affirmations détectables :nonparsable ne signifie pas calculfaux, préfixeprésent ne signifie pas chaînejuste.

Gardes de nonrégression :jour0rapport≥parent−1 etacquis≥25/32. Ce sont des gardes, pas une preuve de gain ni une promotion. Publier également parent/E3-204/E4a parstrate, gains/pertes appariés, troncatures et32canaris.
Les résultats etla vraisemblance seront relus àla fin ; aucun choix demodèle automatique.

## Conservation et publication

Tous poids, étatsoptimiseur, logs et jeux restent sur le serveur ; aucun poids ni secret publié ici.
Snapshots de code/données synthétiques et preuves de lancement expurgésUUIDGPU/LAN, avec SHAoriginal/public dans[source-index.json](source-index.json). Les snapshotsPython portent l'extension`.py.txt`.
Les fichiersClaudeC315 sont préservés ; G314 est archivé intact. Aucun changement de pilote, serviceCore ou machine.
Bilan durable et transmission finale à faire après achèvement ; aucune réussite future présumée.
