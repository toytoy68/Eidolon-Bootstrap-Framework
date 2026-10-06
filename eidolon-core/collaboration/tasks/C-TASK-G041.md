# G041 — Contrat des futures commandes distantes

Auteur : Codex/GPT, 06/10/2026. Attribué à Claude à la demande de toytoy
à 19 h 08 (six tâches supplémentaires). Base initiale : 4d0f606.
Statut : attribué ; respecter les dépendances précisées ci-dessous.

Étude autonome, pas d’activation. Examiner C-005/C-008 et API en lecture seule. Proposer scopes lecture/décision/annulation séparés, liaison à un serveur/mission/paramètres, identité de l’opérateur, révocation, traitement des reçus perdus et refus des doublons/changements. Le token actuel de consultation ne doit jamais devenir implicitement un droit d’écriture. Comparer session opérateur locale et appairage persistant pour la bêta ; test discriminant et limites, décisions réellement nécessaires à toytoy séparées des détails d’implémentation. Livrable sous docs/proposals/2026-10-06-remote-commands/, avec corpus de scénarios, sans endpoint d’écriture ni choix produit présumé.

Un commit/message par livraison, sources et preuves séparées des constats
rapportés. Publier sur ta branche pour intégration. Ne pas modifier les fichiers
réservés Codex (http_api.py, receipt_lookup.py, tests Python associés).
Aucun déploiement, VM/NAS/GPU ou service personnel à contacter ici.
