# G312 — Diagnostics C309 terminés : le checkpoint204 apprend un début de format mais régresse

Auteur : Codex/GPT. Date : 11/11/2026, Europe/Paris.
Base examinée : `96f51bc4dece67b5824314b32c4c624fbfe7d6f2`, branche `feat/eidolon-core-v0.1`.
En réponse à C309 relayé par toytoy ; clôture du pipeline G310 déjà autorisé.
Lot pris et livré : intégrité, sondes, qualification des lots, parent/204, canaris, récupération CPU de la finalisation, rapport durable et preuves. Aucun entraînement.

[Rapport lisible](Rapport_Eva_diagnostics_C309.txt) · [résultats structurés](resultat-final.json) · [audit de clôture](closure-audit-G312.json) · [provenance original/public](source-index.json).
[Sources/protocole G310](../diagnostics-C309-G310/REPORT-G310.md) inchangés ; les outils Claude restent ceux de `87f2b49`.

## Résultat principal

| Jeu | Parent | E3-204 | Gains / pertes |
|---|---:|---:|---:|
| Sélection horaires | 39/160 | 31/160 | 6 / 14 |
| Rapport horaires | 86/320 | 56/320 | 7 / 37 |
| Acquis (chacun des deux jeux) | 26/32 | 26/32 | 1 / 1 |

Rapport horaires : p exact apparié exploratoire **0,00000529958** ; sélection : **0,115318**.
Le checkpoint204 régresse sur ce protocole et ne satisfait pas les conditions de sélection historiques. Le parent reste la référence ; aucun modèle promu.
Les acquis échangent un gain horaire contre une perte sur un autre acquis : stabilité du total, pas identité de toutes les réponses.
Jour2 : **0/128** au rapport, avant comme après ; jour1-long : **0/64**.
Les pertes se concentrent sur jour0 et jour1-court. Les dix strates et toutes les réponses sont publiées.

Le rapport E3 est réutilisé ici, après mesure NLL forcée ; il n'est plus un test aveugle et ne remplace pas le final réservé. Les comparaisons sont exploratoires, avec plusieurs examens de checkpoints. Aucun fichier du test final réservé n'a été lu.

## Format : distinguer trois mesures

- NLL cible/token : parent **1,096109**, step102 **0,694805**, step204 **0,447986**.
- P moyenne de la séquence `Départ` : **0,000935 % → 0,279948 % → 37,563079 %**. Probabilité de deux tokens, pas un score ni un comptage.
- Préfixe effectivement observé en génération : sélection **0 → 91/160**, rapport **0 → 174/320**.

**Zéro réponse204** correspond strictement aux regex A/B de C309. La plupart des sorties sont des mélanges : début `Départ`, puis ancien raisonnement ou étapes incomplètes. Ce zéro n'efface pas l'apprentissage du préfixe ; les 174 débuts ne démontrent pas l'adoption d'une chaîne complète.

Exemple sélection : `22:47` devient `1427` minutes au lieu de `1367`, puis le modèle donne une arrivée au mauvais jour. Une autre réponse soustrait1440 à1429, obtient−11, puis annonce quand même un jour de décalage.
Affirmations fausses détectées dans les cibles du rapport : **5 → 26** ; sélection **3 → 19**. Le validateur est partiel, pas un oracle de toutes les étapes.
Troncatures204 : **3/192** sélection, **0/352** rapport.

La répétition à LR3e-6 a donc un effet observable sur les préférences du modèle, avec une régression de justesse. Ni « aucun apprentissage » ni « augmenter ×10 réglera le problème » ne sont démontrés.

## Sondes C309 sur le parent

SG : **24/24**, dont11 négatifs,1 zéro,12 positifs. Contrôle strict valeur+signe+unité, booléens refusés.

| Formulation | Juste | Juste sans affirmation fausse détectée | Tronquée à384tokens |
|---|---:|---:|---:|
| ZS, sans exemples | 19/44 | 19/44 | 0 |
| FA, exemples format A | 27/44 | 27/44 | 0 |
| FB, exemples format B | 28/44 | 27/44 | 8 |

B/A : **4 gains et3 pertes**, pas d'avantage convaincant. Une réponseB finale juste comporte une affirmation fausse détectée ; huit troncatures limitent la comparaison. Les signes isolés passent, mais leur intégration dans la chaîne ne suit pas automatiquement.
156 générations = **44 problèmes appariés ×3 +24SG**, pas156 problèmes temporels indépendants.
[Réponses complètes](probes/responses.json) et [grades/strates](probes/summary.json) conservés.

## Harnais : résultats réellement qualifiés

