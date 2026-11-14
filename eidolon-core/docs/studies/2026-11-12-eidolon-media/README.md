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


## Avancement G340 — Klein4B, 13/11/2026

[Rapport G340](KLEIN-G340.md) : FLUX.2 Klein4B FP16 sur une V100, Qwen3 CPU FP32 ;12images, répétition exacte. Grille native5/8 proposées,3rejets (main01 à six doigts et deux katanas) ;3,396s médianes GPU/décodage, encodage57,175s/4textes. Pic9 728Mio, GPU/HBM41/43°C. Runtime isolé, attention efficace PyTorch ; recettes différentes des références dev/Schnell. GPU libérés, services actifs, machine allumée ; aucune promotion.


## G341 — 14 novembre 2026

[Klein base 4B](KLEIN-BASE-G341.md) : 12 images, 5/8 proposées, 3 rejets natifs. 63,26 s médianes 1024², sans gain global face à G340. GPU/HBM49/54 °C. Aucune promotion. Extinction demandée pour modifications matérielles ; reprise manuelle.


## Avancement G342 — Z-Image Turbo, 14/11/2026

[Rapport G342](ZIMAGE-G342.md) : Z-Image Turbo FP32 réparti sur deux V100, Qwen3 CPU ;12images, répétition exacte. Natives4/8 proposées,2 réserves katana,2 rejets pour visiteurs supplémentaires. Médiane45,481s, encodage64,430s ; GPU/HBM47/48°C, pics14 068/14 490Mio. Attention découpée et répartition vérifiées. Aucun entraînement ni promotion ; GPU libérés, services actifs, machine allumée. Klein9B différé pour accès soumis à acceptation.


## Avancement G344 — Z-Image non Turbo, 14/11/2026

[Rapport G344](ZIMAGE-BASE-G344.md) :12images terminées,6/8 natives proposées,2 réserves katana ;279,383s médianes,28étapes/CFG4,FP32 sur deux V100. Formats écran rejetés pour cadrage. Maxima GPU51/49°C,HBM53/53°C ; répétition exacte. Usage détaillé à la demande selon toytoy, aucune promotion. GPU libres, services actifs, machine allumée.


## Avancement G345 — Sana Sprint, 14/11/2026

[Rapport G345](SANA-SPRINT-G345.md) : Sana Sprint 1,6B FP32 sur une V100, quatre étapes, guidage intégré 4,5 ; douze images et répétition exacte. Natives : 2/8 proposées, 1 à revoir, 5 rejetées. Médiane 1,833 s hors encodage/chargement ; encodage CPU 26,757 s pour quatre textes. Pic 9 184 Mio, GPU/HBM 42/44 °C. Très rapide, mais six doigts, armes dupliquées et cadrages/visibilité insuffisants. Premier essai arrêté avant génération pour un défaut du paramètre SCM, corrigé et conservé. Aperçus/objets simples uniquement comme piste ; aucune promotion. Runtime inchangé, services actifs, GPU libres, machine allumée.


## Avancement G346 — SD3.5 Medium, 14/11/2026

[Rapport G346](SD35-MEDIUM-G346.md) : SD3.5 Medium FP16 sur une V100, trois encodeurs CPU FP32,40étapes/CFG4,5 sans SLG ;12images, répétition exacte. Natives :1/8 proposée,1 réserve,6 rejets. Médiane22,376s, encodage cinq textes42,891s. Pic10 552Mio, GPU/HBM46/49°C. Deux mains à six doigts, katanas incohérents, duos non conformes. Incidents avant génération conservés ; aucun runtime modifié. GPU libres, services actifs, machine allumée ; aucune promotion. SLG et Large/Turbo non testés.


## Avancement G347 — SD3.5 Medium SLG, 14/11/2026

[Rapport G347](SD35-SLG-G347.md) : SD3.5 Medium FP16 avec SLG[7,8,9]/2,8/0,01–0,2,40étapes/CFG4,5 ;12images, répétition exacte. Natives :3/8 proposées,5rej et0réserve ;24,054s médianes (+7,50% vsG346). Main02 et anse04 corrigées, main01 toujours six doigts, katanas et duos non conformes. Pic10 556Mio, GPU/HBM47/52°C.47appels dont7SLG vérifiés/image. Runtime inchangé, services actifs, GPU libres, machine allumée. Aucune promotion.


## Avancement G348 — SD3.5 Large Turbo, 14/11/2026

[Rapport G348](SD35-LARGE-TURBO-G348.md) : SD3.5 Large Turbo FP16 sur deux V100,4 étapes/guidage0 ;12images, répétition exacte. Natives :5/8 proposées,3rej et0réserve ;3,130s médianes. Deux mains à cinq doigts ; katanas et duo08 rejetés. Même score que Klein5/8 à3,396s sur une seule V100 ; aucune supériorité générale déduite. Pics13 692/8 550Mio, GPU40/37°C, HBM41/36°C.76appels de blocs/carte/image vérifiés. Runtime inchangé, services actifs, GPU libres, machine allumée. Aucune promotion ; Large non Turbo reste non testé.


## Avancement G349 — SD3.5 Large, 14/11/2026

[Rapport G349](SD35-LARGE-G349.md) : SD3.5 Large FP16 sur deux V100,28étapes/CFG3,5 ;12images, répétition exacte. Natives :2/8 proposées,0réserves,6rejets ;36.020s médianes. Deux mains à six doigts, katanas incohérents ; aucun avantage global établi face à Turbo malgré les détails supplémentaires. Pics14078/8926Mio, GPU46/42°C.532appels de blocs/carte/image vérifiés. Runtime inchangé, GPU libres, services actifs, machine allumée. Aucune promotion.


