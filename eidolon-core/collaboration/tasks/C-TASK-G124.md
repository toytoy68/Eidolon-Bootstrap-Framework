# C-TASK-G124 — Annulation ciblée utilisable dans la page

Auteur : Codex/GPT. Attribution : Claude. Date : 09/10/2026, Europe/Paris.
Base examinée : C121 / `8d2613381e833f8d7124aa34f089b2dd94f16d0a`. Statut : PRÊT selon dépendances.

Raccorder les API G100 aux missions de la conversation. Sélection explicite si plusieurs missions, résumé avant accord, empreinte exacte et clé conservée après réponse perdue. Distinguer demande enregistrée, arrêt constaté et effet inconnu. Réutiliser cancel_receipt au retour sans renvoi automatique. Garder annulation moteur média indisponible tant que le contrat moteur ciblé manque ; aucun interrupt global. Tests Chromium clavier, mobile, rechargement et mission étrangère.

Périmètre : Claude garde conversation/mission/API/UI ; Codex garde media_*.py, media-agents.js, tests média et paquet. Ne pas attendre le GPU pour avancer les contrats/tests. Publier preuves réellement exécutées ; aucun main, déploiement ou modification Memory Engine. La fiche ne démarre pas une session.

## Reprise Codex du 09/10 après 17 h 37 — C-068/C-069

Toytoy signale Claude arrêté et autorise Codex à poursuivre.
Correctifs de réponses tardives implémentés et exercés dans V8, avec cas de reçu concurrent. Recette Node/Chromium/HTTP réelle encore à exécuter.
[Preuves et limites](../../docs/validation/2026-10-09/codex-takeover-c068/README.md).
