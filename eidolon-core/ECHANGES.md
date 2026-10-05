# Échanges de travail — Eidolon Core

Canal asynchrone entre toytoy, Codex/GPT et Claude Code, créé le 05/10/2026.
[Protocole](collaboration/README.md) · [TODO](TODO.md) ·
[Cadrage consolidé](docs/CADRAGE-DECISIONS-2026-10-05.md).

## Reprise rapide

Base lors de l'ouverture du canal : `62da8f8d0146b4d60ae891c31238af88803296aa`,
branche `feat/eidolon-core-v0.1` du dépôt `toytoy68/Eidolon-Bootstrap-Framework`.
Toujours vérifier la tête actuelle avant travail ; ce repère n'est pas un verrou.

- Boucle séquentielle, persistance, permissions, outil pur, vérification et
  reprise livrés. Modèle simulé ; rappel mémoire Python local réel.
- [Validation](docs/VALIDATION-2026-10-05.md) : 34 tests Core et 6 intégrations
  mémoire réussis sur la base décrite ; contrôle CLI ciblé lors du lot présentation.
  Aucune nouvelle exécution de ces tests dans le présent lot documentaire.
- Internet/LAN/NAS, fichiers Windows, modèle réel et scénarios A–D élargis :
  cadrés, non implémentés à cette base. Lots C-001 à C-008/C-003W dans la TODO.
- VM indisponible selon toytoy ; aucun déploiement, fusion main ou accès aux
  données personnelles à déduire d'une discussion technique.
- Memory Engine reste développé dans l'autre session. Cette collaboration Core
  ne prend pas possession de ses tâches ou de sa branche.

## Sujets ouverts

| ID | Sujet | Auteur de l'ouverture | État |
| --- | --- | --- | --- |
| C-REV-001 | Revue de la boucle v0.1 et de ses limites avant extension | Codex/GPT | Réponse Claude non reçue |
| C-BRAIN-001 | Critères de mission indépendants du plan proposé | Codex/GPT | Proposition à discuter |
| C-BRAIN-002 | Frontières Internet, LAN et connecteur Windows | Codex/GPT | Proposition à discuter |
| C-BRAIN-003 | Approbation, échec partiel et reprise contrôlée | Codex/GPT | Proposition à discuter |

Demande concrète : [GPT → Claude](collaboration/GPT-TO-CLAUDE.md).
Réponse : [Claude → GPT](collaboration/CLAUDE-TO-GPT.md).
Idées : [BRAINSTORMING.md](collaboration/BRAINSTORMING.md).

## Prises en charge déclarées

| Lot / périmètre | Auteur | Base / branche | État |
| --- | --- | --- | --- |
| Mise en place du canal documentaire | Codex/GPT | Base 62da8f8, branche Core | Livré par le commit introduisant ce fichier |
| Revue C-REV-001 | Non attribué | À renseigner par le relecteur | Aucune prise en charge annoncée |

Un auteur renseigne ici la tâche choisie et les fichiers concernés avant un lot
partagé. Une déclaration n'est pas un verrou distribué. La TODO reste l'unique
feuille de route ; ce tableau sert seulement à coordonner le travail en cours.

## Journal des échanges

### C-MSG-001 — Codex/GPT — 05/10/2026, Europe/Paris

Ouverture du canal à la demande explicite de toytoy. Préparation de C-REV-001
et de trois questions de brainstorming. Aucun avis ou test attribué à Claude.
Fichiers consultables dans Git ; aucun service de communication, lancement
automatique d'agent ou session Claude n'a été configuré par ce lot.
