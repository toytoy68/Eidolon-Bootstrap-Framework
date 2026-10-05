# Eidolon Core — Cahier des charges pour Work

Date : 5 octobre 2026  
Statut : cadrage issu du brainstorming utilisateur, à confronter aux dépôts  
Destinataire : session Work chargée du développement d’Eidolon Core v0.1

## 1. Consigne de reprise

Reprendre le développement autorisé de Core v0.1 en examinant d’abord l’existant :

- Bootstrap / Core : https://github.com/toytoy68/Eidolon-Bootstrap-Framework
- Memory Engine : https://github.com/toytoy68/Eidolon-Memory-Engine
- Branche mémoire indiquée : `refactor/architecture-v1`.

Vérifier les branches, commits, instructions locales, contrats et travaux déjà livrés avant toute modification. Ce document ne constitue pas un audit de leur état actuel. Il complète le périmètre v0.1 déjà communiqué ; signaler une incompatibilité avec ce périmètre avant de l’élargir.

Respecter le standard de présentation Eidolon déjà produit : en-têtes, mentions de marque, affichage des configurations et installations. Retrouver son document de référence dans les dépôts ; reproduire le style établi sans inventer un nouveau standard.

La VM n’est pas disponible jusqu’à la fin de semaine selon le dernier contexte communiqué. Avancer sur les dépôts et les tests accessibles ; distinguer validation locale, simulation et validation réelle sur VM.

## 2. Vision produit et frontière fondamentale

Eidolon part d’un chatbot évolué, façon Jarvis, qui devient un assistant résident capable de connaître son système et son environnement, d’agir sous contrôle et de superviser des agents IA.

Ses trois rôles sont :

- **Assistant IA** : contexte, projets, analyse, assistance et actions autorisées.
- **Chatbot** : dialogue naturel par texte, puis voix et interactions visuelles.
- **Superviseur d’agents IA** : délégation, permissions, suivi et vérification du travail.

**Core orchestre les missions ; Memory Engine conserve la mémoire. Un modèle propose, le code contrôle les autorisations et vérifie les résultats.**

Core reçoit une intention, constitue une mission, récupère le contexte utile, choisit les capacités, contrôle l’exécution, vérifie le résultat et trace le déroulement. Memory Engine demeure indépendant et canonique pour la mémoire persistante. Qdrant est un index reconstruisible, pas la source canonique de cette mémoire.

Une conversation et une mission sont distinctes : fermer l’interface ne doit pas annuler implicitement une mission.

## 3. Architecture cible

Les composants ci-dessous définissent des responsabilités ; ils n’imposent pas un microservice par composant.

| Composant | Responsabilité |
|---|---|
| Core / Mission Manager | Intentions, missions, étapes, états, reprise et résultats |
| Planner / Router | Proposition de plan et sélection des capacités ou modèles |
| Model Adapter | Accès interchangeable aux modèles, initialement Ollama |
| Memory Adapter | Accès aux contrats publics de Memory Engine |
| Policy Engine | Décisions déterministes d’autorisation |
| Tool Manager | Registre, validation des paramètres, timeout, exécution et journalisation |
| Verifier | Contrôle du résultat réel selon le type d’action |
| Scheduler | Missions différées, récurrentes ou conditionnelles |
| Event / Device Bus | Événements, présence, endpoints et télémétrie |
| Interfaces clientes | Chat, Desktop, puis mobile, voix et dispositifs physiques |

Le Planner propose ou délègue une action. Toute exécution passe par Policy et Tool Manager, y compris celle demandée par un agent spécialisé. Une sortie de modèle ne peut modifier les permissions.

## 4. Modèles : candidats et protocole d’évaluation

L’architecture multi-modèles est retenue comme cible. Aucun nom de modèle ne doit être une dépendance structurelle de Core.

- Généraliste / raisonnement : Gemma « 4 26B » est le candidat privilégié dans les échanges.
- Code : Qwen2.5-Coder 7B est le candidat technique.
- GPT-OSS 20B : candidat pour analyse, architecture et usage général.
- Vision : modèle à déterminer.
- Qwen3 30B : candidat aux tâches de réflexion, avec latence jugée pénalisante dans les essais rapportés.

### Observations historiques fournies dans le brainstorming

