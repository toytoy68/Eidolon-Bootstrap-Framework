# Archives de recherche — lecteur et liste locale C-028

Codex/GPT, 07/10/2026. C-D17 (demande relayée par Claude) prévoit l’archivage
automatique et environ 100 recherches actives. Ce premier composant fournit
la **validation des exports et leur catalogue local**. Le producteur de
rotation G057 reste un prototype isolé, en correction G062 ; aucune recherche
active n’est retirée et aucun schéma de garde n’est migré par ce lecteur.

## Consulter et générer liste.md

Depuis eidolon-core, sur un dossier d’archives existant et privé :

```sh
PYTHONPATH=src python -m eidolon_core.research_archive --directory /chemin/archives inspect
PYTHONPATH=src python -m eidolon_core.research_archive --directory /chemin/archives index
PYTHONPATH=src python -m eidolon_core.research_archive --directory /chemin/archives --format human inspect
```

`inspect` ne crée rien. `index` écrit un **liste.md généré**, privé, dans le
même dossier ; les exports et le journal restent inchangés. Une consultation
réussie renvoie 0 ; un refus renvoie 2 avec un code constant, sans traceback,
chemin local ni texte de recherche. Le dossier absent reste absent.

Le catalogue JSON `eidolon-research-archive-catalog/1` donne pour chaque export
son nom, son numéro, son empreinte, l’horodatage de création enregistré, le nombre
de recherches, de textes nettoyés disponibles, d’anciens enregistrements sans
texte et de recherches liées à des missions. Les identifiants de mission,
requêtes, annotations de revue et empreintes de requête d’origine sont exclus.

`liste.md` contient uniquement les noms/liens relatifs fixes et les comptes,
avec une empreinte du catalogue. Il ne contient aucun texte fourni par le modèle
ou les recherches. Les fichiers d’export eux-mêmes sont privés et peuvent
contenir des données : **ne pas exposer le dossier comme racine Web**.

## Contrôles sur les exports

Format lu : `eidolon-research-archive/1`, noms stricts
`research-archive-000001.json`, etc. Un catalogue complet commence à 1.

- JSON UTF-8, clés uniques, types exacts et absence de valeurs non finies.
- Identité de garde commune, recherches uniques, états terminés uniquement.
- Deux événements par recherche : INTENT puis état final identique au corps,
  séquences positives ordonnées et uniques, descripteur et début liés.
- Texte nettoyé présent exactement quand le descripteur le prévoit, contenu
  et empreintes liés. Un ancien enregistrement sans texte reste explicitement
  sans texte ; aucun texte n’est inventé.
- Numéros d’exports consécutifs et chaîne dérivée des empreintes des fichiers,
  avec empreinte de la liste ordonnée des recherches de chaque export.
- Fichiers ordinaires appartenant à l’utilisateur, privés, sans lien symbolique
  final ; répertoire final privé et sans lien. FIFO et autres fichiers spéciaux
  refusés sans en lire le contenu.

Le lecteur valide les liaisons archivées d’une mission, mais ne détermine pas
si cette mission a terminé. La politique de retrait doit être contrôlée par
le futur producteur, en consultant les preuves et états nécessaires.

## Ce qu’un catalogue vérifié établit

`consistency_verified=true` décrit la cohérence des fichiers lus. Les champs
suivants restent **false** : `authenticity_verified`, `live_journal_checked`,
`committed_status_known`, `authorizes_execution`, `request_sent`.

Un export publié juste avant un crash peut être cohérent sans avoir été engagé
dans le journal actif. Ce lecteur ne permet donc ni de le valider comme engagé,
ni de retirer les lignes actives. Une chaîne entièrement réécrite, ou amputée
de sa fin avec réécriture cohérente, ne peut être authentifiée sans référence
extérieure. L’empreinte du catalogue n’est pas une signature.

Le lecteur compare les fichiers et l’inventaire avant/après la lecture. Un
changement détecté provoque un refus complet. La capture n’est pas atomique
avec le journal ou l’évolution ultérieure du dossier. `liste.md` est une vue
reconstructible qui peut devenir périmée ; il ne doit jamais être une autorité
pour la reprise ou la suppression des recherches.

## Publication de l’index

La commande `index` sérialise ses écritures via `.archive-index.lock` (privé).
Elle prépare un fichier temporaire privé, l’écrit complètement, le synchronise,
puis publie atomiquement liste.md et synchronise le dossier. Un index généré
identique n’est pas réécrit. Un liste.md manuscrit ou un lien symbolique est
refusé ; le marqueur de génération identifie les fichiers gérés par l’outil,
sans constituer une authentification contre leur propriétaire.

Une erreur ou coupure peut survenir après publication : relire avant de conclure
que rien n’a été écrit. Un arrêt brutal avant publication peut laisser un fichier
`.liste-*.tmp` privé ; il n’est pas une archive ni une preuve de commit. Aucun
nettoyage automatique de fichiers inconnus n’est fait. Le fichier de verrou peut
rester après une commande refusée ; sa présence ne signifie pas qu’il est détenu.

## Bornes et refus

Au plus 1 000 archives, 2 048 entrées de dossier, 16 Mio par export, 64 Mio
cumulés, 256 recherches par export et 1 Mio pour l’index. Un `.partial`
d’export provoque `PARTIAL_EXPORT_PRESENT`. Aucun catalogue tronqué n’est
présenté comme complet ; les gros historiques auront besoin d’une lecture
segmentée et d’un ancrage explicites. Les délais physiques du stockage ne sont
pas bornés. POSIX/stockage local seulement ; ancêtres du dossier de confiance.

## Suite de C-D17

La cible de **100 recherches actives** est le choix technique proposé pour
« une centaine ». Les missions non terminales doivent conserver leurs preuves,
y compris si cela impose un dépassement explicite du seuil. G062 prépare le
producteur automatique et sa reprise sans perte ; son intégration sera distincte.

Le raccordement Desktop utilisera une projection authentifiée servie par Core.
Ce lot n’ajoute **aucune route HTTP**, aucun accès fichiers Tauri ni déclencheur
automatique. Il ne modifie pas la limite active actuelle de 256 recherches.

[Validation et compatibilité G057](validation/2026-10-07/codex-research-archives/README.md).
