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
