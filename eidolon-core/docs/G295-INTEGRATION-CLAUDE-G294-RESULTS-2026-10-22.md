# G295 — Intégration G294, correctifs et contre-validation VM (22 octobre 2026)

## Livrables intégrés

Base Core `feat/eidolon-core-v0.1`, issue de G293 `07092e0`. Audit Claude G294 `33ed60f` fusionné par PR #1. Correctif `0013` appliqué et testé : `evidence_check` sur les réponses de Core avant enregistrement, `core_note=CITATION_UNSUPPORTED` pour les citations absentes du contexte transmis, ou `NUMBER_NOT_IN_SOURCES` pour les nombres absents des entrées utilisateur, sources et observations. Le champ `semantic_relevance_checked=false` **signale expressément la limite** : il ne valide pas la pertinence d'une note. Les deux avertissements sont visibles dans le client Windows connecté.

Les 7 anciens `xfail(strict=True)` du correctif G294 sont devenus des tests PASS obligatoires. La suite de Claude (22 scénarios) est intégrée au dépôt. La CI Core est réépinglée à Memory `be53d1c`, version contenant le holdout G294.

**G295 :** le modèle Qwen3 Eva Hermes Heretic 4B **exactement identifié** reçoit désormais les exemples de citations et l'ordre des souvenirs « meilleur en dernier » dans Core, sans fusionner les rôles système et utilisateur. Le modèle Gemma3 garde son adaptation existante. Aucun autre modèle Qwen n'est affecté; test spécifique ajouté.

## Campagnes modèles réelles, VM100, GTX 1060 6 Go

22 questions de Claude, **par le parcours ConversationAPI → Dialogue → modèle**, avec souvenirs synthétiques contrôlés (pas une interrogation de Qdrant pour ce jeu). Les résultats sont des verdicts automatiques stricts, à interpréter avec leurs critères et sans prétendre à une certification de vérité.

| Profil | PASS | FAIL | Médiane par tour |
|---|---:|---:|---:|
| Gemma3 4B, G292/G294 | **15/22** | 7 | **3,85 s** |
| Qwen Eva Hermes 4B, **avant adaptation** | **7/22** | 15 | **6,65 s** |
| Qwen Eva Hermes 4B, **avec adaptation G295** | **18/22** | 4 | **10,40 s** |

Échecs Qwen adapté : `wrong-benchmark` (abstention), `never-executed` (abstention et chiffre hors contexte), `future-price` (abstention et catégorie de réponse), `secret` (abstention). Les résultats ne justifient pas une bascule automatique de modèle. **Gemma reste le modèle actif**, Qwen demeure une alternative candidate.

## Tests Memory réels, VM110

- Patch `0068` intégré sur `refactor/architecture-v1`, 20 questions contradictoires.
- Qdrant sémantique de production interrogé **en lecture seule**, 20/20 requêtes sans erreur; 12 négatives proches : note piège rang 1 **8/12**, top 5 **11/12**; 8 paraphrases sans mots-clés : rang 1 **6/8**, top 5 **7/8**. Médiane **4,737 s**. Aucun score ne prouve à lui seul la suffisance.
- Suite Memory complète avec Qdrant jetable : **3196 passed, 7 skipped, 3 xfailed, 12 subtests passed** en **159,94 s**, sortie 0. Dossier `docs/G294-MEMORY-HOLDOUT-RESULTS-2026-10-22.md` et journaux privés `/home/toytoy/eidolon-validation/g294/`.

## Contre-validation Core et client

- Suite Core complète finale VM100 : **2317 passed, 43 skipped, 1 warning, 1328 subtests passed** en **215,32 s**, sortie 0.
- Client connecté Windows : `node build.js --check` OK, `node --test` : **200 passed, 43 skipped**, aucun échec, sur VM100.
- Les 43 tests Core ignorés et les 7 Memory ignorés ne sont pas des validations; le test d'isolation Qdrant jetable est inclus.
- Les tests de compatibilité utilisent les contrats existants, sans modification de schéma du pont Memory. Les scénarios physiques Windows/PIXY et une vraie conversation PC restent hors de cette recette.

## Anomalies restant ouvertes

**P1 : réponse fondée sur une vraie citation mais hors sujet.** Exemple : un résultat d'un autre benchmark utilisé pour une question sur un benchmark jamais exécuté. Le correctif `0013` détecte une citation inventée ou un chiffre absent des sources, mais **pas** un chiffre réel tiré d'une mauvaise source. Les questions négatives proches G294 démontrent le risque. Pour corriger sans faux refus massifs, la suite recommandée est un schéma de preuve citée avec extrait exact, puis un contrôle d'entité/version/année calibré sur les holdouts, avec un modèle vérificateur uniquement en recours.

**P2 : performance.** Le Qwen adapté est plus lent que Gemma sur le jeu G294; la latence doit être optimisée après fiabilité.

**P2 : score historique G287.** Son critère d'abstention accepte à tort le mot « pas ». Le banc G287 est conservé pour reproductibilité historique, **mais ne doit plus servir à classer les modèles**. Utiliser le holdout strict G294 et ses sorties.

## Sécurité et décision

Aucune modification du corpus canonique, du modèle d'embeddings ou de l'index Qdrant. Aucune bascule de modèle. Le correctif G294 est **non bloquant** : il signale le doute mais ne prétend pas démontrer la vérité. La priorité reste la réduction des preuves hors sujet avant une future bêta validée.
