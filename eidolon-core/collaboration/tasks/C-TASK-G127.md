# C-TASK-G127 — Recette intégrée accueil conversation et agents média

Auteur : Codex/GPT. Attribution : Claude. Date : 09/10/2026, Europe/Paris.
Base examinée : C121 / `8d2613381e833f8d7124aa34f089b2dd94f16d0a`. Statut : PRÊT selon dépendances.

Après G122/G123 et raccordement worker : paquet installé, flux accueil → proposition → accord → exécution explicitement activée → suivi → résultat. Couvrir Image/Vidéo créer/modifier/analyser avec moteurs simulés, vraie FFmpeg si disponible, une coupure/reprise et un résultat partiel. Chromium 1280/360, jeton de lecture refusé, absence de chemins/secrets. Séparer code fonctionnel, moteurs simulés et essais matériels VM/PC non exécutés. Aucun déploiement ni qualification GPU inventée.

Périmètre : Claude garde conversation/mission/API/UI ; Codex garde media_*.py, media-agents.js, tests média et paquet. Ne pas attendre le GPU pour avancer les contrats/tests. Publier preuves réellement exécutées ; aucun main, déploiement ou modification Memory Engine. La fiche ne démarre pas une session.

Point de départ : archive publique f2fed6630ac5809ebbc054f6cf392296945fd3fb,
recettes installées dans docs/validation/2026-10-09/codex-hour-1555/.
Adapter aussi les originaux G089/G095 au contrat cancel_proposal G100 ; copies
adaptées déjà recettées 13/13 + 18/18. Le banc worker insère des propositions
comme fixtures de confiance : il ne remplace pas le test dialogue/HTTP/page.
