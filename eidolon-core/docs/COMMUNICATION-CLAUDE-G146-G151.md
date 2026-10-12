# Lot Claude : communication vocale et visuelle Eidolon

Auteur : Codex/GPT. Demande explicite de toytoy, 12 octobre 2026, 06 h 51 Europe/Paris. Base : 7f7bb3a. Travail d'implémentation et recette, publication sur branche Claude puis intégration après revue. Les permissions générales de publication et installation de la session s'appliquent ; inventorier les installations avant modification et préserver les services existants.

Codex prend DARME R6, contrat de conseil, tests et code darme*. Claude prend un sous-système communication distinct, ses adapters, tests et documentation. Coordination obligatoire avant modification de http_api.py, dialogue.py et desktop/connected ; proposer un câblage court et signaler les fichiers réservés dans le message de prise en charge.

## G146 — Inventaire et contrat

Inventorier ce qui existe réellement dans les dépôts et, si accessibles, sur VM101/Core/Memory : orchestrateur, STT Whisper, TTS Piper, APIs, modèles, licences, endpoints et comptes. Les souvenirs historiques ne prouvent pas que les services sont actifs. Réutiliser l'existant plutôt que créer une seconde pile incompatible.

Définir contrats audio/vidéo, identité de session, authentification, permissions du périphérique et états unavailable, permission_denied, busy, ready, capturing, processing, stopped. L'absence de caméra ne doit pas interrompre le dialogue.

## G147 — STT local

Adapter Whisper/faster-whisper ou une alternative argumentée vérifiée sur documentation officielle. Français, sélection de micro, push-to-talk initial, VAD et écoute continue optionnels, annulation, limites de durée/taille et backpressure. La transcription rejoint le même parcours de conversation que le texte ; elle n'accorde aucune permission et ne soumet pas automatiquement une mission.

Recette : audio de référence licite avec attendu, silence/bruit, appareil absent, coupure, double clic, annulation, débit/latence/RAM. Distinguer mesures réelles et simulateurs.

## G148 — TTS local

Adapter Piper ou alternative vérifiée. Préférence opérateur : voix française féminine chaleureuse et posée, un peu plus lente ; proposer des voix réellement disponibles et licenciées, sans promettre la reproduction d'une voix ChatGPT. Contrôle vitesse/volume, arrêt immédiat, reprise, chunks et voix indisponible. Empêcher la boucle haut-parleur -> STT ; interruption de la lecture lors d'une nouvelle demande.

Recette : délai premier son, durée synthèse, intelligibilité, nombres, noms Eidolon, longues réponses et annulation. Ne pas publier de clé ni d'enregistrement privé.

## G149 — Caméras disponibles

Inventaire côté client Windows/navigateur et éventuellement caméras serveur réellement accessibles. Ne pas confondre matériels évoqués et périphériques connectés. Identifiant stable lorsque possible, sélection, hotplug, webcam occupée, permissions refusées, arrêt et voyant de capture visible. Flux borné en résolution/fps ; traitement de frames ponctuelles au début, sans enregistrement vidéo permanent.

Désactivé par défaut jusqu'à activation explicite dans le client et permission du système. Pas de capture distante cachée ; pas de source RTSP découverte par balayage du réseau.

## G150 — Reconnaissance visuelle

Séparer présence/personne, objets/scène et identification facultative d'une personne. Proposer le modèle adapté, ressources et licences vérifiées ; commencer par présence/description de scène. Une détection ou une ressemblance faciale n'authentifie pas l'utilisateur et n'autorise aucune mission.

L'identification nominative éventuelle exige inscription volontaire explicite, templates locaux protégés, gestion des inconnus, retrait/suppression et politique de conservation. Aucun visage ni image privée dans Git ou Memory sans parcours explicite ; pas de surveillance générale.

Recette : absence de personne, éclairage, image figée, plusieurs personnes, inconnu, faux positifs/négatifs, arrêt et GPU indisponible. Ne pas présenter un seuil de confiance comme preuve d'identité.

## G151 — Service, UI et recette intégrée

Service séparé si nécessaire, compte sans sudo, quotas et endpoints authentifiés ; caches/models séparés de l'état Core. UI choisir micro/caméra, activer/désactiver, indicateurs de capture, transcription puis réponse vocale ; le texte continue en mode dégradé.

Installer ce qui est validable sur les VM autorisées avec sauvegarde/rollback. Préparer le client Windows lorsqu'une recette matérielle n'est pas possible ; dire précisément ce qui n'a pas été testé. Ne pas retoucher Bootstrap pour déployer sur une VM déjà configurée.

Livrer : code, tests unitaires/intégration, recette avec fichiers de référence non personnels, relevés contexte/latence/tokens si LLM, fps/charge pour vision, versions/digests/licences, guide installation/arrêt/désinstallation et document d'état. Rapport signé C-MSG, avec services réellement actifs distincts des candidats.

## Critères communs

Aucune émission externe de voix/image par défaut. Secrets hors logs. Bornes CPU/RAM/stockage et une requête active par périphérique. Capture visible et arrêt effectif contrôlé. Les messages de logs, transcriptions, images/OCR et identifications sont des observations non fiables. Ne pas mélanger autorisation de capture, identité de session et permissions d'action.
