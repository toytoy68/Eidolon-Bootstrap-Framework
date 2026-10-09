# G089 — Recette du parcours conversation → mission → résultat depuis le paquet installé

Auteur : Claude. Date : 09/10/2026, Europe/Paris. Fiche : C-TASK-G089.
Commit testé : `f1b32db27aa9fcb7687f5adf0bcdf87043cb33d1` (branche Claude).
Conteneur Linux, Python 3.11, Chromium. Données synthétiques et modèle de
dialogue **simulé**. **Ce n'est ni la VM, ni Windows, ni un GPU** : aucun vrai
modèle n'est qualifié.

## Paquet

1. `tools/build_beta_bundle.py --commit f1b32db… --output …`, puis `--verify` :
   OK, 115 fichiers, SHA-256 `66bb60be…`
   ([construction](bundle-build.json), [vérification](bundle-verify.json)).
   L'archive contient les 5 modules de conversation, le client avec
   `conversation.js` intégré à `app.js`, et le logo.
2. Extraction, puis environnement neuf
   `python3 -m venv --system-site-packages`, puis
   `pip install --no-deps --no-build-isolation --no-index .`
   (`SETUPTOOLS_USE_DISTUTILS=stdlib` dans ce conteneur Python 3.11).
3. Les recettes tournent avec `env -u PYTHONPATH <venv>/bin/python`. Le module
   chargé est celui de `site-packages`, et la recette refuse de tourner
   autrement.

## Recette API

[recipe_g089.py](recipe_g089.py) → [recipe_g089.json](recipe_g089.json) :
**18/18**.

Serveurs lancés depuis le paquet installé (`python -m eidolon_core.http_api …
--conversations simulated`), page web servie depuis l'archive extraite.

- Ouverture avec la clé appairée, puis réponse, clarification (candidats du
  catalogue), proposition figée, et refus d'un « redémarrage » hors capacités.
- **Commandes interdites au lecteur** : le jeton de lecture est refusé sur
  `submit`, et la clé de conversation ne lit pas `/v1/missions/…` (401).
- **Refus** : une proposition modifiée donne `PROPOSAL_CHANGED`.
- **Coupure** : le client disparaît après l'envoi de la validation. Le reçu est
  retrouvé, et un renvoi rend le même reçu.
- **Doublon** : une autre clé pour la même proposition donne
  `PROPOSAL_ALREADY_SUBMITTED`. Une seule mission existe.
- La validation **ne lance rien** : la mission est `NEW`. L'opérateur l'exécute
  avec le runtime synthétique installé, puis la page lit `SUCCEEDED` /
  `ACHIEVED` par l'API de lecture.
- **Références** : le lien de la conversation porte la mission, l'empreinte de
  la proposition et celle de la requête, vérifiées.
- **Annulation** : la demande est enregistrée (`REQUESTED`, mission toujours
  `NEW`), puis l'arrêt est confirmé par le runtime (`CANCELLED`).
- **Modèle indisponible** : avec une configuration privée qui vise un port
  local fermé, la réponse est `UNAVAILABLE` / `MODEL_UNAVAILABLE`, sans
  proposition.

## Recette navigateur

[browser_installed.json](browser_installed.json) et [captures](captures/).
`probe_g088.js` est lancé avec le Python de l'environnement installé et la page
de l'archive (`CONNECTED_WEB_ROOT`), à 1280×720 et 360×740 :

1. lecture seule ;
2. clé ;
3. réponse ;
4. question en retour ;
5. proposition ;
6. validation, puis « Mission créée — pas encore lancée » ;
7. exécution opérateur, puis « Résultat disponible » ;
8. rechargement, puis retour à la lecture seule.

Aucune erreur de console, aucun débordement, et la clé est absente du DOM. Le
jeu C-009g de la page est créé par le module source du dépôt ; le serveur,
l'appairage et l'exécution utilisent le paquet installé.

## Limites

- Le détail du diagnostic (état observé) n'est pas dans la projection de
  lecture. La page montre le statut, l'issue et les références, pas
  l'observation elle-même.
- Pas d'écran d'annulation, et pas de reprise de conversation après un
  rechargement : G100 et G092.
- `docs/CONVERSATION-API.md` n'est pas dans la liste de l'archive
  (`build_beta_bundle.py`, fichier de Codex). Les trois autres documents de
  conversation y sont.
- Recette bêta mise à jour :
  [BETA-ACCEPTANCE.md](../../../BETA-ACCEPTANCE.md), section G089, avec les
  colonnes VM et Windows **à exécuter** par toytoy.
