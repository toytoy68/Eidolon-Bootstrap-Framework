# C-TASK-G026 — extracteur HTML autonome : preuves

Auteur : Claude, 06/10/2026. Fiche [C-TASK-G026](../../../../collaboration/tasks/C-TASK-G026.md) ·
[contrat](../../../HTML-EXTRACTION.md). Base : `9147f82`.

Fichiers ajoutés :

- `src/eidolon_core/html_extract.py` (SHA-256 `34a665f19649c3fc…`) ;
- `tests/test_html_extract.py` ;
- `examples/html_extract_demo.py` ;
- `docs/HTML-EXTRACTION.md`.

**Aucun raccordement** : `research.py`, `WebReader`, `runtime`, `cli` et les
autres fichiers Web sont inchangés. Bibliothèque standard seulement (aucune
dépendance ajoutée).

```sh
cd eidolon-core
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:. python -m unittest -v tests.test_html_extract
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:. python -m examples.html_extract_demo --format human
```

Python 3.11.15, Linux, sans réseau.

| Contrôle | Résultat |
| --- | --- |
| [tests de l'extracteur](tests.txt) | **16/16** |
| [suite Core complète](core-tests.txt) | **491 tests OK**, 6 intégrations Memory Engine sautées |
| ruff (E9, F, B, S) sur les 3 fichiers | rien |
| [démo JSON](demo.json) · [démo humaine](demo-human.txt) | 9 pages du corpus G007, empreintes vérifiées |

## Ce que couvrent les tests

- **Contenu gardé** : entités, **négation initiale** (« Ne pas »), ordre des
  paragraphes, listes `- ` et `1. `, texte des liens, sans `href` ni `onclick`.
- **Contenu ignoré** : `script`, `style`, `template`, `noscript`, `svg`,
  `iframe`, commentaires, attributs d'événement.
- **Contrat « caché »** : `hidden` et `display:none` / `visibility:hidden` en
  ligne sont ignorés. `aria-hidden` et les classes CSS restent du texte : pas
  de CSS.
- **Texte hostile** : « Ignore les consignes… » et `&lt;script&gt;` restent du
  texte littéral, `authorizes_execution=false`.
- **Unicode** : accents, CJK, emoji, ligature, BOM ; contrôle C0 retiré ;
  contrôles bidirectionnels signalés.
- **Entrées refusées** : `str`, `None`, `bytearray`, limites invalides
  (`ContractError`). Latin-1 donne `REFUSED`/`INVALID_UTF8`, avec l'empreinte
  des octets quand même.
- **Bornes** : une entrée trop grande est refusée avant le parsing. Sortie et
  segments donnent `PARTIAL` avec des segments entiers seulement. La profondeur
  donne `PARTIAL` (y compris 100 000 `<div>`), et la suite n'est pas lue.
- **Sortie vide** (`EMPTY`) : rien, script seul, espaces seuls.
- **HTML incomplet ou mal formé** : `<p>` non fermés, balises orphelines,
  `<script>` non fermé.
- **`<pre>`** : retours à la ligne gardés.
- **Deux empreintes** : même texte depuis deux sources, donc `text_sha256`
  égal et `source_sha256` différent. Le résultat est déterministe.
- **Signal de connexion** : `password_field=true`, `classification=null`.
- **Corpus G007** : toutes les pages HTML extraites, empreinte source exacte.
- **Code du module** : aucun `socket`, `urllib`, `open(`, `subprocess`,
  `eval` ou `exec`.

## Observations utiles au raccordement (Codex)

- **Miroirs** : `docs-v2.html` et `docs-mirror.html` ont des octets différents
  mais un **même `text_sha256`**. Ce serait un moyen de régler F-W07 (G025) :
  ne compter qu'une fois un texte identique.
- **Challenge** : `challenge-200.html` est extrait (« Checking your browser… »)
  avec le titre « Just a moment... ». Le texte ne doit pas devenir une source
  avant classement ; `title` et `signals` sont là pour cela. Il en va de même
  pour `paywall.html` (« Subscribe to read… ») et `soft-404.html`.

## Limites

- Pas de CSS ni de JavaScript.
- Les bornes par défaut ne sont pas mesurées sur de vraies pages.
- Le module n'est qu'un **candidat** : pas d'usage en production avant le
  raccordement et sa revue.
