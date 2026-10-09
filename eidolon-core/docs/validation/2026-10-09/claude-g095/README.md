# G095 — Recette indépendante et bilan du parcours conversation → mission → résultat

Auteur : Claude. Date : 09/10/2026, Europe/Paris. Fiche : C-TASK-G095.
Commit testé : `27510e8a5dbc0d706f09e878feaba04dc1c8411a` (branche Claude).
Archive : 127 fichiers, `--verify` OK ([construction](bundle-build.json),
[vérification](bundle-verify.json)). Installée dans un environnement neuf
(`--no-index`), recettes lancées avec `env -u PYTHONPATH` depuis `/`.
Conteneur Linux, Python 3.11, Chromium. **Aucun vrai modèle, GPU, VM ni
Windows.**

## Résultats exécutés

- [recipe_g095.py](recipe_g095.py) → [recipe_g095.json](recipe_g095.json) :
  **13/13**, dont la recette G089 d'origine rejouée **sans modification** :
  **18/18**.
- Navigateur depuis le paquet installé et la page de l'archive
  ([browser_installed.json](browser_installed.json)), à 1280 et 360 px :
  parcours complet jusqu'à « Résultat disponible », 0 erreur.

| Section | Vérifié |
| --- | --- |
| A | parcours G089 : connexion de lecture distincte de la commande, conversation, clarification, proposition, accord, mission créée **non lancée**, exécution opérateur, résultat lu, références, annulation demandée/confirmée, modèle indisponible, doublons et coupure |
| B | contexte partiel annoncé (2 tours exclus sur 22) ; reprise : conversation listée |
| C | **stockage occupé** : un écrivain tient la base, d'où un 503 `CONVERSATION_STORE_BUSY` en 2,0 s ; après libération, le **même** tour aboutit |
| D | **interruption** : serveur tué (`SIGKILL`) pendant l'appel à un moteur local qui ne répond pas. Après redémarrage : `pending`, puis `MODEL_ATTEMPT_INTERRUPTED` ; **1 seul** appel moteur au total |
| E | export cohérent, historique, sans clé ; export falsifié détecté |
| F | **artefact rejeté** par le magasin de Codex (`UNSUPPORTED_MEDIA_HEADER`) ; PNG réel importé, puis proposition média liée à sa référence rattachée (jamais un chemin) ; artefact d'un autre propriétaire refusé ; aucun état média ne vaut succès |

Pendant la mise au point, deux erreurs venaient de **ma recette**, pas du code :

- une attente trop courte : l'échéance d'admission vaut le budget de la
  tentative plus 5 s ;
- une lecture de la sortie standard seule, alors que le magasin écrit son refus
  sur la sortie d'erreur.

Les deux sont corrigées dans la recette.

## Bilan : implémenté / testé en simulation / à qualifier sur matériel

| Capacité | Implémenté | Testé en simulation (conteneur) | À qualifier sur matériel |
| --- | --- | --- | --- |
| Lecture seule par défaut, jeton de lecture sans droit d'écriture | oui (`http_api`) | oui, paquet installé et Chromium | VM et Windows (tunnel SSH) |
| Appairage d'un client de conversation (clé `ecc_`, révocation) | oui | oui | VM : remise de la clé au PC |
| Conversation, clarification, hors capacités | oui | oui, modèle **simulé** | **vrai modèle** (Ollama ou llama-server sur la V100) : qualité des réponses à mesurer |
| Contexte borné et annoncé, tours entiers | oui | oui | budget réel du modèle choisi |
| Proposition figée, accord humain, mission créée sans lancement | oui | oui | — |
| Exécution de la mission et lecture du résultat | oui (runtime existant, diagnostic synthétique) | oui | missions réelles : hors MVP |
| Doublons, coupures, réponse perdue, processus tué | oui | oui (avant/après G090) | coupure réseau réelle du tunnel |
| Stockage occupé | oui (503 borné) | oui | — |
| **Stockage plein** | erreur SQLite rendue en 503 `CONVERSATION_UNAVAILABLE` | **non testé** : pas de disque plein reproductible ici | à vérifier sur VM (quota ou partition pleine) |
| Modèle indisponible ou trop lent | oui (`UNAVAILABLE`, budget mural, arrêt) | oui (port fermé, moteur bloqué) | vrai modèle lent ou saturé |
| Annulation demandée / arrêt confirmé | oui (API) | oui | pas d'écran (G100) |
| Export historique et inspection | oui | oui | — |
| Interface : accueil, reprise, clavier, 320 px, zoom | oui | Chromium Linux | **WebView Windows (Tauri)**, échelle 125/150 % |
| Média : proposition figée, référence opaque, propriétaire | **contrat seulement** (G094) | tests contractuels et magasin réel de Codex | raccordement, upload authentifié, worker : non livrés |

## Limites exactes des agents média (reprises de MEDIA-AGENTS.md, Codex)

- Pas d'exécution depuis l'accueil.
- Moteurs ComfyUI et Ollama Vision testés sur API **simulées** ; FFmpeg et
  FFprobe réels.
- États `QUEUED`, `ENGINE_COMPLETED_UNVERIFIED`, `OUTPUTS_IMPORTED_UNVERIFIED`
  et `RESULT_UNVERIFIED` : **jamais une réussite métier**.
- Délai HTTP = délai de socket, pas d'échéance murale globale ; décodages
  FFmpeg limités à 30 s.
- Vidéo : pas de suivi temporel exhaustif, ni d'OCR garanti, ni de
  transcription sonore.
- Arbitrage GPU avec le dialogue, budgets globaux, rétention et validation
  sémantique des sorties : à faire.
- Aucune qualification de la V100, de Windows ou d'un vrai modèle de
  génération.

## Ce qui n'est jamais compté comme objectif atteint

- Une réponse du modèle, même une proposition : la mission n'existe qu'après
  un accord humain.
- Un reçu de soumission : la mission est `NEW`, non lancée.
- Un reçu de file ou un état moteur média.

Seul le statut `SUCCEEDED`, avec son issue `ACHIEVED` lus par l'API de lecture
après exécution par le runtime, est un résultat de mission.
