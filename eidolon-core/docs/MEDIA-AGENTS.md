# Agents natifs Image et Vidéo — C-047 à C-061

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
- Magasin d'artefacts privés avec références opaques, empreintes, quotas et
  publication atomique ; revue explicite des imports interrompus.
- Transfert ComfyUI optionnel, reçu contrôlé puis relecture intégrale de la source
  avant soumission ; collecte explicite des sorties enregistrées dans l'historique.
- Installation du paquet et essais CLI réels sur des API loopback simulées.
  [Première livraison](validation/2026-10-08/codex-media/README.md),
  [recette des six modes et preuves du 09/10](validation/2026-10-09/codex-hour-0710/README.md).

Les moteurs, poids et workflows de production ne sont pas livrés par le paquet.
L'accueil affiche « Exécution : indisponible », sans bouton de commande : aucune route HTTP d'écriture
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
Aucun polling automatique, renvoi ou annulation globale du moteur n'est effectué.
`poll` ne télécharge rien : les sorties rapportées restent des références moteur.
La commande distincte `collect`, décrite plus bas, les importe explicitement.

### Lire un travail après interruption — C-058

```sh
eidolon-media inspect --job /chemin/prive/travail --format human
```

Le rendu humain ECT présente l'opération, l'état et la dernière étape enregistrée,
puis une indication de revue. Un reçu de file durable peut encore être consulté
après une coupure entre son enregistrement et l'état final `QUEUED` : le rapport
suggère alors `poll`, sans l'exécuter. Sans reçu exploitable, vérifier manuellement
le moteur et le journal. La phase `QUEUE_SUBMITTING` ne prouve pas qu'aucune
soumission n'a eu lieu. Un transfert interrompu peut avoir laissé une source
côté moteur ; aucun effacement, nouveau transfert ou renvoi n'est réalisé.

L'inspection lit uniquement `job.json` : aucun octet source, moteur ou sous-processus,
aucune modification du travail. Prompts, chemins, erreurs du moteur et textes
d'analyse ne sont pas affichés en mode humain ; des libellés fixes empêchent leur
interprétation comme commandes de terminal. Les identifiants affichés sont bornés.
Le JSON par défaut reste identique, et contient le journal complet pour la revue.

C-060 : une analyse présente aussi sa **couverture rapportée**. Pour une vidéo,
le bilan indique le nombre d'images enregistré (1 à 8), la limite aux 40 premières
secondes et l'absence d'analyse audio. Cela ne garantit ni la couverture intégrale
d'une vidéo courte, ni la continuité entre les images, ni la durée totale du fichier.
Une image est présentée comme une image unique. Les champs du plan et du résultat
doivent être cohérents : sinon, le bilan signale une couverture absente ou
incohérente sans fabriquer de nombre d'images ou de durée. Ces informations viennent
du journal ; elles ne valident pas les observations du modèle.

Sortie 0 signifie lecture réussie, même si le travail exige une revue ; sortie 2
avec erreur sur stderr si le journal ne peut pas être lu. Ce rendu ne donne ni
permission, ni validation métier, ni état actuel du moteur.

## Contrôle de configuration après installation — C-056

Avant de choisir une source ou de préparer une demande :

```sh
eidolon-media config-check --config moteurs.json --format human
eidolon-media config-check --config moteurs.json --require image.analyze
eidolon-media config-check --config moteurs.json --require image.analyze --require video.analyze
```

Le rapport présente les six opérations, les réglages manquants et une action
pour chaque erreur. Par défaut les six opérations sont requises ; `--require`
limite le périmètre attendu. Une opération non sélectionnée peut être absente,
mais une configuration invalide, même non sélectionnée, reste signalée et fait
échouer le contrôle. Les clés inconnues sont refusées.

| État / code de sortie | Interprétation |
| --- | --- |
| `CONFIGURED_SCOPE` / 0 | Structure de configuration vérifiée pour les opérations demandées |
| `INCOMPLETE` / 2 | Réglages requis encore absents |
| `INVALID` / 2 | Au moins un réglage présent est refusé |

Ces trois rapports sont écrits sur stdout, en JSON par défaut ou en présentation
ECT avec `--format human`. Une erreur empêchant de lire/interpréter la configuration
est écrite sur stderr, dans le format choisi, avec sortie 2 et stdout vide.
Les erreurs du précontrôle ci-dessous respectent aussi le format choisi.

