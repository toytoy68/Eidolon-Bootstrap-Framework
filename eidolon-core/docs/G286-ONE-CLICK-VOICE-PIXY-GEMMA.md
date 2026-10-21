# G286 — ouverture, vocal, PIXY et Gemma3

**Suite G287 :** toytoy a réaffirmé son autorisation permanente du projet en
réponse à la demande de publication publique. Le blocage décrit plus bas est
historique et résolu ; G286 est publié en `33e093c`. Voir le
[bilan G287](G287-MODELES-DARME-WINDOWS.md) pour la qualification Windows et DARME.

22 octobre 2026, Codex/GPT. Base GitHub `3a48da4`. Autorisation directe de toytoy :
modifications et déploiement sur ses VM, amélioration du client pendant son absence.
Ajout explicite de la mobilité de sa caméra EMEET PIXY sous Windows.

## Client Windows

Le lanceur natif remplace l'exécution PowerShell : connexion SSH silencieuse par
identité dédiée, vérification de la clé hôte, appairage sans saisie et ouverture du
client. Le transport est supervisé pendant la session ; aucun message de dialogue
n'est renvoyé automatiquement après une coupure. Fermer l'application ferme le
transport et retire la clé temporaire. L'identité importée est protégée avec DPAPI
par compte Windows. Les essais Windows DPAPI/ACL sont définis, pas validés sur Linux.

Le port local reste 8767 : l'API Core vérifie Host/Origin, un port local arbitraire
produisait HTTP 403 lors de la recette. Le lanceur vérifie aussi le PID propriétaire
de l'écoute. Un second lancement ramène la fenêtre existante. Le raccourci reste
créable par `Eidolon.exe --shortcut` ; aucun poste Windows de l'utilisateur n'a été
modifié à distance.

Le paquet personnel doit contenir `connection.json`, `desktop-identity`,
`Eidolon.exe`, `eidolon-consultation.exe` et `Eidolon-camera.exe`.
La configuration et la clé privées restent hors Git/CI. Le paquet générique ne
permet aucune connexion. Aucun paquet complet qualifié Windows n'est revendiqué.

La coquille native appairée autorise micro, caméra et lecture audio sur l'origine
Core verrouillée. Les paramètres de confidentialité Windows restent applicables.
Le vocal démarre automatiquement après ouverture de la conversation. Arrêt manuel,
fermeture de session et annulation conservent leur effet ; pas de double boucle.
Le micro Windows par défaut est préféré, et la PIXY est préférée aux autres caméras
si elle est identifiée ; le choix manuel d'une autre caméra est respecté.
La caméra est préparée puis relâchée ; aucune vidéo n'est enregistrée au lancement.

## Caméra PIXY Windows

Panneau natif compagnon, lancé avec l'application : gauche/droite/haut/bas par pas
bornés à 5 degrés, recentrage, arrêt, suivi automatique et confidentialité caméra.
Détection HID Windows limitée à VID `328f`, PID `00c0`, usage/page `0083`, rapport
sortant de 32 octets. Plusieurs correspondances sont refusées. Aucun driver Linux,
serveur local HTTP, commande shell arbitraire ou flux vidéo dans ce panneau.
Les commandes manuelles désactivent d'abord le suivi ; aucun mouvement en continu.

Écriture USB réussie signifie commande transmise, pas mouvement confirmé. La caméra
physique et son firmware n'ont pas été testés. Le suivi peut exiger un flux vidéo
ouvert par une autre application. Confidentialité caméra ne coupe pas le micro
Eidolon : l'interface le précise. L'arrêt du panneau ne restaure pas le mode
matériel précédent ; aucun état matériel n'est inventé.

Références :
- https://github.com/Romonaga/PixyPilot
- https://github.com/Romonaga/PixyPilot/blob/main/docs/EMEET_PIXY_HID_REFERENCE.md
  (document observé au blob `127210b595ba3849e359e4bf6daabdbc0b92fbf2`).
- https://docs.rs/tauri/2.12.1/tauri/webview/struct.WebviewWindowBuilder.html

## Gemma3 : méthode et résultats pré-déploiement

