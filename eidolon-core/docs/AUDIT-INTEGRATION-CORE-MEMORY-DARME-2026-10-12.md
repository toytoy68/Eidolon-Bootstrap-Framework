# Audit d'intégration Core / Memory / Darme — 12 octobre 2026

Statut : **audit documentaire initial**, aucune validation VM ni mise en production.
But : rendre possible une mission utilisateur « diagnostique ton serveur, rappelle les incidents antérieurs et propose des corrections avec preuves ».

## Éléments vérifiés dans le dépôt

- TODO Core du 12/10 : G181 raccordement optionnel Qdrant, G182 76 tests ciblés ; suite complète et mesures réelles non récupérées. Le Qdrant de recette doit être vérifié/arrêté avant relance.
- G181 : la recherche Web est encore synthétique dans le parcours de dialogue ; le serveur a un accès sortant, mais le modèle n'a pas encore d'outil de recherche réel raccordé.
- Queue G185 : Claude doit revoir G180/G181/G182, G184 et C156 ; G183 concerne le chargement des modèles et les profils. Une attribution n'est pas une session active.
- C070 : identité Core et SOUL sont spécifiés, pas entièrement intégrés.
- Le Core possède des contrats de mission persistante, preuve, vérification et reprise ; l'intégration de tous les outils et services réels reste à qualifier.

## Limitation immédiate

Le connecteur MCP Eidolon Collaboration renvoie une erreur interne lors de la lecture du statut et des diagnostics Core/Memory. **Aucune affirmation d'état live de VM100/VM110 n'est autorisée.** Ne pas relancer G182 à l'aveugle.

## Contrat de la mission de diagnostic (proposé)

Entrée : demande authentifiée et périmètre explicite des ressources autorisées.
1. Core crée une mission persistante et conserve l'identité du demandeur.
2. Darme / Policy autorise des outils de **lecture seule** de monitoring ; liste blanche d'opérations, quotas et délais.
3. Outils collectent les métriques horodatées avec provenance (CPU, RAM, disques, réseau, services, GPU).
4. Core demande un rappel Memory contextualisé (incidents similaires) ; ne jamais confondre rappel avec état actuel.
5. Core peut demander une recherche Web réelle facultative, en transmettant seulement la requête nécessaire, jamais le contenu privé du Memory Engine par défaut.
6. Synthèse sépare : mesures observées, souvenirs historiques, hypothèses et recommandations.
7. Validateur exige références, horodatages, permissions et état terminal ; échec/UNKNOWN n'est jamais promu en succès.
8. Aucune correction, redémarrage, modification de configuration ou accès Internet externe n'est exécuté implicitement.

## Écarts à fermer

| Bloc | État documentaire | Condition de validation |
| --- | --- | --- |
| Core dialogue/mission | Code et tests en développement | Mission de bout en bout avec modèle réel |
| Memory lexical/canonique | Disponible ; Qdrant optionnel en cours | Corpus réel, paraphrases, abstention, provenance |
| Qdrant G182 | Résultats non récupérés | Lire journaux et contrôler serveur temporaire avant reprise |
| Darme/Policy | Intégration à inspecter en VM | Lecture seule, refus, audit et révocation |
| Monitoring | Outils à qualifier | Horodatage, source, absence de valeurs inventées |
| Web | Fixtures actuellement | Fournisseur réel, politique réseau, citations et absence de fuite |
| Identité / SOUL | Documents disponibles | Chargement sécurisé et intégration runtime |
| Résilience | Contrats existants | Crash, reprise, double soumission, effet incertain |
| UX | Dashboard en chantier | Rapport lisible PC/mobile avec erreurs explicites |

## Scénarios de test prioritaires

T1 nominal : monitoring réel + rappel d'incident pertinent + rapport sourcé.
T2 mémoire indisponible : rapport partiel, pas de souvenir inventé.
T3 métrique périmée : marquée inconnue, pas de diagnostic certain.
T4 permission refusée : BLOCKED, aucune commande lancée.
T5 Web indisponible : dégradation contrôlée sans prétendre avoir cherché.
T6 outil interrompu : reçu durable, reprise sans double action.
T7 souvenir contradictoire : versions et dates conservées, pas d'écrasement.
T8 requête de correction sensible : demande de confirmation séparée, pas d'auto-exécution.

## Réutilisation open source à étudier

- Hermes Agent : format des skills, apprentissage procédural, déclenchement et évaluation ; ne pas remplacer Core.
- OpenHands SDK : worker de code isolé avec diff et tests, sous contrôle du Mission Manager.
- Graphiti / Hindsight : relations temporelles et réflexion ; conserver Markdown canonique.
- DCGM Exporter : observabilité V100, compatibilité pilote à vérifier.
- Sandboxes : comparer isolation existante, conteneurs et microVM avant ajout d'une couche K3s.

## Ordre des travaux

P0 : rétablir MCP et relire G182, sans relancer le benchmark identique.
P0 : recette Memory/Qdrant sur données réelles et contrat de rappel.
P0 : vérification des permissions Darme + monitoring lecture seule.
P0 : mission diagnostique complète, d'abord sans Web puis avec fournisseur réel.
P1 : skills, isolation d'exécution, modèle de soi et personnalités.
P2 : agents développeurs et mémoire réflexive.

**Règle :** pas de fusion main, pas de modification des références attendues, pas de déploiement sans recette explicite.
