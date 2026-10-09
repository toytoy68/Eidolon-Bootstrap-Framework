# Eidolon Core — état du 9 octobre 2026, reprise Codex après 17 h 37

Branche `feat/eidolon-core-v0.1`, sans fusion dans main ni déploiement.
Claude C122 est intégré ; toytoy signale Claude arrêté, limite atteinte.
Codex a repris les corrections C122 et G125, puis les courses de réponses
du chat dans C-068/C-069. **La validation Python de ce nouveau lot est en attente.**

| Partie | Disponible dans le code | Suite nécessaire |
| --- | --- | --- |
| Accueil Image/Vidéo | Deux espaces, brouillons créer/modifier/analyser | Dialogue et soumission authentifiée reliés au worker |
| Exécution média | Adaptateurs, artefacts privés, transferts, collecte, worker durable | Modèles/workflows réels et parcours accueil complet |
| Installation locale | Espace privé et configuration à compléter | Installation séparée des moteurs ; qualification du matériel |
| Conversation/mission | Persistance, appairage, propositions, annulation, résultats ; réponses tardives isolées | Python/HTTP/Chromium et paquet installé sur la nouvelle révision |
| Liens et sauvegardes | Identifiant exact du travail figé, liens inclus dans le digest, migration explicite v5 | Tests Python de migration et sauvegarde sur copie |
| Disponibilité | Verrou SQLite distingué d'une base indisponible, aucune répétition automatique | Exécuter les tests SQLite/HTTP préparés |
| Ressources | Réservation média durable, effets incertains conservés | Arbitrage partagé avec dialogue/planification ; qualification GPU |

## Vérifications du lot actuel

Environnement système indisponible : aucun Python, Node, Chromium ni build
Python exécuté. **69 cas JavaScript réussis dans V8** avec transports scriptés
et substituts de modules Node : 39 conversation et 30 session. Les nouveaux
cas de concurrence ont d'abord reproduit les défauts. Bundle recalculé avec la
fonction `build.js:bundle()` ; syntaxe vérifiée.

**13 nouveaux tests Python préparés, non exécutés.** Les corrections serveur
et la migration restent candidates à valider avant usage réel.
[Preuves, limites et commandes](validation/2026-10-09/codex-takeover-c068/README.md).

## Dernière validation complète antérieure : C-067

**1 332 tests Python**, zéro ignoré, Memory activée ; **77 Node**, 24 Chromium
ignorés chez Codex. Archive reproductible et installation neuve, 82 modules
identiques ; six modes média ; recette conversation 13/13 + 18/18.
HTTP loopback et FFmpeg/FFprobe réels, moteurs simulés.
Ces résultats précèdent C-068/C-069 et ne qualifient pas le nouveau code.
[Preuves C-067](validation/2026-10-09/codex-hour-1555/README.md).

## Restant

G122/G123 : dialogue → soumission HTTP média → worker → résultats page.
G124/G125 : correctifs implémentés, validation complète à reprendre.
G126 : contre-revue indépendante par Claude à sa reprise.
G127 : recette complète navigateur/HTTP. VM/V100, moteurs réels et Windows
restent non qualifiés. L'initialisation média n'installe ni moteurs ni poids.
Le nombre de tests ne donne pas un pourcentage de maturité.
[File active](../collaboration/tasks/QUEUE.md).
