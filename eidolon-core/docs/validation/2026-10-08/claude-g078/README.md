# G078 — Logo officiel dans le client connecté

Auteur : Claude. Date : 08/10/2026, Europe/Paris. Base : `8aeec52` (branche Claude,
`feat/eidolon-core-v0.1` fusionnée, `a813f37` inclus). Fiche : C-TASK-G078.
Données synthétiques (jeu C-009g), boucle locale, Chromium Linux.

## Résultat en une phrase

Le client est prêt et testé. Mais il ne peut **pas** afficher le logo sans une
modification de `http_api.py`, fichier réservé à Codex. La livraison est donc
**une paire de correctifs à appliquer ensemble**. Sur la branche, seul le logo
dérivé est ajouté ; il n'est encore référencé nulle part.

## Pourquoi un correctif serveur est nécessaire

- `http_api.ASSETS` sert trois fichiers fixes : `/`, `/app.js` et `/style.css`.
- Toute autre adresse exige le jeton et répond 401.
- La CSP `img-src 'self'` interdit une image `data:`, et le logo canonique
  (1,4 Mio) dépasse `MAX_ASSET` (512 Kio).

Appliquer le client seul casse un test existant :
`server.test.js` exige une console sans erreur, et Chromium y écrit « 401 » pour
le logo. Je ne pousse donc pas le client seul.

## Fichiers

| Fichier | Rôle |
| --- | --- |
| [make_logo.js](make_logo.js) | dérive `desktop/connected/eidolon-logo.png` du logo officiel |
| `desktop/connected/eidolon-logo.png` (ajouté) | logo dérivé, 412×112 px, 88 718 octets |
| [client-logo.patch](client-logo.patch) | `index.html`, `src/main.js`, `style.css`, `app.js` régénéré |
| [http_api-logo.patch](http_api-logo.patch) | proposition pour Codex : logo servi **s'il est présent** |
| [probe_logo.js](probe_logo.js), [probe_logo.json](probe_logo.json), [captures/](captures/) | client réel, 360/1280, clair/sombre, avec le serveur actuel et le serveur proposé |
| [probe_server_logo.py](probe_server_logo.py), [résultat](probe_server_logo.txt) | cas limites du serveur proposé |

## Logo dérivé, sans redessin

- Source : `assets/branding/eidolon-logo.png`, sha256 `53b394be…`, non modifiée.
- Transformation : recadrage sur le dessin (seuil de luminosité 60, marge de 24 px,
  zone `28,287 1573×428`), puis réduction par moitiés successives jusqu'à
  112 px de haut. Les pixels viennent tous du logo : aucun redessin, aucune
  variante exploratoire.
- Le fond bleu nuit du logo est conservé. Il forme un cartouche arrondi, lisible
  en thème clair comme en thème sombre.
- Hauteur affichée : 56 px (40 px sous 760 px). L'image est en 2× pour les
  écrans HiDPI.

## Client (client-logo.patch)

- `<h1>` contient le logo, avec le texte alternatif « Eidolon Core
  Technologies », et le nom texte « Eidolon Core ».
- Le logo est `hidden` par défaut. `main.js` ne l'affiche qu'une fois l'image
  décodée, puis masque le texte. Sinon, le texte reste : **jamais d'image
  cassée**.
- Le badge « Consultation seule » ne se coupe plus. Il passe sous le logo quand
  la place manque.
- Rien ne change dans les permissions, les statuts, les requêtes `/v1` ou le
  stockage. Aucune requête externe.

## Serveur proposé (http_api-logo.patch, 5 lignes)

- `"/eidolon-logo.png": ("eidolon-logo.png", "image/png")` dans `ASSETS`.
- `OPTIONAL_ASSETS` : si le fichier est absent, le dossier reste valide et le
  serveur répond 404.
- Pourquoi optionnel : `tools/build_beta_bundle.py` (`ALLOW_FILES`) n'inclut pas
  le logo. Une version obligatoire empêcherait de démarrer le serveur depuis
  l'archive bêta (`INVALID_WEB_ROOT`). L'ajout à l'archive relève de G083.
- Les garde-fous existants s'appliquent au logo : lien symbolique refusé,
  `MAX_ASSET`, fichier public comme les trois autres.

## Mesures

Client réel ([probe_logo.json](probe_logo.json)), une capture par cas :

| Serveur | 360×740 | 1280×720 | Débordement | Réponses en erreur |
| --- | --- | --- | --- | --- |
| actuel | texte « Eidolon Core », pas d'image cassée | idem | 0 px | `/eidolon-logo.png 401` |
| proposé | logo 147×40 px, nom « Eidolon Core Technologies » | logo 206×56 px | 0 px | aucune |

Les deux thèmes, clair et sombre, donnent le même résultat, avant et après la
connexion.

Serveur proposé ([probe_server_logo.txt](probe_server_logo.txt)) :

- logo servi en `image/png`, identique octet pour octet au fichier ;
- ancien dossier sans logo : démarrage normal, logo en 404 ;
- lien symbolique, lien cassé ou dossier à la place du logo : `INVALID_WEB_ROOT` ;
- fichier trop gros : `ASSET_TOO_LARGE`.

Suites complètes, sur une copie avec les deux correctifs appliqués :

- client : `node --test "desktop/connected/tests/**/*.test.js"` → **73/73** ;
- Python : `python3 -m unittest discover -s tests -t .` → **971 OK** (7 ignorés).

Les deux correctifs s'appliquent sans conflit sur `8aeec52` et reproduisent
exactement l'arbre testé (`cmp`). `build.js --check` passe.

Sur la branche telle que poussée (logo ajouté, client inchangé), les suites
restent vertes : client 73/73 ; `test_http_api`, `test_beta_check`,
`test_build_beta_bundle`, `test_beta_fixture` et `test_preflight` OK.

## Contraste

- Un logotype n'est pas soumis au seuil de contraste WCAG 1.4.3.
- La signature « Core Technologies » mesure environ 5 px de haut à 40 px
  d'affichage : elle n'est **pas lisible**. Le texte alternatif la donne
  entière.
- Les textes de l'en-tête sont inchangés et restent couverts par
  `a11y.test.js`.

## À décider (Codex)

1. Appliquer `http_api-logo.patch` (ou une variante), puis `client-logo.patch`,
   dans le même commit.
2. Ajouter `desktop/connected/eidolon-logo.png` à `ALLOW_FILES` ou à une liste
   optionnelle de `build_beta_bundle.py`. Je le traiterai avec G083 si Codex
   préfère.
3. Mettre à jour la phrase de `preflight.py`, « Les trois fichiers du
   client », si le logo devient un quatrième fichier.

## Limites

- Chromium Linux seulement : la WebView Windows et l'échelle 125/150 % ne sont pas vues.
- Pas de version vectorielle ni monochrome du logo, conformément à `LOGO.md`
  (lots dédiés).
