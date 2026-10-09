# Session Codex du 09/10/2026, commencée à 12 h 04 Europe/Paris

Dépôt Eidolon-Bootstrap-Framework, branche feat/eidolon-core-v0.1. Aucune VM,
installation système, fusion main ou modification du dépôt Memory Engine.

## Claude C107 et contre-revue

C107/b654a3b intégré par avance rapide ; 54 tests conversation/API/stockage/dialogue
réussis (`claude-targeted.txt`). Les sondes indépendantes G085-R5 et G086-R1 ont
été adaptées à leurs corrections ; leurs versions originales restent conservées
dans le dossier `codex-hour-0953`. Base étrangère inchangée et sources retirées
quand la mémoire est omise du prompt : corrections vérifiées.

`probe_g087_credentials.py` reproduit deux nouveaux constats : magasin de jetons
étranger accepté par une instance active et une instance rouverte ; création
externe vide avant refus d'un parent symbolique. Données synthétiques, aucun jeton
publié. G087-R1/R2 confiés à Claude dans G113 ; ses sources restent inchangées.
Le raccordement G088 dans http_api.py lui est explicitement confié.

## C-061 — Admission média durable

Groupe POSIX privé, une place, configuration explicite, réservation fsyncée avant
appel moteur/décodage/transfert. Persiste après analyse, mise en file, délai dépassé,
coupure et panne de journal. Libération de l'identifiant exact sur déclaration
opérateur, motif borné ; aucune expiration ou déduction depuis le PID. Aucun
contrôle de VRAM, arbitrage du dialogue ou exclusion des clients externes revendiqué.

- `resources-initial.txt` : 11 tests dédiés, dont huit processus simultanés et
  véritable arrêt `os._exit(77)` du processus exécutant un travail.
- `media-tests.txt` : première intégration, 122 tests avec un échec car le champ
  du précontrôle n'était pas encore raccordé ; journal conservé.
- `media-final.txt` : 122 tests réussis après raccordement du précontrôle.
- `python-full.txt` : 1 177 tests réussis, zéro ignoré, Memory activée, 194,696 s.
  Cette passe a chargé la première version du garde ; la finition de fsync du
  parent lors de la création et le refus du parent symbolique sont vérifiés par
  la passe média suivante, et non attribués rétroactivement à cette passe complète.
- `media-final-durable.txt` : 122 tests réussis après la finition du stockage.
- `c061-source-manifest.json` : empreintes des sources finales, test et builder.

Commande complète :

```sh
PYTHONPATH=src:.:/workspace/scratch/16ec975b83e7/memory-reference EIDOLON_MEMORY_INTEGRATION=1 python -m unittest discover -s tests -t . -q
```

La recette installée `installed_media_resources.py` est préparée pour les six
opérations avec HTTP moteur simulé, FFmpeg réel et garde activé. Ses résultats
seront ajoutés après installation du paquet publié ; sa présence seule ne prouve
pas une exécution. Aucune qualification de modèle réel, GPU, VM ou Windows.


## Intégration C110 / G088–G089

C110/8f20041 reçu et intégré avec les deux historiques. G087-R1/R2 vérifiés
indépendamment : refus des magasins étrangers/remplacés et de la cible liée,
identité sous transaction et absence de recréation. Résultat `g087-rechecked.json`.
59 tests Python ciblés (`claude-integrated.txt`), 69 tests Node réussis et 14
Chromium ignorés (`client-node.txt`). `client-build.txt` : bundle client à jour.
Les captures navigateur de Claude ont été examinées ; Chromium n'a pas été lancé ici.

Nouvelle sonde `probe_g090_concurrent_turn.py` : deux tentatives simultanées du
même tour provoquent deux appels modèle simulé, mais un seul tour et une même
réponse stockés. **Aucun doublon de mission prétendu.** Confié à Claude pour
G090 (G115), avec les mentions lecture seule devenues inexactes en mode conversation.
La recette G089 installée indépendante reste à exécuter à cette étape.

## C-062 — Métadonnées techniques, sans validation sémantique

`artifact-probe` rehash les octets, utilise FFprobe explicitement choisi, dans
un processus séparé borné (10 s murales, 5 s CPU, 512 Mio d'espace virtuel,
64 Mio par allocation FFprobe, sortie 16 Kio lue progressivement). Protocoles
file/pipe et démultiplexeur fixé ; références externes MOV désactivées. Copie
privée temporaire, magasin inchangé, aucun moteur appelé. Durées/cadences
absentes non fabriquées. Métadonnées du premier flux visuel seulement, pas de
décodage intégral, d'analyse audio ou de comparaison sémantique à la demande.

- `metadata-initial.txt` : 9 tests dédiés réussis, incluant cinq formats réels
  (PNG, JPEG, WebP, MP4, WebM), arrêt au délai/sortie trop grande, épuisement de
  mémoire limité au processus sondeur et absence de reflet stderr.
- `media-c062-final.txt` : **131 tests média réussis** sur la version finale.
- `python-integrated-final.txt` : **1 194 tests réussis, zéro ignoré**, 198,939 s,
  Memory activée, C-061/C-062 et C110 intégrés ; code final figé pour cette passe.
- `final-source-manifest.json` : empreintes des 72 modules Python, des tests
  nouveaux, du builder et du bundle JavaScript.

FFmpeg et FFprobe locaux 6.1.1, médias générés synthétiquement. Les modèles restent
simulés ; aucune qualification GPU/VM/Windows ou contenu réel. La recette installée
média inclut maintenant six contrôles FFprobe et les réservations des six modes.
