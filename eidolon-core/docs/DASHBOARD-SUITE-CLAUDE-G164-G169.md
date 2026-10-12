# Suite Claude — G164–G169, 12 octobre 2026
Base de reprise : feat/eidolon-core-v0.1, après intégration C147/C148 et installation VM par Codex. Ne pas repartir d'une ancienne copie : préserver comm_credentials.py, correctif de consigne de présence, fermeture HTTPError et réservation de validation avant digest.

| Lot | Travail attendu |
|---|---|
| G164 | Recette STT français : noms toytoy/Eidolon, nombres, silence/bruit, phrases longues ; proposer un initial_prompt/vocabulaire contrôlé, comparer avant/après sans transformer le silence en texte. Mesures du serveur disponibles dans dashboard-vm/REPORT.md. |
| G165 | Finaliser le guide Windows du week-end et une recette microphone/caméra réels, permissions, branchement à chaud, anti-écho, clavier et zoom 125/150 %. Les tests Chromium sur VM ne qualifient pas WebView2/Edge/matériel. |
| G166 | Concevoir puis préparer le canal de lecture Memory → dashboard Core : rôle SSH limité au socket/commande fixe, pinning serveur, fraîcheur/péremption, aucune clé admin au frontend. Codex exécutera la provisioning VM après revue. Garder not_covered tant que le canal réel n'est pas recetté. |
| G167 | Auditer readiness/reprise des trois services : attente des ports après Type=simple, service média absent, révoquer une clé pendant une requête, annulation et file basse priorité. Aucun assouplissement de ProtectHome pour contourner un accès SQL ; utiliser la vue ReadOnlyClientCredentials. |
| G168 | Préparer une activation explicite des outils monitor.machine/monitor.darme dans le Runtime de Core (SDK G161), avec tests de propositions/permissions/référence aux snapshots ; ne pas élargir silencieusement la politique par défaut ni accepter commande/chemin/target utilisateur. Coordonner http_api.py avant publication. |
| G169 | Préparer l'affichage futur VM101 GPU : température, puissance, utilisation et VRAM avec source/cadence/date ; valeurs absentes null, pas celles du Core CPU. Étudier contention vision/dialogue et mise à l'échelle d'images ; ne pas prendre notre unique cercle synthétique pour une qualification de personnes. |

Codex réserve les installations et les futurs collecteurs/tunnels VM. Pour les modules partagés, publier réservations et commits ; ces tâches sont autorisées par la poursuite demandée par toytoy. Le fichier ne démarre aucune session.