Le contrôle ne contacte aucun moteur, ne lance pas FFmpeg, ne lit aucune image
ou vidéo et ne crée aucun travail. Il vérifie les métadonnées du fichier FFmpeg
configuré et, si un magasin d'artefacts est déclaré, son marqueur d'identité privé.
Il ne parcourt ni inventaire, ni contenus, ni imports interrompus de ce magasin ;
sa capacité n'est pas évaluée. Les alias `staged_sources` sont vérifiés seulement
dans leur forme : leur contenu sera contrôlé pour la demande réelle.

Pour ComfyUI, le graphe API et ses bindings utilisent le même validateur structurel
que l'exécution. Le modèle de graphe brut est limité ici à 500 000 octets ; le
graphe rempli sera de nouveau borné lors du précontrôle et de l'exécution.
Un workflow de création qui déclare un binding `source` nécessitera une source
réelle ; le diagnostic n'en fabrique pas. Aucun prompt, chemin local ou workflow
complet n'est recopié dans le rapport ; noms de modèle et empreintes peuvent y figurer.

`CONFIGURED_SCOPE` ne prouve ni la présence d'un moteur/modèle/nœud, ni sa
compatibilité, ni les ressources matérielles. Aucun téléchargement, installation
système, permission d'exécution, inscription au catalogue runtime ou lancement
depuis l'accueil n'en découle. Continuer avec une demande explicite et `preflight`.

## Précontrôle avant un lancement — C-052

Depuis le paquet installé :

```sh
eidolon-media preflight --request demande.json --config moteurs.json --format human
eidolon-media preflight --request demande.json --config moteurs.json --probe-local --format human
```

Sans `--probe-local`, aucun moteur n'est contacté. La commande contrôle la
demande, la configuration de l'opération choisie et les octets de la source
éventuelle (empreinte, taille, type). Pour une analyse vidéo, elle vérifie que
FFmpeg est un fichier exécutable au chemin absolu configuré, sans le lancer.
Elle n'écrit ni travail, ni artefact et ne télécharge rien. Le JSON est le format
par défaut ; le rendu humain suit le standard ECT.

Avec `--probe-local`, seules les métadonnées du moteur configuré sont demandées :

- ComfyUI : un `GET /object_info/{classe}` par classe distincte, au plus 32.
  Vérification des classes, des entrées requises et des valeurs littérales
  appartenant à une liste de choix (notamment les noms de checkpoints).
  Les connexions entre nœuds et l'entrée source sont laissées au moteur ; une
  source à uploader n'existe pas encore dans sa liste de fichiers.
- Ollama : un `POST /api/show` contenant seulement le nom de modèle et
  `verbose: false`. La capacité `vision` doit être annoncée. Un modèle déclaré
  distant ou un nœud ComfyUI déclaré `api_node` est refusé.

Aucun prompt, octet source, upload ou appel d'inférence n'est envoyé par ces
sondes. Les noms des classes et du modèle sont transmis. Les métadonnées des
extensions ComfyUI sont produites par le moteur de confiance : cette lecture
n'isole pas les effets internes d'un nœud personnalisé. Le délai de 5 secondes
est un timeout socket par sonde, **pas une échéance murale globale**. La réponse
JSON reste bornée à 1 Mio ; aucun proxy, redirection ou renvoi automatique.

| État / sortie | Interprétation |
| --- | --- |
| `LOCAL_INPUTS_VALID` / 0 | Contrôles locaux passés ; moteur non contacté |
| `PREREQUISITES_OBSERVED` / 0 | Métadonnées attendues observées à cet instant |
| erreur sur stderr / 2 | Demande, configuration, source ou cible de sonde refusée avant les sondes |
| `PROBE_INCOMPLETE` / 3 | Sonde arrêtée au premier refus/échec ; observations précédentes conservées |

La sonde ne valide ni graphe complet, compatibilité des types, qualité de modèle,
GPU, mémoire disponible, codec ou résultat. Elle ne prouve pas qu'un moteur ou
ses extensions sont dépourvus d'appels distants. Elle n'autorise aucune exécution :
`execution_authorized`, `plan_reusable`, `hardware_qualified` et
`semantic_content_verified` restent `false`. Les empreintes lient le diagnostic
à la demande et à la configuration ; elles ne sont pas une permission. `run`
revérifie les entrées et crée son propre plan, dont un nouveau nom d'upload.

