# Suite proposée après revue

Eidolon Core Technologies (ECT), 12 novembre 2026.

1. **Revue de G325** : sécurité des chemins et du catalogue, reprise incertaine,
   interruption Comfy globale, bornes de ressources et licences. Corriger avant
   d'activer au boot ; aucune fusion automatique.
2. **Qualité image** : jeu de prompts non privés, vérification humaine, SDXL et
   checkpoint d'inpainting revu ; un seul nouveau modèle à la fois, seed fixe,
   mesure chargement/inférence séparée. LoRA générique légalement utilisable à
   installer explicitement et tester réellement avant annonce de compatibilité.
3. **Qualité vidéo** : augmenter progressivement étapes, durée puis résolution,
   avec garde mémoire ; évaluer cohérence temporelle. AnimateDiff seulement
   après audit de l'extension. Ne pas appeler le profil Wan T2V un moteur I2V.
4. **Ordonnancement commun** : bail GPU atomique adopté par Eva, Ollama et Media,
   réservation libérée sur panne. Mesurer mode A (instances indépendantes), B
   (affectation image/vidéo), puis C uniquement avec un backend supportant un
   vrai placement multi-GPU. Mesurer PCIe/P2P/NVLink, énergie et latence. Aucun
   regroupement implicite de VRAM ; la surveillance PID actuelle reste coopérative.
5. **Exploitation privée** : compte système distinct, ACL par utilisateur familial,
   quotas/rétention DB et fichiers temporaires, sauvegarde chiffrée si souhaitée,
   rotation jetons, miroir de roues et licences, service permanent durci.
6. **Intégration Core** : brancher LocalGenerationClient dans les couches
   conversation_media existantes, cartes de progression et affichage résultats
   dans le HUD, puis voix. Maintenir les octets volumineux hors Memory Engine ;
   indexer seulement une sélection explicite de métadonnées utiles.
7. **Deux V100 32 Go** : refaire entièrement la recette mémoire/thermique/énergie,
   essayer SDXL et vidéos plus longues sur une carte, puis répartition explicite.
   Les 64 Go physiques cumulés ne deviennent pas automatiquement un tensor de
   64 Go utilisable. Aucun achat requis pour les résultats de la phase présente.

Décisions ultérieures utiles : priorité qualité image ou vidéo, utilisateurs
autorisés à la bibliothèque, budget GPU concurrent avec Eva, rétention et
activation permanente du service. Aucune de ces décisions n'est requise pour
conserver et relire le prototype déjà validé.

## Priorité adoptée G332 — candidats et deux GPU

Toytoy autorise les essais des modèles nécessitant les deux V10016Go actuelles.
Suivre la [file versionnée](CANDIDATE-QUEUE-G332.md), en commençant par une
répartition véritable du générateur FLUX.1 Schnell, puis les alternatives SDXL.
Chaque candidat garde son état non testé tant qu'aucune preuve matérielle
spécifique n'est produite. Les modèles dont les poids seuls dépassent 32Go
nécessitent quantification/offload et ne sont pas comptés comme résidents FP16.

## Avancement G333 —13/11/2026

RealVisXL V5.0 et Juggernaut XL v9 testés sur V10016Go, témoin SDXL régénéré,
27images avec paramètres comparables. [Résultats](CHECKPOINTS-G333.md) :
5propositions visuelles,3doutes,16rejets hors répétitions. Aucun profil promu.
Confirmation hors réglage/multi-seeds et formats écran restent nécessaires.
Poursuivre ensuite les autres architectures et la vidéo selon la file ; ne pas
assimiler le succès FP16 SDXL à une validation des kernels des autres modèles.

Politique toytoy :300W par V100 pour image/vidéo,200W pour Eva/discussion.
La bascule automatique nécessite le bail GPU commun ; aucun réglage modifié G333.
Modèles :14,75Gio libres ; données :226,86Gio. Préparer un emplacement dédié sur
le volume données avant de télécharger d'autres gros poids, sans suppression
automatique des modèles ni changement de pilote/environnement existant.

## Avancement G334 — Sana 600M, 13/11/2026

[Sana 600M](SANA-G334.md) fonctionne sur une V100 avec encodage CPU FP32 :
12 générations, 2/8 images natives proposées, 2 douteuses et 4 rejetées.
Formats écran réussis techniquement, contenu non conforme. Gemma2 soumis à ses
restrictions propres ; ne pas présenter ce pipeline comme libre de toute restriction.
Sana 1,6B, Sprint et encodage GPU1 restent non testés. Tester le placement de
l'encodeur sur GPU1 ne constitue qu'une piste pour les 22 s CPU, sans gain mesuré.
Poursuivre la file et la vidéo ; aucun profil ou entraînement promu.

## Avancement G335 — Sana 1,6B, 13/11/2026

[Sana 1600M FP16](SANA-G335.md) testé avec runner/plan G334 inchangés :
12 générations, répétition exacte, 1/8 native proposée, 2 doutes et 5 rejets.
Médiane GPU/décodage +41%, VRAM 9,60 Gio, sans progrès qualitatif global établi.
Sprint et encodeur GPU1 restent non testés. Ne pas prioriser la seule taille :
poursuivre une autre architecture ou la vidéo après audit précis du candidat.
PDF préféré pour les revues sur téléphone, HTML G334 ouvert en texte chez toytoy.


## Avancement G337 - AnimateDiff, 13/11/2026

[Diagnostic G337](ANIMATEDIFF-G337.md) : G336 retrouve non revu ; 6 nouveaux clips apres correction beta schedule, toujours rejetes. 2 controles SD1.5 reconnaissables : defaut localise a la chaine AnimateDiff, cause non resolue. Aucun modele promu. GPU liberes, machine allumee. FLUX.1 dev reste I10 non teste.


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
