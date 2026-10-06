# G035 — Recette bêta Debian / PC Windows

Auteur : Codex/GPT, 06/10/2026. Attribué à Claude. Après G034 ou pendant attente.
Livrer docs/BETA-ACCEPTANCE.md : commandes exactes, prérequis, état synthétique
séparé, token privé, tunnel SSH, lancement/arrêt/retrait, panne/reconnexion.
Le serveur reste loopback, même port local/distant. Pas de modification de
pare-feu, VPN, SSH, service, GPU ou système par ces instructions automatiques.

S'appuyer sur le code effectivement publié, pas seulement le contrat. Les
étapes impossibles ici restent « À EXÉCUTER SUR VM/WINDOWS », sans PASS fictif.
Séparer ce premier observateur du futur chat/modèle et des commandes distantes.
Préparer une checklist d'acceptation brève pour toytoy et une liste de blocages.

Complément G051 : C-009c publié a8ae8fa949cc3fc54474285f8c1412eb23075b6c.
Ajouter le diagnostic `http_api --check` avant démarrage ; lire
docs/HTTP-PREFLIGHT.md pour JSON et codes 0/2. Il ne teste pas le port libre
ni le tunnel/navigateur. Ne pas transformer PASS en qualification bêta.
