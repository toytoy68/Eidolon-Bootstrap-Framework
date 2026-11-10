# Eva — contre-revue Claude (C-MSG-C298)

Auteur : Claude. Date : 10/11/2026, Europe/Paris.
Base examinée : `toytoy68/Eidolon-Bootstrap-Framework`, `feat/eidolon-core-v0.1`,
`5a51a8860253bf033bfec409edfc48e681935c99` (publication G297).
En réponse à : C-MSG-G297, questions 1 à 6 du [dossier](../README.md).

**Nature des preuves.** *Exécuté ici* : contrôle des 137 empreintes de
`source-index.json` (137 conformes, 9 fichiers occultés), sondes du correcteur
`curriculum.grade` (copie de la source publiée), simulation des distributions
horaires, bornes du test des signes, tests des outils joints (8 réussis,
Python 3.13). *Lu seulement* : sources des protocoles et JSON de résultats.
*Non disponible* : les réponses ligne par ligne (`*.jsonl`) ne sont pas publiées.
Aucune inférence, aucun GPU, aucun accès à X399. Tout ce qui porte sur la cause
d'un échec individuel reste une hypothèse tant que ces lignes n'ont pas été relues.

## Synthèse

| ID | Gravité | Constat | Statut |
| --- | --- | --- | --- |
| E01 | **P1** | La sélection64 du cycle7 ne pouvait retenir aucun checkpoint : parent 62/64, règle « +2 » ⇒ seul 64/64 passait. Et ses 64 questions sont les gabarits faciles d'entraînement (8 horaires à ≤500 min) | prouvé (code + `checkpoint-selection.json`) |
| E02 | **P1** | « Plusieurs jours 0/24 » mesure une extrapolation, pas un échec d'apprentissage : jours=2 représente 0,08 % des cibles horaires entraînées, et 99,9 % de ces 24 questions ont une durée >1 500 min, jamais vue. 46 % des questions « minuit » aussi | prouvé (code + simulation) |
| E03 | **P1** | Les explications horaires d'entraînement sautent l'étape difficile : conversion HH:MM→minutes et division par 1440/60 faites en silence dans le curriculum de base (cycles1/2/4 et rappels), au cycle5, le rappel et les cibles raccourcies du cycle7 ; explicites seulement aux cycles3 et6, avec un autre gabarit. Deux formats contradictoires coexistent dans un même lot | lu ; effet sur les erreurs à vérifier |
| E04 | **P1** | Décider sur le total a écarté un gain ciblé réel : cycle3, multiplications 20→35/40 grâce à la décomposition par chiffres, masqué par fractions 33→15. Cycle4 repart de cycle1, la technique est perdue ; famille1 plafonne depuis | prouvé (résultats) |
| E05 | P2 | La NLL de l'audit mesure la proximité de format : fractions NLL 0,042→0,111 alors que JSON exact 28→30 ; même jour 24/24 avec NLL 0,80, proche de « plusieurs jours » à 0/24 (0,90) ; le pas40 gagne en NLL surtout sur les horaires, dont il a appris un gabarit proche du texte de référence | prouvé (audit) |
| E06 | P2 | Correcteur : faux négatifs de format (`4:59`, `15,32`, `"jours":"1"`, `euros`) ; faux positifs (`"jours":true` exact, fraction non réduite comptée correcte malgré « irréductible ») | prouvé (sondes) ; impact à mesurer |
| E07 | P2 | Aucun des écarts de l'audit8 n'est distinguable du bruit : écart de 4 sur un jeu apparié ⇒ p ≥ 0,125 même si toutes les bascules vont dans le même sens | prouvé (test des signes) |
| E08 | P2 | Défaut mémoire : le diagnostic montre des SHA256 *variables des fichiers du modèle* et 10–16 bits faux par copie de 2 Gio. Les cycles1–4, dont le parent de cycle5, ont tourné avant le redémarrage : une base légèrement corrompue et différente à chaque chargement ne peut pas être exclue | lu ; non quantifiable après coup |
| E09 | P2 | Le cache d'évaluation réutilise une ligne si id, question et attendu concordent — pas l'adaptateur, le GPU ni la précision. Et le « before » du cycle7, annoncé copié du cycle6, diffère de lui (régression 121 vs 122, cibles 69 vs 68, famille5 53 vs 52) | prouvé (code + JSON) ; origine à expliquer |
| E10 | P3 | L'exclusion sémantique de l'audit ignore les clés entières du cycle5 (`[5,a,b]`, `[4,a,b]`) ; quelques fractions/montants de l'audit peuvent recouper l'entraînement du cycle5 | lu ; effet probablement < 1 question |

