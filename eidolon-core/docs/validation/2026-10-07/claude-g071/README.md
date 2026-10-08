# C-TASK-G071 — Contre-revue de la consultation HTTP des archives (C-030)

Claude, 08/10/2026. Base : `638b392` (contient `archive_page.py` ; `src` figé).
Aucun fichier client G066 ni source de l'API modifié.

```sh
python3 probes_g071.py <src figé>      # code 1 si une assertion échoue → probes.txt (≈ 15 s)
```

Méthode :

- Vrai `ReadServer` sur 127.0.0.1, port éphémère, jeu bêta Codex `research-archives`.
- Sockets brutes là où `http.client` normaliserait les en-têtes.
- `archive_page.read_catalog` est enveloppé **seulement pour compter** les lectures
  réelles du catalogue.
- Toutes les réponses sont collectées puis fouillées pour y chercher des valeurs
  privées.

**Résultat : 51/51 assertions.**

## Confirmé

- **Authentification avant lecture** : sans jeton, mauvais jeton, schéma
  « bearer » en minuscules ou deux en-têtes `Authorization` → 401, et le
  catalogue n'est jamais lu. Un corps de 9 Kio est refusé (413) avant toute
  lecture.
- **Host/Origin** :
  - Host étranger, Host absent, Origin étrangère ou `null` → 403 ;
  - `localhost` sur le même port → 200.
- **Corps strict** : JSON invalide, clé dupliquée, tableau, `limit` 0, 101,
  `true`, `"5"` ou `1.0`, champ inconnu, curseur mal formé → 400 avec un code
  constant, sans lecture du catalogue.
  - `text/plain` → 415.
  - `chunked` → 400.
  - Corps plus court qu'annoncé → 408 en 3 s.
  - GET sur la route ou export brut demandé par son nom → 404.
- **Pagination exhaustive** : avec `limit` 1, 2 ou 100, chaque archive sort une
  fois, dans l'ordre.
- **Curseurs** :
  - curseur d'un autre Store → `RESET_REQUIRED STORE_CHANGED`, sans élément ;
  - empreinte inventée, ou catalogue changé entre deux pages →
    `CATALOG_CHANGED`, sans mélange ;
  - curseur au-delà de la fin → 400.
- **Fichiers** : export en 0644, lien symbolique, FIFO (0,01 s, sans blocage),
  `.partial`, dossier en 0755, export creux de 16 Mio + 1, budget de lecture
  épuisé, dossier supprimé après démarrage (non recréé) → 503
  `ARCHIVES_UNAVAILABLE`, sans aucune page.
- **Capacité** :
  - deux lectures simultanées → la seconde reçoit `ARCHIVES_BUSY` immédiatement,
    la première aboutit ;
  - quatre connexions lentes → `BUSY` immédiat, puis le service reprend.
- **Aucune fuite** : dans les 51 réponses, aucun texte de requête, `guard_id`,
  identifiant de mission ou de recherche, chemin local, champ `runs` ou
  `cleaned_query`. Aucun champ d'autorité n'est vrai. Les en-têtes de sécurité
  (`no-store`, CSP) sont présents.
- **Empreintes** : Store et archives inchangés après toutes les lectures. Les
  essais destructifs de la section 3 sont remis exactement à l'identique.

## Observations (pas des défauts)

- Un catalogue restauré à l'identique rend un ancien curseur de nouveau valide
  (même empreinte). C'est conforme : le curseur désigne une position, pas un
  droit.
- Une empreinte inventée donne `RESET_REQUIRED` plutôt que 400. Rien n'est
  révélé.
- Quatre connexions lentes **sans jeton** occupent tous les exécutants jusqu'au
  délai d'inactivité (3 s) : un processus local peut donc maintenir le service
  occupé en les renouvelant. C'est limité au loopback, et connu du modèle
  « capacité saturée » (`BUSY`), mais à noter avant une exposition par tunnel.

## Limites

- Loopback seulement, en root (les refus de propriétaire ne sont pas observables).
- Pas de tunnel SSH, de Windows ni de navigateur dans ce lot (le client est couvert
  par G066 et G069).
