# G261/G262 — Réception C186/C187, qualification et prochaine série

Codex/GPT, 15 octobre 2026, Europe/Paris. Sources : Core `216647d`, Claude `6bcbafa`/`0a0f897`, Memory `a0cc112`.

## Livré localement

- Branche Claude retrouvée : `ccr-d3dc80a2-wouvy3`. Fusion Core `48229d6` avec deux parents ; conflit d'ajouts dans ECHANGES résolu en gardant intégralement les deux auteurs. Aucune réponse Claude réécrite.
- Patchs Memory 0052–0054 appliqués avec attribution dans `2b9fb03af445d57d03a933bec2da7d6ab906d8b7` ; compte rendu ultérieur `e8ccd2f`. Originaux conservés dans Core. Le pin CI pointe sur 2b9fb03, à publier **avant** Core.
- G260 : fixture mode 000 restaurée en finally, refus applicatif conservé. Le test sous utilisateur ordinaire n'est pas validé par un succès root.
- G261 : diagnostic de contexte. Un état futur correctement formé INDEX_ affiche une phrase générique, sans reprendre le texte reçu. STALE/UNVERIFIED restent visibles même si partial est faux ou absent. Un diagnostic n'est jamais attribué à une mémoire non envoyée ; états arbitraires ou malformés ignorés. Quatre tests indépendants échouaient avant correction. Source et bundle synchronisés.
- C187 relu : compte dédié recommandé, mais `.write.lock` a+b incompatible avec readonly (verrou absent **et** préexistant). Vrai backend/rappel + EROFS simulé ; aucune VM ni montage réel testé. [Revue détaillée](G261-C187-SERVICE-ACCOUNT-REVIEW.md).
- TODO et QUEUE actualisés. **G258 répondu, G260 annulé, G262 = dix tâches nouvelles**, centrées sur préparation du compte/recette et contre-revues ciblées. Pas de suppression, adoption en production, installation ou modèle réel.

## Preuves de cette session

| Contrôle | Résultat réellement observé |
| --- | --- |
| Nouvelles sondes Memory 0052–0054 | 23 réussies, -W error, 0,75 s |
| Memory complet Python 3.12 | 2890 réussis, 6 échecs, 18 ignorés, 4 xfail, 12 sous-tests ; 119,70 s |
| MCP loopback après installation locale socksio | 1 réussi, -W error, 1,38 s |
| Core ciblé G256/G258/G254 avec intégration Memory | 130 réussis, -W error, 1,63 s |
| UI G261 avant correction | 4 échecs, 7 réussis |
| UI ciblée après correction, incluant sondes Claude | 20 réussis, 10 ignorés (Chromium absent), aucun todo |
| Node complet | 160 réussis, 36 ignorés (Chromium absent), aucun échec/todo ; 7,89 s |
| Core complet avec intégration Memory | 1928 réussis, 22 échecs, 51 ignorés, 1317 sous-tests ; 285,55 s |
| Bundle et diff | build --check et git diff --check réussis |

Les comptes se chevauchent. Les suites complètes **ne sont pas vertes dans ce runtime** :

- Memory : cinq échecs de socket AF_UNIX (PermissionError, runtime) et un échec de dépendance socksio, recontrôlé seul après installation. Les cinq AF_UNIX restent non validés ; on ne recompose pas un total vert.
- Core : deux échecs os.chown (EINVAL), vingt échecs de socket AF_UNIX (PermissionError). La liste couvre les préflights de communication, les relais/moniteurs DARME et sd_notify. Aucun de ces échecs n'a été masqué ou transformé en skip.
- Core : 45 exclusions des essais de sauvegarde/chiffrement faute de `age` et six dépendances d'identité optionnelles absentes. Les sous-tests diffèrent de la CI pour ces raisons ; ne pas comparer seulement les totaux.
- Chromium : Playwright disponible mais binaire absent. Le téléchargement renvoie une archive vide/invalide ; pas de navigateur exécuté. Les 187 passes Chromium de G259 portent sur **216647d**, pas sur le nouveau bundle.
- Non root : changement d'UID local refusé, donc pas de contre-preuve verte G260 sous utilisateur ordinaire. Le rouge originel a été lu dans le run CI 38722774251.

## Historique du blocage de publication

Deux pushes ont été bloqués par la revue automatique. La seconde décision dit que l'autorisation historique récupérée n'est pas considérée comme texte utilisateur autorisant la destination. Le remote vérifié est le dépôt GitHub public de toytoy68 ; aucun contournement par API ou autre canal.

Travail préparé et committé localement ; les tâches ne sont pas transmises. Après confirmation explicite :

1. Relire les têtes distantes et intégrer tout nouvel ajout sans écrasement.
2. Publier Memory sur `refactor/architecture-v1`, puis Core sur `feat/eidolon-core-v0.1` (jamais main).
3. Vérifier les nouveaux workflows, particulièrement test non root, suite Core et Chromium ; conserver les résultats réellement obtenus.
4. Mettre à jour les bilans et préciser à Claude le SHA publié, sans prétendre que le fichier démarre sa session.

MCP en erreur -32603. Aucun compte créé, migration, déploiement, fusion main, données privées ou benchmark G182.

## Publication autorisée et effectuée via GitHub

Confirmation explicite de toytoy le 15/10 à 14 h 02 Europe/Paris. Git CLI sans identifiants, publication par le connecteur GitHub avec contrôle du HEAD attendu et sans force. Memory publié `f534315a5cbc8e06cae2f9a3a3d575bec698bee6`, contenant les changements des commits locaux 2b9fb03/e8ccd2f et la confirmation. Core : parent de développement 216647d et second parent Claude 0a0f897, afin de conserver ses commits. Les SHA Codex locaux cités plus haut décrivent les préparations locales ; les références publiées font foi pour la reprise. Pin CI mis à jour sur Memory publié. G262 ouvert, résultats CI à récupérer. Aucun main ni déploiement.

## Résultat final après publication

Les quatre workflows sont verts sur Memory f534315 et Core 70fc0c6. [Bilan final et journaux](G262-PUBLICATION-2026-10-15.md) : 2896 Memory, 1991 Core, 202 Chromium et 5 contrôles root. Les limitations et échecs de l'exécution locale ci-dessus restent un historique exact ; ils ne remplacent pas les résultats CI ultérieurs.
