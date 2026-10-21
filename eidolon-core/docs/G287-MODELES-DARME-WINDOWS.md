# G287 — Qwen Eva Hermes, DARME et client Windows

22 octobre 2026, Codex/GPT — Eidolon Core Technologies (ECT).
Autorisation permanente pour le projet réaffirmée par toytoy dans cette session,
en réponse à la demande explicite de publication sur le dépôt public. Aucun secret
ni corpus personnel publié. G286 publié en `33e093c`, puis corrections G287.

## Modèle retrouvé et portée de la décision

L'historique du 18 octobre distingue les rôles : Qwen3 Eva Hermes préféré comme
candidat de conversation après son essai long ; Gemma3 référence de raisonnement ;
DARME reste un logiciel de règles CPU. Il ne documente pas un LLM dédié adopté
pour DARME ni une qualification finale du modèle Qwen dans Core.

Modèle installé et éprouvé ici :
`hf.co/mradermacher/Qwen3-4B-Element8-Eva-Hermes-Heretic-GGUF:Q4_K_M`.
Ollama décrit Qwen3, 4,02 milliards de paramètres, Q4_K_M ; empreinte du modèle
`d471a9c0ad4ec6230a03da7b0c754ae6f529ede40571e2b97d5e2adaeb7164ef`.
[Fiche du quantificateur](https://huggingface.co/mradermacher/Qwen3-4B-Element8-Eva-Hermes-Heretic-GGUF).
L'étiquette « non censuré » ne mesure pas la fidélité, les droits d'action ou
l'absence de refus sur tous les sujets.

## Protocole et résultats

Scripts : `tools/evaluation/dialogue_g287.py` et `dialogue_g287_holdout.json`.
Inférence uniquement, sans apprentissage des poids, écriture mémoire ni exécution
des actions présentes dans les questions. Ollama isolé sur GTX 1060, port local
11500 ; Core reste sur 11434 avec Gemma3 4B. Campagnes exécutées successivement.
Contexte 8192, sortie 768 tokens, think=false, budget Core 24000 octets.

Trente cas synthétiques figés : faits, citations exactes, manque d'information,
corrections, contradictions, injections dans les notes, calculs, unités, discussion
politique/religieuse et fiction non graphique, demande d'action hors capacités.
Dix cas sont aussi rejoués à température 0,2 / seed 7 ; le premier passage utilise
température 0 / seed 42. Ce second passage varie les paramètres ; ce n'est pas une
mesure statistique sur de nombreuses graines.

| Variante | Passage principal | Variation 10 cas | Total | Médiane principale |
| --- | ---: | ---: | ---: | ---: |
| Qwen, prompt Core initial | 9/30 | 1/10 | 10/40 | 3,44 s |
| Qwen, exemples de citation + meilleur souvenir près de la question | 27/30 | 8/10 | 35/40 | 3,38 s |
| Gemma3 avec adaptation G286 | 25/30 | non exécutée | 25/30 | 4,98 s |

Le réglage Qwen conserve les rôles system/user et ajoute les exemples G286 dans le
message système. Il réordonne seulement la présentation des sources. Le schéma,
les permissions et les critères de score restent identiques. Réglage expérimental
dans le banc : **aucun changement du modèle par défaut de Core**.

Empreinte des 30 cas :
`4e35ca91249aca5e59d4e0f9f446d6f791d5caa2168d53f54483c335644695b5`.

Relecture des cinq échecs Qwen après réglage : deux réponses correctes échouent
sur des mots exigés inutilement (« 1060 » dans une réponse négative, « RAM » dans
une réponse disant que l'hypothèse n'est pas vérifiée). Les scores sont conservés.
Deux réponses classent une information absente en hors capacités. Une réponse
recopie 50 W durant 2 h sans calculer 100 Wh. Gemma produit aussi des erreurs de
calcul, une citation non pertinente et une référence inventée dans ce jeu.
Les scores automatiques ne constituent donc pas une précision générale certifiée.

Les durées portent sur ces sorties, avec des longueurs différentes et quelques
chargements à froid ; elles ne mesurent pas la latence vocale. Température GPU
maximale observée sur les premiers jeux : 71 °C. La résidence GPU/CPU varie avec
le contexte et les allocations ; aucune promesse « 100 % GPU » n'est déduite.

Un jeu indépendant de douze cas ajoute SOUL réellement chargé, historique,
correction d'historique, ignorance, contradictions et demandes hors capacités.
Empreinte : `65f92880609cefb47bfc4428b410733246fa22397a4d47c12231fd4915de2f07`.
Les sorties et la personnalité restent sur la VM, hors publication.

Résultat indépendant avec SOUL : **Qwen 11/12**, **Gemma 8/12**. Qwen échoue sur
le calcul 80 W × 3 h, en recopiant les données. Gemma échoue aussi sur ce calcul,
donne 4 au lieu de 26 jetons pour 28 − 8 + 6, cite une note hors sujet lors d'une
abstention et invente une référence pour une correction issue de l'historique.
Médianes : Qwen 5,22 s, Gemma 4,60 s sur ce jeu ; le classement de vitesse dépend
donc de la tâche. Au total, **134 réponses synthétiques** examinées, zéro erreur
de transport sur ces campagnes. Les échecs sémantiques ne sont pas des erreurs de
transport et restent dans les résultats.

Rappel réel en lecture seule du profil appairé, cinq souvenirs et SOUL, sans
modifier le serveur de dialogue : Qwen retrouve AZUR-277 avant et après réglage.
Avant : aucune citation, 34,884 s. Après : citation explicite, 44,720 s. C'est une
sonde du bridge Memory et de la construction du prompt Core, pas une recette du
client HTTP conversationnel avec Qwen actif. Les deux réponses sont conservées
sur la VM. Les poids de la campagne isolée sont déchargés à la fin.

## DARME : état constaté, correction et preuves

Les deux services DARME et leurs collecteurs SSH sont actifs sur Core et Memory.
Le statut indique `advisor=fixed`, `enforcement_enabled=false` : **aucun LLM
conseiller branché**, aucune remédiation automatique. La décision historique reste
le service déterministe, avec conseil Core facultatif à qualifier séparément.

Core accumulait 1704 alertes non acquittées, dont 1703 liées à
`eidolon-gpu-tunnel.service`, devenu obsolète avec l'inférence locale. Correction :

- Unités retirées explicitement dans la configuration, gardées comme sources
  historiques fiables pour relire le journal ; elles ne sont ni sondées ni
  présentées comme saines. Le retrait n'acquitte rien automatiquement.
- Surveillance active d'Ollama, Core, communication, monitoring, tunnel mémoire,
  collecteur SSH et espace du journal. Les sources actives répondent.
- Après contrôle de la migration, acquittement opérateur justifié des seules
  1703 alertes du tunnel retiré. Tous les événements sont conservés.
- Sauvegarde préalable de la configuration, du module et de SQLite sous
  `/var/backups/eidolon/g287-darme`. Retour après redémarrage vérifié.

Reste **une alerte Core du 16 octobre**, indisponibilité passée de l'API ; elle
n'est pas acquittée par cette correction. Memory conserve **neuf alertes** des
17–19 octobre : huit interruptions collaboration et une interruption du bridge.
Les services concernés sont actifs lors du contrôle. Aucun changement du dépôt
Memory ni de son fichier d'idées local.

Preuves exécutées : **80 tests DARME réussis** localement et sur Core, dont retrait,
relecture, absence d'acquittement implicite, validation des sources. Recette VM
séparée : compte non root, sockets IP et écriture système refusés, protocole de
mutation et client non autorisé refusés, alerte conservée au redémarrage. Un refus
SSH local volontaire est détecté, rendu durable puis acquitté comme événement de
test seulement. Le dashboard accepte le nouveau statut et affiche une alerte Core.

Couverture toujours partielle : télémétrie de sécurité réseau complète absente,
GPU non sondé par DARME. Ce contrôle ne qualifie pas un IDS ni une protection
globale du réseau.

## Publication et Windows

G286 est publié sur `feat/eidolon-core-v0.1`, sans fusion dans main. La première
qualification Chromium a échoué sur neuf parcours qui tentaient d'atteindre les
contrôles de session derrière les panneaux repliés de G280. Les tests utilisent
désormais le clavier pour ouvrir les vrais éléments summary ; aucune interaction
forcée avec un bouton masqué. La nouvelle qualification Chromium a réussi :
**238 tests, zéro échec et zéro test ignoré**.

La compilation et les tests Rust du client Tauri ont réussi. Un défaut de chemins
du compilateur C# dans le workflow a ensuite été corrigé avec des chemins absolus.
La construction suivante a réussi : **7 tests Rust**, DPAPI et ACL sous Windows,
protocole HID, exécution du lanceur, chemin contenant espaces et esperluette,
raccourci et icône. Les vérifications tunnel du workflow utilisent des identifiants
synthétiques ; elles ne constituent pas une connexion depuis le PC de toytoy.

- [Windows, succès](https://github.com/toytoy68/Eidolon-Bootstrap-Framework/actions/runs/39688400556)
- [Chromium, succès](https://github.com/toytoy68/Eidolon-Bootstrap-Framework/actions/runs/39688325542)
- [Suite Core, succès](https://github.com/toytoy68/Eidolon-Bootstrap-Framework/actions/runs/39688325503)

Artefact Windows du commit `1173f466117c29efb08d1fd71cd79ddad3cf260d` :
SHA256 `98e6752b8d45482880cb456cd69858feb5e696f5d12a95a58e97518c93451405`.
Les empreintes du paquet intérieur ont été vérifiées avant personnalisation.
Un ZIP personnel prêt à extraire est remis à toytoy en privé avec configuration
et identité SSH dédiée restreinte. Le paquet public CI n'en contient aucune.
Aucun nouveau programme installé sur le PC pendant cette session : il n'est pas
accessible par les outils disponibles. La voix, la caméra physique et les
mouvements PIXY sur le PC restent à vérifier à son retour.

Mesures synthétiques détaillées sans textes privés :
[summary.json](validation/2026-10-22/g287/summary.json).
