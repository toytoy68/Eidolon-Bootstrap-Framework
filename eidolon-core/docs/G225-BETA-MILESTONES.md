# G225 — Contrat de passage vers la bêta Core + Memory

Date : 14 octobre 2026. Cette fiche ne constitue pas une recette exécutée.

## Jalons

**J1 — CI Core et Memory verts :** suites sur SHAs figés, sans échec inattendu. Le runner doit inclure age, OpenSSL, FFmpeg et cryptography pour ne pas ignorer silencieusement les tests critiques de sauvegarde, média et Darme. Les skips d'intégration réelle doivent rester explicites.

**J2 — Worker Memory sans effets dangereux :** provenance document/révision, droits de profil, état Qdrant vérifié, accusé d'indexation, relecture canonique immédiatement avant l'action. Aucune suppression automatique.

**J3 — Core ↔ Memory ↔ PC :** recette B01–B12 sur VM isolées et PC Windows, avec historique, mémoire sourcée, refus d'action, dégradation, redémarrage et restauration.

**J4 — Bêta candidate :** tests reproductibles, sauvegardes, surveillance Darme, diagnostic Web I1/W1, SOUL chargé, documentation d'exploitation et rollback. Validation humaine avant fusion main.

## Conditions bloquantes

Un workflow vert ne démontre ni la connectivité MCP, ni les permissions du serveur, ni les performances du GPU. Les avertissements de threads et les tests ignorés sont des dettes de qualification, pas des succès. Une source mémoire non disponible ne doit pas être remplacée par une réponse inventée.

## Prochaines tâches après J1

1. Auditer les skips restants et warnings de threads.
2. Rejouer les 19 scénarios de worker sur une implémentation réelle isolée.
3. Vérifier le bridge Memory réel et la fraîcheur I1 en dialogue.
4. Vérifier W1 sous charge et après expiration DNS.
5. Restaurer l'accès MCP et exécuter B01–B12 sur VM/PC.
