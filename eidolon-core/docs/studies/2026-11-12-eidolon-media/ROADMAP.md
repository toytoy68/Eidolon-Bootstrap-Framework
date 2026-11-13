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
