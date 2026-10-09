# G088 — Accueil conversationnel et suivi de mission

Auteur : Claude. Date : 09/10/2026, Europe/Paris. Fiche : C-TASK-G088.
Base : branche Claude, `feat/eidolon-core-v0.1` intégrée jusqu'à `39f2a8c`.
Données synthétiques (jeu C-009g), modèle de dialogue **simulé**, boucle locale,
Chromium Linux.

## Ce qui est livré dans le client

Fichiers :

- [src/conversation.js](../../../../desktop/connected/src/conversation.js) ;
- section `#conversation` d'`index.html` ;
- styles ;
- raccordement dans `main.js` ;
- `build.js` (une entrée ajoutée).

`media-agents.js`, les espaces Image et Vidéo, les archives et la
consultation ne changent pas.

- **Sans clé de conversation, la page reste en lecture seule.** Seul le
  formulaire « Clé de conversation » existe. La clé est distincte du jeton de
  lecture, gardée dans une fermeture JavaScript et jamais dans le DOM, le
  stockage ou un cookie. Une clé au mauvais format n'est même pas envoyée.
- **Tours** : affichés avec leur état. Le brouillon n'est pas montré ;
  viennent ensuite « Envoyé », « Reçu », « Envoi incertain » ou « Refusé ».
  Un envoi incertain se renvoie **avec la même clé** : Core rejoue alors le
  tour sans doublon.
- **Réponses** :
  - nature de la réponse (Réponse, Question en retour, Proposition, Hors
    capacités, Indisponible) ;
  - **raison de Core en français**, placée avant le texte du modèle, qui est
    alors étiqueté « Texte du modèle » ;
  - choix possibles tirés du catalogue, et sources.
- **Proposition** :
  - requête dérivée par Core, version, cible, et la mention « rien n'est
    lancé tant que vous ne validez pas » ;
  - un **motif obligatoire** ;
  - la page **recalcule l'empreinte** (JSON canonique et SHA-256, identique à
    `contracts.digest`, vérifié sur l'exemple G084). Si elle diffère de celle
    de Core : refus local `DIGEST_MISMATCH`, et rien n'est envoyé.
  - Une validation incertaine se vérifie par son **reçu**, jamais par une
    nouvelle clé.
- **Suivi** : les étapes viennent du statut réel de la mission, lu par la
  session de consultation existante (bouton « Suivre la mission dans
  Détails »).

  | Statut de la mission | Étape affichée |
  | --- | --- |
  | `NEW` | Mission créée — pas encore lancée |
  | `RUNNING`, `BLOCKED` | En cours |
  | `SUCCEEDED`, `FAILED`, `CANCELLED`, `ABANDONED` | Résultat disponible |
  | `REVIEW_REQUIRED` | Effet inconnu — voir les preuves, ne pas relancer |
  | autre statut | affiché tel que reçu |

  Aucune progression n'est simulée.

## Montage sur le serveur

**Appliqué dans `http_api.py`**, avec l'accord de Codex (C-MSG-G113 : « tu peux
modifier directement http_api.py et ses tests »). Le texte appliqué est
[http_api-conversations.patch](http_api-conversations.patch), avec une limite
portée ensuite à **100 000 octets** : 8 000 caractères dans tout encodage JSON
valide, y compris des paires de substitution échappées à 12 octets par
caractère. Cette limite est définie à un seul endroit et un test le vérifie.

Tests du montage, sur serveur réel :
[test_http_conversations.py](../../../../tests/test_http_conversations.py).

- Désactivé par défaut.
- Le jeton de lecture n'écrit pas, et la clé de conversation ne lit pas.
- Host, Origin et transfert sont contrôlés **avant** la branche conversation.
- Chaque route garde sa limite.

Ce que fait le montage :

- monte `ConversationAPI.handle` sous `/v1/conversations/` sur la **même
  origine**, comme l'exige la CSP `connect-src 'self'` ;
- s'applique **seulement** si l'opérateur lance `--conversations simulated` ou
  `--conversations <configuration de modèle privée>` ;
- utilise pour ces routes une limite de 100 000 octets ; les autres routes et
  `MAX_REQUEST` ne changent pas ;
- laisse `handle()` refuser le jeton de lecture sur ces routes ;
- crée les missions avec le catalogue synthétique (MVP G084).

Sans `--conversations`, le serveur répond 401 à l'ouverture, et la page affiche
« Conversation refusée ou indisponible ».

La recette Chromium a été rejouée sur le code du dépôt **après** l'application
du montage (`probe_g088.js src`) : mêmes résultats aux deux tailles.

## Preuves

- [probe_g088.js](probe_g088.js) → [probe_g088.json](probe_g088.json). Serveur
  réel avec le correctif appliqué sur une copie, à 1280×720 et 360×740 :
  1. lecture seule ;
  2. connexion de lecture, puis ouverture **au clavier** (le focus passe sur
     le message) ;
  3. réponse, puis question en retour (`sim-memory`, `sim-nas`), puis
     proposition ;
  4. validation enregistrée, puis « Mission créée — pas encore lancée » ;
  5. exécution par le runtime synthétique côté opérateur, puis « Résultat
     disponible », avec `SUCCEEDED` visible dans Détails ;
  6. rechargement, puis retour à la lecture seule.

  À chaque étape : 0 px de débordement, 0 erreur de console, aucun bouton de
  commande interdit par les tests, **clé absente du DOM**.
- Captures : [proposition-360.png](captures/proposition-360.png),
  [proposition-1280.png](captures/proposition-1280.png),
  [parcours-360.png](captures/parcours-360.png),
  [parcours-1280.png](captures/parcours-1280.png).
- `tests/conversation.test.js` : 8 tests sur transport scripté (clé, envois
  incertains, empreinte, reçu, réponses tardives ignorées, étapes).
- Suite client complète sur le serveur **non** modifié : **89/89** dans Chromium
  réel. Les tests « no command button » restent vrais en lecture seule.
- Suite Python : **1 166 OK** (6 ignorés). Avec le correctif sur une copie :
  `test_http_api`, `test_beta_check` et `test_preflight` réussis.

## Défauts trouvés et corrigés pendant la recette

- La règle CSS `display: flex` affichait le formulaire de clé alors qu'il était
  `hidden`. Désormais, `[hidden]` est forcé dans la section.
- Une question en retour affichait « Je propose… » (texte du modèle) avec un
  code brut. La raison de Core est maintenant en français et passe d'abord.
- La liste ne défilait pas jusqu'au dernier échange.

## Limites

- **Rechargement** : la clé est oubliée, comme le jeton de lecture. La page
  rouvre une **nouvelle** conversation ; l'ancienne reste sur le serveur.
  Reprendre une conversation relève de G092 (reconnexion et accessibilité du
  chat).
- Le badge « Consultation seule » de l'en-tête ne change pas quand une
  conversation est ouverte.
- Pas d'annulation dans la page : la route `cancel` existe (G087), mais l'écran
  viendra avec G100.
- Chromium Linux seulement : la WebView Windows n'est pas vue.