Machine annoncée : i7-11700, 32 Go DDR4, RTX 3080 Ti FE 12 Go, Ollama. Ces données décrivent les essais rapportés, pas nécessairement la configuration actuelle.

| Étiquette rapportée | Vitesse approximative | Impression rapportée |
|---|---:|---|
| Qwen2.5-Coder 7B | 126 tok/s | Très rapide, adapté au code |
| Gemma 4 12B | 71 tok/s | Bon équilibre conversation / vitesse |
| GPT-OSS 20B | 55 tok/s | Bon raisonnement, réflexion courte |
| Gemma 4 26B | 32 tok/s | Bon candidat au raisonnement principal |
| Qwen3 30B | 32 tok/s | Réflexion longue |

Ces chiffres restent des observations utilisateur non reproduites dans ce document. Les noms exacts, tags, digests, architecture dense/MoE, quantification, contexte, offload CPU/GPU et méthode de mesure sont à retrouver. Les notes de stabilité et estimations VRAM ajoutées par GPT Chat ne constituent pas des mesures validées. Ne pas en déduire une qualification automatique pour les agents.

Prévoir un protocole reproductible pour comparer des modèles et variantes :

- exactitude sur réponses vérifiables, raisonnement et suivi des consignes ;
- appels d’outils, schémas structurés, paramètres et comportement face aux refus ;
- stabilité sur essais répétés, erreurs, hallucinations et résistance aux instructions présentes dans les données ;
- latence initiale, durée totale, débit de génération et coût du thinking ;
- contexte effectivement utilisable et qualité du rappel dans ce contexte ;
- VRAM, RAM, consommation, température et concurrence ;
- verdict par rôle : conversation, planification, code, vision, supervision.

Le choix automatique fondé sur ces résultats vient ultérieurement. La v0.1 peut utiliser un modèle configurable unique.

## 5. Autonomie et autorisations

| Niveau | Exemples | Règle |
|---|---|---|
| Lecture autorisée | Mémoire, fichiers autorisés, diagnostics, métriques, rapports | Autorisation limitée au périmètre configuré |
| Action déléguée sous politique | Benchmark, fichier de travail, maintenance prévue | Exécution si délégation et conditions applicables |
| Confirmation requise | Modification importante, suppression, arrêt/redémarrage, configuration sensible, effet extérieur | Attendre une décision utilisateur liée à l’action concrète |
| Interdit | Contournement, désactivation des protections, modification des permissions par le LLM, commande matérielle dangereuse directe | Refus déterministe |

Ces exemples sont une direction de politique, pas une liste universelle figée. Les autorisations doivent être configurables et explicites ; une délégation préalable doit pouvoir être représentée.

Une confirmation porte sur une action, une cible et des paramètres précis. Un changement matériel du plan invalide la confirmation correspondante. Définir le comportement pour refus, expiration, annulation et absence de réponse.

## 6. Missions, échecs et vérification

Cycle de vie conceptuel à adapter aux conventions existantes :

`CREATED → PLANNED → RUNNING → COMPLETED`, avec attente utilisateur, attente ressource, échec, annulation et reprise explicites.

Conserver les étapes terminées, les résultats, l’erreur et les conditions de reprise. FAILED ne signifie pas abandon définitif. Ne pas relancer aveuglément une action à effet de bord après une interruption : vérifier son état et traiter l’incertitude avant retry.

Une réponse « OK » d’un outil ne prouve pas la réussite. Définir une vérification adaptée, indépendante lorsque possible : après un redémarrage, vérifier l’état du service ; après une création, vérifier l’artefact attendu.

Tracer intention, plan, décision de politique, confirmation éventuelle, exécution, résultat et vérification avec identifiants corrélés. L’état opérationnel des missions appartient à Core ; il ne remplace pas la mémoire sémantique de Memory Engine.

## 7. Eidolon Desktop sur le PC principal

Vision utilisateur explicitement souhaitée :

- application Windows installée, avec icône **E Eidolon bleue** ;
- accès depuis la barre des tâches et présence discrète dans la zone de notification ;
- démarrage automatique à l’ouverture de session, activable dans les paramètres ;
- clic : ouvrir le chat ; menu rapide : voix, missions, état du serveur, silence et paramètres ;
- accueil et interpellation contextuels à la connexion ou lors de la présence utilisateur.

