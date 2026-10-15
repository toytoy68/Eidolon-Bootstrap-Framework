# G260 — Lot annulé après réception de C186

**Ne pas exécuter cette liste.** C186, retrouvé sur `ccr-d3dc80a2-wouvy3`, répond déjà aux dix G258. Ce brouillon local non publié est remplacé par [les dix nouvelles tâches G262](G262-CLAUDE-TASKS.md).

## Répartition préparée avant récupération de la branche Claude

Auteur : Codex/GPT, 15/10/2026, Europe/Paris. Demande directe de toytoy : « Redonne dix tâches à Claude et attaque la suite ».
Bases : Memory `a0cc112abb5deaa459608ed80dbf412b8de7149d`, Core `216647dd3152dfee272ff057ab75e7d540c2ba47`. Dernier retour reçu : C185.

Ce lot reprend les dix tâches G258 encore sans réponse publiée : ce ne sont pas vingt tâches. Si une tâche est déjà faite localement, publier sa preuve sous son identifiant G258 ; ne pas la refaire. Tous les SHA nécessaires sont disponibles. Priorité 1–3, puis 4–7, puis 8–10. Les éléments des propositions restent expérimentaux.

| # | Tâche et correspondance | Livrable attendu |
| --- | --- | --- |
| 1 | G258-1 : contre-revue verrou G259 | Succès, exception, trop grande réponse et déconnexion : second rappel accepté pendant envoi bloqué ; calculs toujours exclusifs et capacité bornée. Tests distincts sans modifier le pont. |
| 2 | G258-2 : réponse immuable | Fournisseur réutilisant un dict mutable ; second rappel modifiant cet objet : premier client reçoit uniquement ses propres octets. Reproducteur TCP ou synchronisation déterministe. |
| 3 | G258-3 : diagnostic UI | Notes absentes/malformées, états inconnus, mémoire non transmise ; diagnostic valide conservé. Source et bundle sous Chromium ; aucun todo supplémentaire. |
| 4 | G258-4 : politique construite directement | HostPolicy contournant validate_host_policy et durée positive arrondie à zéro. Défauts rouges, correctif expérimental, refus avant fabrique. |
| 5 | G258-5 : JSON extrême | 1e999, entiers longs, Unicode/UTF-8, profondeur exacte ; erreurs publiques stables, pas de traceback contenant l'entrée. |
| 6 | G258-6 : chemin remplacé | Ancêtres renommés/substitués, lien, accès refusé, disparition. Distinguer identité du fichier ouvert et identité actuelle du chemin ; décrire limites sans promettre une authenticité. |
| 7 | G258-7 : précontrôle portable et utilisateur ordinaire | Primitives POSIX absentes : refus explicite. Exécuter la politique/instantané sous UID non root ; contre-revoir le correctif de fixture G260 sans toucher au fichier réservé. Linux serveur vs Windows PC documentés. |
| 8 | G258-8 : cohérence des reçus d'alias | Faux alias, mélange générations/digests, rejeu sous autre politique d'horloge/grâce. Aucune autorisation de supprimer déduite du reçu. |
| 9 | G258-9 : budget des projections | Plusieurs archives et révisions ; nombre maximal de points et durée de rétention des anciennes projections. Mesures synthétiques bornées et proposition explicite, sans benchmark modèle. |
| 10 | G258-10 : recette bêta priorisée | Parcours Memory → pont → Core → PC, prérequis et preuves manquantes, ordre court d'essais et critères d'arrêt. Distinguer expérience, CI et VM ; inclure les quatre xfail historiques et modèles réels non qualifiés. |

Pour chaque tâche : commit, fichiers, commande, résultat observé, limites et reproducteur avant correctif. Préserver les patchs originaux et archiver CLAUDE-TO-GPT avant réponse. Ne pas transformer une proposition en production.

Codex réserve : `tests/test_claude_host_policy_g256.py` pour corriger le nettoyage de permissions qui casse la CI non root ; bilans et workflows/pins ; prochaine intégration de maintenance à préciser séparément. Les fichiers expérimentaux `tools/claude_*` et les sondes distinctes restent à Claude. Aucun déploiement, fusion main, suppression de génération, relance G182, capteur ou service.
