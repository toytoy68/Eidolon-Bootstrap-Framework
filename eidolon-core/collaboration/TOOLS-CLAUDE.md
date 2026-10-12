# Bibliothèque d'outils de Claude (session Claude Code, cloud)

Auteur : Claude. Date : 12/10/2026, Europe/Paris. Demande de toytoy : « la
liste des outils disponibles dans votre librairie ».

Ce sont les outils de **cette session de développement**, pas ceux du
runtime Eidolon. Une capacité n'est pas une permission. Mes règles de projet
(pas de VM, pas de fusion sur main, pas de PR sans demande, etc.)
s'appliquent par-dessus.

Statut : **utilisé** (dans ce projet), **disponible** (jamais utilisé ici),
**différé** (chargé à la demande avant usage), **bloqué** (essayé, échec).

## 1. Fichiers, code et terminal

| Outil | Rôle | Statut |
| --- | --- | --- |
| `Bash` | Commandes dans le conteneur Linux : Git, Python, Node, tests, navigateur Chromium et Playwright | utilisé |
| `Read` | Lire un fichier, une image, un PDF | utilisé |
| `Write` | Créer ou remplacer un fichier | utilisé |
| `Edit` | Remplacement exact dans un fichier | utilisé |
| `Glob` | Trouver des fichiers par motif | utilisé |
| `Grep` | Chercher dans le contenu (ripgrep) | utilisé |
| `NotebookEdit` | Modifier un notebook Jupyter | différé |
| `EnterWorktree` / `ExitWorktree` | Copie de travail Git isolée | différé |
| `Monitor` | Surveiller une condition (attente active bornée) | différé |

## 2. Web

| Outil | Rôle | Statut |
| --- | --- | --- |
| `WebSearch` | Recherche Web (résultats et liens) | utilisé (12/10) |
| `WebFetch` | Lire une page Web | **bloqué** pour brave.com et developers.google.com (DNS) |
| Sortie HTTPS du terminal | Par proxy imposé | github.com et PyPI : OK ; huggingface.co, wenet.org.cn, modelscope.cn, download.pytorch.org : **bloqués** |

## 3. GitHub (connecteur MCP `github`, limité au dépôt Core)

Tous **différés**, aucun utilisé ici : `get_file_contents`,
`create_or_update_file`, `push_files`, `delete_file`, `create_branch`,
`list_branches`, `list_commits`, `get_commit`, `search_code`,
`search_commits`, `search_repositories`, `search_issues`,
`search_pull_requests`, `search_users`, `list_issues`, `issue_read`,
`issue_write`, `add_issue_comment`, `sub_issue_write`, `list_issue_types`,
`list_issue_fields`, `get_label`, `list_pull_requests`,
`pull_request_read`, `create_pull_request`, `update_pull_request`,
`update_pull_request_branch`, `merge_pull_request`,
`pull_request_review_write`, `add_comment_to_pending_review`,
`add_reply_to_pull_request_comment`, `resolve_review_thread`,
`unresolve_review_thread`, `request_copilot_review`,
`enable_pr_auto_merge`, `disable_pr_auto_merge`, `actions_list`,
`actions_get`, `actions_run_trigger`, `get_job_logs`, `get_check_run`,
`list_releases`, `get_latest_release`, `get_release_by_tag`, `list_tags`,
`get_tag`, `get_me`, `get_teams`, `get_team_members`,
`list_repository_collaborators`, `fork_repository`, `create_repository`,
`run_secret_scanning`, `update_issue_comment`.

Je pousse par `git` dans le terminal. Le dépôt Memory n'est **pas** dans mon
périmètre GitHub : poussée refusée (403), d'où les patchs.

## 4. Sessions et automatisation Claude Code (connecteur `claude-code-remote`)

Tous **disponibles**, aucun utilisé pour Eidolon :
- **Sessions** : `create_session`, `send_message`, `get_session`,
  `list_sessions`, `list_events`, `get_event`, `interrupt_session`,
  `archive_session`, `unarchive_session`, `set_session_title`,
  `set_session_tags`, `list_environments` ;
- **Rappels et tâches planifiées** : `send_later`, `create_trigger`,
  `update_trigger`, `delete_trigger`, `fire_trigger`, `get_trigger`,
  `list_triggers`, `watch_url`, `unwatch_url` ;
- **Dépôts** : `list_repos`, `add_repo`, `register_repo_root` ;
- **Suivi de PR** : `subscribe_pr_activity`, `unsubscribe_pr_activity` ;
- **Aide sur l'environnement** : `read_documentation`.

Plus, en local : `ScheduleWakeup` ; `CronCreate`, `CronDelete` et `CronList`
(différés).

Aucune de ces commandes ne lance de session Eidolon : ce fichier ne démarre
rien.

## 5. Agents et organisation du travail

| Outil | Rôle | Statut |
| --- | --- | --- |
| `Agent` | Sous-agent (exploration, plan, tâche générale) | disponible, non utilisé ici |
| `SendMessage`, `ListAgents` | Parler à un sous-agent ou à une autre session | différé ou disponible |
| `TaskCreate`, `TaskUpdate`, `TaskList`, `TaskGet`, `TaskStop` | Liste de tâches de la session | utilisé (anciennes tâches G032–G160) |
| `EnterPlanMode`, `ExitPlanMode` | Mode « plan d'abord » | différé |
| `AskUserQuestion` | Poser une question à choix à toytoy | disponible |
| `ReadNotifications`, `PushNotification` | Notifications de session | disponible ou différé |
| `ReportFindings` | Rapport de revue de code typé | disponible |

## 6. Documents, pages et fichiers pour toytoy

| Outil | Rôle | Statut |
| --- | --- | --- |
| `SendUserFile` | Envoyer un fichier dans le chat (captures) | utilisé (12/10) |
| `Artifact`, `ArtifactComments`, `ArtifactData` | Pages privées publiées sur claude.ai | disponible ou différé, non utilisé |
| `DesignSync` | Synchronisation de design | différé |
| Claude Docs (`batch`, `update`, `guide` ; `create`, `read`, `query`, `export`, `delete` différés) | Documents partagés | disponible, non utilisé |

## 7. Extensions, skills et connecteurs

- **Gestion** : `Skill`, `SuggestSkills`, `ListSkills`, `SearchSkills`,
  `ListPlugins`, `SearchPlugins`, `SuggestPluginInstall`, `ListConnectors`,
  `SuggestConnectors`, `SearchMcpRegistry`, `ListMcpResourcesTool`,
  `ReadMcpResourceTool`, `ReadMcpResourceDirTool`, `ToolSearch`.
- **Skills proposés** dans la session :
  - revue de code ;
  - revue de sécurité ;
  - simplification ;
  - lancement d'application ;
  - documents Word, PDF, PowerPoint, Excel ;
  - recherche approfondie ;
  - navigateurs (pane intégré, Chrome) ;
  - contrôle de l'ordinateur ;
  - création de skills ;
  - graphiques ;
  - configuration de Claude Code.
- Les skills « navigateur », « contrôle de l'ordinateur » et Chrome
  demandent l'application de bureau reliée au PC de toytoy : **non
  disponibles** dans cette session cloud.
- **Connecteur « Eidolon Collaboration MCP »** : **absent** de ma
  bibliothèque.

## 8. Ce que je n'ai pas

Aucun accès SSH ou réseau à VM100, VM101, VM110, au NAS ou au PC Windows.
Aucun GPU. Aucun secret d'Eidolon.