Le serveur héberge Core. Desktop est un client distant : il présente le dialogue, les missions et notifications, et expose seulement les capacités locales autorisées.

Accueil type : « Bonjour toytoy. Eidolon est en ligne. Deux missions sont terminées et une attend ton accord. »

Éviter les accueils répétés, respecter le mode silencieux et les préférences de notification. Prévoir le cas Core hors ligne, la reconnexion et le rattrapage des événements. La fermeture du client ne vaut pas annulation des missions serveur.

L’application Windows complète reste une phase ultérieure. Dès v0.1, concevoir les contrats pour des clients distants, sans choisir prématurément un framework Desktop.

## 8. Présence, identité, webcam et voix

La webcam peut permettre de différer l’accueil jusqu’à ce qu’une personne soit devant l’écran et, ultérieurement, de différencier les personnes.

Séparer :

1. présence : quelqu’un est devant le PC ;
2. identité probable : la personne ressemble à un profil connu ;
3. authentification : identité vérifiée pour les permissions.

Pour la voix, distinguer transcription de la parole, identification du locuteur et authentification. Whisper/Piper figurent dans les expérimentations antérieures ; leur intégration actuelle reste à vérifier.

**Visage et voix servent au contexte et à la personnalisation ; ils ne suffisent pas seuls à autoriser une action sensible.**

La détection primaire doit pouvoir se faire sur le PC. Envoyer des événements à Core plutôt qu’un flux vidéo continu. L’envoi d’images au modèle Vision nécessite une capacité autorisée et une mission qui le justifie.

Événements conceptuels :

- `USER_PRESENT`, `USER_ABSENT` ;
- `USER_IDENTIFIED` avec identité probable, origine et confiance ;
- `USER_UNKNOWN`, changement ou verrouillage de session.

Prévoir caméra/micro indisponibles ou désactivés, plusieurs personnes, indices contradictoires, faux positifs et identité inconnue. Un score de modèle n’est pas automatiquement une probabilité calibrée ; ne pas additionner naïvement les confiances visage/voix.

Les captures et empreintes biométriques demandent une activation explicite, une conservation minimale et des règles de suppression. Pour une personne inconnue, permettre un contexte invité et masquer les informations personnelles. L’absence peut suspendre la parole sans interrompre une mission.

## 9. Endpoints physiques et état de l’environnement

Wall-E est un endpoint parmi d’autres : Desktop, robot, serveur, NAS, caméra, ESP32, domotique ou futur dispositif.

Le dashboard cible doit montrer l’état du monde connu par Eidolon et les missions associées.

| Donnée | Exemple |
|---|---|
| Identité / type | WALL-E, robot |
| Connexion | ONLINE, OFFLINE, DEGRADED, dernier contact |
| Capacités autorisées | Caméra, audio, navigation |
| Télémétrie | Batterie, température, capteurs, erreurs |
| Contexte | Localisation déclarée, présence |
| Travail | Mission, étape, tâche en cours |

Les valeurs de batterie ou de latence illustrées dans le brainstorming sont des exemples, pas des mesures actuelles.

Prévoir identité stable d’endpoint, authentification, autorisations par capacité, horodatage, origine et fraîcheur des données. Distinguer « dernière valeur connue » et « état actuel ». Un équipement déconnecté ne doit pas rester présenté comme prêt à exécuter une action.

Core doit pouvoir corréler une mission avec le robot, l’agent Vision et la mémoire sollicitée. La v0.1 peut définir les contrats ou employer des endpoints simulés ; elle n’exige pas une intégration matérielle complète.

## 10. Robot et sécurité déterministe

Chaîne cible : intention du modèle → Core → politique → outil contrôlé → contrôleur robot → ESP32 → moteurs.

Les limites de vitesse, fins de course, courant, arrêt d’urgence et anticollision restent dans les couches logicielles et matérielles adaptées. Les fonctions de sécurité ne doivent pas dépendre du LLM ou de la disponibilité réseau du serveur.

Core supervise les missions ; le contrôle temps réel et la mise en sécurité restent locaux. Aucun pilotage moteur direct par une sortie libre du modèle.

