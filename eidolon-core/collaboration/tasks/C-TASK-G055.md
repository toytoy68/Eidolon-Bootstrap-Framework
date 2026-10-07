# C-TASK-G055 — Banc des frontières réseau Tauri et CSP Core

Auteur : Codex/GPT, 07/10/2026 Europe/Paris. Attribution : Claude. Statut : PRÊT.
Base intégrée : `608e115b948675dac601b004d3a4d3f54b744adf` (G050–G053 inclus).

## Périmètre

`docs/validation/2026-10-07/claude-g055/`

À partir de G053, tester le vrai client Core et une page sonde : fetch, WebSocket, EventSource, iframe, images et nouvelles fenêtres. Distinguer règle de navigation, CSP HTTP Core et ACL IPC ; ne pas promettre un filtrage général de la webview. Utiliser seulement des serveurs loopback synthétiques. Livrer banc reproductible et limites Linux/Windows séparées ; pas de modification http_api.py.

## Livraison

Un commit distinct, message signé avec SHA, commandes exécutées, résultats et limites. Préserver les preuves précédentes. Enchaîner la tâche prête suivante si une dépendance bloque. Aucun main, déploiement, fournisseur réel ou accès aux données personnelles.
