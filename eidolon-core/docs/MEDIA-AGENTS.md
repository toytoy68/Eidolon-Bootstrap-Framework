# Agents natifs Image et Vidéo — C-047/C-048

Décision toytoy, 08/10/2026 à 20 h 18 Europe/Paris : deux accès directs depuis
l'accueil, chacun pour **créer, modifier et analyser**. À 20 h 21, tout le parcours
chat/conversation/mission est confié à Claude ; Codex possède les agents média.

## Livré et installé avec le paquet

- Deux agents déclarés par `eidolon-media agents` ; aucun téléchargement de modèle.
- Six opérations validées, demandes et travaux locaux distincts des missions Core.
- Accès Image/Vidéo dans le client connecté, sélection de fichier et brouillon
  en mémoire. Aucune lecture du contenu ni requête média depuis cette interface.
- Adaptateur de soumission ComfyUI pour création/modification d'images/vidéos,
  avec workflows API définis par l'opérateur, sans modèle imposé.
- Adaptateur Ollama Vision : image unique ; vidéo via FFmpeg, jusqu'à huit images
  dans les 40 premières secondes, taille maximale 512 × 512, **sans audio**.
- Installation du paquet et essais CLI réels sur des API loopback simulées.
  [Preuves](validation/2026-10-08/codex-media/README.md).

Les moteurs, poids et workflows de production ne sont pas livrés par le paquet.
Le bouton d'exécution de l'accueil reste désactivé : aucune route HTTP d'écriture
ni permission média n'est ajoutée au jeton de lecture. Les agents sont installés
comme modules et commandes locales ; ils ne sont pas encore des outils enregistrés
au catalogue de missions du runtime. Le raccordement de ces deux frontières reste
à livrer conjointement avec la couche conversation/mission de Claude.

## Installation locale explicite

Sur Linux/POSIX, depuis `eidolon-core/`, dans un environnement Python isolé :

```sh
python -m pip install .
eidolon-media agents
```

Sans installation : `PYTHONPATH=src python -m eidolon_core.media_cli agents`.
La commande ajoute les modules au paquet Core et expose `eidolon-media`.
Elle ne configure ni service système, ni modèle, ni moteur graphique, ni GPU.
FFmpeg est nécessaire uniquement pour l'analyse vidéo ; son chemin absolu doit
être fourni explicitement dans la configuration. Aucun installateur Bootstrap
ou gestionnaire de paquets système n'est exécuté par les agents.

## Demande et usage

Fichier de demande pour une image :

```json
{"agent":"image","operation":"create","prompt":"Un atelier de robotique lumineux","format":"landscape"}
```

Pour une analyse : `operation: "analyze"`, `source` désigne un fichier local
choisi explicitement, et aucun format/durée n'est fourni. Pour vidéo create/edit,
`duration_seconds` vaut 5, 10 ou 15. Formats souhaités : square, landscape, portrait.
Une modification exige une source. Texte limité à 4 000 caractères ; PNG/JPEG/WebP
jusqu'à 20 Mio ; MP4/WebM jusqu'à 200 Mio. Le fichier source est lu en une fois dans
ces limites avant appel, empreinte conservée ; aucun écrasement de la source.
La reconnaissance d'en-tête ne constitue pas une validation complète du codec.

```sh
eidolon-media prepare --request demande.json
eidolon-media run --request demande.json --config moteurs.json --job /chemin/prive/nouveau-travail --execute-local
eidolon-media inspect --job /chemin/prive/nouveau-travail
eidolon-media poll --job /chemin/prive/nouveau-travail
```

`prepare` est hors ligne et ne lit pas le contenu de la source. `run` réclame
un dossier **nouveau** dans un parent de confiance existant. Le dossier est privé
(mode 0700), conserve la demande, l'empreinte de source et l'intention avant appel.
Le drapeau `--execute-local` décrit un appel explicite local ; il ne remplace pas
l'identité et les permissions d'une future API multiutilisateur.

`inspect` ne contacte aucun moteur. `poll` consulte une fois l'historique d'un
travail ComfyUI accepté : absence d'entrée ne signifie ni arrêt ni absence d'effet.
Aucun polling automatique, renvoi, annulation globale du moteur ou téléchargement
d'une sortie n'est effectué. Les chemins de sortie rapportés restent des références
non vérifiées, jamais lus automatiquement comme chemins locaux.

## Configuration des moteurs

Clés acceptées uniquement : `ollama_endpoint`, `vision_model`, `comfy_endpoint`,
`workflows`, `staged_sources`, `ffmpeg`. Adresses HTTP à IP loopback littérale avec
port explicite ; aucun proxy, redirection, découverte LAN ou service cloud.

