# Collaboration asynchrone Core — Codex/GPT et Claude Code

Ce canal sert aux revues, questions, propositions et brainstormings. Il est
indépendant du canal Memory Engine. Les fichiers n'exécutent aucune action,
n'accordent aucun accès et ne démarrent ni ne réveillent un assistant.

## Fichiers et responsabilités

| Fichier | Usage |
| --- | --- |
| [ECHANGES.md](../ECHANGES.md) | Reprise, index des sujets, prises en charge, conclusions courtes |
| [GPT-TO-CLAUDE.md](GPT-TO-CLAUDE.md) | Demandes et réponses rédigées par Codex/GPT |
| [CLAUDE-TO-GPT.md](CLAUDE-TO-GPT.md) | Réponses et questions rédigées par Claude Code |
| [BRAINSTORMING.md](BRAINSTORMING.md) | Alternatives argumentées, questions ouvertes, propositions non décidées |
| [archive/](archive/README.md) | Versions précédentes des messages, conservées sans réécriture |
| [TODO.md](../TODO.md) et `docs/` | Tâches, contrats et décisions consolidées |

Chaque auteur modifie son fichier de messages. Il peut proposer une correction
à l'autre auteur, mais ne réécrit pas sa réponse comme si elle venait de lui.
Pour un message relayé par toytoy, indiquer auteur déclaré, relais et origine ;
ne pas prétendre avoir directement observé la session ou ses tests.

## Début de travail

1. Lire les consignes, vérifier branche/commit/état local, récupérer les refs
   distantes si possible. Actualiser un checkout propre par avance rapide.
2. Lire ECHANGES, le message reçu et les documents liés. Indiquer la base exacte
   examinée ; si l'accès est limité à une archive, le signaler.
3. Déclarer le lot et les fichiers prévus dans les prises en charge. Si le lot
   est déjà travaillé, prendre une revue ou une tâche distincte ; ne pas modifier
   simultanément les mêmes fichiers dans un répertoire partagé.

Pour du code en parallèle : checkouts/worktrees et branches distincts, par
exemple `claude/core-c001-review` et `codex/core-c002`. Ne jamais changer la
branche d'un répertoire utilisé par l'autre auteur. Publier commits/diffs pour
revue selon les autorisations ; pas de push forcé pour résoudre une divergence.
La branche de travail autorisée est actuellement `feat/eidolon-core-v0.1`.
L'intégration d'un lot s'effectue après examen de sa base, son diff et ses preuves ;
ce protocole n'autorise pas une fusion dans main ou un déploiement.

## Format minimal d'un message

```markdown
## C-MSG-XXX — Titre
Auteur : Codex/GPT ou Claude Code
Date : horodatage avec fuseau
Base examinée : dépôt, branche, SHA complet
En réponse à : C-REV-XXX / C-BRAIN-XXX / C-MSG-XXX
Nature : question / proposition / revue / résultat / décision rapportée
Statut : ouvert / répondu / à arbitrer / clos

Constat ou proposition :
Preuves : fichiers, commandes, résultats, journaux ou scénario reproductible.
Limites : simulé, lu seulement, non reproduit, VM non testée, etc.
Suite proposée :
```

Différencier lecture du code, tests réellement exécutés par l'auteur et résultats
rapportés. Un accord entre deux modèles ne remplace pas un test ou une décision
utilisateur nécessaire. Ne pas inventer une réponse absente.

## Numérotation par auteur

Décision de toytoy, 05/10/2026 vers 14 h 30 (Europe/Paris), en réponse à la
proposition de Claude dans C-MSG-C009 : « Ok pour moi ». Les deux auteurs
publient sur des branches différentes et leurs numéros se sont croisés quatre
fois. Désormais, chaque identifiant nouveau porte la lettre de son auteur :
`G` pour Codex/GPT (`C-MSG-G010`, `C-BRAIN-G008`), `C` pour Claude
(`C-MSG-C010`, `C-BRAIN-C008`). Les identifiants déjà publiés par Codex/GPT
restent inchangés. Les éléments Claude publiés pendant les collisions portent
déjà leur forme `C` : C-MSG-C008, C-MSG-C009, C-BRAIN-C007. Le nombre suit le
plus grand numéro connu, toutes lettres confondues ; deux auteurs peuvent donc
avoir le même nombre sans collision.

## Brainstorming et décisions

Pour chaque idée : besoin, options, compromis, essai discriminant et statut.
Statuts possibles : PROPOSÉ, EN DISCUSSION, À ARBITRER, ADOPTÉ, REJETÉ, DIFFÉRÉ.
Conserver les contributions signées ; la vue de l'autre auteur doit être
ajoutée sous la sienne, sans l'écraser.

Les contraintes déjà fixées par toytoy font référence. Les choix d'implémentation
ordinaires dans le périmètre autorisé peuvent avancer sans approbation répétée.
Un désaccord métier ou une extension de périmètre se présente avec des options
concrètes. Une proposition sans décision reste ouverte, sans expiration
automatique. Une absence de réponse n'est ni un accord ni un veto ; poursuivre
les tâches autorisées indépendantes sans inventer de consensus.

Quand une décision est acquise : identifier qui décide et sur quelle base,
consolider dans `docs/`, puis actualiser la TODO. ECHANGES/BRAINSTORMING conservent
un lien vers cette décision ; ils ne deviennent pas une deuxième architecture.

## Archivage et fin de lot

Conserver les messages actifs courts, en renvoyant aux sources pour le détail.
Avant remplacement d'un message actif non vide, copier ses octets dans
`archive/` avec nom unique date-auteur-ID, puis indiquer le lien depuis le message
suivant. Ne jamais écraser une archive. Les placeholders sans contribution ne
sont pas des messages reçus et n'ont pas besoin d'être archivés.

Commit cohérent, bilan daté et preuves, statut TODO réel, publication selon
l'autorisation de la session puis contrôle distant. Un conflit sur un fichier
partagé exige la conservation des contributions des deux auteurs, pas le choix
automatique d'une version. Aucun secret ou corpus privé dans ces échanges.

## Démarrer la revue avec Claude Code

Dans une session disposant d'un accès à ce dépôt :

> Lis CLAUDE.md, AGENTS.md et eidolon-core/ECHANGES.md. Vérifie la branche et le
> commit actuels, puis traite la demande active dans GPT-TO-CLAUDE.md. Dépose ta réponse
> signée dans CLAUDE-TO-GPT.md en distinguant tes tests des résultats rapportés.
> Tu peux enrichir les sujets de BRAINSTORMING.md. Préserve le travail existant.

Un accès en lecture seule permet une revue relayée par toytoy ; l'accès en
écriture doit être disponible pour publier directement. Aucun serveur MCP Core
ou mécanisme de synchronisation automatique n'est supposé opérationnel.
