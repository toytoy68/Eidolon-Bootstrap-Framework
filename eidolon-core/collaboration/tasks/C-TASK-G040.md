# G040 — Préparer le lancement PC par tunnel SSH

Auteur : Codex/GPT, 06/10/2026. Attribué à Claude à la demande de toytoy
à 19 h 08 (six tâches supplémentaires). Base initiale : 4d0f606.
Statut : attribué ; respecter les dépendances précisées ci-dessous.

Après G031/G035, sans remplacer leur recette. Livrer scripts candidats et documentation sous desktop/connected/launchers/ : lanceur PowerShell avec serveur/utilisateur/port explicites, bind SSH LOCAL 127.0.0.1, URL locale, vérification port/ssh, arrêt de son seul tunnel et messages ECT. Mode aperçu sans connexion par défaut ; aucune clé créée, aucun mot de passe/token imprimé, aucune modification de pare-feu ou installation. Ne pas supprimer la vérification de clé hôte SSH. Ne pas prétendre remplacer la future application Windows. Syntaxe/tests Windows à marquer non exécutés si PowerShell/Windows absents. Les choix de framework restent ouverts.

Un commit/message par livraison, sources et preuves séparées des constats
rapportés. Publier sur ta branche pour intégration. Ne pas modifier les fichiers
réservés Codex (http_api.py, receipt_lookup.py, tests Python associés).
Aucun déploiement, VM/NAS/GPU ou service personnel à contacter ici.
