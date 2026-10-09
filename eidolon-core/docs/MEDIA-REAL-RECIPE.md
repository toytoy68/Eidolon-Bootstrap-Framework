# Recette Image/Vidéo sur les moteurs choisis — C-063

Cette fiche prépare les essais sur le serveur Linux/POSIX de l'opérateur.
**Aucun essai matériel n'est déclaré réussi dans cette fiche.** Les recettes
automatisées du dépôt emploient des moteurs simulés. Les agents et leurs CLI sont
installables ; moteurs, poids, workflows et compatibilité matérielle sont à vérifier
sur l'installation choisie. [Contrats et commandes](MEDIA-AGENTS.md).

## Ce qui est prêt dans l'archive source

Les six fichiers de `examples/media/` sont des demandes valides pour `prepare`.
Copier ceux à utiliser dans le dossier privé de la recette, puis les adapter :

| Demande | Entrée à choisir | Observation attendue à fixer avant le lancement |
| --- | --- | --- |
| `image-create.json` | Prompt, format, workflow de création | Sujet/couleurs demandés ; dimensions souhaitées |
| `image-edit.json` | Image locale ou référence d'artefact, workflow d'édition | Modification demandée et éléments devant rester identiques |
| `image-analyze.json` | Image dont le contenu est connu de l'opérateur | Observations exactes et incertitudes explicites |
| `video-create.json` | Prompt, format, durée, workflow vidéo | Mouvement, sujet, dimensions et durée souhaités |
| `video-edit.json` | Vidéo locale ou référence d'artefact, workflow d'édition | Modification, éléments conservés et durée souhaitée |
| `video-analyze.json` | Vidéo de référence avec repères visuels datés | Observations sur l'échantillon, sans inventer l'audio ou la suite |

Les chemins `/REMPLACER/image.png` et `/REMPLACER/video.mp4` sont des emplacements
à remplacer. Ce sont des chemins **du serveur où la CLI tourne**, jamais une
instruction d'envoi d'un chemin Windows au moteur. Pour utiliser le magasin privé,
importer explicitement la source, enlever `source` de la demande et ajouter
`artifact` avec l'objet `reference` obtenu. Source locale et artefact sont exclusifs.

Les fichiers ne contiennent ni URL moteur, ni modèle par défaut, ni workflow
fictif présenté comme fonctionnel. Aucun fichier n'exécute quoi que ce soit seul.

## Figer le contexte de chaque essai

Conserver dans le dossier privé de recette la version/commit de Core, les versions
des moteurs et extensions, les identifiants/empreintes des poids choisis, la
configuration, la demande et les sources. Relever la topologie réelle (hôte/VM,
GPU accessible, autres clients utilisant ce GPU). Fixer avant l'essai les critères
de contenu, dimensions/durée et coût acceptable ; une modification de critères
ou de configuration constitue un nouvel essai, pas une correction rétroactive.

Les artefacts et journaux peuvent contenir les prompts et noms locaux. Conserver
les preuves dans le dossier de recette choisi ; rien n'est envoyé au dépôt par
les commandes de cette fiche.

## Préparer sans inférence

Installer le paquet Core dans un environnement Python isolé selon le guide.
Configurer un moteur réellement présent et un workflow API pour chaque opération
à essayer. Le dialogue peut partager le GPU, mais **n'est pas encore arbitré par
le garde média** : organiser les essais sans concurrence avec les autres clients.

```sh
eidolon-media agents
eidolon-media config-check --config moteurs.json --require image.create --format human
eidolon-media prepare --request image-create.json
eidolon-media preflight --request image-create.json --config moteurs.json --format human
eidolon-media preflight --request image-create.json --config moteurs.json --probe-local --format human
```

Adapter le nom de demande et `--require` à l'opération essayée. Répéter `--require`
pour plusieurs opérations, ou l'omettre pour exiger les six. Le premier précontrôle
ne contacte aucun moteur ; le second en lit les métadonnées, sans prompt, source
ou inférence. Un contrôle structurel réussi ne qualifie ni workflow, ni poids, ni GPU.

Créer un groupe avec `resource-init` et ajouter son `root`/`pool_id` à la configuration
si les essais doivent partager une place. Conserver les identifiants retournés.
`resource-inspect` doit être relu avant la suite ; `AVAILABLE` décrit seulement
le registre, pas l'état réel du GPU ou du moteur.

## Exécuter une opération choisie

Cette commande **envoie le prompt et la source choisie au moteur local configuré**.
Le dossier de travail est nouveau, dans un parent privé existant :

```sh
eidolon-media run --request image-create.json --config moteurs.json --job /chemin/prive/recette/travail-image-creation --execute-local
eidolon-media inspect --job /chemin/prive/recette/travail-image-creation --format human
```

En création/édition, `QUEUED` est un reçu de file. Consulter explicitement `poll`,
puis `collect` vers le magasin d'artefacts choisi quand l'historique est terminé.
En analyse, `RESULT_UNVERIFIED` est une réponse de modèle dans le journal ; aucune
collecte ComfyUI ne s'applique. Un échec ou une réponse perdue impose une revue
du travail existant avant tout nouvel essai ; aucun renvoi automatique.

## Examiner le résultat et clôturer la réservation

Pour une image ou vidéo collectée, conserver la référence retournée, puis utiliser
`artifact-probe` avec le FFprobe installé choisi. Comparer les métadonnées observées
aux critères fixés. Un conteneur lisible n'est pas une preuve que toutes ses images
sont décodables ; ouvrir explicitement l'export dans le lecteur choisi et examiner
le contenu pour le critère métier. Une exportation est toujours vers un fichier nouveau.

Pour l'analyse, comparer les propos du modèle aux repères connus. Le mode vidéo
n'envoie qu'un échantillon d'au plus huit images des quarante premières secondes,
sans audio. Ne pas lui attribuer la compréhension du film entier, de mouvements
continus ou d'un événement situé après cette fenêtre.

Relever durée d'attente/exécution et ressources avec les outils de l'opérateur.
Ne pas assimiler mémoire de modèle encore résidente à une tâche en cours, ni
absence du processus client à un moteur au repos. Vérifier l'état du moteur avant
`resource-release`, avec l'identifiant exact et un motif. `poll`, `collect` et
`artifact-probe` ne libèrent jamais le groupe et n'annulent aucun moteur.

## Tableau de résultat à remplir

Une ligne par essai, avec identifiant/dossier et liens vers ses preuves :

| Opération | Serveur/moteur/poids | Critères figés avant essai | Journal et résultat | Coût mesuré | Verdict opérateur |
| --- | --- | --- | --- | --- | --- |
| image.create | À renseigner | À renseigner | Non exécuté | Non mesuré | À faire |
| image.edit | À renseigner | À renseigner | Non exécuté | Non mesuré | À faire |
| image.analyze | À renseigner | À renseigner | Non exécuté | Non mesuré | À faire |
| video.create | À renseigner | À renseigner | Non exécuté | Non mesuré | À faire |
| video.edit | À renseigner | À renseigner | Non exécuté | Non mesuré | À faire |
| video.analyze | À renseigner | À renseigner | Non exécuté | Non mesuré | À faire |

Le PC Windows et l'accueil de l'appli ont leur propre recette. À ce stade, l'espace
média de l'accueil prépare un brouillon ; il ne lance pas encore ces opérations.
Les essais CLI Linux ne valident donc ni l'upload authentifié du PC, ni le contrat
conversation/média G094, ni l'exécution depuis l'accueil. Un verdict doit rester
limité au moteur, aux poids, à la machine, à l'opération et aux critères réellement essayés.
