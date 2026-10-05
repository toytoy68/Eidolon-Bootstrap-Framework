# Trois tâches proposées à Claude Code

Auteur : Codex/GPT, 05/10/2026, Europe/Paris. Demande explicite de toytoy.
Base commune : `3cb1ae551fcbeb16badbf6e2110901928ea0a618`.
Statut : **prêtes à prendre, aucune prise en charge Claude présumée**.

| Ordre | Fiche | Livrable |
| --- | --- | --- |
| 1 | [C-REV-003](C-REV-003.md) | Contre-revue ciblée des reçus et de la réconciliation |
| 2 | [C-CLAUDE-001](C-CLAUDE-001.md) | Catalogue pur de cibles et capacités, testé sans réseau |
| 3 | [C-CLAUDE-002](C-CLAUDE-002.md) | Adaptateur Ollama optionnel, testé avec transport simulé |

Codex prend **C-001a**, critères de mission indépendants du modèle :
`objectives.py`, `runtime.py`, `store.py`, `presentation.py`, tests existants et
`test_objectives.py`, README/TODO et documentation de ce lot. Ne pas modifier ces
fichiers dans les tâches Claude ; proposer les raccordements dans la réponse.

Utiliser des branches/checkouts distincts et des commits séparés par fiche.
Lire AGENTS.md, CLAUDE.md et le protocole avant travail. Déclarer le lot choisi
avec base et fichiers dans son message Claude ; Codex reportera la prise en
charge dans ECHANGES à l'intégration pour éviter un conflit documentaire.
Ne pas modifier le fichier GPT. Archiver sa propre réponse précédente à l'identique.
Contributions au brainstorming : ajouter un bloc signé, conserver les avis existants.

Aucune connexion à la VM, au NAS, à Windows ou à un modèle réel dans ces lots.
L'adresse `192.168.1.135` désigne VM100 Core selon toytoy ; ce n'est ni une URL
Ollama, ni une validation de connectivité, ni une permission de déploiement.
Ne pas modifier Memory Engine, Bootstrap ou main. Si le push est bloqué, remettre
un patch avec SHA de base, commandes et résultats ; ne pas inventer de publication.
