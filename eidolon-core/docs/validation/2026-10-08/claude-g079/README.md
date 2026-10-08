# G079 — Icône Windows multirésolution : inspection de `icon.ico`

Auteur : Claude. Date : 08/10/2026, Europe/Paris. Base : `7065b85`. Fiche : C-TASK-G079.

## Ce qui existait déjà

`desktop/tauri/icons/icon.ico` a été produit en C100–C101. Il combine le cadre de
`eidolon-icon-reference.png` et le « e » du logo programme. toytoy l'a validé le
08/10 (« Ok on valide ça »). Il est déclaré dans `bundle.icon` de
`tauri.conf.json`, et `cargo build --offline` a réussi sur `590b7e2`. Les
icônes n'ont pas changé depuis.

Le logo manuscrit n'est pas remplacé. Ce lot ne modifie aucune icône : il
**inspecte le fichier `.ico` lui-même**, et non les PNG qui l'ont produit.

## Méthode

- [inspect_ico.py](inspect_ico.py) : bibliothèque standard seulement. Le script
  - lit l'en-tête ICONDIR et chaque entrée ;
  - vérifie les CRC ;
  - décode chaque PNG interne (RGBA 8 bits, les cinq filtres) ;
  - extrait chaque entrée telle que Windows la lit.

  Résultat : [inspect_ico.json](inspect_ico.json).
- [sheet_ico.js](sheet_ico.js) : planche des entrées extraites, à 1:1 et
  agrandies ×6 sans lissage, sur fond clair `#f3f3f3`, sombre `#202020` et
  bleu `#1d4e89`. Résultat : [planche-ico.png](planche-ico.png).
- Indice de lisibilité « contraste e/fond » : rapport WCAG entre les 10 % de
  pixels opaques les plus clairs (le « e ») et la médiane (le fond). C'est un
  indice grossier, pas une norme.

## Structure : conforme

- 170 238 octets, type 1, **9 images** : 16, 20, 24, 32, 40, 48, 64, 128 et 256 px.
- Chaque taille annoncée correspond au PNG interne. Toutes les entrées sont en
  32 bits avec 1 plan.
- Pas de chevauchement ; les données commencent juste après le répertoire.
- Les quatre coins sont transparents (alpha 0) à toutes les tailles.

## Lisibilité aux tailles demandées

| Taille | Usage Windows typique | Version | Contraste e/fond | Constat |
| --- | --- | --- | --- | --- |
| 16 | barre de titre, petites icônes | « e » seul, carré plat | 8,4 | « e » reconnaissable ; trait épais |
| 24 | barre des tâches à 100 % | « e » seul | 8,3 | net |
| **32** | barre des tâches à 125–150 %, Alt+Tab | **complète** (cadre et orbite) | **5,5** | **le plus faible** : « e » flou, halo mêlé au cadre sur fond bleu |
| 48 | bureau, Explorateur « moyennes icônes » | complète | 7,1 | net |
| 256 | Explorateur « très grandes icônes » | complète | 9,2 | fidèle au logo |

## Adaptation proposée : 32 px (décision toytoy)

La variante simplifiée existe déjà (`logo-e-petit-32.png`, même générateur
`logo_e.js`). Elle donne **10,4** contre 5,5. Voir
[comparaison-32.png](comparaison-32.png) et le générateur
[compare_32.js](compare_32.js).

Proposition : utiliser la variante simplifiée jusqu'à 32 px, et la version
complète à partir de 40 px. Ce changement modifierait l'icône validée : je ne
l'applique **pas** sans accord de toytoy.

## Limites

- Aucune recette Windows n'a été exécutée. Rien n'est vu dans l'Explorateur, la
  barre des tâches, Alt+Tab ou à une échelle de 125/150 %. Windows choisit
  lui-même l'entrée la plus proche et peut réduire une taille absente, par
  exemple 30 px, à partir de 32.
- Les entrées PNG sont prises en charge à toutes les tailles depuis Windows
  Vista. Un outil ancien qui n'accepte que le BMP pour les petites tailles n'est
  pas testé.
- `bundle.active` reste `false` : pas d'installateur produit.
