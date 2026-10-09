# G127 — Recette intégrée : accueil conversation → agents Image/Vidéo

Auteur : Claude. Date : 09/10/2026, Europe/Paris. Fiche : C-TASK-G127.

- **Paquet** : archive du commit `33e310e4953800b0aba091d5fa5927b9bfe23230`,
  141 fichiers, `--verify` OK ([construction](bundle-build.json),
  [vérification](bundle-verify.json)).
- **Installation** : environnement neuf (`--no-index`, sans `PYTHONPATH`),
  recette lancée depuis `/`.

## Résultat exécuté

[recipe_g127.py](recipe_g127.py) et [browser_g127.js](browser_g127.js)
→ [recipe_g127.json](recipe_g127.json) : **33/33**.

Pour chacun des **six modes** (image et vidéo × créer, retoucher, analyser),
le parcours est le même :

1. L'humain écrit dans la conversation (vrai serveur, modèle de dialogue
   **simulé**).
2. Core fige une proposition média.
3. L'humain valide avec sa clé appairée : un ticket durable est créé, avec
   **0 appel moteur**.
4. L'opérateur lance explicitement (`eidolon-media-worker run
   --execute-local`) : **1 seul appel**, un second lancement ne rappelle pas
   le moteur.
5. Pour créer et retoucher : `poll`, puis `collect`.
6. Le résultat est lu par la route `media_results` : `MATCHED`, empreinte
   des fichiers vérifiée, texte d'analyse non vérifié, `success_claim:
   false`.

Cas ajoutés :

| Cas | Résultat |
| --- | --- |
| jeton de lecture sur la conversation | refusé (`READ_TOKEN_NOT_ALLOWED`) |
| **coupure** : processus du worker tué pendant que le moteur tient la requête | ticket `ATTEMPTED` ; relancer ne rappelle pas le moteur ; réservation GPU conservée pour revue ; la page dit « Tentative enregistrée — effet à vérifier » |
| **résultat partiel** : deux sorties annoncées, la seconde illisible | collecte `COLLECTION_INCOMPLETE`, 1 sur 2 importé et conservé ; la page dit « Collecte partielle : 1 sur 2 » |
| **Chromium 1280 et 360 px**, après rechargement et reprise | 8 demandes lues, aucun débordement, 0 erreur, aucun bouton ni image dans les résultats, ni chemin privé ni clé dans la page |
| réponse de la route | aucun chemin privé, aucune clé, aucun jeton |

Le faux moteur HTTP reprend la forme de celui de Codex
(`codex-hour-1555/installed_media_worker.py`), avec deux ajouts : une
requête retenue (pour la coupure) et une sortie manquante (pour le
partiel).

## Ce qui est fonctionnel, simulé, ou à faire sur matériel

| Élément | Statut ici |
| --- | --- |
| Dialogue → proposition figée → accord → ticket → lancement explicite → suivi → résultat | **code réel**, paquet installé |
| Dépôt des conversations v6, file Codex, espace C-067, réservation C-061 | **code réel** |
| FFmpeg / FFprobe | **réels** (fixtures 64×64, 2 s) |
| ComfyUI, Ollama Vision | **simulés** (HTTP en boucle locale) |
| Modèle de dialogue | **simulé** (déterministe) |
| GPU V100, vrais workflows, qualité des images | **non testé**, à qualifier sur VM |
| Navigateur | Chromium Linux ; **WebView Windows non testée** |
| Tunnel SSH réel | non testé ici (relais local en G082) |

## Limites

- Le lancement reste une commande opérateur : la page n'a aucun bouton
  « lancer ». C'est voulu.
- G126-R1 reste ouvert : un ticket v1 s'exécute même après une v2
  (décision Codex).
- Une seule coupure (pendant l'appel moteur) et un seul cas partiel ont été
  provoqués.
