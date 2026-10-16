# Eidolon — dossier PC et VM, 17–18 octobre 2026

Eidolon Core Technologies (ECT) • Local AI • Modular • Reliable • Reproducible

**Dossier candidat préparé hors VM.** Lire [RACCORDEMENTS-G270.md](RACCORDEMENTS-G270.md) pour les nouveaux parcours et [RECETTE.md](RECETTE.md) pour la recette initiale, puis remplir [MACHINE-INVENTORY.md](MACHINE-INVENTORY.md). Le rapport unique final est [RAPPORT-UNIQUE.md](RAPPORT-UNIQUE.md).

La livraison G273 actualise les sources et ce dossier, avec le même sous-paquet Windows G270 prêt à extraire. Dans le ZIP source, les fichiers sont sous `sources/core/eidolon-core` et `sources/memory`. Les SHA exacts et empreintes de chaque fichier sont dans `MANIFEST.json` à la racine. Le sous-paquet source ne contient pas de binaire ; le sous-paquet Windows joint contient l'exécutable et les deux lanceurs vérifiés. Aucune image VM n'est fournie. Dépendances, modèles, secrets, données et journaux privés ne sont pas inclus. Les historiques de validation volumineux sont exclus ; certains anciens tests documentaires demandent un checkout Git complet.

| Fichier | Utilisation |
| --- | --- |
| `RECETTE.md` | Ordre de validation PC/VM, commandes et critères d'arrêt |
| `DIAGNOSTIC-G271.md` | Configuration et fichiers locaux contrôlés avant lancement, sans service ni écriture |
| `SERVICES-HORS-VM-G273.md` | Synchronisation, conservation, sessions/clés, mesure biométrique et file GPU partagée |
| `library-sync.service.in` | Suivi documentaire candidat, compte/chemins à adapter |
| `gpu-queue.example.json`, `identity-evaluation.synthetic.example.json`, `identity-captures.example.json` | Budgets illustratifs, évaluation synthétique et manifeste inactif sans consentement |
| `DOCUMENTS-G272.md` | Extraction PC/NAS, formats, limites, analyse et mémorisation séparées |
| `PROFILS-ENROLEMENT-G272.md` | Enrôlement volontaire du profil connecté, modèles et limites |
| `ETAT-PRIVE-G272.md` | Copie arrêtée des reçus, quotas et gabarits vers un nouvel état |
| `identity-runtime.face.example.json`, `identity-runtime.voice.example.json` | Configurations optionnelles ; chemins et poids à vérifier, calibration absente |
| `ROLLBACK.md` | Retour arrière sans écraser les données courantes |
| `MACHINE-INVENTORY.md` | Comptes, services, chemins, ports à relever sur place |
| `inventory_pc.ps1` | Inventaire Windows sans installation ni connexion |
| `inventory_vm.py` | Inventaire Linux en lecture seule, services explicitement nommés |
| `index.example.json` | Exemple pour un nouvel alias de passages et Ollama CPU |
| `remember.example.json` | Souvenir synthétique, aperçu puis application explicite |
| `host-policy.example.json` | Proposition de seuils de maintenance, à revoir |
| `maintenance.example.json` | Chemins à remplacer et liste d'identifiants autorisés |
| `activity.example.json` | Format d'un reçu d'activité ; horodatages fictifs à ne pas réutiliser |
| `maintenance.service.in`, `maintenance.timer.in` | Brouillons de service/timer, aucun installateur ni activation |
| `results.template.json` | 50 validations, toutes `NOT_RUN` initialement |
| `RACCORDEMENTS-G270.md` | Profils, chat, Internet, NAS, activité entre VM et Windows résident |
| `beta-runtime.example.json` | Associations client/profil et permissions des services |
| `maintenance-profile.example.json` | Maintenance de toute une racine explicitement liée au profil |
| `core-profile.service.in`, `memory-profile.service.in`, `maintenance-remote.service.in` | Candidats distincts, jamais installés automatiquement |
| `../../desktop/windows/` | Résident Windows et démarrage à la connexion, aperçu par défaut |
| `check_results.py` | Vérifie que les preuves sont remplies ; n'autorise jamais la bêta |

Le seuil de charge 0,7, les ports et le modèle des exemples sont des **valeurs de recette proposées**. Les vérifier sur place. La fenêtre 04–08 Europe/Paris et les délais de 30 minutes sont ceux du contrôleur actuel. Une activité inconnue est traitée comme récente. Le producteur d'activité Core et sa lecture authentifiée entre VM sont implémentés en G270 ; vérifier leur fraîcheur réelle avant activation. Le compte de service C187 reste à décider.

Aucun installateur historique présent dans les sources n'est requis par ce dossier. Ne pas lancer les scripts Bootstrap/deployment pour suivre cette recette.