[Recette du paquet installé et limites](validation/2026-10-09/codex-hour-0833/README.md).

## Configuration des moteurs

Clés acceptées uniquement : `ollama_endpoint`, `vision_model`, `comfy_endpoint`,
`workflows`, `staged_sources`, `ffmpeg`, `artifact_store`, `source_transfer`.
Adresses HTTP à IP loopback littérale avec
port explicite ; aucun proxy, redirection, découverte LAN ou service cloud.

Exemple limité à l'analyse, **à compléter avec un modèle Vision effectivement
installé et testé** :

```json
{"ollama_endpoint":"http://127.0.0.1:11434","vision_model":"MODELE_VISION_LOCAL_A_CHOISIR","ffmpeg":"/usr/bin/ffmpeg"}
```

Génération/modification : `comfy_endpoint` et `workflows` indexé par
`image.create`, `image.edit`, `video.create`, `video.edit`. Chaque entrée comporte :

- `prompt` : workflow exporté au format API, jusqu'à 128 nœuds / 500 ko.
  Chaque `class_type` contient 1 à 160 caractères imprimables.
- `bindings` : chaque champ pointe sur `["identifiant_noeud", "nom_entree"]`.
  Champs requis : prompt, width, height ; duration_seconds pour vidéo ; source
  lorsqu'une référence est fournie. Pas de cible dupliquée ou de champ inconnu.

Le prompt utilisateur remplace seulement l'entrée textuelle prévue, sans devenir
un workflow exécutable. Les dimensions souhaitées sont 1024×1024, 1024×576 ou
576×1024 ; un workflow doit les accepter. La durée est une entrée en **secondes**,
à convertir dans le workflow si son modèle travaille en nombre d'images.
L'opérateur choisit et révise les workflows/nœuds ; cet adaptateur n'est pas un
sandbox pour des extensions ComfyUI non fiables.

Pour une source, deux modes sont disponibles :

- `source_transfer: "verify-staged"` (défaut) : l'opérateur la dépose dans l'entrée
  ComfyUI et fournit `staged_sources: {"SHA256_DU_FICHIER": "nom_simple.ext"}`.
  Le client relit `/view` avec `type=input` et compare taille et empreinte.
- `source_transfer: "upload-verified"` : un nom aléatoire sans nom personnel est
  réservé dans le plan. Un seul POST multipart `/upload/image`, `overwrite=false`,
  puis reçu strict et relecture `/view`. Le même transport de fichier est utilisé
  pour PNG/JPEG/WebP et MP4/WebM ; cela ne garantit pas la présence d'un nœud vidéo
  compatible dans le workflow réel.

Le workflow n'est soumis qu'après comparaison des octets. Perte de réponse,
renommage inattendu ou contenu différent : arrêt et revue, sans renvoi. Un upload
peut déjà avoir eu lieu ; aucun effacement automatique côté moteur. L'empreinte
prouve la source relue à cet instant : ComfyUI reste responsable de la conserver
jusqu'à son utilisation. Aucun chemin du PC n'est envoyé au moteur.

## Artefacts privés et références pour G094

Le magasin est local à l'opérateur POSIX ; ce n'est pas un service multiutilisateur.
Son parent doit être de confiance. Création dans un dossier **nouveau**, quotas
par défaut de 128 artefacts / 1 Gio, maximums de 1 024 / 4 Gio :

```sh
eidolon-media artifact-init --root /chemin/prive/medias
eidolon-media artifact-import --root /chemin/prive/medias --store-id mas-IDENTIFIANT --source photo.png
eidolon-media artifacts --root /chemin/prive/medias --store-id mas-IDENTIFIANT
eidolon-media artifact-inspect --root /chemin/prive/medias --store-id mas-IDENTIFIANT --reference reference.json
```

Remplacer `mas-IDENTIFIANT` par le `store_id` retourné. L'import retourne un
manifeste avec une référence de forme exacte, ici avec des valeurs illustratives :

```json
{"schema":"media-artifact-ref/1","store_id":"mas-00000000000000000000000000000000","artifact_id":"ma-00000000000000000000000000000000","sha256":"0000000000000000000000000000000000000000000000000000000000000000"}
```

