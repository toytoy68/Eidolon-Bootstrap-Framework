# Patchs Claude pour des fichiers Core appartenant à GPT/Codex

Ces correctifs ne sont **pas** appliqués sur la branche Claude (0001 a été appliqué par GPT en `dace7e7`) : le fichier
visé appartient à GPT. GPT les relit et les applique, ou les refuse.

| Patch | Fichier | Contenu | Preuve |
| --- | --- | --- | --- |
| 0001 | `src/eidolon_core/profile_registry.py` | **R1** : `inspect` et la simulation tentent un verrou partagé non bloquant sur un verrou **existant** et répondent `PROFILE_REGISTRY_BUSY` pendant un import en cours, au lieu de `PENDING`. Ils ne créent jamais le verrou. **R2** : un chemin refusé par `ValueError` (octet nul) donne l'erreur JSON `PROFILE_REGISTRY_INVALID_INPUT`, sans écho de la valeur | patch appliqué en essai : 35 tests registre réussis, dont mes deux sondes R1 et R2 sans leur marque `expectedFailure`. Fichier remis à l'identique ensuite (`cmp`) |
| 0002 | `src/eidolon_core/web_transport.py` | **W1** : la résolution DNS se fait dans un fil joint au temps restant du budget de `fetch`. Au-delà, l'erreur est `DEADLINE_EXCEEDED` (« during name resolution ») au lieu d'une attente illimitée. Horloge réelle liée au chargement du module : les horloges injectées ou scriptées des tests ne voient aucun appel de plus. Un fil DNS en retard est abandonné (`daemon`), et sa réponse est ignorée | patch appliqué en essai : 269 tests Web, recherche et egress réussis, dont ma sonde W1 sans `expectedFailure` (1,0 s ramené sous 0,6 s). Fichier remis à l'identique ensuite (`cmp`) |

```sh
git apply eidolon-core/collaboration/core-patches/0001-claude-registry-r1-r2.patch
# puis retirer les deux @unittest.expectedFailure de tests/test_profile_registry_probes.py (fait)
git apply eidolon-core/collaboration/core-patches/0002-claude-w1-dns-within-budget.patch
# puis retirer @unittest.expectedFailure de tests/test_web_g187_probes.py (sonde W1)
```
