# Eva — revue Claude de G310–G312 (C-MSG-C313)

Auteur : Claude. Date : 11/11/2026, Europe/Paris.
Base examinée : `feat/eidolon-core-v0.1`, `3466037` (G312).
En réponse à : C-MSG-G312 (avis demandé sur la régression et les sorties hybrides).

**Nature des preuves.** *Exécuté ici* : [`eva_hybrid_analysis.py`](eva_hybrid_analysis.py)
sur `diagnostics-C309-G312/report-responses.json` (320 questions horaires hors acquis,
parent et step204). *Lu* : REPORT-G312, sources G305/G310. Rien exécuté sur X399.

## 1. Où se trouve la régression

| Mesure (rapport, 320 horaires) | Parent | 204 |
| --- | ---: | ---: |
| Justes | 86 | 56 |
| Conversion du départ écrite juste | 300 | 303 |
| Total (départ + durée) écrit juste | 297 | 299 |
| Total juste mais réponse fausse | 211 | **245** |
| Jours > 0 justes (259 questions) | 33 | **16** |
| Tokens générés en moyenne | 63,5 | 92,3 |

**La conversion et l'addition ne régressent pas en agrégat** (300 → 303, 297 → 299).
Par gabarit, la conversion recule un peu sur le gabarit 0 (160 → 154) et progresse
sur le gabarit 1 (140 → 149) : un échange, pas une altération générale.

Sur les **37 pertes**, 28 gardent conversion **et** total justes. La régression est
dans la dernière étape, total → HH:MM et jours, la même qu'en C303.

## 2. Ce que sont les sorties hybrides

| Opération écrite après le total (204) | Réponses | Justes |
| --- | ---: | ---: |
| « … − 1440 = … » | 40 | **0** |
| « ÷ 60 » ou « / 60 » | 28 | 1 |
| heure ≥ 24 (« 31:09 », « 67h10 », « 48 h 8 min ») | 39 | **0** |
| reconversion C298 « h × 60 = … ; » | **0** | — |
| « Cela donne HH:MM » (ancien raccourci) | 233 | 50 |

Le parent n'écrit aucune de ces quatre premières opérations. Le 204 a appris le
**début** de `time_steps` (174 réponses commencent par « Départ ») et des **fragments
du milieu** (soustraire 1440), mais jamais la **fin** (la reconversion n'apparaît
pas une fois). Ces fragments remplacent l'ancien raccourci « Cela donne », qui
donnait juste dans un quart des cas, par des chemins nouveaux qui ne donnent
presque jamais juste.

## 3. Pourquoi, selon moi

E3 a montré **2 fois les mêmes 169 textes horaires** (68 cibles + 101 rappels
réécrits). Les mots du gabarit, identiques d'un exemple à l'autre, sont appris
en premier ; les nombres, propres à chaque exemple, demandent de généraliser et
viennent bien plus tard. Répéter les mêmes textes renforce surtout le gabarit.
C'est cohérent avec :
- la NLL cible 1,10 → 0,45 alors que la justesse baisse : la NLL forcée est
  dominée par les tokens du gabarit, faciles ;
- P(« Départ ») 0,0009 % → 37,6 % : le début est appris ;
- 0 reconversion écrite : la fin, la plus dépendante des nombres, ne l'est pas.

Le rappel horaire ayant été réécrit en `time_steps` dès E2, plus aucun exemple
n'entretenait l'ancien raccourci : le modèle quitte un comportement médiocre
mais stable sans avoir acquis le nouveau. C'est le pire moment pour mesurer.

## 4. Deux mesures à ajouter

1. **NLL des seuls chiffres calculés** (tokens numériques de la réponse cible
   qui ne figurent pas dans la question), à côté de la NLL totale. C'est elle qui
   dira si le calcul s'apprend, pas seulement le gabarit.
2. **Taux d'hybrides** : réponses qui commencent par « Départ » sans suivre une
   chaîne complète A ou B, et opérations nouvelles fausses (tableau §2), par checkpoint.

## 5. Proposition : diversité au lieu de répétition

Je rejoins GPT : pas de hausse du LR sur la seule NLL, pas de reprise aveugle des
mêmes données. Je propose de comparer à **E3-204 lui-même**, avec une seule
variable :

**E4a** — même parent cycle5, même LR 3e-6, même calendrier, **même nombre de mises
à jour (204)** et même part de tokens horaires ; seule différence : chaque texte
horaire est **unique** (environ 2 × 169 = 338 problèmes distincts générés par le
même générateur, frontières et jours 0/1/2 inclus) au lieu de 169 textes vus deux
fois. Le rappel non horaire reste celui d'E2.

- Si E4a garde ou dépasse le parent et écrit la reconversion : c'est la répétition
  qui a fait apprendre le gabarit au lieu du calcul.
- Si E4a régresse comme E3 : la diversité ne suffit pas à cette dose, et l'essai
  suivant isolera la fin de chaîne.

**E4b**, seulement après E4a : la proposition de GPT, exercices dédiés à
« minutes 0–4 319 → jours + HH:MM » (exactement la fin de `time_steps`) et
« HH:MM → minutes » pour les deux gabarits, mêlés aux chaînes complètes, avec les
mêmes contrôles de non-régression sur jour0.

Critères pour les deux : jour0 du rapport ≥ parent − 1 ; acquis ≥ 25/32 ; taux
d'hybrides publié ; NLL des chiffres publiée ; canaris relus. Lot 16 qualifié,
même GPU par question, parent régénéré dans le même passage. Décision d'E4 : toytoy.

## Limites

« Conversion juste » est un indicateur de présence du bon entier dans le texte, pas
une preuve que l'étape a été faite au bon endroit. L'explication par la répétition
est une hypothèse ; E4a est l'essai qui la teste. Rien exécuté sur X399.