## Avancement G350 — Sana Sprint0,6B, 14/11/2026

[Rapport G350](SANA-SPRINT-600M-G350.md) : Sana Sprint 0,6B FP32 sur une V100, 4 étapes / guidage intégré 4,5 ; 12 images, répétition exacte. Natives : 2/8 proposées, 0 réserve, 6 rejets ; 1.279 s médianes contre 1.833 s en 1,6B. Gain de temps et de VRAM, sans progrès de conformité ; candidat limité aux aperçus simples, aucune promotion. Pic 5336 Mio, GPU 42 °C, HBM 43 °C. Quatre appels du générateur vérifiés par image. Runtime inchangé, GPU libres, services actifs, machine allumée.


## Avancement G351 — FLUX Schnell Q8, 14/11/2026

[Rapport G351](FLUX-Q8-G351.md) : FLUX Schnell GGUF Q8_0, calcul FP16 sur une V100 ; 4 étapes, guidage 0, 12 images, répétition exacte. Natives : 4/8 proposées, 2 réserves et 2 rejets ; 15.613 s médianes contre 6.451 s pour le complet réparti G339. Schnell tient sur une seule carte, mais le Q8 ne gagne pas en vitesse ; option pour libérer GPU1, aucune promotion. Pic 15158 Mio, GPU 43 °C, HBM 50 °C. Incident de placement CPU détecté puis corrigé, trace conservée. Runtime partagé inchangé, GPU libres, services actifs, machine allumée.


## Avancement G352 — FLUX Schnell Q4, 14/11/2026

[Rapport G352](FLUX-Q4-G352.md) : FLUX Schnell GGUF Q4_0, calcul FP16 sur une V100 ; 4 étapes, guidage 0, 12 images, répétition exacte. Natives : 3/8 proposées, 2 réserves, 3 rejets ; 16.212 s médianes contre 15.613 s Q8. Pic 9824 Mio (-35.2 % vs Q8), GPU/HBM 44/49 °C. Moins de VRAM, mais main 01 plus floue et poignée surnuméraire en 06 ; aucun gain de vitesse, aucune promotion. Copie de licence corrigée avant génération, trace conservée. Runtime inchangé, GPU libres, services actifs, machine allumée.


## Avancement G353 — Juggernaut v10/v9, 14/11/2026

[Rapport G353](JUGGERNAUT-X-G353.md) : Juggernaut v10/v9, même DPM++2M Karras30/CFG5 sur une V100 ; 24 images et deux répétitions exactes. V10 1/8 proposées, 1 réserves, 6 rejets / 17.565s ; v9 3/8 proposées, 0 réserves, 5 rejets / 17.600s. V10 ne remplace pas v9 pour cette grille. Conserver les deux comme options spécialisées ; aucun nouveau modèle par défaut. Export JSON du scheduler corrigé avant génération, trace conservée. Runtime inchangé, GPU libres, services actifs, machine allumée.


## Avancement G354 — Juggernaut Lightning, 14/11/2026

[Rapport G354](JUGGERNAUT-LIGHTNING-G354.md) : Juggernaut XL Lightning, une V100 FP16, DPM++ SDE Karras6/CFG1,8, 11 appels UNet ; 12 images et répétition exacte. 1/8 proposées, 0 réserves, 7 rejets ; médiane 6.843s, temps divisé par 2.57 face au v9 G353 historique (recettes différentes). Gain de vitesse confirmé, conformité insuffisante : ne pas remplacer v9 ni les références FLUX par cette recette. Aucun déploiement ; runtime inchangé, services actifs, GPU libres, machine allumée.


## Avancement G355 — Juggernaut XI v11, 14/11/2026

[Rapport G355](JUGGERNAUT-XI-G355.md) : Juggernaut XI v11, une V100 FP16, DPM++2M Karras30/CFG5 ; 12 nouvelles images et répétition exacte. 2/8 proposées, 1 réserves, 5 rejets ; médiane 17.562s. V9 G353 historique3/8/17,600s, même recette. Conserver XI comme option pour les portraits en duo ; pas de remplacement global du v9 ou des références FLUX sur cette grille. Runtime inchangé, services actifs, GPU libres, machine allumée. Attribution RunDiffusion/KandooAI, CC BY-NC-ND4.0 et conditions auteur conservées ; aucun poids redistribué.


## Avancement G356 — Juggernaut XI Lightning, 14/11/2026

[Rapport G356](JUGGERNAUT-XI-LIGHTNING-G356.md) : XI Lightning Civitai-Version, une V100 FP16/VAE upcast FP32, SDE Karras6/CFG1,8,11 appels UNet ;12 nouvelles images, répétition exacte. 0/8 proposées,0 réserves,8 rejets ;6.840s. Références historiques XI standard2/8+1réserve/17,562s et XL Lightning1/8/6,843s. Ne pas retenir XI Lightning comme modèle principal avec cette recette. Sa vitesse est utile, mais la conformité est insuffisante sur cette petite grille ; le contrôle 4:3 mérite une confirmation sur plusieurs seeds avant tout usage régulier. Licences/attribution conservées, runtime inchangé, GPU libres, services actifs, machine allumée.
