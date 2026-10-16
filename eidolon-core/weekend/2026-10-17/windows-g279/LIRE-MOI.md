# Eidolon — conversation automatique

1. Remplace les anciens fichiers par ceux de ce ZIP, dans un dossier du Bureau.
2. Ouvre `Eidolon-tunnel.cmd` comme auparavant et garde sa fenêtre ouverte.
3. Lance `Lancer-Eidolon.cmd`.

**Première fois seulement :** entre le mot de passe SSH quand il est demandé. Le lanceur récupère la clé et la conserve chiffrée pour ton compte Windows. Aucun copier-coller dans l'application.

**Ensuite :** lance `Lancer-Eidolon.cmd`, la conversation s'ouvre automatiquement. Le tunnel doit toujours être ouvert. Ne lance pas l'EXE seul : le lanceur lui transmet l'appairage.

Si PowerShell bloque le fichier téléchargé : vérifie la provenance de ce ZIP, clic droit → Propriétés → Débloquer avant extraction. Aucune politique Windows permanente n'est changée.

`Oublier-appairage.cmd` supprime uniquement l'appairage enregistré sur ce PC. Il ne révoque pas la clé serveur. Au lancement suivant, le mot de passe SSH sera redemandé pour refaire l'appairage.

L'authentification serveur reste active. Les fichiers téléchargés ne contiennent aucune clé personnelle. La validation de l'ouverture sur ton PC reste à faire.