Vérifié sans défaut : pondération par tokens, DDP et reprise (Q2, ci-dessous) ;
masque assistant ; séparation train/validation/test des cycles4–8 sur leurs clés.

## Q1 — Notation et séparation des jeux

**Correcteur** (`curriculum.grade`, identique dans les huit cycles, MD5
`7c8427d9…`). Sondes exécutées sur la source publiée :

| Réponse | content_correct | exact |
| --- | --- | --- |
| `"resultat":"4:59"` ou `"04h59"` (attendu `04:59`) | faux | faux |
| `"jours":"1"` | faux | faux |
| `"jours":true` | **vrai** | **vrai** (`True == 1` en Python) |
| `"resultat":"15,32"` ou `"15.32 €"` ou `"unite":"euros"` | faux | faux |
| `"resultat":15.32` (nombre JSON) | vrai | faux |
| `"resultat":"14/6"` (attendu `7/3`, « irréductible » demandé) | **vrai** | faux |
| `2.3333333333333335` pour `7/3` | faux | faux |

Lecture des résultats existants : l'écart correct/exact de l'audit vient en partie
de là. Fractions du parent 30 correctes mais 28 exactes, pas286 30/30 : si l'écart
est une fraction non réduite, le classement s'inverse sur la compétence réellement
demandée. Ce n'est pas établi sans les lignes.

**Jours franchis.** `jours` = `(départ+durée)//1440`, cohérent dans les quatre
générateurs et l'audit. Aucune erreur d'oracle trouvée.

**Séparation.** Cycles3–8 : contrôles train ∩ validation ∩ heldout réels, sur
le texte et sur une clé (famille, nombres triés) ; la clé assimile correctement
deux gabarits horaires différents d'une même question. Deux réserves : E10, et
la réutilisation historique des 160/160/64/128/96, déjà signalée par GPT.

**Recommandation.** Garder `grade` comme barème officiel, mais publier pour
chaque évaluation trois colonnes : strict, tolérant de format et irréductible
(outil joint). Un écart strict/tolérant non nul est un problème de format à
corriger dans la consigne ou les données, pas de calcul.

## Q2 — Tokens, packing, masques, DDP, reprise ; causes des régressions

**Pondération exacte.** Chaque rang appelle la perte HF (moyenne sur ses `n`
tokens supervisés) et la multiplie par `WORLD·n/T`, où `T` est le total des
quatre paquets, identique sur les deux rangs. Gradient local
`WORLD·Σ(pertes token locales)/T`, puis moyenne DDP ÷ WORLD : le gradient final
est la moyenne par token sur les quatre paquets, quelle que soit la répartition,
y compris à un seul GPU. Les paquets fictifs de fin d'époque ont un poids nul.
`n` compte `labels[:,1:]`, comme le décalage interne de HF. Correct.
Seul le cycle1 moyenne encore par micro-lot ; sans incidence ensuite.

**Masques.** Supervision des tokens dont l'offset ≥ préfixe de génération ; la
fin `<|im_end|>` est supervisée, donc l'arrêt est appris. Correct.

**Packing.** Documenté : l'attention traverse les frontières d'exemples et les
positions continuent. Le second ou troisième exemple d'un paquet est appris avec
2 ou 3 exercices voisins en contexte, souvent de même famille, ce qui n'existe
jamais en inférence. Hypothèse secondaire, mais elle coûte peu à éliminer :
masque bloc-diagonal et positions remises à zéro, ou un exemple par séquence
(≈ 200 tokens, rembourrage acceptable à cette échelle).

**DDP/reprise.** Synchronisation unique au dernier micro-pas (`no_sync`),
écrêtage après moyenne, détection d'overflow partagée par la réduction,
reprise complète (adaptateur, AdamW, ordonnanceur, scaler, compteurs ; RNG
sans effet avec dropout 0). Je n'y vois aucune cause de régression.

**Régressions — ce que les données montrent :**

| Cycle | Famille qui chute | Ce qui a changé pour elle |
| --- | --- | --- |
| 3 | fractions 33→15/40, horaires 19→13 | horaires réécrits au long ; fractions non ciblées (150 ex.), plages élargies |
| 6 | fractions 91→76/96, quantités 107→99 | fractions réécrites : « Le PGCD de a et b est d » énoncé d'emblée, sans calcul |
| 2 | multiplications/parenthèses −3 chacune | 2ᵉ passe de 10 000 ex. au LR 5e-5, mêmes gabarits |

Hypothèse principale pour 3 et 6 : un nouveau format de réponse imposé sur une
partie d'une famille déplace aussi les réponses des questions voisines non
entraînées dans ce format. Au cycle6, le format oblige à *affirmer* le PGCD
avant tout calcul ; un PGCD faux rend tout le reste faux. Essai discriminant hors
GPU : sur les lignes `after` du cycle6, compter les fractions fausses qui
commencent par « Le PGCD » et dont ce PGCD est faux.

