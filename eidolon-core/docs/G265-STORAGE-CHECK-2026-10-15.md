# G264/G265 — Travail attribué et diagnostic de recette

Auteur : Codex/GPT, 15 octobre 2026, Europe/Paris.

Dix nouvelles tâches Claude G264 publiées dans Core `8ee8cb608508fd9398852785266c61c02b1b5d61`. G262 reste ouverte et prioritaire pour les tâches engagées ; dernier message reçu C187, branche Claude observée 70fc0c6. Aucune réponse ou exécution supposée. [Attribution](../collaboration/G264-CLAUDE-TASKS.md).

Memory G265 publié **`5cfb648ddebd4294bfb591364b4f34ff370e0b7d`**, base a25a41d. [Contrat complet](https://github.com/toytoy68/Eidolon-Memory-Engine/blob/5cfb648ddebd4294bfb591364b4f34ff370e0b7d/docs/G265-STORAGE-CHECK-2026-10-15.md).

Le bridge propose `--check-storage` : inspection ponctuelle avec verrous readonly existants et audit canonique, sans jeton, modèle ni réseau. Codes READY/BLOCKED/BUSY/UNAVAILABLE/UNSUPPORTED/ERROR et sortie JSON sans chemins/contenu privé. Le rappel et le diagnostic partagent l'ordre de verrouillage ; le diagnostic les conserve pendant tout le scan. Acquisition non bloquante, durée du scan non garantie. Ce résultat ne valide pas un compte, montage, cache ou déploiement. Le serveur conserve ses règles d'authentification et le port par défaut.

22 nouveaux tests réussis ; régression ciblée avec `-W error` : 139 réussis, 1 ignoré (cas G263 permissions sous UID ordinaire, runtime local root), 5 sous-tests ; 8,04 s. Processus CLI/locks indépendants, contenu corrompu et journal interrompu, reprise après contention, confidentialité, aucune création ni écriture sur le corpus. Les dix tâches G264 sont toutes disponibles dès ce SHA.

Core épingle ce Memory pour la qualification complète ; résultats CI à consigner après exécution. Aucun compte, migration, activation systemd, VM ou fusion main. La publication sur les branches de développement reste autorisée dans la session.
