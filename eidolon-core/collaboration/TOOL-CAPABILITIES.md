# Registre partagé des outils — ChatGPT / Claude / Eidolon

Date : 12/10/2026. Statut : inventaire initial, **non exhaustif**. Ce registre décrit des capacités observées ou déclarées ; il ne confère aucun droit et ne garantit pas qu'un connecteur fonctionne.

## Règles
- Chaque agent maintient sa propre section ; ne jamais présenter un outil de l'autre comme testé sans son rapport.
- Pour chaque outil : nom, fonction, environnement, portée (lecture/écriture/exécution), limites, prérequis, statut **déclaré / observé / testé / indisponible**, date et preuve.
- Les jetons, secrets, chemins privés sensibles et adresses personnelles ne sont jamais consignés.
- Une capacité documentée n'est pas une permission ; toute action reste soumise à l'autorisation de l'utilisateur et aux politiques du système.
- Mettre à jour après changement d'outil, de permissions ou de connecteur ; les tests doivent être datés.

## ChatGPT — observations de cette session

| Famille | Usage | Portée | Statut au 12/10 |
| --- | --- | --- | --- |
| GitHub (connecteur) | Lire fichiers/commits, publier fichiers et messages sur branches autorisées | Lecture et écriture GitHub | **Testé** : commits publiés sur feat/eidolon-core-v0.1 |
| Eidolon Collaboration MCP | Statut d'échanges, diagnostics VM, outils de workspace et tests isolés, exécution VM Core si opérationnel | Variable selon outil et autorisations | **Déclaré mais indisponible** : erreur interne sur statut et diagnostics lors de cette session |
| Exécution locale Python / conteneur | Analyse, prototypes et tests dans un environnement temporaire, distinct des VM Eidolon | Local au runtime ChatGPT | Disponible ; ne donne pas accès implicite aux VM |
| Recherche Web | Recherche et consultation de pages publiques | Lecture Web | Disponible dans l'environnement ChatGPT, **pas** preuve d'accès Web du Core Eidolon |
| Automatisations | Veille GitHub planifiée | Notifications programmées | **Testé** : veille hebdomadaire créée |

La liste des noms d'outils MCP exposés ne signifie pas que leurs fonctions répondent. Ne jamais publier de credentials ni confondre ChatGPT, le runtime Core et les VM.

## Claude — à compléter par Claude

| Famille | Usage | Portée | Statut et preuve |
| --- | --- | --- | --- |
| Accès Git / dépôt | Branches, commits, revue, tests | À préciser | À confirmer |
| Exécution terminal / code | Lecture, écriture, tests, installation locale | À préciser | À confirmer |
| Accès VM Core / Memory | Diagnostics, commandes, fichiers, déploiement | À préciser | À confirmer |
| Navigation / recherche Web | Fournisseur, outils et limites | À préciser | À confirmer |
| Collaboration MCP | Échanges et outils VM | À préciser | À confirmer |
| Autres outils / skills / plugins | Capacités spécifiques | À préciser | À confirmer |

**Demande :** Claude complète cette section dans son propre rapport de collaboration, en distinguant capacités disponibles, testées et indisponibles ; ChatGPT consolidera ensuite le registre sans attribuer de permissions fictives.

## Eidolon Core — outils runtime (distincts des assistants développeurs)

Inventorier séparément : connecteurs Memory, Darme/Policy, monitoring, recherche Web, navigateur, outils système, modèles, STT/TTS, caméras, agents média, skills. Pour chaque entrée, préciser si elle est simulée, raccordée, testée en VM ou active en production.

## Usage pour répartir le travail

Avant toute affectation : (1) consulter le registre, (2) vérifier l'accès effectif, (3) déclarer le propriétaire du lot, (4) prévoir un fallback si l'outil est indisponible, (5) publier le résultat et les preuves.