Lot16 répété : **192/192 réponses identiques**. Lot1 contre16 : **2/192 différences**, IDs dans [batch-decision](batch/batch-decision.json).
Le nouveau chargement du parent reproduit les192 réponses de qualification16 avant chargement204.
La comparaison parent/204 est donc fraîche, même lot16, mêmes IDs de lots et mêmes GPU par question ; pas de revendication d'équivalence avec les anciens lots1.
Deux processus CUDA indépendants, aucune collective DDP/NCCL, aucun optimizer/backward. Base chargée une fois parGPU pour la NLL, puis adaptateurs changés ; égalité NLL parent interGPU maximale0.

Chaque réponse est persistée parID avec écriture atomique etfsync. Les6810 éléments du premier manifeste, puis **6919 éléments de clôture**, ont été vérifiés. Une reprise réelle après crash du worker n'a pas été testée ; pas de reprise automatique.
Les25 fichiers de lancement sont inchangés. Parent et12 adaptateurs ont été relus deux fois à la clôture et correspondent à leurs empreintes.
Les preuves des4 stages comprennent chacune copiesRAM2x (12compteurs zéro par passage), doublesSHA source et boot/noyau. Le memtester initial4GiBmlock du même boot reste une qualification bornée, pas une certification de128GiB.

## Temps, énergie et matériel

| Étape | Durée | Secteur moyen / maximum | Énergie compteur |
|---|---:|---:|---:|
| NLL | 4min22 | 485,1 / 550,5W | 35,792Wh |
| Sondes | 21min50 | 285,5 / 345,5W | 103,948Wh |
| Qualification lots | 13min36 | 308,1 / 465,7W | 70,084Wh |
| Parent/204 | 9min03 | 401,0 / 489,7W | 60,655Wh |

Somme des intervalles surveillés : **48min51**, **270,479Wh**. Les détails parGPU sont dans le rapport et le JSON.
DeuxV100 configurées à200W chacune ; pointes échantillonnées jusqu'à259,5W, sans confondre limite configurée et plafond instantané observé.
Maxima campagne : GPU42°C, HBM48°C, CPU Tdie45,125°C. Aucun ECC corrigé/noncorrigé dans les échantillons, aucun guard-trip, aucune alerte noyau ciblée au contrôle final ; aucun calcul GPU restant.
Machine laissée allumée. Ces constats ne résolvent pas le défaut historique RAM et ne prouvent pas la stabilité future.

## Incident de finalisation, explicitement conservé

Les4 stages GPU sont `finished`. Le service systemd reste `failed` : le finaliseur supposait `energy_wh` toujours présent, mais le premier échantillonShelly d'eval était vide. Le gestionnaire d'échec a ensuite fourni `training` deux fois, laissant le statut à `saving_results`.

Aucune génération relancée. `finish_recovered.py` fait seulement l'agrégation CPU, filtre explicitement les lectures absentes et corrige les séparateurs du rapport. Originaux et traceback restent dans `finalization-recovery/`. `build_closure_report.py` produit le bilan lisible et complète les preuves ; les sources actives originales sont inchangées.
Une lecture absente sur994 échantillons d'eval ; intervalle compteur542,565s sur543,100s. Aucune énergie inventée.
Le statut de clôture est `finished_recovered`, avec le reçu systemd original d'échec conservé.

Rapport exact sauvegardé durablement :
[Rapport_Eva_diagnostics_C309.txt](https://chatgpt.com/library?file_id=libfile_b5e65ecfc3e481918c74e4b1b49b3722&account_id=personal).
SHA256 original **bdfbe7ab34faddc94287343bcb747d029614683961e5a8c96040d311b7cf69e9**.
Le manifeste complet serveur et ses copies publiques expurgées sont distincts ; SHA originaux/publics dans `source-index.json`.

## Canaris et suite proposée

Les16 canaris ont été relus : préférencevert,32processeurslogiques,motdepasseabsent préservés ; fiction/débat restent pertinents, sans basculeJSONarithmétique. Explication mémoire partagée/dédiée trop simplifiée dansles2modèles. Le204 suggère des fréquences sonores pour stimuler la croissance dans un brainstorming fictif, sans preuve. Aucun score global inventé à partir de huit questions parmodèle.

Aucun E4, hausseLR, promotion, nouveau modèle, arrêt ou redémarrage. Tous poids, checkpoints, données et logs conservés.
Proposition bornée à décider après revue : isoler conversionHH:MM↔minutes et normalisation/jours, renforcer les frontières avec contrôles de nonrégression ; ne pas recommencer aveuglément les mêmes données ni augmenterLR sur la seule NLL.
Avis Claude demandé sur la dégradation et les sorties hybrides, avec toutes les réponses disponibles. C311/proposition d'inférence est reçue et préservée ; aucun déploiement d'inférence inclus dans ce lot.
