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
- DPAPI/import non exécutés sous Linux, puis réussis sur le runner Windows.
- Workflow Windows étendu : tests DPAPI, démarrage sans processus enfant,
  instance unique, compilation Inno, installation et désinstallation jetables.
- Client non déployé sur le PC de toytoy ; seul le correctif de synthèse décrit
  plus bas a été déployé sur la X399.

## Suite

CI Windows réussie ; poursuivre le détecteur local et l'appairage HTTPS.
L'installateur de ce lot doit rester un artefact de recette tant que les fonctions
vocales et le parcours d'appairage définitif ne sont pas intégrés.

## Contrôleur vocal préparé séparément

Le module connected/src/resident-voice.js orchestre des adaptateurs locaux de
détection et de session ; il n'est pas raccordé à app.js ou au compagnon.
Les adaptateurs doivent libérer leur micro avant de terminer, y compris lors
d'une annulation. Le contrôleur sérialise arrêt/reprise, refuse une activation
sans consentement ou sans détecteur qualifié, invalide les résultats tardifs
et ne rejoue jamais une conversation échouée. Le statut reste « stopping »
jusqu'à restitution réelle du contrôle par l'adaptateur.

Sept tests Node exécutés avec adaptateurs simulés : succès. Aucun microphone
réel ni moteur acoustique utilisé par cette suite.

Réapplication de gate-v3.json au rapport v2 sauvegardé (pas une nouvelle
inférence) : rappel 0,855, latence p95 151 ms ; refus pour rappel insuffisant,
audio général non indépendant, quatre graphies et la voix UPMC.
Ces chiffres viennent du rapport détaillé sauvegardé ; ils diffèrent légèrement
du résumé C199.

## Validation Windows terminée

Run 42311133081, commit e686390 : succès de toutes les étapes, dont import DPAPI,
instance unique, absence de processus enfant au démarrage silencieux, compilation
Inno Setup, installation et désinstallation avec conservation de la connexion.
Artefact eidolon-windows-candidate : installateur générique et exécutables.
Le commit d4852de ajoute uniquement le contrôleur JS, ses tests et cette note ;
les fichiers Windows testés sont identiques. Aucun test acoustique Windows réel.

## Correctif serveur découvert pendant la recette

La synthèse sur X399 échouait réellement par HTTP 504 après 30,056 s.
Piper lançait 61 threads, et le cgroup du service comptait huit refus de création
de tâche avec TasksMax=64. Un appel hors service réussissait.
Correctif : environnement minimal fixe avec OPENBLAS_NUM_THREADS=1,
OMP_NUM_THREADS=1, MKL_NUM_THREADS=1 ; aucun héritage d'environnement parent.
Les quotas CPU=200 %, mémoire=3G et TasksMax=64 restent inchangés.

Régression exécutée rouge avant correction. Suite communication : 84 tests,
83 réussis et un ignoré. Commit de production afb79a7, service comm redémarré.
Recette réelle via API Core après correctif : Piper HTTP 200 en 7,021 s ;
Whisper HTTP 200 en 5,705 s, transcription exacte de la phrase synthétique
« Bonjour, le système vocal fonctionne. ». Total 12,757 s, pids.events max=0.
Ce test valide synthèse/transcription sur CPU, pas la latence d'une conversation
LLM complète ni le microphone de toytoy. Température relevée après : Tdie 35,5 °C.