## 11. Scheduler et notifications

Cible : tâches différées, récurrentes, déclenchées par événement ou condition, avec suivi et reprise.

Exemples de besoins futurs, sans demande de les programmer maintenant :

- analyser les logs la nuit ;
- surveiller NAS, disques ou températures ;
- lancer un benchmark lorsque les ressources sont disponibles ;
- reprendre après redémarrage ;
- signaler une batterie faible et proposer ou déclencher une recharge autorisée ;
- consulter périodiquement une source externe autorisée.

Le modèle formule la tâche ; le Scheduler applique les conditions sans garder nécessairement le LLM chargé. Les règles de maintenance 04 h–08 h et de reprise après inactivité évoquées pour Memory Engine doivent être vérifiées dans ses contrats avant mutualisation.

Notifications : distinguer accueil, information, demande d’accord et alerte ; prévoir priorités, déduplication, silence, accusés de réception et confidentialité selon la présence.

## 12. Première tranche v0.1

Réussir la chaîne : **demande → mission → contexte mémoire → proposition → autorisation → outil → vérification → résultat → trace**.

Livrer d’abord :

- missions et étapes persistées, états explicites et reprise contrôlée ;
- adaptateur Memory Engine utilisant ses contrats existants ;
- adaptateur modèle configurable, initialement Ollama ;
- Policy et Tool Manager avec quelques outils bornés ;
- vérificateurs et erreurs structurées ;
- interface minimale utilisable et contrats pour clients distants ;
- tests des scénarios ci-dessous et documentation de lancement.

Prévoir des points d’extension sobres pour Presence, Identity, Device/Endpoint, Telemetry et événements. Ne pas développer toute la cible pour justifier ces extensions.

Hors première tranche complète : application Desktop finale, reconnaissance biométrique, robot réel, Vision, domotique, routage avancé par benchmarks et Scheduler complet. Leur place dans l’architecture doit être documentée.

## 13. Scénarios de validation

| Scénario | Comportement attendu |
|---|---|
| A — « Que savons-nous du projet X ? » | Rappel mémoire, synthèse avec références disponibles, aucune action système ; indiquer le manque de contexte |
| B — « Vérifie l’état du service X » | Outil de lecture autorisé, contrôle du résultat, réponse et trace |
| C — « Redémarre X » | Action concrète soumise à la politique, attente d’accord si nécessaire, exécution puis vérification ; refus sans exécution |
| D — « Analyse X puis lance Y » | X réussit, Y échoue ; conserver X, expliquer Y, permettre une reprise sans rejouer X |
| E — cible ambiguë | Demander la précision utile ; aucune action sur une cible devinée |
| F — interruption | Recharger la mission ; traiter une exécution incertaine avant retry et éviter un effet doublé |
| G — dépendance indisponible | Erreur explicite, attente ou échec contrôlé ; aucune réussite inventée |
| H — client reconnecté | Retrouver état des missions et événements pertinents sans les recréer |

A–D sont les scénarios centraux demandés. E–H précisent les cas nécessaires pour vérifier leur robustesse. Présence, identité et robot peuvent être testés plus tard avec simulations.

## 14. Méthode et livrables attendus de Work

1. Examiner le code, la documentation et le standard d’affichage.
2. Comparer ce cadrage aux contrats existants et au périmètre v0.1 antérieur.
3. Documenter acquis, écarts, décisions et points ouverts.
4. Développer une tranche verticale utilisable couvrant A–D.
5. Tester les permissions, refus, reprise et résultats réels, puis documenter les limites.
6. Mettre à jour la feuille de route et les documents de suivi selon les conventions du dépôt.

Chaque bilan distingue : implémenté, testé localement, testé avec services réels, validé sur VM et restant à faire. Un test simulé n’atteste pas le bon fonctionnement sur l’infrastructure réelle.

Points à arbitrer après inspection : API/transport, stockage opérationnel des missions, authentification des clients, premier outil réel et sa cible de test, politique détaillée, framework Desktop, gestion des notifications, protocole endpoint, modèles et tags exacts.

Ce document fixe la direction produit et les frontières d’architecture. Il n’autorise pas à lui seul des accès matériels, une capture webcam/micro, une action externe ou une modification des politiques de sécurité.