Aucune modification des poids ni auto-entraînement sur les réponses du modèle.
Adaptation de l'entrée : consignes dans le tour utilisateur initial adapté à Gemma,
exemples synthétiques de citation/abstention, sources les mieux classées près de la
question. Les références, métadonnées et droits ne sont pas modifiés. L'adaptation
est limitée à la famille `gemma3` via Ollama et identifiée dans model_id. Elle reste
incluse dans le budget de contexte existant. Les autres moteurs sont inchangés.

Source : https://ai.google.dev/gemma/docs/core/prompt-structure

Mesures locales sur GTX 1060 6 Go, Gemma3 4B, seed 42, température 0, sortie 512 :

| Variante | Critères réussis sur 10 |
| --- | ---: |
| Configuration initiale, contexte 4096 | 4 |
| Contexte 8192 seul | 4 |
| Tour unique, contexte 8192 | 4 |
| Tour unique + exemples | 8 |
| Tour unique + exemples + meilleur souvenir en dernier | 9 |

Le cas restant est un faux négatif du critère automatique exigeant « 1060 » alors
que la question demandait uniquement si la V100 était installée : la réponse
« non, seulement commandée », correctement citée, est pertinente. Le critère et le
résultat 9/10 sont conservés, sans ajustement après observation.

Six cas supplémentaires avec le vrai adaptateur Core et la structure complète des
souvenirs : six critères automatiques réussis. Relecture : une abstention cite une
note non pertinente. Réserve conservée ; ces petits jeux synthétiques ne prouvent
pas la fiabilité générale du rappel réel. La latence médiane du dernier jeu de
réglage est 4,92 s ; ce n'est pas une mesure de latence vocale ni un benchmark général.
Les deux premières campagnes se sont brièvement chevauchées : ne pas utiliser
leurs durées pour attribuer un gain de performance.

## Vérifications et statut de publication

- 4 tests adaptation Gemma, 45 tests dialogue, 155 tests conversation : réussis.
- 38 tests ciblés JS (communication, veille, démarrage et appairage) : réussis sur Core.
- Programmes lanceur et PIXY compilés avec Mono ; rapports HID/entrées/quoting testés.
- Tests Windows DPAPI/ACL et moteur WebView2 : non exécutés dans Linux.
- Compte dédié côté Core : appairage réel, HTTP 200 via transfert autorisé ; shell et
  transfert vers le port 22 refusés. Configuration sshd vérifiée avant rechargement.
- Publication GitHub refusée par la revue automatique : autorisation explicite de
  publication publique demandée. Aucun contournement ; code conservé sur VM et
  checkout local, CI Windows pas déclenchée. Aucune fusion dans main.

Le journal privé G286 sur Core conserve configurations sauvegardées, évaluations et
preuves API. Le rollback conserve le commit pré-déploiement et la configuration
modèle.

## Déploiement Core et recette réelle — 22/10/2026

Sources du lot déployées dans `/opt/eidolon-core/bootstrap` au commit `5be99bd`,
sur la branche de développement existante, sans publication GitHub. Configuration
active : `gemma3:4b`, contexte 8192, température 0, seed 42, sortie maximale 512.
API, communication, monitoring et tunnel mémoire actifs ; santé API HTTP 200.

Question identique avant/après, dans deux conversations neuves : « Retrouve la
note synthétique de recette G277 : quelle balise contient-elle ? ». Avant : balise
absente, aucune citation, 27,786 s. Après : « D'après la note, la balise est
AZUR-277. [eidolon-v4-00-index-011@1] », 36,534 s. Cinq souvenirs fournis dans
les deux cas, index cohérent, aucune citation inconnue après. Ceci valide ce cas
réel ; V07 reste une réserve de qualité générale, sans promesse de performance.
Un premier contrôle après redémarrage est parti avant l'écoute du serveur et a
reçu une connexion refusée ; le contrôle relancé ci-dessus et la santé HTTP ont
réussi, sans redémarrage automatique du service.

Dernière compilation Mono des deux programmes et tests natifs : réussis ; les
contrôles DPAPI/ACL Windows sont explicitement ignorés sous Linux. Le lancement
du panneau PIXY tolère une erreur Windows de création du processus, pour garder
la conversation disponible. Le nouveau client Tauri n'est pas encore compilé,
le paquet personnel n'est pas livré et aucun déploiement sur le PC n'est déclaré.
