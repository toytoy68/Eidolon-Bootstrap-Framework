# G223 — Reprise des tests et intégration Core / Memory

Date : 14 octobre 2026, matin. Exécution réelle sur GitHub Actions, Python 3.13 / Ubuntu ; aucune VM de production modifiée.

## Résultats confirmés

- **Core** : GitHub Actions run 38515724706, SHA `0cf3f2cc414cd007ae219458a7c04f3a44457b47`, **1594 passed, 64 skipped, 1283 subtests passed, 5 warnings**, durée 298,29 s. Statut workflow SUCCESS. Les tests ignorés et les avertissements doivent être qualifiés avant une bêta.
- **Memory** : première exécution run 38515748725, 2198 passed, 2 failed, 3 skipped. Deux défauts : attente WAIT dans un ancien test, rejet des intentions répétées par document. Corrections : `b0f5f0d`, `cc971c6`.
- **Memory relancée** : run 38515986136, SHA `cc971c67d15731b2855cd2ee70dbd27a10a7ef11`, **2200 passed, 3 skipped, 12 subtests passed**, durée 137,21 s. Statut SUCCESS.
- Les 19 scénarios du worker de référence, les moteurs Qdrant réels, les services VM, les périphériques Windows et les essais MCP ne sont pas couverts par ces succès.

## Intégration Core publiée

- `memory_bridge_client.py` : refus des contrôles dans les requêtes, enveloppe de réponse typée, vérification des bornes.
- `memory.py` : BridgeMemory valide le contexte via `validate_context` avant de le fournir au dialogue.
- Tests : `test_memory_bridge_client.py` et `test_memory_bridge_boundary.py`, incluant enveloppe invalide, permissions du token et lien symbolique.
- SHAs : `ffd5aa3`, `7a91f6d`, `1350a19`, `a79649f`, `daef92d`.

## Infrastructure de validation

- Workflow Memory `.github/workflows/memory-tests.yml`, premier démarrage invalide corrigé, puis compilation et pytest réellement exécutés.
- Workflow Core `.github/workflows/core-tests.yml`, tests exécutés sur la branche de développement.
- GitHub Actions ne reproduit pas la VM Debian, la configuration réelle, le tunnel SSH, le GPU ou les secrets de production.

## Suite prioritaire

1. Auditer les 64 tests Core ignorés et les 3 tests Memory ignorés.
2. Intégrer les patchs Core I1/W1 après revue, puis exécuter à nouveau Core.
3. Implémenter l'adaptateur worker avec relecture canonique et autorisation par profil, sans suppression Qdrant.
4. Rejouer le contrat de 19 scénarios et les sondes Qdrant isolées.
5. Restaurer MCP/Cloudflare puis exécuter B01–B12 sur VM et PC avec sauvegardes vérifiées.

Aucun merge main, aucun déploiement VM, aucune suppression automatique.