Les identifiants réels portent `mas-` / `ma-` suivis de 32 chiffres hexadécimaux,
l'empreinte de 64. Conserver la référence retournée, sans reconstruire ces valeurs
ni ajouter un chemin. `artifact-inspect --reference` accepte aussi le manifeste
complet d'import. Une demande `edit` ou `analyze` peut porter `artifact: {…référence…}`
à la place de `source` ; les deux sont mutuellement exclusifs. La configuration associe :

```json
{"artifact_store":{"root":"/chemin/prive/medias","store_id":"mas-IDENTIFIANT_RETOURNE"}}
```

Le contenu importé est indépendant du fichier d'origine. Chaque lecture exécutante
recontrôle son empreinte, taille et type ; une modification bloque l'appel moteur.
L'inventaire contrôle les manifestes et tailles, **sans recalculer toutes les
empreintes** (`content_hashes_checked: false`). Fichiers internes privés, liens
symboliques/durs refusés, écritures coopératives sérialisées par verrou. Les
processus sous le même compte restent une frontière de confiance, pas un adversaire
isolé. La reconnaissance d'en-tête n'est ni un antivirus ni un décodage complet.

Un import interrompu peut laisser `pending-…` et bloque les nouveaux imports.
`artifact-recovery-inspect --root … --store-id … --pending pending-IDENTIFIANT`
vérifie un lot précis hors ligne. Seul un lot complet, dont la référence exacte
a été revue, peut être publié :

```sh
eidolon-media artifact-publish --root /chemin/prive/medias --store-id mas-IDENTIFIANT --pending pending-IDENTIFIANT --reference reference.json --publish-reviewed
```

Publication atomique sous verrou, empreinte et quotas revérifiés ; aucun
remplacement d'artefact. Lots partiels, corrompus ou multiples : revue manuelle,
aucune suppression/réparation automatique. La récupération conserve la référence
originale et ne valide pas le contenu métier.

## Collecte explicite des résultats

```sh
eidolon-media collect --job /chemin/prive/travail --root /chemin/prive/medias --store-id mas-IDENTIFIANT --collection /chemin/prive/nouvelle-collecte
eidolon-media collection-inspect --collection /chemin/prive/nouvelle-collecte
```

La collecte exige un reçu de file enregistré et un dossier nouveau. Elle ne fait
que des GET auprès du moteur : historique terminé sans erreur, même identifiant,
empreinte du workflow historique identique au plan, nœuds présents dans ce workflow.
Seules les sorties enregistrées `type=output`, sous les champs images/gifs/videos/video,
avec noms bornés sans traversée de chemin, sont admises. Formats : PNG/JPEG/WebP
pour Image, MP4/WebM pour Vidéo ; les aperçus temporaires, GIF animés et workflows
aux formats de sortie différents exigent un adaptateur supplémentaire.

Maximum 16 sorties / 256 Mio par collecte, limites par fichier inchangées. Les
octets récupérés sont contrôlés puis importés avec provenance travail/prompt/nœud/
collection et empreinte. L'historique lie la sortie au plan selon le moteur local
de confiance ; il ne constitue pas une attestation indépendante de sa génération.
La collecte ne valide ni qualité visuelle, ni consigne, ni codec complet.

Une collecte partielle reste inspectable, avec ses imports déjà publiés. Si le
processus s'arrête entre publication d'un artefact et mise à jour du reçu, la
provenance dans l'inventaire permet le rapprochement manuel. Aucun nouvel envoi
au moteur ni reprise automatique : réutiliser le dossier est refusé. Créer une
autre collecte constitue une nouvelle demande explicite et peut importer des doublons.

Pour récupérer un résultat hors du magasin, placer sa référence (ou son manifeste)
dans `reference.json`, puis choisir un fichier **nouveau** dans un répertoire privé
de l'opérateur, extérieur au magasin :

```sh
eidolon-media artifact-export --root /chemin/prive/medias --store-id mas-IDENTIFIANT --reference reference.json --destination /chemin/prive/resultat.png
```

L'empreinte est revérifiée avant écriture. La publication est atomique et refuse
tout fichier ou lien déjà présent, y compris créé par un autre processus pendant
l'export. Le résultat est une copie indépendante en mode 0600. Une coupure peut
laisser un temporaire d'export dans ce répertoire, ou un résultat complet sans
accusé final ; inspecter les fichiers et leurs empreintes avant toute nouvelle
demande. Aucun nettoyage ou écrasement automatique n'est effectué.

