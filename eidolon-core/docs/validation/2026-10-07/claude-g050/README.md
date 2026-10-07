# G050 — contre-revue du nettoyage local des requêtes (C-013)

Auteur : Claude, 07/10/2026. Fiche [C-TASK-G050](../../../../collaboration/tasks/C-TASK-G050.md).

Cibles figées par `git archive` :

- `5194221` (cible de la fiche) ;
- `48a33fc` (tête de `feat` à 09 h 52), avec la garde C-014a.

`query_cleanup.py` est **identique** dans les deux. Sources Codex non
modifiées ; la proposition est jointe à part.

```sh
cd <copie>/eidolon-core && PYTHONPATH=src python3 <dépôt>/eidolon-core/docs/validation/2026-10-07/claude-g050/probes_g050.py <dépôt>/eidolon-core
```

Valeurs fictives seulement (`example.invalid`, plages d'adresses de
documentation, numéros inventés). Fournisseurs, lecteur et DNS simulés ;
aucun réseau. Sorties :

- [48a33fc](probes-48a33fc.txt) ;
- [5194221](probes-5194221.txt) : parties A et B, identiques ; pas de garde à
  cette version ;
- [avec la proposition](probes-proposal.txt).

Rappel de la décision : C-D16 fait retirer IP, IBAN, téléphone, courriel,
chemin local et URL.

## Confirmé

| Point | Résultat |
| --- | --- |
| Corpus G029 rejoué | **27/27** identiques aux sorties Codex (texte nettoyé et reçu) |
| Fournisseurs et replis | deux séries de 3 fournisseurs (panne, 429, vide, résultats) : tous reçoivent **le même texte nettoyé** ; aucune valeur retirée dans le rapport |
| Requête vide après nettoyage | `QUERY_EMPTY_AFTER_CLEANUP` : **0 fournisseur, 0 lecteur, 0 DNS** (courriel seul, IP + téléphone, URL seule) |
| Même cas avec la garde | intention puis `COMPLETED` ; la valeur retirée n'apparaît dans aucun fichier de la garde ; une requête normale passe ensuite |
| Diagnostics | caractère de contrôle, longueur, NFKC trop long : messages constants, sans la valeur |
| Unicode | `＠` pleine chasse, chiffres pleine chasse, U+200B invisible : retirés |

## G050-1 — catégories décidées, formes courantes non retirées (P2)

20 cas sur 36 laissent passer une valeur des catégories de C-D16 :

| Catégorie | Reste dans la requête envoyée |
| --- | --- |
| IP | `198.51.100.7.` en fin de phrase ; `ip:198.51.100.7` ; zéros en tête `198.051.100.007` ; **le port** de `198.51.100.7:25565` (`:25565` reste) |
| IBAN | en minuscules ; avec tirets |
| Téléphone | `0033 6 12 34 56 78` ; `+33 (0)6 12 34 56 78` ; marques combinantes entre chiffres |
| Courriel | `jean @ example.invalid` ; `jean(at)example.invalid` (formes épelées, déjà annoncées) |
| URL | **sans schéma** : `www.example.invalid/reset?token=…`, `example.invalid/reset?token=…` ; schémas `smb://`, `sftp://` |
| Chemin | `/opt/…`, `/srv/…`, `./secrets/…`, `%USERPROFILE%\…`, entre guillemets simples, Windows non cité avec espace (la fin reste) |

Le port compte pour toytoy : ne jamais publier le port Minecraft.

## G050-2 — empreinte de la requête brute dans le rapport (P3)

Le rapport garde `query_sha256 = digest(requête brute)`. Le reçu garde aussi
`original_sha256` (SHA-256 brut). Pour une requête courte, faite surtout
d'une donnée retirée (« rappeler 06 12 34 56 78 »), l'empreinte se retrouve
par essais : il y a moins de 10⁸ numéros mobiles français. La documentation
dit déjà que les empreintes ne protègent pas contre un dictionnaire, mais
**ces deux champs annulent en partie le retrait** si le rapport sort de la
machine.

Proposition : n'exporter que `cleaned_sha256`, ou une empreinte avec un sel
local secret. Codex décide.

## Proposition (non appliquée)

[proposal-query-cleanup.diff](proposal-query-cleanup.diff), qui ne touche
que `query_cleanup.py` :

- **IP** : accepte `:` avant et un point final après ; zéros en tête ; port
  retiré avec l'adresse ;
- **IBAN** : tirets ; minuscules seulement si chaque groupe contient un
  chiffre (« fr12 pour cela vous » reste) ;
- **téléphone** : préfixe `00`, et `(0)` ;
- **URL** : tout schéma (`ssh`, `smb`, `sftp`…) ; sans schéma, `www.…`, ou
  domaine + chemin **avec** `?` ;
- **chemins** : `/opt`, `/srv`, `/data`, `/usr`, `/run`, `%VAR%\`,
  guillemets simples, relatif à deux niveaux (`./a/b`, pas `./configure`).

Mesuré sur une copie :

- 27/27 identiques sur le corpus G029 ;
- **4 écarts sur 36** au lieu de 20 : marques combinantes, deux courriels
  épelés, chemin Windows non cité avec espace ;
- aucun faux positif nouveau sur les 11 cas témoins (`node.js/express`,
  `README.md#install`, `./configure`, ratio, date, numéro de série…) ;
- `test_query_cleanup`, `test_research`, `test_research_guard` : **53 OK**
  ([sortie](proposal-tests.txt)).

Points à trancher :

- un domaine avec un chemin **sans** `?` (`example.invalid/compte/jean`)
  reste envoyé. C'est un choix pour ne pas retirer `node.js/express` ;
- les faux positifs existants restent : version `1.2.3.4`, référence
  produit à 10 chiffres, `dead:beef::1`, forme IBAN.

## Limites

- Ce n'est **pas une anonymisation**, même avec la proposition. Noms,
  adresses postales, courriels épelés et secrets libres restent.
- 36 cas écrits à la main : aucun taux sur une population réelle.
- Titres et extraits renvoyés par les fournisseurs ne sont pas nettoyés
  (déjà documenté).
- Python 3.11, Linux. Ni VM, ni fournisseur réel.