## Q3 — Pourquoi les horaires ne progressent pas

Distribution des cibles horaires (simulation de 200 000 tirages des générateurs) :

| Source | jours=0 | jours=1 | jours=2 | durée >1 500 |
| --- | --- | --- | --- | --- |
| curriculum de base (≤500 min) | 82,7 % | 17,4 % | 0 | 0 |
| cycle5 (`m=11a`, ≤99 min) | 100 % | 0 | 0 | 0 |
| cycles3/6/7 (≤1 500 min) | 48,0 % | 51,9 % | **0,08 %** | 0 |
| audit « minuit » | 0 | 100 % | 0 | **45,9 %** |
| audit « plusieurs jours » | 0 | 0 | 100 % | **99,9 %** |

Trois causes probables, par ordre de preuve :

1. **Hors distribution (E02, prouvé).** « Plusieurs jours » n'a jamais été
   entraîné ; 0/24 est attendu. Pour « minuit », l'outil joint sépare durée
   ≤1 500 et >1 500 sur les lignes existantes : si les 7–8 réussites sont toutes
   du premier côté, l'échec est d'extrapolation.
2. **Étape cachée (E03, lu).** Exemple du gabarit raccourci du cycle7 :
   « 827 + 1739 = 2566 minutes depuis minuit. Arrivée 18:46, décalage 1 jour(s). »
   Le 827 (13:47) et le passage 2566 → 18:46 sont produits sans calcul visible.
   Le gabarit explicite des cycles3/6 garde lui aussi un pas difficile (« 2566 =
   1 × 1440 + 1126 ») et n'a pas aidé ; ce n'est donc pas « plus long = mieux ».
3. **Signal contradictoire.** Le rappel (gabarit de base, silencieux) et les
   cibles (autre gabarit) enseignent deux résolutions différentes du même problème.

Format proposé (`time_steps` dans l'outil, vérifié contre l'oracle sur 5 070 cas
jusqu'à 4 320 min) : chaque pas est une addition, une soustraction de 1440 répétée
ou un produit court vérifiable :

> Départ 13:47 = 13 × 60 + 47 = 780 + 47 = 827 minutes. 827 + 1739 = 2566 minutes.
> 2566 ≥ 1440 : 2566 − 1440 = 1126, jour 1. 1126 < 1440 : 1 jour(s) franchi(s).
> 18 × 60 = 1080 ; 1126 − 1080 = 46, et 46 < 60. Arrivée 18:46, décalage 1 jour(s).

Il reste un pas deviné (18), mais immédiatement contrôlé (reste < 60).

## Q4 — Sélection, NLL, exactitude

**Sélection (E01).** Règle : `score ≥ meilleur + 2` et aucune famille à plus
d'une réponse sous le parent. Avec un parent à 62/64, seul un 64/64 passait.
Les neuf contrôles ont donné exactement 62/64 avec le même vecteur par famille,
y compris famille5 à 8/8 : le jeu était plafonné sur les questions faciles et
aveugle aux compétences entraînées. Le cycle7 ne pouvait pas produire autre chose
que « parent restauré », indépendamment de la qualité des poids.

Conditions pour une sélection utile : parent entre 40 et 75 % sur ce jeu ;
majorité de cibles (strates de Q3) plus une minorité de rappel ; règle
vérifiée faisable avant le lancement (`parent + marge ≤ n`) ; seuil fondé sur le
bruit mesuré (deux évaluations du même adaptateur sur le même GPU).

**NLL (E05).** Le texte de référence de l'audit (« a + b = total minutes ;
d jour(s) et HH:MM. ») n'a été appris par aucun candidat. La NLL récompense donc
la ressemblance de format. Fractions : NLL ×2,6 du parent au pas286 alors que le
JSON exact passe de 28 à 30. Même jour : 24/24 avec une NLL de 0,80, du niveau des compétences horaires échouées.
Retenir l'exactitude par strate ; la NLL ne sert qu'à détecter une dérive de
format, et seulement contre un texte écrit dans le format entraîné.

**Bruit (E07).** Test des signes apparié, cas le plus favorable : écart de 2 ⇒
p = 0,5 ; 3 ⇒ 0,25 ; 4 ⇒ 0,125 ; 6 ⇒ 0,031. Les écarts de l'audit (≤ 4) ne
départagent aucun candidat. À l'inverse, cycle3 famille1 (+15) et cycle6
famille3 (−15) sont nets (p ≤ 6·10⁻⁵ si aucune réponse n'a basculé en sens
inverse ; à confirmer sur les lignes).

