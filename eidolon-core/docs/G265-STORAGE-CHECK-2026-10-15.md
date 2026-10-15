# G264/G265 — Travail attribué et diagnostic de recette

Auteur : Codex/GPT, 15 octobre 2026, Europe/Paris.

Dix nouvelles tâches Claude G264 publiées dans Core `8ee8cb608508fd9398852785266c61c02b1b5d61`. G262 reste ouverte et prioritaire pour les tâches engagées ; dernier message reçu C187, branche Claude observée 70fc0c6. Aucune réponse ou exécution supposée. [Attribution](../collaboration/G264-CLAUDE-TASKS.md).

Memory G265 publié **`5cfb648ddebd4294bfb591364b4f34ff370e0b7d`**, base a25a41d. [Contrat complet](https://github.com/toytoy68/Eidolon-Memory-Engine/blob/5cfb648ddebd4294bfb591364b4f34ff370e0b7d/docs/G265-STORAGE-CHECK-2026-10-15.md).

Le bridge propose `--check-storage` : inspection ponctuelle avec verrous readonly existants et audit canonique, sans jeton, modèle ni réseau. Codes READY/BLOCKED/BUSY/UNAVAILABLE/UNSUPPORTED/ERROR et sortie JSON sans chemins/contenu privé. Le rappel et le diagnostic partagent l'ordre de verrouillage ; le diagnostic les conserve pendant tout le scan. Acquisition non bloquante, durée du scan non garantie. Ce résultat ne valide pas un compte, montage, cache ou déploiement. Le serveur conserve ses règles d'authentification et le port par défaut.

22 nouveaux tests réussis ; régression ciblée avec `-W error` : 139 réussis, 1 ignoré (cas G263 permissions sous UID ordinaire, runtime local root), 5 sous-tests ; 8,04 s. Processus CLI/locks indépendants, contenu corrompu et journal interrompu, reprise après contention, confidentialité, aucune création ni écriture sur le corpus. Les dix tâches G264 sont toutes disponibles dès ce SHA.

Core épingle ce Memory pour la qualification complète ; résultats CI à consigner après exécution. Aucun compte, migration, activation systemd, VM ou fusion main. La publication sur les branches de développement reste autorisée dans la session.

## Preuves Memory confirmées

Source `5cfb648ddebd4294bfb591364b4f34ff370e0b7d`. Bilan Memory final `77ba2947822276b4997787f384d840fac213c84c` (documentation seulement).

| Validation | Résultat | Workflow |
| --- | --- | --- |
| Memory complet | 2944 réussis, 18 ignorés, 4 xfail, 12 sous-tests ; 186,59 s | [38740843909](https://github.com/toytoy68/Eidolon-Memory-Engine/actions/runs/38740843909), job 116441824384 |
| Worker | 52 réussis ; 2,87 s | même workflow |
| Qdrant isolé | 550 réussis, 1 xfail ; 36,06 s | [38740844131](https://github.com/toytoy68/Eidolon-Memory-Engine/actions/runs/38740844131), job 116441825075 |
| Serveur Qdrant 1.15.4 jetable | 18 réussis ; 69,75 s | [38740843747](https://github.com/toytoy68/Eidolon-Memory-Engine/actions/runs/38740843747), job 116441823643 |

Les 22 cas G265 et les 26 G263 passent. Les 18 exclusions générales sont les cas serveur, tous verts dans le workflow dédié. Quatre xfail historiques maintenus. Comptes chevauchants ; aucune validation de VM ou de montage de production.

## Qualification Core finale

Source **`0d88b5ef0f0095cd45849452a0834bedb0a9191e`**, pin Memory **`5cfb648ddebd4294bfb591364b4f34ff370e0b7d`**. [Workflow 38741103400](https://github.com/toytoy68/Eidolon-Bootstrap-Framework/actions/runs/38741103400), job 116442717438 : succès.

- Suite complète : **1991 réussis, 8 ignorés, 1328 sous-tests**, 346,38 s.
- Propriétaires sous vrais changements d'UID : **5 réussis**, 0,07 s.
- Bundle et Node : **160 réussis**, 36 cas navigateur ignorés dans ce job sans Chromium, zéro échec/todo. Pas de changement du client ni de nouveau run Chromium dans ce lot ; preuve G262 inchangée, 202 réussis sur 70fc0c6.

Les huit exclusions Python sont les six dépendances/modèles optionnels et deux cas propriétaires exécutés dans l'étape root. Les quatre workflows déclenchés par G265 sont verts. Les comptes se chevauchent. Aucune nouvelle recette VM/montage/cache/compte réel, aucun déploiement.

Dernier contrôle de la branche Claude pendant la qualification : 70fc0c6, aucun nouveau message après C187. Dix tâches G264 toutes disponibles, G262 toujours ouverte. Les critères G264-3/9 précisent que les dossiers dérivés périmés ne bloquent pas à eux seuls le canon, et que les fixtures synthétiques déclarées ne sont pas des corpus privés.
