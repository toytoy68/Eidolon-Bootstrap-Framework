# Eidolon Core — séance du 8 octobre 2026

Codex/GPT, séance commencée à 04 h 35 (Europe/Paris), à la demande de toytoy.
Code livré : `2a6488a6956051ea4df817aed07e7ef538043b3f`, sur
`feat/eidolon-core-v0.1`. Aucun déploiement ni modification de main.

## Propositions pour les futurs agents

Les [huit propositions](proposals/2026-10-08-agent-toolbox.md) sont consignées.
Les propositions de Claude seront ajoutées plus tard ; toytoy choisira ensuite.

| Sujet | Proposition Codex à comparer |
| --- | --- |
| Catalogue | Étendre le registre Core existant ; outils et limites sélectionnés par mission |
| Profils | Documentaliste, analyste et diagnostic, avec droits distincts |
| Résultats | Sources, vérification et références d'artefacts consultables |
| Permissions | Contrôles appliqués par l'exécuteur ; secrets hors des prompts |
| Isolation | Protection adaptée à l'outil et à la machine qui l'exécute |
| Reprise | Délais, quotas, annulation ; pas de répétition aveugle d'une action |
| Skills | Procédures versionnées distinctes des outils et des agents |
| Interface | Voir disponibilités, droits, appels et erreurs |

Préférence proposée : un contrat commun Core, avec outils natifs et adaptateurs
distants selon le besoin. Premier parcours : mémoire et fichiers → calcul →
rapport sourcé. Les alternatives sont documentées ; aucun nouvel outil ou droit
n'a été activé sur la base de ces propositions.

## Travail livré sur le socle existant

| Lot | Résultat utile |
| --- | --- |
| C-034 | Réponses Ollama et paramètres validés strictement ; erreurs distantes non recopiées dans les diagnostics |
| C-035 | `qualification-check` vérifie un rapport hors ligne et distingue conforme au périmètre, incomplet et rejeté |
| C-036 | Choix explicite du candidat llama-server dans le fichier privé, comme Ollama ; défaut déterministe conservé |
| C-037 | Corps HTTP incomplets et cadrage ambigu refusés ; erreurs de lecture normalisées, aucune relance implicite |
| C-038 | `model-config-check` contrôle la configuration sans serveur, mission, état ni lecture de valeur de clé |

Les deux adaptateurs portent le contrat /3. Les missions des anciens contrats
conservent leur historique ; leur reprise avec une autre configuration est
bloquée. [Commandes et limites](LOCAL-MODEL-CLI.md).

## Vérifications exécutées

**886 tests Python réussis**, dont les six intégrations au code réel Memory
Engine, sur corpus synthétique. Paquet construit hors réseau et installé dans
un environnement temporaire : 49 modules identiques ; recettes bêta 24/24 et
25/25. Deux faux serveurs locaux éprouvent les planificateurs, les clés et la
reprise sans nouvel appel. Archive construite depuis le commit publié : 85 fichiers comparés aux objets Git,
trois verdicts de qualification et deux inspections de configuration vérifiés.
[Preuves et commandes reproductibles](validation/2026-10-08/codex-hour-0435/README.md).

Aucun modèle, GPU, serveur utilisateur, VM Debian ou PC Windows réel qualifié.
Les tests client Node/Chromium n'ont pas été rejoués ; ces sources sont inchangées.

## Limites mémoire à conserver dans la suite

Sur Memory Engine b33c3a0, les imports recouvrants de conversations identiques
et le refus des champs parts mal formés passent à travers la liaison Core.
Deux limites restent reproduites : un extrait peut perdre la négation située
avant les mots recherchés ; deux versions d'une conversation peuvent rappeler
deux fois le même message. Les réserves et références sont conservées, mais
ne suffisent pas à rétablir le sens perdu. Le moteur mémoire n'a pas été modifié.

Le comparatif d'outillage inclut désormais ces cas. La file Claude G064–G071
est préservée et le compte rendu G088 est disponible ; aucune session Claude
n'est présumée démarrée par la publication des fichiers.
