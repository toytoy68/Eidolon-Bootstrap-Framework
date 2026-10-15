# Eidolon — dossier PC et VM, 17–18 octobre 2026

Eidolon Core Technologies (ECT) • Local AI • Modular • Reliable • Reproducible

**Dossier candidat préparé hors VM.** Commencer par [RECETTE.md](RECETTE.md), puis remplir [MACHINE-INVENTORY.md](MACHINE-INVENTORY.md). Le rapport unique final est [RAPPORT-UNIQUE.md](RAPPORT-UNIQUE.md).

Dans le ZIP, les sources sont sous `sources/core/eidolon-core` et `sources/memory`. Les SHA exacts et empreintes de chaque fichier sont dans `MANIFEST.json` à la racine. Ce sont des sources, pas un exécutable Windows ni une image VM. Dépendances, modèles, secrets, données et journaux privés ne sont pas inclus. Les historiques de validation volumineux sont exclus ; certains anciens tests documentaires demandent un checkout Git complet.

| Fichier | Utilisation |
| --- | --- |
| `RECETTE.md` | Ordre de validation PC/VM, commandes et critères d'arrêt |
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
| `results.template.json` | 26 validations, toutes `NOT_RUN` initialement |
| `check_results.py` | Vérifie que les preuves sont remplies ; n'autorise jamais la bêta |

Le seuil de charge 0,7, les ports et le modèle des exemples sont des **valeurs de recette proposées**. Les vérifier sur place. La fenêtre 04–08 Europe/Paris et les délais de 30 minutes sont ceux du contrôleur actuel. Une activité inconnue est traitée comme récente. Le producteur automatique de reçus d'activité et le compte de service C187 restent à finaliser ; ne pas activer le timer en leur absence.

Aucun installateur historique présent dans les sources n'est requis par ce dossier. Ne pas lancer les scripts Bootstrap/deployment pour suivre cette recette.
