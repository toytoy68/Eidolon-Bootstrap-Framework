# G263 — Préparer le rappel pour le compte dédié

Auteur : Codex/GPT, 15 octobre 2026. Reprise demandée par toytoy après G262.

Memory publié : `86950c87fbff54169010042fa1e8887c9bf7465e`, parent `795784a`. [Contrat complet, tests et limites](https://github.com/toytoy68/Eidolon-Memory-Engine/blob/86950c87fbff54169010042fa1e8887c9bf7465e/docs/G263-READONLY-STORAGE-2026-10-15.md). Core modifie uniquement le pin CI et la coordination/documentation dans ce lot.

Le mode explicite `--read-only-storage` permet le rappel sans ouvrir le verrou en écriture ni créer les répertoires. Les verrous existants sont toujours exclusifs et partagés avec les écrivains. Rien n'est déplacé. Les sources Linux locales sont couvertes ; le montage systemd cible, les UID réels du service et le cache reranker restent à qualifier. Les valeurs par défaut restent inchangées.

25 nouveaux tests réussis, 1 ignoré (runtime root) ; 117 tests ciblés et 5 sous-tests réussis au total. Scénarios : rappel simple/projet avec EROFS injecté, HTTP réel, pertes de verrou, fichiers spéciaux/liens, remplacement à l'acquisition, préflight avant écoute, réentrance, exclusivité interprocessus et reprise. Pas de véritable montage readonly exécuté dans ce runtime. Le test chmod sous UID ordinaire doit être exécuté en CI.

Les dix G262 restent attribuées à Claude ; aucun retour après C187 observé sur sa branche 70fc0c6 au début de ce lot. G263 rend leur contre-revue de production possible sans annuler les expériences demandées. [Coordination](../collaboration/GPT-TO-CLAUDE.md).

Publication déjà autorisée dans la session sur les branches de développement. Aucun compte créé, aucune migration, aucun déploiement/main/benchmark G182. Résultats complets CI à ajouter après exécution sur les SHA publiés.
