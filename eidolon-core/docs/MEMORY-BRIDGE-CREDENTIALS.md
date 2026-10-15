# Préparer le jeton du pont Memory

Contrat du lecteur Linux `bridge_credentials.read_bridge_token`, G235 ; précisions
C181/G241 du 15 octobre 2026. Aucune installation ou modification d'un secret réel
n'a été exécutée pendant cette révision.

Le chemin configuré dans BridgeMemory doit désigner un fichier régulier appartenant
à l'utilisateur effectif qui exécute Core, mode exactement 0600, sans lien physique
supplémentaire. Son dossier parent immédiat appartient au même utilisateur, mode
exactement 0700. Tous les composants du chemin, depuis la racine, doivent être des
répertoires réels : un lien symbolique dans un ancêtre est refusé, même si sa cible
est privée. Un home accessible via un lien nécessite donc un chemin réel sans lien
pour ce jeton. Cette règle ne change pas les droits des autres dossiers du projet.

Le fichier contient au maximum 4096 octets, blancs et saut de ligne compris.
Après retrait des blancs aux extrémités, le jeton comporte de 32 à 4096 caractères
ASCII imprimables sans espace intérieur. Le lecteur vérifie taille, propriétaire,
type, nombre de liens, identité et métadonnées avant/après lecture, puis l'identité
du parent. Un refus intervient avant tout appel réseau et les erreurs n'incluent
ni le chemin privé ni la valeur du jeton.

Avant une future activation, vérifier ces propriétés sur le chemin choisi et
s'assurer que Core s'exécutera sous le bon compte. Un dossier parent 0755, un
fichier appartenant à un autre compte ou un chemin avec lien ne sont pas acceptés.
Ne pas recopier le jeton dans les rapports, logs ou issues. Le guide décrit les
prérequis ; l'activation du pont et sa recette sur VM restent des étapes séparées.

Les cinq sondes de Claude sont conservées dans
`tests/test_bridge_credentials_claude_g235.py`. La CI les exécute aussi en root
sur ses fichiers temporaires pour couvrir réellement les changements de propriétaire ;
la suite ordinaire reste exécutée sous le compte habituel du runner.