Exemple limité à l'analyse, **à compléter avec un modèle Vision effectivement
installé et testé** :

```json
{"ollama_endpoint":"http://127.0.0.1:11434","vision_model":"MODELE_VISION_LOCAL_A_CHOISIR","ffmpeg":"/usr/bin/ffmpeg"}
```

Génération/modification : `comfy_endpoint` et `workflows` indexé par
`image.create`, `image.edit`, `video.create`, `video.edit`. Chaque entrée comporte :

- `prompt` : workflow exporté au format API, jusqu'à 128 nœuds / 500 ko.
- `bindings` : chaque champ pointe sur `["identifiant_noeud", "nom_entree"]`.
  Champs requis : prompt, width, height ; duration_seconds pour vidéo ; source
  lorsqu'une référence est fournie. Pas de cible dupliquée ou de champ inconnu.

Le prompt utilisateur remplace seulement l'entrée textuelle prévue, sans devenir
un workflow exécutable. Les dimensions souhaitées sont 1024×1024, 1024×576 ou
576×1024 ; un workflow doit les accepter. La durée est une entrée en **secondes**,
à convertir dans le workflow si son modèle travaille en nombre d'images.
L'opérateur choisit et révise les workflows/nœuds ; cet adaptateur n'est pas un
sandbox pour des extensions ComfyUI non fiables.

Pour une source, l'opérateur doit la déposer dans l'espace d'entrée de ComfyUI
et fournir `staged_sources: {"SHA256_DU_FICHIER": "nom_simple.ext"}`. Le client
contrôle l'empreinte du fichier local et le nom déclaré, mais ne peut pas prouver
que le fichier déposé côté ComfyUI n'a pas changé. **Upload et vérification de la
source distante restent à développer** ; ne pas annoncer une chaîne de retouche
vérifiée avec ce seul mécanisme. Aucun chemin du PC n'est envoyé au moteur.

## États, résultats et limites

| État | Signification |
| --- | --- |
| LOCAL_DRAFT | Demande préparée, aucun travail envoyé |
| INTENT | Intention persistée ; après interruption, revue nécessaire |
| QUEUED | ComfyUI a retourné un identifiant, pas un résultat vérifié |
| RESULT_UNVERIFIED | Réponse d'analyse reçue ; observation du modèle, pas fait confirmé |
| REVIEW_REQUIRED | Appel/résultat incertain ; aucune relance automatique |
| ENGINE_COMPLETED_UNVERIFIED | Historique moteur terminé, sorties non contrôlées |

Le modèle Vision est rappelé avec sortie bornée, sans streaming et déchargement
demandé après traitement (`keep_alive: 0`). Réponse tronquée, modèle différent,
JSON invalide ou incomplet refusés. La vidéo ne bénéficie pas encore d'un suivi
temporel exhaustif, d'OCR garanti, de transcription sonore ni d'identification
de personnes. Les descriptions restent non vérifiées et ne déclenchent aucune action.

Les travaux média ont leur propre journal de préfiguration : pas de réutilisation
implicite de `SUCCEEDED`, des reçus d'approbation ou des identités de missions Core.
Le délai HTTP est un timeout socket, pas une échéance murale globale. Les décodages
FFmpeg sont limités à 30 secondes ; les images transmises et réponses sont bornées.
L'arbitrage GPU partagé avec le dialogue, les budgets globaux, la rétention,
l'import vérifié des sorties et le raccordement au worker Core restent à faire.
Aucun résultat ne qualifie la V100, Windows ou un vrai modèle de génération.

## Interface avec le chantier Claude

G084–G089 restent à Claude. Le brouillon navigateur `media-draft/1` contient
uniquement des métadonnées de sélection et n'est **jamais** accepté tel quel par
une API d'exécution. Le serveur devra prendre en charge un upload authentifié,
produire une référence d'artefact validée, présenter la proposition puis lancer
l'agent sous le contrat de mission et ses droits. Ne pas envoyer un chemin fourni
par un navigateur à `run`. Codex conserve les trois modules `media_*.py` et
`desktop/connected/src/media-agents.js` pour ce raccordement.

Sources primaires consultées le 08/10/2026 pour les adaptateurs :
[API ComfyUI](https://docs.comfy.org/development/comfyui-server/comms_routes),
[API generate Ollama](https://docs.ollama.com/api/generate). Le code a été testé
avec des API simulées ; compatibilité d'une installation réelle à qualifier.
