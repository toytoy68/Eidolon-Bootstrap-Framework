# Formats écran — complément G326

Eidolon Core Technologies (ECT), 12 novembre 2026.

Complément G327 : le profil SDXL utilise 1024×576 en16:9 et768×576 en4:3 ;
voir [SDXL](SDXL.md). La table ci-dessous reste celle de SD1.5 et des vidéos.

La géométrie de génération et le cadre du fichier final sont séparés. Un export
1920×1080 n'est pas une génération native Full HD et n'ajoute pas de détails.
Le redimensionnement final est effectué sur CPU, avec proportions conservées.
Pas de modèle d'upscaling, de recadrage ni d'étirement à cette étape.

| Option format | Génération image | Génération vidéo | Présentation |
| --- | --- | --- | --- |
| native (défaut historique) | width/height existants | width/height existants | Format inchangé |
| 16:9 | 768×432 | 512×288 | Plein cadre 16:9 |
| 4:3-pillarbox | 576×432 | 384×288 | Image 4:3 centrée, bandes noires latérales |

`output_size` : native, 720p (1280×720) ou 1080p (1920×1080).
L'export 720p/1080p nécessite un format explicite. En format 4:3-pillarbox,
native désigne un cadre 16:9 à la hauteur de génération : 768×432 pour l'image,
512×288 pour la vidéo. Aucun paramètre de dimensions arbitraires d'export n'est
accepté ; les anciennes limites des requêtes sans format sont conservées.

En 1080p, le contenu 4:3 occupe 1440×1080, centré entre deux bandes de 240 pixels.
En 720p, il occupe 960×720 entre deux bandes de 160 pixels. Les bandes font partie
du PNG/MP4 ; la lecture ne dépend pas d'un réglage particulier du lecteur.
L'encodage H.264 avec pertes peut modifier de quelques niveaux des pixels près
de la frontière ; les bandes PNG restent exactement noires.

Exemple pour LocalGenerationClient :

```python
job = client.submit({
    'profile': 'wan21-text',
    'prompt': 'A small sailboat on a mountain lake',
    'format': '16:9',
    'output_size': '1080p',
    'frames': 9, 'fps': 8, 'steps': 12, 'seed': 42,
}, idempotency_key='lake-wide-001')
```

Remplacer format par `4:3-pillarbox` pour les bandes latérales. Ne pas ajouter
width/height sauf s'ils correspondent exactement au preset : les contradictions
sont refusées avant la mise en file. Le champ request des métadonnées conserve
les dimensions réellement générées et le choix d'export.

Pour img2img/SVD avec format explicite, l'entrée est ajustée uniformément dans
la géométrie de génération, avec fond noir si ses proportions diffèrent. Pour
l'inpainting, source et masque doivent avoir les mêmes dimensions initiales ;
le masque utilise un redimensionnement au plus proche. Cela préserve l'alignement,
mais peut introduire des bandes dans le contexte de génération. Fournir une
source au bon ratio donne un meilleur point de départ. La fidélité sémantique
de l'édition et la conservation pixel à pixel après redimensionnement final
ne sont pas garanties : conserver l'original pour une retouche précise.

Les nouveaux formats sont disponibles dans l'API expérimentale locale. Aucun
sélecteur graphique du HUD n'est encore livré. Les anciennes requêtes sans
format gardent leur comportement.

## Vérification

Tests dédiés : ratio exact, normalisation stable, refus des dimensions
contradictoires, contenu 4:3 et bandes exactes, entrée portrait sans déformation,
masque binaire, géométrie PNG, MP4 1080p réellement encodé/décodé avec cadence
et durée conservées. 213 tests média : 209 réussis/4 ignorés en développement
(PyAV absent), 208 réussis/5 ignorés sur X399 (CLI ffmpeg absent).

`display_probe.py` réalise explicitement six générations locales : SD1.5,
Wan2.1 et SVD, chacun dans les deux formats, avec export 1080p. Vidéos de cinq
images à huit images/seconde et six étapes : contrôle technique des géométries,
pas recette esthétique, durée utile ou test prolongé. Images à douze étapes.
Les résultats et paramètres complets restent privés sur X399. Voir
`display-validation.json` pour les seuls résultats agrégés.

Les choix de cadrage n'impliquent aucun changement de politique de contenu,
aucune sélection de modèle spécialisé et aucun service cloud.
