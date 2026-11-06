# Client résident — lot 1, 7 novembre 2026

Candidat de développement, pas une livraison du réveil vocal local.

## Changements

- Compagnon natif Windows dans la zone de notification. Fermer la conversation
  laisse le compagnon disponible. Une seconde invocation active la première.
- Démarrage silencieux --background : aucune conversation ni capture micro.
- Ouverture du lanceur G286 existant : connexion/appairage SSH automatiques.
- Import graphique du dossier d'un ancien client : validation de la connexion,
  reprise de l'identité DPAPI du compte ou import protégé de la clé fournie.
  Aucun exécutable de l'ancien dossier n'est importé. Le serveur et sa clé hôte
  restent ceux du dossier choisi ; cet import ne migre pas une ancienne adresse.
- Installateur Inno Setup par utilisateur, raccourci et démarrage Windows
  optionnels, désinstallation sans effacement automatique de l'appairage.
- Paquet générique limité à quatre exécutables, sans identifiant privé.

## Limites importantes

L'API HTTPS avec appairage par code reste à construire. Le présent lot réutilise
le tunnel G286 sans manipulation quotidienne ; il ne remplace pas son protocole.
L'import facilite une connexion existante mais n'enregistre pas un nouvel appareil
avec une identité indépendante côté serveur.

Aucun détecteur vocal n'est raccordé au compagnon. Le menu l'indique. Ouvrir le
client G286 garde son comportement vocal existant (veille transcrite sur le
serveur) ; ne pas confondre cela avec le futur réveil local. Pour quitter le
compagnon, fermer d'abord sa conversation afin d'arrêter capture et transport.
La fenêtre physique, le micro et la reprise Windows doivent encore être testés.

## Sauvegarde des modèles vérifiée

Les modèles et rapports G296 sont conservés dans l'archive VM100 sur X399.
Les SHA-256 recalculés correspondent aux fichiers de provenance :

- v1 : 3a47740fae969d7ba8c2d1e3d9ee2bcbca041ab3b3bda9fc7e432077d7c173b2
- v2 : f21475ebe0ba63691b6bda9135d903871826d5b6a93bb9d81550203c182bec1f

Les deux provenances indiquent activated=false. C199 reste la référence pour
les défauts du banc v2 et la qualification v3/humaine. Aucun entraînement lancé.

## Preuves

- Compagnon et tests compilés avec Mono sur VM100, sans lancement de l'interface.
- Validation des arguments et configuration exécutée : RESIDENT_INPUTS_PASS.
- DPAPI/import Windows explicitement non exécutés sous Linux.
- Workflow Windows étendu : tests DPAPI, démarrage sans processus enfant,
  instance unique, compilation Inno, installation et désinstallation jetables.
- Aucune modification de production, aucune installation sur le PC de toytoy.

## Suite

Exécuter la CI Windows, puis poursuivre le détecteur local et l'appairage HTTPS.
L'installateur de ce lot doit rester un artefact de recette tant que les fonctions
vocales et le parcours d'appairage définitif ne sont pas intégrés.
