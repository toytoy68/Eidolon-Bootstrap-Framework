# Validation expérimentale — G325

Eidolon Core Technologies (ECT). Mesures réelles du 12 novembre 2026 sur X399.
Les tests avec moteur simulé ne sont pas comptés comme validations GPU.

## Résultats réels

| Recette finale | Sortie | Durée API | Pic VRAM | GPU / HBM max |
| --- | --- | ---: | ---: | ---: |
| SD1.5 texte, 20 étapes | PNG 512×512 | 4,35 s | 4 080 Mio | 34 / 36 °C |
| SD1.5 image → image | PNG 512×512 | 4,95 s | 4 400 Mio | 35 / 36 °C |
| Retouche masquée, 20 étapes | PNG 512×512 | 4,51 s | 4 400 Mio | 35 / 37 °C |
| Wan2.1 1.3B, 20 étapes | MP4 H.264 320×256, 17 images, 8 i/s, 2,125 s | 20,21 s | 13 200 Mio | 37 / 40 °C |
| SVD, 15 étapes | MP4 H.264 320×256, 14 images, 7 i/s, 2 s | 21,39 s | 11 888 Mio | 37 / 39 °C |

Mesures complètes : [validation-summary.json](validation-summary.json). Les
répétitions réelles SD1.5, Wan 9 images et SVD 14 images ont produit des fichiers
SHA256 identiques avec seed 42. Wan 17 images et la recette finale sont également
identiques. Ceci vaut pour ce runtime/ces entrées, pas pour tout GPU ou pilote.
Les graphes diffèrent parfois par le préfixe unique de fichier : comparer aussi
les paramètres normalisés, pas seulement le hash du graphe.

Les caches Comfy ont été vidés entre répétitions pour provoquer un vrai recalcul.
Le cache disque Linux n'a pas été vidé. Les durées englobent chargement, file,
inférence et export. Le chargement isolé n'a pas été mesuré systématiquement.
Après déplacement de stockage et redémarrage des deux seuls services média,
une génération par LocalGenerationClient a réussi en 6,31 s ; un ancien résultat
est resté lisible. Ce dernier prompt diffère, ce n'est pas une répétition seed.

Échantillonnage nvidia-smi environ 0,5 s : les maxima ne capturent pas tous les
transitoires. GPU1 réglée à 200 W, mais une lecture Wan atteint **247,43 W** :
ne pas présenter 200 W comme un plafond instantané démontré. Énergie secteur
machine entière : environ 0,214 Wh image, 0,215 Wh masque, 1,50 Wh Wan,
1,929 Wh SVD pour le lot final. Granularité du Shelly et charges de fond limitent
la comparaison. Ce ne sont pas des joules GPU isolés. CPU max retenu 48,75 °C.

## Qualité et corrections issues des essais

La première image montre correctement une cabane rouge, un lac et des montagnes.
L'édition demandant une cabane bleue est restée rouge et trop accentuée : la
chaîne img2img fonctionne, sa fidélité sémantique n'est pas qualifiée. La retouche
initiale altérait les pixels hors masque : ajout d'une composition masquée native,
puis égalité exacte hors masque vérifiée sur une nouvelle génération réelle.
Cela ne prouve pas la perfection esthétique à l'intérieur du masque.

Wan produit une courte séquence lisible, stylisée/postérisée ; faible résolution
et peu d'étapes. Les trames décodées de Wan et SVD changent et ne sont pas noires.
Ce contrôle ne démontre pas une animation naturelle ou une qualité de production.
L'animation SVD complète n'a pas fait l'objet d'une revue visuelle exhaustive.

L'export MP4 initial héritait d'une base de temps erronée. Correction des PTS et
time_base, puis décodage réel et vérification de cadence, durée, dimensions et
nombre de trames. Les sorties finales sont bien 8 et 7 i/s, pas les valeurs
incorrectes observées avant correction.

## Tests logiciels et lifecycle

205 tests média découverts dans chaque environnement :

- Environnement de développement : **202 réussis, 3 ignorés** (PyAV absent).
- Venv X399 : **200 réussis, 5 ignorés** (exécutables ffmpeg/ffprobe absents).
- Les trois tests PyAV réels passent sur X399 ; les cinq tests ffmpeg passent
  en développement. Ce ne sont pas 205 tests réussis simultanément sur X399.
- Contrats testés : chemins, token, tailles, états SQLite, reprise incertaine,
  validation des graphes/résultats, sélection catalogue, transport HTTP, conflit
  GPU simulé et limites. Les LoRA utilisent des fixtures, pas de poids GPU.

Commande : `PYTHONPATH=src python -m unittest discover -s tests -p 'test_media*.py' -q`
depuis eidolon-core. Les suites autres que média n'ont pas été relancées ; le
changement du transport partagé conserve le comportement 200 par défaut.

Moteur réel : mauvais jeton et Origin refusés 401, même clé d'idempotence → même
job, progression observée à 3/40 étapes, annulation d'un job WAITING immédiate,
annulation RUNNING confirmée par execution_interrupted dans l'historique Comfy.
Les faux moteurs sont utilisés seulement pour les scénarios de panne dangereux
à provoquer en production (reprise ambiguë, concurrence étrangère).

## Fonctionnement hors ligne et non-régression observée

Les générations ont été exécutées dans des unités systemd avec réseau limité
à localhost. Un processus placé dans chacun des cgroups a pu joindre 127.0.0.1:8189
et n'a pas pu joindre 1.1.1.1:443 (timeout) ; le contrôle hors cgroup pouvait le
joindre. Contrôle renouvelé après déplacement pour moteur et API finale.
Internet n'a pas été coupé pour l'hôte entier afin de préserver les autres services.
Ce test valide l'absence d'accès Internet du périmètre de génération, pas une
réinstallation complète à partir de zéro sans téléchargement.

Pilote 550.163.01 et environnements Eva inchangés. GPU0 reste à 1 Mio, pas de
calcul média dessus. Services Core/comm/monitor/memory-tunnel/Ollama/Darme actifs
avant et après. VM Memory Engine restée active ; VM de tests et Minecraft non
démarrées. Aucun arrêt d'entraînement, reboot ou extinction. Compteurs NVLink
CRC/Replay/Recovery tous à zéro à la clôture ; aucun nouveau débit NVLink mesuré.
La vérification de services actifs n'est pas un test exhaustif de non-régression
fonctionnelle de tout Eidolon.

## Critères de phase 1

Texte→image, édition, courte vidéo, API privée, génération sans API extérieure,
exécution sans accès Internet, sondes GPU et répétitions documentées : **atteints
sur le périmètre expérimental indiqué**. Pas de dégradation détectée des services
observés. Restent : qualité vidéo, chargement isolé, tests prolongés, réinstallation
hors ligne, ordonnancement global Eva, LoRA réels, UI/HUD/voix, modèle réparti,
comparaison énergétique des modes A/B/C et V100 32 Go. L'intégration complète
ne doit donc pas être déclarée terminée.

Preuves privées sur X399 : LAB/benchmark-{image,video,svd,release}-* et
LAB/lifecycle-report.json, post-storage-check.json, final-egress-check.json.
Les prompts, sources, vidéos, jetons et bases complètes ne sont pas publiés.