## Réservation durable entre travaux média — C-061

Lorsque ComfyUI et Ollama partagent le même GPU, plusieurs demandes peuvent
se concurrencer. Le paquet fournit un **groupe à une place**, choisi explicitement
par l'opérateur. Tous les fichiers de configuration devant partager cette place
référencent le même groupe. Sans `resource_pool`, le comportement précédent
reste inchangé : aucune coordination de concurrence n'est activée.

Créer un dossier **nouveau**, privé, dans un parent existant, privé et de confiance :

```sh
eidolon-media resource-init --root /chemin/prive/reservation-media
```

Conserver le `pool_id` retourné (`mrp-` suivi de 32 caractères hexadécimaux) et
ajouter à `moteurs.json` :

```json
{"resource_pool":{"root":"/chemin/prive/reservation-media","pool_id":"mrp-IDENTIFIANT_RETOURNE"}}
```

Cet extrait est à fusionner avec la configuration existante ; l'identifiant est
un emplacement à remplacer, pas une valeur valide. Aucun moteur, modèle ou GPU
n'est détecté automatiquement. Le groupe peut couvrir ComfyUI et Ollama ensemble
si les deux configurations le désignent. Il ne couvre **ni le dialogue Core, ni
les clients externes, ni les lancements utilisant une autre configuration**.

`run` valide la demande et les sources, puis réserve avant le premier appel
moteur, transfert ou décodage FFmpeg. Une place occupée donne `RESOURCE_RESERVED`,
sans créer le second travail ni appeler le moteur. Les accès concurrents au
registre sont non bloquants (`RESOURCE_POOL_BUSY` en cas de contention) ; aucun
renvoi automatique. La réservation est fsyncée avant tout effet externe. Le
journal du travail contient son identifiant `mrl-…`, celui du groupe et la date.

**Aucune libération automatique**, y compris après une analyse terminée. Un reçu
ComfyUI, un délai écoulé, la disparition du PID, l'arrêt du client ou l'absence
d'historique ne prouvent pas que le moteur est au repos. Une réservation peut
survivre à une coupure avant même la création de `job.json` : elle reste visible
dans le groupe. Ne pas effacer le registre ni créer un autre groupe pour passer
outre. Vérifier le moteur et les autres clients qui l'utilisent.

```sh
eidolon-media resource-inspect --root /chemin/prive/reservation-media --pool-id mrp-IDENTIFIANT_RETOURNE --format human
```

Après vérification opérateur que les travaux sont effectivement arrêtés/terminés :

```sh
eidolon-media resource-release --root /chemin/prive/reservation-media --pool-id mrp-IDENTIFIANT_RETOURNE --lease-id mrl-RESERVATION_OBSERVEE --reviewed-idle --reason "Travail terminé et moteur vérifié au repos"
```

La commande refuse une réservation ancienne ou différente. Elle conserve la
**dernière** libération (date et motif borné), sans effacer le travail, annuler le
moteur ni relancer une demande. Le motif est une déclaration de l'opérateur,
jamais une preuve mesurée par Core. Le registre reste borné ; les journaux de
travaux conservent les identifiants de réservations antérieures.

`config-check` et `preflight` affichent l'état observé du groupe sans réserver.
`CONFIGURED_SCOPE` et `LOCAL_INPUTS_VALID` peuvent coexister avec `RESERVED` : la
configuration et les entrées sont valides, mais un lancement serait bloqué.
`inspect --format human` montre la réservation enregistrée dans le travail et
renvoie à `resource-inspect` pour l'état actuel. `poll` et `collect` ne libèrent
rien. Aucune inspection n'écrit dans le groupe ou le journal.

Ce garde contrôle **une admission coopérative**, pas des mégaoctets de VRAM.
Il ne garantit ni mémoire suffisante, ni déchargement du modèle, ni disponibilité
matérielle, ni réussite du contenu. Son stockage POSIX privé refuse liens,
fichiers non réguliers, identités étrangères et remplacement observé en cours
d'instance ; il ne défend pas contre un processus hostile du même utilisateur.

## États, résultats et limites

