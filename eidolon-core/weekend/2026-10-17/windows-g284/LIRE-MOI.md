# Eidolon — ouverture automatique du tunnel G284

Extraire tous les fichiers dans le dossier permanent Eidolon, en remplacant les anciens fichiers. Conserver le fichier additionnel eidolon-auto-tunnel.ps1 a cote de Eidolon.exe. Si le chemin reste le meme, votre raccourci actuel reste utilisable.

Double-cliquer **Eidolon.exe** : le lanceur ouvre maintenant le tunnel SSH automatiquement, attend qu'il ecoute, puis ouvre la conversation avec l'appairage Windows existant. Plus besoin d'ouvrir Eidolon-tunnel.cmd avant.

Un tunnel SSH deja present vers le meme serveur et le meme port est reutilise. Un port occupe par un autre programme est refuse ; aucun programme existant n'est arrete.

Si une cle SSH ou un agent deja configure permet la connexion, le tunnel s'ouvre en arriere-plan. Sinon, une fenetre SSH s'ouvre automatiquement et demande le mot de passe. Garder cette fenetre ouverte tant que vous utilisez Eidolon. Le lanceur ne sauvegarde pas ce mot de passe et ne cree pas de nouvelle cle SSH.

La cle d'hote du serveur doit deja etre connue, comme avec le tunnel precedent. Une cle changee ou inconnue reste refusee. La premiere recuperation de l'appairage peut encore demander une authentification SSH distincte.

Pour un nouveau raccourci Bureau : Creer-raccourci.cmd. Pour la barre des taches : clic droit sur Eidolon.exe ou son raccourci > Afficher plus d'options > Epingler a la barre des taches.

Le tunnel reste disponible apres fermeture de la conversation pour les relances. Il n'y a pas de reconnexion permanente : apres coupure reseau, relancer Eidolon. Le binaire reste non signe.
