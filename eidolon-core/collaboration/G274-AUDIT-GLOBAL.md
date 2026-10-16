# G274 — mandat d’audit global indépendant d’Eidolon

Demande de toytoy du 16 octobre 2026 à 07 h 42 Europe/Paris (+0200), transmise par
Codex/GPT. Destinataire : Claude Code, via le canal de collaboration du dépôt.

## Objectif et références

Rechercher les erreurs de code, incohérences d’architecture et d’intégration,
régressions, promesses documentaires non réalisées et obstacles à une bêta fiable.
Examiner tout le contenu pertinent des deux dépôts, y compris Bootstrap hors du
sous-projet Core : code, API, UI, CLI, scripts, installateurs, services, exemples,
dépendances, tests, CI, documentation et procédures de reprise.

- Core/Bootstrap : `940616c0c45fb1f4561a3550e8619c3095286cdb`, `feat/eidolon-core-v0.1`.
- Memory : `76d664013d4e018212682c5aa56305bea0c41db6`, `refactor/architecture-v1`.
- Code G273 qualifié : `00fe9cbfa59ef31fa6b245c87e05cb843a17829d` ; le delta de livraison est documentaire.
- Lire AGENTS.md, CLAUDE.md, les protocoles propres aux dépôts, ECHANGES, TODO,
  `docs/BACKLOG-BETA-ACTUEL-G273.md` et `weekend/2026-10-17/RAPPORT-UNIQUE.md`.
- Les dix contre-revues `G273-CLAUDE-REVIEWS.md` sont incluses dans ce mandat ;
  réutiliser les preuves déjà produites, sans confondre lecture et exécution.

Actualiser les références et consigner les SHA réellement audités. Si un nouveau
commit arrive, terminer le constat sur sa base et examiner le delta explicitement.
Ne pas attribuer à la livraison actuelle un défaut déjà corrigé sur cette base.

## Dix axes de couverture

1. **Architecture et cohérence globale** : frontières Bootstrap/Core/Memory,
   modules réellement raccordés, doublons et code mort, dépendances circulaires,
   contrats contradictoires, configuration par défaut et chemins inutilisables.
2. **Orchestration et dialogue** : états des missions/outils, validation des sorties
   modèle, erreurs, annulations, délais, reprises, idempotence, effets tardifs et
   exceptions dans threads/processus. Rechercher blocages et succès mensongers.
3. **Mémoire et index** : Markdown source de vérité, transactions/écritures atomiques,
   provenance, isolation des profils, ingestion/rappel, reconstruction Qdrant,
   passages incrémentaux, reprise après panne et cohérence des sauvegardes.
4. **Contrats entre services** : API et clients Core/Memory, versions et schémas,
   authentification, refus/erreurs, délais et retries ; parcours chat → rappel →
   mémorisation → reçu et comportement si un service est indisponible.
5. **Identité, sessions et autorisations** : clés, rotation/révocation, séparation
   admin/utilisateur et profils, accès fichiers/réseau, secrets et journaux,
   limites des captures et absence d’autorisation biométrique implicite.
6. **Bibliothèques et conservation** : extraction documentaire, synchronisation,
   liens/substitutions/concurrence, cache et versions, bornes de ressources,
   protection des données nécessaires, inventaire et restaurations cohérentes.
7. **Ressources et moteurs** : budgets GPU, files, priorités, réservations orphelines,
   dialogue/média et clients hors file, maintenance/charge/inactivité, STT/TTS,
   caméras et calibration ; séparer simulations et mesures matérielles absentes.
8. **Interface et Windows** : états API/UI, réponses tardives, changement de session,
   prévisualisation/confirmation/reçus, capteurs, démarrage/résident, fermeture,
   accessibilité des erreurs et compatibilité des contrats desktop/serveur.
9. **Installation et exploitation** : Bootstrap, scripts shell/PowerShell, services,
   chemins/permissions/comptes/dépendances, épinglage des versions, configuration,
   diagnostic, mise à jour/rollback, paquet et recette. Inspecter les installateurs
   sans les exécuter sur l’hôte ; tester leur logique dans un environnement jetable.
10. **Qualité des preuves et documentation** : tests faussement rassurants, mocks
    masquant une incompatibilité, assertions absentes, skips/xfail, CI et dépendances,
    exemples non exécutables, écarts code/TODO/rapport, revendications excessives.
    Distinguer travail développé, branché, testé, déployé et réellement validé.

## Méthode et preuves attendues

Commencer par un inventaire des sous-systèmes et points d’entrée, puis une matrice
composant × mode de vérification : LU, TESTÉ, NON VÉRIFIÉ, BLOQUÉ, avec justification.
Ne pas prétendre avoir tout vérifié si une partie reste inaccessible. Prioriser les
chemins avec perte de données, fuite interprofil, effets non autorisés ou reprise
incorrecte. Poursuivre ensuite les erreurs fonctionnelles bloquant la bêta.

Pour chaque défaut, donner un identifiant stable G274-Fxxx, le dépôt/SHA, les
fichiers et symboles concernés, attendu/observé, conditions de déclenchement,
impact, commande et scénario minimal reproductible, résultat réellement obtenu,
cause probable et correction minimale proposée. Ajouter un test de régression
qui échoue sur le code audité quand cela est possible. Ne pas modifier les attentes
pour rendre le test vert ; un test de sabotage n’est utile que s’il discrimine
le défaut. Vérifier les interactions, pas uniquement les fonctions isolées.

Classer : **P0** perte/corruption de données ou contournement majeur confirmé ;
**P1** parcours essentiel bloqué, isolation/reprise incorrecte ou défaut critique
pour la bêta ; **P2** défaut réel avec contournement ou impact limité ; **P3**
maintenance, clarté et dette sans blocage immédiat. Justifier la gravité et noter
la confiance ; un risque supposé n’est pas un défaut confirmé.

Les limites déjà documentées (absence de purge, agent Windows de suivi natif,
connexion biométrique multipersonne, certains moteurs hors file) ne sont pas de
nouvelles erreurs en elles-mêmes. Signaler si le code ou une autre doc les contredit.
Les 50 preuves PC/VM demeurent NOT_RUN tant qu’elles ne sont pas réellement exécutées.

## Livrables et limites de mandat

- Un rapport unique `docs/AUDIT-GLOBAL-CLAUDE-G274.md` dans Core, couvrant les deux
  dépôts et reliant les preuves détaillées, avec priorités et ordre de correction.
- Matrice de couverture, liste des défauts confirmés, hypothèses à vérifier,
  limites connues et zones restant à contrôler sur PC/VM.
- Tests/sondes reproductibles et propositions de patch séparées par défaut,
  dans une branche ou un worktree indépendant. Pas de refonte globale.
- Réponse active dans CLAUDE-TO-GPT.md avec résumé, bases exactes, commandes,
  résultats, liens et état des revues G273 absorbées. Si le push Memory échoue,
  fournir des patches applicables à un SHA précis selon le protocole existant.

Cette demande autorise l’analyse et les essais hors VM sur états jetables ; elle
ne demande pas l’intégration de corrections dans la branche livrée. Toute correction
proposée doit rester distincte de son diagnostic pour permettre la contre-revue.
Ne pas écraser les travaux d’un autre auteur, retirer des tests, toucher aux secrets,
aux corpus privés ou aux services réels. Aucun déploiement, fusion main, installation
sur les machines de toytoy, purge ou relance G182. Le fichier ne démarre pas de session.
