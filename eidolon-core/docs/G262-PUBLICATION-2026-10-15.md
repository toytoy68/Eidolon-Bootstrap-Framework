# G262 — Publication et qualification finales, 15 octobre 2026

Codex/GPT. Publication explicitement confirmée par toytoy à 14 h 02 Europe/Paris ; résultats CI vérifiés dans les journaux après fin des jobs. Les quatre workflows déclenchés sont verts.

## Sources publiées

- Memory code et tests : `f534315a5cbc8e06cae2f9a3a3d575bec698bee6` ; bilan documentaire ultérieur `795784a34f566d02c04eb184b06c13326d61bb0c`.
- Core code, tests et dix tâches G262 : `70fc0c688e3f2cda9aff9fd575a85273b32d780b`, pin Memory exact f534315. Parents : développement `216647d` et Claude `0a0f897` ; ses commits C186/C187 sont conservés.
- Les arbres Git publiés ont été comparés aux arbres préparés : identiques. La publication via connecteur utilise le HEAD attendu et refuse le push forcé. Les SHA Codex locaux des rapports précédents sont des repères de préparation, pas les SHA distants.

## Résultats observés

| Validation | Résultat |
| --- | --- |
| [Memory complet](https://github.com/toytoy68/Eidolon-Memory-Engine/actions/runs/38731894360) | **2896 réussis**, 18 ignorés, 4 xfail historiques, 12 sous-tests ; 272,31 s |
| Worker, même run | **52 réussis** ; 3,44 s |
| [Contrat Qdrant ciblé](https://github.com/toytoy68/Eidolon-Memory-Engine/actions/runs/38731894351) | **550 réussis**, 1 xfail ; 36,97 s |
| [Core complet, utilisateur ordinaire](https://github.com/toytoy68/Eidolon-Bootstrap-Framework/actions/runs/38732111130) | **1991 réussis**, 8 ignorés, 1328 sous-tests ; 325,89 s |
| Propriétaires du jeton, étape root du même run | **5 réussis** ; 0,06 s |
| [Chromium](https://github.com/toytoy68/Eidolon-Bootstrap-Framework/actions/runs/38732111165) | **202 réussis**, aucun échec, ignoré ou todo |

Le scénario mode 000 de G260 s'exécute sous utilisateur ordinaire dans le job principal ; le correctif de nettoyage est donc confirmé, sans retrait de l'assertion de refus. Les erreurs locales AF_UNIX/chown ne se reproduisent pas dans ce runner. Les nouveaux diagnostics G261 et le bundle sont qualifiés dans Chromium réel.

Comptes chevauchants. Les 18 exclusions Memory sont les scénarios réservés au serveur Qdrant dédié : aucune nouvelle exécution serveur n'est revendiquée. Les 8 exclusions Core = six dépendances d'identité optionnelles et deux contrôles de propriétaire exécutés séparément sous root. Les quatre xfail historiques restent ouverts ; une CI verte n'est pas une recette VM/PC/modèle réel.

## Collaboration et suite

- C186/C187 reçus et intégrés, 0052–0054 conservés et appliqués ; G258 entièrement répondu.
- Brouillon G260 annulé ; **dix nouvelles tâches G262 publiées**, disponibles dans GPT-TO-CLAUDE et G262-CLAUDE-TASKS. Pas de nouvelle réponse Claude supposée ni de session déclenchée.
- TODO et QUEUE actualisés. Le code du présent complément documentaire est identique au code recetté ci-dessus ; aucune raison de relancer les suites pour ce seul bilan.
- Compte dédié C187 recommandé mais non adopté/activé ; incompatibilité du verrou a+b avec readonly toujours ouverte, confiée aux préparations G262.
- Aucun main, déploiement, migration, compte créé, corpus privé ou relance G182. MCP indisponible au dernier contrôle ; la recette VM/PC reste distincte.
