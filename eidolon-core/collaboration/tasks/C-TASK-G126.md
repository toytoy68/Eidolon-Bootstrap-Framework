# C-TASK-G126 — Contre-revue indépendante du worker média Codex

Auteur : Codex/GPT. Attribution : Claude. Date : 09/10/2026, Europe/Paris.
Base examinée : C121 / `8d2613381e833f8d7124aa34f089b2dd94f16d0a`. Statut : PRÊT selon dépendances.

Dès livraison C-064, éprouver consentement courant, lien au propriétaire, clé rejouée avec contenu modifié, processus concurrents, arrêt entre réservation et retour moteur, fichier manquant/modifié, réservation GPU durable. Exiger zéro second appel moteur pour le même ticket, aucune reprise automatique incertaine, aucune réussite sémantique déduite. Publier reproducteurs et limites, sans éditer media_*.py : Codex corrige sa couche.

Périmètre : Claude garde conversation/mission/API/UI ; Codex garde media_*.py, media-agents.js, tests média et paquet. Ne pas attendre le GPU pour avancer les contrats/tests. Publier preuves réellement exécutées ; aucun main, déploiement ou modification Memory Engine. La fiche ne démarre pas une session.

Complément C-067 : vérifier aussi workspace-init/inspect (coupure entre chaque
composant, aucune réutilisation silencieuse d’un dossier partiel, identité de
magasin, configuration remplacée). C-065/C-066 : précontrôle sans essai consommé
et échéance HTTP sans second POST ni libération implicite.
