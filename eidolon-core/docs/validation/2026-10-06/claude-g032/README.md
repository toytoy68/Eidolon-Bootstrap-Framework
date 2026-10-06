# G032 — robustesse de l'extracteur HTML : défauts, corrections, coût

Auteur : Claude, 06/10/2026. Fiche [C-TASK-G032](../../../../collaboration/tasks/C-TASK-G032.md).
Base : `7de3646` (`html_extract.py` `34a665f1…`, identique à G026 `06718be`).
Après : `html_extract.py` `039b778d…`. Toujours **non raccordé** au WebReader ;
aucune classification ajoutée. Contrat mis à jour : [HTML-EXTRACTION.md](../../../HTML-EXTRACTION.md).

```sh
cd eidolon-core
PYTHONPATH=$TREE/src python3 docs/validation/2026-10-06/claude-g032/probes_g032.py
PYTHONPATH=src:. python3 -m unittest tests.test_html_extract -v
```

Sorties :

- [sondes avant](probes-before-7de3646.txt) et [après](probes-after.txt) ;
- [tests après : 24/24](tests-after.txt) ;
- [nouveaux tests sur le code d'avant](new-tests-on-base.txt) : 7 des 8
  nouveaux tests échouent (15 sous-cas). Le 8e fixe un comportement déjà
  correct (segment unique trop long).

## Défauts confirmés et corrigés

| # | Défaut (avant) | Après |
| --- | --- | --- |
| G032-1 (P2) | Un CR seul ou un saut de page entre deux mots était **retiré** : `ne\rpas conclure` → `nepas conclure`, **négation perdue**. Tout fichier CRLF recevait aussi un faux `CONTROL_CHARACTERS_REMOVED`. | CR et FF traités comme espaces HTML ; `ne pas conclure`, sans avertissement |
| G032-2 (P2) | `<p>` et `<li>` non fermés (HTML valide) restaient ouverts : 200 `<p>` → `PARTIAL`/`DEPTH_LIMIT` ; un `<li hidden>` ou `<p hidden>` cachait **tout le texte suivant** (résultat `EMPTY`) | fermetures implicites p/li/dd/dt ; texte visible gardé ; ni faux `DEPTH_LIMIT` ni faux `UNBALANCED_TAGS`/`UNCLOSED_ELEMENTS` |
| G032-3 (P3) | Titre : un `<title>` d'icône SVG s'ajoutait (`Ticône`), deux titres se concaténaient, un `<title>` dans `body` devenait du texte visible | premier titre du document seulement, jamais dans le texte |
| G032-4 (P3) | `limits={}`, `0`, `''`, `[]`, `False` acceptés en silence avec les défauts | `ContractError` |
| G032-5 (P3) | Contrôles C1 bruts (U+0085, U+009B) gardés dans le texte | retirés et signalés |
| G032-6 (P3) | `visibility:collapse` et `content-visibility:hidden` non considérés comme cachés | cachés, documentés |

Points sondés **sans défaut** : contrôle par entité `&#7;` (supprimé par
`html.unescape`), `&#0;` (→ U+FFFD), bidi par entité (signalé), variantes de
`display:none` (casse, espaces, `!important`, position).

Comportement gardé et désormais documenté : un premier segment plus long que
`output_chars` donne `PARTIAL` sans texte.

## Non-régression

- Les 16 tests G026 restent verts.
- Le corpus G007 (9 pages) donne les **mêmes** statuts, empreintes de texte,
  titres et avertissements avant et après.
- La démo `examples.html_extract_demo` s'exécute.

## Coût sur entrée maximale (128 000 octets, défauts)

| Entrée | Avant | Après |
| --- | --- | --- |
| paragraphes | 16 ms, `PARTIAL`/`OUTPUT_LIMIT` | 13 ms, idem |
| imbrication `<div>` × 25 600 | 56 ms, `PARTIAL`/`DEPTH_LIMIT` | 56 ms, idem |
| entités `&amp;` × 25 600 | 8 ms, OK | 10 ms, OK |

Mesure sur une seule machine, sans charge. La fermeture implicite parcourt la
pile (128 au plus) à chaque balise ouvrante : le coût reste borné par la
profondeur.

## Limites résiduelles

- Pas d'arbre HTML complet : tables (`td`/`tr` non fermés), formulaires, et
  `<title>` non fermé suivent `html.parser`, pas le navigateur.
- Pas de CSS : une classe qui cache du texte n'est pas vue.
- Rien n'est classé (challenge, connexion, paywall) : signaux seulement.
