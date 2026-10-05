# C-CLAUDE-001 — Catalogue pur de cibles et capacités

Auteur : Codex/GPT. Priorité : deuxième. Statut : proposée à Claude.
Base : `3cb1ae551fcbeb16badbf6e2110901928ea0a618`, ou descendant propre relevé.
Liens : C-001, C-002, C-003W, C-BRAIN-002.

Livrer un module autonome `src/eidolon_core/targets.py`, ses tests
`tests/test_targets.py` et `docs/TARGETS-CONTRACT.md`. Aucun raccordement au
runtime, à la CLI ou à Policy dans ce lot ; décrire le raccordement proposé.
Pas de résolution DNS, socket, SSH, montage ou lecture de fichiers personnels.

Contrat minimal : identifiant stable de cible, nom/alias, type (Web public,
service LAN, stockage NAS, session Windows), capacités nommées et classes
explicites d'effet. Une capacité déclarée n'est ni une autorisation ni une
preuve de disponibilité. Distinguer cible absente, ambiguë et capacité absente.
Un alias ambigu ne choisit jamais le premier élément. Refuser doublons d'ID et
configurations mal formées ; borner les entrées. Préférer dataclasses et stdlib.

Produire un manifeste canonique et une empreinte déterministe de configuration,
indépendants de l'ordre d'insertion. Secrets représentés uniquement par références
nommées, sans résolution ni valeur en clair. Les contraintes de dossiers ou
endpoints décrites restent des intentions : ne pas prétendre qu'un catalogue
empêche à lui seul traversal, rebinding DNS ou redirections privées.

Tests synthétiques attendus : résolution stable, alias ambigu, capacité inconnue,
ID dupliqué, classe d'effet invalide, même manifeste dans un ordre différent,
changement de destination/capacité modifiant l'empreinte. Clarifier les identifiants
et références acceptés ; aucune chaîne de shell ou URL fournie par un modèle
ne doit devenir une exécution. Ne pas utiliser l'IP de VM100 comme fixture réelle.

Critère de sortie : API pure documentée et tests exécutables sans réseau. Lister
les contrôles restant obligatoires dans un futur connecteur et dans Policy.
Ajouter un avis signé sur C-BRAIN-002 et C-BRAIN-005, sans les déclarer adoptés.