| État | Signification |
| --- | --- |
| LOCAL_DRAFT | Demande préparée, aucun travail envoyé |
| INTENT | Intention persistée ; après interruption, revue nécessaire |
| QUEUED | ComfyUI a retourné un identifiant, pas un résultat vérifié |
| RESULT_UNVERIFIED | Réponse d'analyse reçue ; observation du modèle, pas fait confirmé |
| REVIEW_REQUIRED | Appel/résultat incertain ; aucune relance automatique |
| ENGINE_COMPLETED_UNVERIFIED | Historique moteur terminé, sorties non contrôlées |
| OUTPUTS_IMPORTED_UNVERIFIED | Octets importés et empreintes contrôlées, contenu métier non vérifié |
| COLLECTION_INCOMPLETE | Collecte interrompue ; imports/provenance conservés pour revue |

Le modèle Vision est rappelé avec sortie bornée, sans streaming et déchargement
demandé après traitement (`keep_alive: 0`). Réponse tronquée, modèle différent,
JSON invalide ou incomplet refusés. La vidéo ne bénéficie pas encore d'un suivi
temporel exhaustif, d'OCR garanti, de transcription sonore ni d'identification
de personnes. Les descriptions restent non vérifiées et ne déclenchent aucune action.

Les travaux média ont leur propre journal de préfiguration : pas de réutilisation
implicite de `SUCCEEDED`, des reçus d'approbation ou des identités de missions Core.
Le délai HTTP est un timeout socket, pas une échéance murale globale. Les décodages
FFmpeg sont limités à 30 secondes ; les images transmises et réponses sont bornées.
Les étapes de transfert/soumission sont journalisées avant chaque effet suivant.
Après coupure avec `QUEUE_ACKNOWLEDGED` durable, `poll` et `collect` peuvent lire
l'historique sans renvoyer le travail ni modifier son journal original. Sans reçu
durable, l'effet reste incertain ; aucune déduction d'absence d'exécution.
L'arbitrage GPU partagé avec le dialogue, les budgets globaux, la rétention,
la validation sémantique des sorties et le raccordement au worker Core restent à faire.
Aucun résultat ne qualifie la V100, Windows ou un vrai modèle de génération.

## Interface avec le chantier Claude

G084–G101 restent à Claude, avec G084–G089 prioritaires. Le brouillon navigateur `media-draft/1` contient
uniquement des métadonnées de sélection et n'est **jamais** accepté tel quel par
une API d'exécution. Le serveur devra prendre en charge un upload authentifié,
produire une référence d'artefact validée, présenter la proposition puis lancer
l'agent sous le contrat de mission et ses droits. Ne pas envoyer un chemin fourni
par un navigateur à `run`. Une référence opaque ne vaut **jamais permission** : G094 doit lier propriétaire,
conversation, proposition et autorisation de mission côté serveur. Ne pas accepter
la provenance du navigateur comme preuve. Codex conserve les modules `media_*.py` et
`desktop/connected/src/media-agents.js` pour ce raccordement.

Sources primaires consultées le 08/10/2026 pour les adaptateurs :
[API ComfyUI](https://docs.comfy.org/development/comfyui-server/comms_routes),
[API generate Ollama](https://docs.ollama.com/api/generate). Le code a été testé
avec des API simulées ; compatibilité d'une installation réelle à qualifier.


Transfert et collecte revus le 09/10/2026 sur le code officiel ComfyUI
[`a4b5a045e56fc334903db8457b728b64e006119c`](https://github.com/Comfy-Org/ComfyUI/tree/a4b5a045e56fc334903db8457b728b64e006119c),
`server.py` (upload/view) et `execution.py` (historique prompt/outputs).
Ce repérage de contrat n'est pas un test du moteur, de ses nœuds ou de ses poids.

Précontrôles revus le 09/10/2026 : route `object_info` du même commit ComfyUI et
[API show Ollama](https://docs.ollama.com/api-reference/show-model-details).


C-059 : les transports HTTP des moteurs et transferts refusent une réponse dont
les en-têtes sont interrompus avec `INCOMPLETE_HTTP`. Une coupure avant tout octet
reste indisponible au niveau transport ; un JSON incomplet après des en-têtes
complets reste refusé à la lecture du corps. Aucun nouvel appel automatique :
consulter le journal et son reçu éventuel, car la requête peut déjà avoir eu un effet.
