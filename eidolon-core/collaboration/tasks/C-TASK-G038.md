# G038 — Banc de bout en bout client–API réel

Auteur : Codex/GPT, 06/10/2026. Attribué à Claude à la demande de toytoy
à 19 h 08 (six tâches supplémentaires). Base initiale : 4d0f606.
Statut : attribué ; respecter les dépendances précisées ci-dessous.

Après G031 et C-009b publiés. Ajouter un banc autonome sous desktop/connected/tests/integration/ : processus Python HTTP réel sur loopback, état synthétique, navigateur réel si disponible. Cas : liste/pagination, annulation faite par CLI distincte observée sans réémission, serveur arrêté puis relancé, nouveau Store, mauvais token, reçu historique/absent. Attendre des événements/conditions, pas des délais arbitraires longs. Nettoyer uniquement les processus et dossiers créés par le banc. Ne pas changer src/ ; ouvrir des constats reproductibles si nécessaire. Produire une commande de reproduction et distinguer test Linux navigateur de Windows réel.

Un commit/message par livraison, sources et preuves séparées des constats
rapportés. Publier sur ta branche pour intégration. Ne pas modifier les fichiers
réservés Codex (http_api.py, receipt_lookup.py, tests Python associés).
Aucun déploiement, VM/NAS/GPU ou service personnel à contacter ici.

Mise à jour G049 : G031 a déjà livré desktop/connected/tests/server.test.js.
Réutiliser et étendre ce banc, sans recréer les quatre scénarios déjà présents ;
priorité aux reçus, à la pagination et au nettoyage de tous les chemins d’échec.
Codex a corrigé le nettoyage quand Chromium ne démarre pas et le saut explicite
si son exécutable manque. Conserver ces protections dans les extensions.
