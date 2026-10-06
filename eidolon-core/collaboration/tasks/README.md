# Trois tâches proposées à Claude Code

Auteur : Codex/GPT, 05/10/2026, Europe/Paris. Demande explicite de toytoy.
Base commune : `3cb1ae551fcbeb16badbf6e2110901928ea0a618`.
Statut historique au message G010 (état courant en fin de fichier) : **C-REV-003 et C-CLAUDE-001 reçus dans c2792d6 ;
adaptateur C-CLAUDE-002 étape 2 reçu, étude matérielle étape 1 à faire**.
Voir C-MSG-G010 pour l'intégration et ses corrections.

| Ordre | Fiche | Livrable |
| --- | --- | --- |
| 1 | [C-REV-003](C-REV-003.md) | Contre-revue ciblée des reçus et de la réconciliation |
| 2 | [C-CLAUDE-001](C-CLAUDE-001.md) | Catalogue pur de cibles et capacités, testé sans réseau |
| 3 | [C-CLAUDE-002](C-CLAUDE-002.md) | Étude 2 × V100/NVLink puis adaptateur candidat simulé |

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

Révision matérielle utilisateur du 05/10 : **2 × V100 32 Go + NVLink prévus**.
C-CLAUDE-002 commence désormais par la compatibilité Volta et la stratégie GPU.
Ollama reste candidat. Précision à 14 h 28 : modules SXM2 sur adaptateur PCIe,
NVLink sur son PCB. Référence de l'adaptateur et topologie effective à relever. [Note et sources](../../docs/INFERENCE-2XV100-2026-10-05.md).

## Nouveau lot — C-MSG-G011

L'étude V100 de Claude est reçue dans ec7582b ; précisions demandées dans
[C-TASK-G003](C-TASK-G003.md). Développement indépendant :
[C-TASK-G002](C-TASK-G002.md), validateur de rapports de qualification.
Revue : [C-TASK-G001](C-TASK-G001.md). Codex prend le diagnostic simulé C-004a.
Les prises en charge Claude restent à confirmer dans sa réponse.

- [C-TASK-G004](C-TASK-G004.md) : Claude, adaptateur candidat API chat llama.cpp
  sur transport simulé, fichiers séparés de C-005a. Prêt à prendre.

- [C-TASK-G005](C-TASK-G005.md) : Claude, contre-revue C-005a sur `5c169cb`,
  sondes et preuves uniquement ; prêt à prendre après livraison G004.

## Répartition courante — C-MSG-G016

G004 et G005 reçus ; les mentions « prêt à prendre » ci-dessus sont historiques.
[C-TASK-G006](C-TASK-G006.md) est le prochain développement Claude : transport
HTTP candidat isolé. Codex traite la lisibilité des accords O-G5-1/O-G5-2.

## Brainstorming et prototype — C-MSG-G017

G006 publié par Claude (`6a972ff`), à relire avant intégration. Nouveau lot
[C-TASK-G007](C-TASK-G007.md) : alternatives de recherche et corpus synthétique
indépendant. Codex prend le coordinateur `research.py`, hors runtime.

## Répartition courante — C-MSG-G018

G006/G007 intégrés dans `534f4f4`, puis transport durci et lecteur raccordé.
[C-TASK-G008](C-TASK-G008.md) : contre-revue Claude, sondes et rapport uniquement.
Les mentions précédentes décrivent les répartitions historiques.

## Répartition courante — C-MSG-G021

Maquettes Claude C019 reçues à `176edac` ; revue Codex publiée avec sonde isolée.
G008 reçu dans `e55dc5d` pendant cette revue ; ne pas refaire ce lot.

1. [C-TASK-G009](C-TASK-G009.md) : prototype bureau autonome, transitions et preuves.
2. [C-TASK-G010](C-TASK-G010.md) : faisabilité du paquet Windows, choix encore ouvert.

Codex réserve le contrat serveur client/reconnexion ; Claude reste propriétaire
du prototype. Fiches prêtes, démarrage de sa session non présumé.

## Répartition courante — C-MSG-G022

G009 prototype bureau et G010 étude Windows restent confiés à Claude ; leur
livraison n'est pas présumée. Nouveau [C-TASK-G011](C-TASK-G011.md) : contre-revue
D1/D2/C5, après son lot GUI engagé et avant G010 si possible. Codex livre les
correctifs Web et garde le futur contrat serveur du client. Pas de modification
simultanée du prototype ou des modules de production.

## Répartition courante — C-MSG-G023, 06/10/2026

G009 reçu ensuite dans 111da40, intégré intact ; 17 tests de logique reproduits,
UI non rejouée ici faute de Chromium. Nouveau [G013](C-TASK-G013.md) : réparer
le suivi des commandes incertaines, puis [G012](C-TASK-G012.md) : consommateur
JS et raccordement du contrat client-sync/1 au prototype. G011 garde sa base
Web figée e25cd2a ; G010 reste l'étude Windows à suivre. Codex livre C-008a et garde le serveur,
le stockage et les futures commandes. Ne pas attendre la VM pour ces tâches.

## État courant — C-MSG-G025, 06/10/2026

G011 reçu dans 25ea564 et intégré ; D3 corrigé par Codex, courte
contre-vérification demandée. G013 puis G012 restent prioritaires. Nouvelle
[G014](C-TASK-G014.md) : contre-revue des reçus locaux de décisions C-008b après
ces deux lots ; G010 reste l'étude Windows suivante. C-CLAUDE-002 : étude et
adaptateur intégrés, qualification matérielle différée, pas une tâche code en
attente de Claude. Les paragraphes antérieurs sont des états historiques.

## État courant — C-MSG-G026, 06/10/2026

G013 intégré (deef553), 28 tests Node reproduits ; 11 UI seulement rapportés.
D3 contre-vérifié par Claude C023. G012 reste prioritaire, avec voyant « Reçu à
vérifier » ; G014 conserve sa cible C-008b. Nouveau [G015](C-TASK-G015.md) pour
revoir séparément l'annulation C-008c après G014. G010 reste ouverte.

## État courant — C-MSG-G027, 06/10/2026

G012 reçu dans cc9a64b et intégré comme candidat ; trois écarts reproduits.
[G016](C-TASK-G016.md) confie la correction du consommateur et de ses libellés,
avant G014/G015 si aucun lot déjà engagé. G014 et G015 restent distincts, G010
reste ouverte. Codex livre C-008d (copie historique bloquée pour exécution) et
conserve les sources Python. Aucune réponse à G016 présumée.
