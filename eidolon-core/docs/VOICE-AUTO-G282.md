# Vocal automatique G282 — 17 octobre 2026

> **Remplacé en partie — G296, 23/10/2026 :** décision de l'opérateur relayée par GPT : un **seul** mot
> d'appel, « Eidolon ». « Dis-moi » est retiré du client, de l'interface et des tests
> ([étude G296](ETUDE-CORNELIUS-G296.md)). Le texte ci-dessous décrit l'état du 17/10 et reste
> inchangé pour l'historique.

Demande de toytoy : « Eidolon » ou « Dis-moi », réponse « Oui ? », demande envoyée après une pause puis réponse vocale. Base e51fd86.

## Usage

Relancer le client, ouvrir l’œil, cliquer **Démarrer le vocal auto**. Ce geste autorise la session ; le démarrage de l’application ne capture rien. Deux appels activés initialement, sélectionnables séparément. Appel seul : « Oui ? », puis écoute de la demande. Appel et demande dans une même phrase : demande conservée, pas de salutation intermédiaire. Une pause de 1,5 seconde termine le segment. Après réponse, retour en veille. Arrêter l’écoute relâche le micro ; fermeture/changement de conversation, capture d’identité et déchargement arrêtent aussi le mode.

## Frontière PC / VM

La détection d’énergie s’effectue sur le PC, **la reconnaissance des appels passe par faster-whisper sur la VM Core**. En veille, les segments parlés sont donc transmis à cette VM, même sans appel reconnu. Ils ne sont pas envoyés au dialogue sans appel. Aucun moteur de reconnaissance cloud et aucune nouvelle dépendance. Ce n’est pas un détecteur lexical entièrement local au PC. La page l’indique avant démarrage.

Le seuil RMS initial 0,015 et les 250 ms de signal demandent une validation avec le micro réel. Silence sans parole : segment abandonné localement après 10 secondes, puis reprise. Parole continue limitée à 28 secondes : segment abandonné plutôt que commande tronquée. Après appel seul, dix secondes sans parole ramènent en veille. Les appels doivent être au début de la transcription. « Dis-moi » présente davantage de déclenchements involontaires, désactivable séparément.

## Conversation et arrêts

Un seul segment et un seul envoi à la fois. Les pistes sont arrêtées avant transcription et avant lecture vocale ; reprise après lecture et garde de 400 ms. Une interruption ignore les retours tardifs. Aucun renvoi automatique d’un envoi incertain. Un brouillon saisi ou un tour en cours/incertain bloque l’envoi vocal. Les propositions d’action gardent le parcours de confirmation existant. Le vocal ne valide aucune mission. La synthèse est bornée aux 2 000 premiers caractères ; la réponse intégrale reste écrite.

## Vérification

Tests Node : appels, appels joints, expiration après silence, arrêt pendant transcription/réponse, anti-écho, absence de double boucle, réseau incertain, segmentation, absence de transmission du silence, libération tardive des pistes. Suites communication et conversation existantes conservées.

Recette réelle via API Core, audio synthétique Piper puis WAV 16 kHz vers Whisper : « Dis-moi, quelle heure est-il ? » reconnu à l’identique en 5,4 s pour le cycle synthèse/transcription ; « Eidolon ! » reconnu « Eidolon. » en 4,9 s. Aucun message de dialogue ni action créé par ces deux sondes. Ces temps ne mesurent pas la latence micro réelle.

Chromium absent de l’environnement local : interface et acoustique sur Windows non encore qualifiées. Pas de nouvelle compilation EXE : changement des ressources servies par Core, redémarrage API et contrôle HTTP des octets après déploiement.
