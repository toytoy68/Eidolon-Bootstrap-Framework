# Eidolon-Media — prototype V100, G325

Eidolon Core Technologies (ECT) · Local AI • Modular • Reliable • Reproducible

12 novembre 2026, Europe/Paris. **Prototype matériel fonctionnel ; intégration
HUD/voix et ordonnancement global encore expérimentaux. Aucune fusion dans main.**

## Livrables

- [Architecture et audit](ARCHITECTURE.md).
- [Compatibilité, licences et sources](COMPATIBILITY.md).
- [Contrat API, installation et exploitation privée](OPERATIONS.md).
- [Validation réelle et limites](VALIDATION.md), [mesures sans contenus](validation-summary.json).
- [Feuille de route](ROADMAP.md).
- [File des candidats image/vidéo, une et deux V100](CANDIDATE-QUEUE-G332.md), G332.
- [Essai FLUX réparti sur deux cartes](MULTIGPU-G332.md), preuves et limites séparées.
- [Comparaison SDXL, RealVisXL et Juggernaut](CHECKPOINTS-G333.md),27générations réelles et revue complète,13/11.
- [Sana 600M](SANA-G334.md) et [Sana 1,6B](SANA-G335.md) : 12 générations par variante, comparaison et revue complète ; aucune promotion.
- [Formats 16:9 et 4:3 avec bandes latérales](DISPLAY.md), complément G326.
- [SDXL : essai matériel et comparaison](SDXL.md), complément G327.
- [Protocole de qualification visuelle](QUALITY-PROTOCOL.md), campagne G328.
- [Boucle de préférences](PREFERENCE-LOOP.md) et [premier pilote LoRA réel](PREFERENCE-RESULTS.md), G329 ; candidat non promu.
- `src/eidolon_core/media_service.py`, `media_service_client.py`,
  `media_profiles.py`, `media_registry.py` : composants facultatifs du paquet Core.
- [Workflows API ComfyUI](workflows/) : six graphes sans extension tierce.
- [Téléchargement initial explicite](download_models.py),
  [recette mesurée](benchmark.py), [sonde d'annulation](lifecycle_probe.py).
- [Versions Python observées](requirements-observed.txt) : inventaire figé,
  pas encore un miroir de roues avec hashes.

Les poids, prompts d'exploitation, sources et résultats restent sur la X399.
Le dépôt contient le code, les graphes génériques, les empreintes et les mesures
agrégées. Le service ne contacte aucun fournisseur d'inférence, ne télécharge
aucun modèle et ne modifie pas Memory Engine.

## Résultat immédiatement utilisable

**État au13/11 après redémarrage (G335)** : les unités transitoires ci-dessous
sont inactives. Les recettes G325–G332 restent des résultats historiques ;
G333 à G335 testent les candidats via des runners Diffusers isolés, sans les
déclarer intégrés à cette API. Voir OPERATIONS pour une remise en route contrôlée.

API authentifiée : `http://127.0.0.1:8190`. ComfyUI dédié : `127.0.0.1:8189`.
Accès depuis la machine uniquement. Aucun port public, tunnel ou exposition LAN
ajouté. Le jeton reste dans le fichier privé indiqué dans OPERATIONS.

| Fonction | État |
| --- | --- |
| Texte → image SD1.5 | Génération réelle 512×512, seed fixe reproduite |
| Image → image | Réelle ; fidélité au changement demandé limitée |
| Retouche masquée | Réelle ; pixels hors masque identiques après composition |
| Texte → vidéo Wan2.1 1.3B | MP4 H.264 réel, 320×256, 17 images à 8 i/s |
| Image → vidéo SVD | MP4 H.264 réel, 320×256, 14 images à 7 i/s |
| Suivi, annulation, idempotence | Contrôlés sur le moteur réel |
| Bibliothèque privée | Artefacts identifiés et vérifiés, fichiers 0600, API à jeton |
| Catalogue checkpoints/LoRA SD1.5 | Contrats/tests logiciels ; checkpoint de base réellement sélectionné ; aucun LoRA chargé sur GPU |
| HUD, conversation complète et voix | Façade cliente prête ; activation en production non réalisée |

Les unités de recette sont **transitoires**, sans activation au démarrage. Le
serveur reste allumé. Consulter OPERATIONS avant une remise en route : le PID du
moteur est un paramètre de sécurité et doit correspondre à l'instance courante.


## Tests de formulation G331

[Plan et résultats réels](PROMPT-TESTS-G331.md) :12 générations SDXL, prompts
original/détaillé comparés à seeds et réglages constants.12 succès techniques,
12 rejets visuels,aucune nouvelle paire ni entraînement. [Preuves](prompt-validation-g331.json).


## Avancement G338 — FLUX.1 dev, 13/11/2026

[Rapport G338](FLUX-DEV-G338.md) : générateur FP16 réellement réparti sur deux V10016, encodeurs CPU ; 12 images, répétition exacte. Grille native : 4/8 proposées, 2 réserves, 2 rejets pour cadrage. 70,58 s médianes GPU/décodage 1024². Correctif VAE par tuiles après OOM initial conservé. GPU/HBM max 47/51 °C ; aucune promotion. Formats écran générés mais cadrage non conforme. GPU libérés, machine allumée.


## Avancement G339 — FLUX dev/Schnell, 13/11/2026

[Comparatif G339](FLUX-COMPARISON-G339.md) : Schnell complet testé sur la grille G338, 12 images locales, répétition exacte ; 4/8 proposées, 2 réserves, 2 rejets, comme dev mais sur des images différentes. 6,451 s médianes GPU/décodage contre 70,577 s dev ; facteur 10,94 hors encodage/chargement. Rendu visuel et conformité distingués ; Schnell réussit un duo en pied, dev plus crédible sur les katanas. Aucune promotion, GPU libérés, machine allumée. Autres candidats non testés inchangés.