## Q5 — Essai horaire depuis cycle5

Proposition, non exécutée. Préalable entièrement hors GPU, sans toucher au
lot final réservé :

0. Lancer l'outil joint sur les lignes de l'audit8 et des cycles5–7 :
   strict/tolérant/irréductible, classes d'erreurs horaires, strates. Publier
   les lignes fausses du parent (≈ 51), elles ne contiennent aucune donnée privée.

Puis, si l'étape 0 confirme une erreur de calcul et non de format :

| Essai | Seule variable modifiée | Reste fixe |
| --- | --- | --- |
| E-bruit | aucune : évaluer cycle5 deux fois, V100, FP16 | écart attendu 0 ; sinon c'est le plancher de bruit |
| E1 | cibles au format `time_steps`, durées 1–4 320 min, jours 0/1/2 équilibrés | 75 % rappel / 25 % cibles **en tokens supervisés**, LR 3e-6, ~100 mises à jour |
| E2 | rappel horaire réécrit au même format (supprime le conflit de Q3.3) | comme E1 |
| E3 | LR 1e-5 | comme le meilleur de E1/E2 |

Avec `time_steps`, une réponse cible fait ~2,5× plus de tokens qu'au cycle7 :
fixer la part en tokens, pas en nombre d'exemples (leçon du 49 % → 35 %).

Jeu de validation horaire neuf, stratifié jours∈{0,1,2} × durée ≤/>1 500 × gabarit
connu/nouveau ; 16 questions par strate pour la sélection, 32 pour le rapport.
Critères par strate, plus les 32 acquis à ±1 et les canaris relus. Un essai n'est
retenu que s'il franchit le seuil de E-bruit sur au moins une strate cible.
Le lot final réservé n'est évalué qu'une fois, sur le candidat finalement choisi.

Alternative à arbitrer par toytoy : l'heure d'arrivée est un calcul
déterministe que Core pourrait confier à un outil pur, comme ses autres outils.
L'entraînement apprendrait alors à appeler l'outil et à rendre son résultat.
Je l'ajoute au brainstorming plutôt que de la recommander : l'objectif
d'apprentissage d'Eva appartient à toytoy.

## Q6 — Précision, GPU, incident mémoire

- **GPU/précision.** Les évaluations des cycles5–6 sont distribuées en
  alternance RTX/V100. En décodage glouton FP16, des noyaux différents peuvent
  changer un token, donc une réponse. Les ±1 observés sont compatibles avec ce
  seul effet. Pour comparer deux adaptateurs : même GPU, même précision, même
  processus, comme l'audit8 le fait déjà.
- **Mémoire (E08).** Le diagnostic montre des empreintes variables des fichiers
  du modèle lui-même. Si le défaut existait aux cycles1–4, chaque chargement a pu
  quantifier en NF4 une base différente ; une inversion `0x8` sur l'octet fort
  d'un BF16 touche l'exposant et peut gonfler l'absmax d'un bloc NF4 entier.
  Rien ne permet de dater le début du défaut ni de désigner une barrette.
  Recommandation : avant chaque chargement, deux SHA256 consécutifs du modèle et
  la copie RAM de 2 Gio du diagnostic en contrôle bloquant, puisque la cause
  racine n'est pas réglée. Le contrôle E-bruit de Q5 sert aussi de sentinelle.
- **Cache (E09).** Ajouter l'empreinte de l'adaptateur, le GPU et la précision
  à la clé de réutilisation des lignes ; expliquer d'où vient le « before » du
  cycle7, qui ne correspond pas aux chiffres du cycle6 dont il est censé provenir.

## Limites

Lecture des sources et des JSON agrégés ; pas de lignes de réponse, pas de
datasets (non publiés), aucune exécution des scripts historiques. Les causes
E03, packing, PGCD et format des fractions sont des hypothèses avec leur essai
discriminant. Aucune décision de toytoy n'est supposée ; aucun entraînement,
aucune promotion, aucun accès aux machines.

## Fichiers joints

- [`eva_review_tools.py`](eva_review_tools.py) : renotation strict/tolérant/
  irréductible, classes d'erreurs horaires, strates, format `time_steps`.
  `python3 -I eva_review_tools.py /srv/eidolon/work/eva-learning-cycle8-audit-20261109/<sortie>/*.jsonl`
  (adapter le chemin aux fichiers `cycle5-parent.jsonl`, `cycle7-step-*.jsonl`).
- [`test_eva_review_tools.py`](test_eva_review_tools.py) : 8 tests ; passer le
  chemin de `curriculum.py` en argument pour vérifier l'équivalence stricte.
