# C-023 — suivi G055, politique HTTP commune

Codex/GPT, 07/10/2026. Rapport Claude G055 intégré depuis 2568e16 ; les deux
bancs Linux/WebKit restent rapportés par Claude, pas reproduits ici (Rust et
WebKit absents).

La relecture révèle une exception à la fonction `_send` : la réponse de
saturation préauthentification `BUSY`. Son corps JSON fixe et `nosniff` étaient
présents, mais CSP et Referrer-Policy absents. `before.txt` reproduit l’absence
sur un vrai serveur avec quatre connexions occupées. Aucun contournement de
navigateur ou fuite de données n’est démontré par cette absence.

C-023 mutualise les en-têtes existants, sans changer la CSP. La réponse BUSY
reste fixe, sans lecture de requête/jeton/Store, sans nouveau worker ni attente
non bornée. La politique complète est maintenant testée sur HTML/JS/CSS,
API, refus 400/401/403/404/405, erreur de stockage 503 et saturation 503.

`PYTHONPATH=src python -m unittest tests.test_http_api tests.test_http_availability tests.test_receipt_lookup -q`

**68 tests réussis** (`after.txt`). Sockets loopback réelles, données synthétiques.
Pas de test Chromium/WebView2, aucune assertion de filtre réseau dans Tauri.
