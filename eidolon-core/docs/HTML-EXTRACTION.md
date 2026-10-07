# Extraction HTML autonome — C-TASK-G026

Auteur : Claude, 06/10/2026. Module **candidat** `eidolon_core.html_extract`,
protocole `eidolon-html-extract/1`. Bibliothèque standard seulement
(`html.parser`). **Pas raccordé** à `research.py` ni à `WebReader` : ce
raccordement, et la classification des pages de challenge, de connexion et de
paywall, restent à faire par Codex.

## Mise à jour Codex du 07/10 — C-011

Le statut autonome ci-dessus décrit la livraison G026. Le raccordement
**optionnel** à WebReader/ResearchCoordinator est désormais livré :
[contrat](WEB-READER.md#c-011--extraction-html-optionnelle-07102026).
Le comportement de la fonction extract reste inchangé ; classement d'accès,
provenance/cache et refus du partiel sont pris en charge par le coordinateur.
Aucun accès externe ou mission réseau n'est activé par défaut.

## API

```python
from eidolon_core.html_extract import ExtractLimits, extract
result = extract(raw_bytes, ExtractLimits(input_bytes=128_000, output_chars=64_000, depth=128, segments=2_000))
```

Fonction pure : des octets en entrée, aucun accès réseau ou fichier, aucun
JavaScript, aucune ressource distante, aucun modèle. Un `str`, `None` ou
`bytearray` lève `ContractError`, de même que des limites invalides.

| Champ | Sens |
| --- | --- |
| `status` | `OK`, `EMPTY` (rien de visible), `PARTIAL` (une borne atteinte), `REFUSED` (entrée trop grande ou UTF-8 invalide) |
| `complete` | `true` seulement pour `OK` et `EMPTY`. Un texte `PARTIAL` n'est **jamais** une extraction complète |
| `text` | segments séparés par une ligne vide ; `null` si rien ou refus |
| `source_sha256` | empreinte des **octets reçus**, quelle que soit l'issue |
| `text_sha256` | empreinte du **texte extrait** (UTF-8). Deux sources différentes peuvent avoir le même texte (miroir) |
| `title` | `<title>` normalisé, 300 caractères au plus. Signal, pas contenu |
| `signals` | `password_field`, `forms`, `classification=null` : signaux neutres pour un futur classement challenge/login/paywall |
| `warnings` | codes bornés, voir ci-dessous |
| `trust` / `authorizes_execution` | toujours `untrusted_external_text` / `false` |

## Règles d'extraction (contrat explicite)

- **Ignorés** :
  - le contenu de `script`, `style`, `template`, `noscript`, `svg`, `math`,
    `iframe`, `object`, `embed`, `canvas`, `select`, `datalist`, `head` et
    `title` (un titre n'est jamais du texte visible, même dans `body`) ;
  - les commentaires, déclarations et CDATA ;
  - **tous les attributs**, donc `on*=`, `href` et `src`.
- **Gardés** : le texte des liens, l'ordre des paragraphes, les négations (aucun
  mot n'est filtré), les entités décodées.
- **Mise en forme** : les listes sont préfixées `- ` ou `1. `. `<pre>` garde ses
  retours à la ligne ; ailleurs, les espaces sont fusionnés et `<br>` commence
  un nouveau segment.
- **Caché**, et donc ignoré : l'attribut `hidden`, et un `style` en ligne
  contenant `display:none`, `visibility:hidden`, `visibility:collapse` ou
  `content-visibility:hidden`. Avertissement `HIDDEN_CONTENT_SKIPPED`.
- **Fermetures implicites** (G032), comme le HTML valide : un bloc ferme un
  `<p>` ouvert ; un `<li>` ferme le `<li>` précédent de la même liste ; un
  `<dd>`/`<dt>` ferme le précédent. Ces fermetures et l'absence de balise de
  fin facultative (`p`, `li`, `dd`, `dt`, `tr`, `td`…) ne sont ni comptées en
  profondeur ni signalées comme malformation.
- **Titre** : le premier `<title>` du document seulement ; un `<title>` d'icône
  SVG ou MathML n'en est pas un.
- **Pas caché** : `aria-hidden`, les classes CSS et les feuilles de style. Ce
  module **ne reproduit pas le rendu CSS**.
- **Encodage** : UTF-8 strict, BOM accepté. Sinon `REFUSED`/`INVALID_UTF8`,
  sans remplacement de caractères ni devinette de charset.
- **Caractères** : CR et saut de page sont des espaces HTML, normalisés (CR
  seul ou CRLF → saut de ligne ; saut de page → espace), jamais retirés, pour
  ne pas coller deux mots (« ne\rpas »). Les autres contrôles C0, DEL et les
  contrôles C1 sont retirés (`CONTROL_CHARACTERS_REMOVED`), y compris après
  décodage d'une entité. Les contrôles bidirectionnels sont signalés
  (`BIDI_CONTROLS_PRESENT`), pas retirés.
- **HTML mal formé** : toléré, comme `html.parser`. Les balises non fermées et
  orphelines sont signalées (`UNCLOSED_ELEMENTS`, `UNBALANCED_TAGS`).

## Bornes

| Borne | Défaut | Dépassement |
| --- | --- | --- |
| `input_bytes` | 128 000 | `REFUSED` / `INPUT_TOO_LARGE`, aucun parsing |
| `output_chars` | 64 000 | `PARTIAL` / `OUTPUT_LIMIT` |
| `depth` | 128 éléments ouverts | `PARTIAL` / `DEPTH_LIMIT` |
| `segments` | 2 000 | `PARTIAL` / `SEGMENT_LIMIT` |

Pour `PARTIAL`, seuls des **segments entiers** sont gardés : une phrase n'est
jamais coupée. Le segment en cours au moment d'une borne de profondeur est
abandonné. Un premier segment plus long que `output_chars` donne donc
`PARTIAL` **sans texte** (`text=null`).

`limits` absent vaut les valeurs par défaut ; toute autre valeur qu'un
`ExtractLimits`, y compris `{}`, `0` ou `False`, lève `ContractError`.
Coût mesuré sur une entrée maximale de 128 000 octets : 10 à 60 ms
(imbrication profonde : le plus lent), voir les preuves G032.

## Limites

- Pas de CSS, pas de JavaScript : un texte rendu par script est absent, et un
  texte masqué par une classe CSS est présent.
- Un challenge, une connexion ou un paywall sont extraits comme du texte
  ordinaire. Il faudra les classer **avant** d'utiliser ce texte comme source,
  au raccordement ; `signals` et `title` servent à cela.
- Le texte reste une donnée externe non fiable : il n'est ni vérifié ni
  autorisé.

- Pas d'arbre HTML complet : seules les fermetures implicites ci-dessus sont
  reproduites. Tables, formulaires et contenu de `<title>` non fermé suivent
  encore `html.parser`, pas le navigateur.

[Preuves G026](validation/2026-10-06/claude-g026/README.md) ;
[robustesse G032](validation/2026-10-06/claude-g032/README.md).
