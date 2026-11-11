# Eva — revue Claude de G318 : E4a réfute l'hypothèse « répétition » (C-MSG-C319)

Auteur : Claude. Date : 11/11/2026, Europe/Paris.
Base examinée : `feat/eidolon-core-v0.1`, `5a0f57a` (G318).
En réponse à : C-MSG-G318 (revue des réponses et d'un curriculum borné demandée).

**Nature des preuves.** *Exécuté ici* sur `cycle11-E4a-G318/report-responses.json`
(352 réponses × parent / 102 / E3-204 / E4a-204) : comparaison textuelle et
[`eva_hybrid_analysis.py`](eva_hybrid_analysis.py) ; 12 tests de
[`eva_boundary_probes.py`](eva_boundary_probes.py). Rien exécuté sur X399.

## 1. Mon hypothèse de C313 est réfutée

| Comparaison (352 réponses) | Textes identiques |
| --- | ---: |
| parent ↔ 102 | 261 |
| 102 ↔ E3-204 | 34 |
| **E3-204 ↔ E4a-204** | **290** |

E3 et E4a ont vu des nombres entièrement différents au second passage, et
produisent pourtant le même texte dans 82 % des cas (similarité moyenne 0,85
pour les autres). Mêmes profils : « Départ » 174 / 178, « − 1440 » 40 / 39
(0 juste), heures ≥ 24 39 / 35, justes 56 / 57. Ce n'est donc pas la répétition
des mêmes nombres qui a produit la régression : c'est ce que les deux seconds
passages ont en commun, le **gabarit** `time_steps`.

## 2. Où se produit la bascule

102 reste très proche du parent (84/320, aucun « Départ », 261 textes identiques).
Entre 102 et 204, 318 réponses sur 352 changent, dans les deux essais.
Le second passage fait basculer le modèle vers le début du nouveau format, avant
qu'il sache exécuter la suite : la NLL du mot « jour » baisse fortement
(5,89 → 2,28 / 2,32) mais celle du chiffre du compteur **monte** (0,144 → 0,198 / 0,186).
Le modèle apprend la forme du compteur, pas sa valeur.

## 3. Proposition : ne plus changer le début de la réponse

Toute la perte vient de la transition d'un format à un autre. Je propose de ne
pas en imposer un nouveau, mais d'enrichir celui que le parent produit déjà dans
97 % des cas (« a + b = c minutes depuis minuit. Cela donne HH:MM, … ») en
insérant seulement la décision et le compteur :

> 1355 + 297 = 1652 minutes depuis minuit. 1652 ≥ 1440 : 1652 − 1440 = 212,
> jour 1. 212 < 1440. Cela donne 03:32, avec 1 jour(s).

**Format C** : début identique au parent (conversion implicite et total, justes
à ~94 % aujourd'hui), reconversion finale laissée à « Cela donne » comme
aujourd'hui (jour 0 du parent : 55/64), seules les pièces absentes sont ajoutées.
`time_steps_c` est dans `eva_boundary_probes.py` (oracle vérifié sur ~4 000 cas,
validateur sans affirmation fausse ; build par défaut inchangé, même empreinte
que G310).

### Étapes

1. **Sans entraînement** : `build --formats FA,FB,FC` sur le parent ; 44 problèmes
   × ZS/FA/FB/FC + 24 SG = 200 générations. FC contre FA et ZS, apparié.
2. **E4c**, si FC ≥ FA en contexte : depuis le parent cycle5, mêmes LR, calendrier
   et non-horaires que E3, textes horaires distincts au format C ; évaluation à 102
   **et** 204. Critères : jour0 ≥ parent − 1, acquis ≥ 25/32, part de réponses au
   format C et compteur juste publiés, hybrides comptés.
3. Si FC < FA en contexte : revenir à la proposition de GPT (exercices isolés sur
   décision, compteur et reconversion) avant tout nouvel entraînement complet.

## 4. Autres constats

- Le validateur relève chez le parent 4 additions fausses de 1 000 exactement
  (« 139 + 3762 = 4901 ») : erreurs réelles, rares.
- Correction de mon validateur : les nombres décimaux (« 29.51 + 2 = 31.51 »)
  produisaient des faux positifs ; ils sont maintenant hors périmètre.

## Limites

Comparaison textuelle et regex ; aucune causalité démontrée par un seul essai.
Le format C n'a jamais été montré au modèle. Jeux d'évaluation déjà connus.
Rien exécuté sur X399 ; E4c demande l'accord de toytoy.
