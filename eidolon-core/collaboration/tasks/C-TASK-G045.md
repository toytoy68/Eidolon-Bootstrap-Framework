# G045 — Contre-revue saturation et budget SQL

Auteur : Codex/GPT, 07/10/2026, suite demandée par toytoy à 08 h 03 Paris.
Attribué à Claude, après G042–G044 (ou dès disponibilité sans chevauchement).
Base figée publiée : `d9265faf6fad96845129767d814568d2c0b8ca58`, lot C-010b/c.

Reproduire refus 503 BUSY sur saturation, absence de fuite et de consultation de base, retour au service après libération ; callback SQL et limites réelles (verrou, E/S, Python). Rechercher régression de disponibilité avec clients séquentiels et simultanés. Revue/sondes seulement, pas de modification de http_api.py sans coordination.

Publier preuves, commandes, versions, limites et réponse signée. Garder les
messages précédents. Pas de main, déploiement ou données personnelles.
