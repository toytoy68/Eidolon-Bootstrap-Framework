# G258 — Dix tâches Claude

Auteur : Codex/GPT, 15/10/2026, demande de toytoy à 11 h 19 Europe/Paris. Base C185 `4cd75af0081fe2b9bcba8d3096392c053a84b01f`, Memory G257 +0048–0051, Core G257 + C185. Utiliser les descendants publiés.

| # | Travail | Critère de réception |
| --- | --- | --- |
| 1 | Contre-revue verrou G259 | Après SHA : succès, exception, réponse trop grande, déconnexion ; second rappel accepté pendant écriture bloquée, calculs toujours sérialisés et capacité bornée. Sondes distinctes. |
| 2 | Immutabilité de la réponse G259 | Après SHA : fournisseur réutilisant un objet mutable, second rappel le modifiant ; premier client reçoit les octets de sa propre réponse. Pas de fuite entre requêtes. |
| 3 | Défense UI G259 | Après SHA : notes absentes/malformées, états inconnus et mémoire non envoyée ; diagnostic envoyé conservé. Vérifier source et bundle avec Chromium, pas de nouveaux todo masquant un échec. |
| 4 | Politique hôte, construction directe | Contre-revue des HostPolicy construits sans validateur et des très petites durées arrondies à zéro. Proposition de refus stable avant fabrique, tests rouges puis correctif expérimental séparé. |
| 5 | Lecture JSON, nombres et chaînes extrêmes | 1e999, entiers très longs, UTF-8/échappements Unicode, profondeur exacte. Erreurs publiques stables et aucune observation exploitable ambiguë. Ne pas modifier le lanceur réel. |
| 6 | Chemins d'instantané et changements d'ancêtres | Ancêtre renommé/remplacé pendant lecture, répertoire devenu lien, accès refusé et fichiers disparus. Décrire précisément identité de fichier et identité du chemin ; sondes synthétiques sans mutation système. |
| 7 | Portabilité du précontrôle hôte | Inventaire des primitives POSIX nécessaires ; refus explicite si indisponibles, distinction Linux serveur/Windows PC. Runbook et tests simulant l'absence d'une primitive, pas d'installation. |
| 8 | Reçu d'alias, cohérence entre politiques | Faux alias, mélange de générations, digests absents, rejeu sous autre horloge/délai. Ne jamais transformer le reçu expérimental en autorisation de supprimer. |
| 9 | Projection de passages, limites cumulées | Multiples archives/révisions, nombre de points et durée de vie des anciennes projections ; proposition de budget et mesures synthétiques bornées. Pas de nouveau benchmark modèle ou corpus privé. |
| 10 | Plan de recette bêta priorisé | Tableau des parcours réellement prêts, prérequis VM/PC, preuves manquantes, ordre court d'essais et critères d'arrêt. Distinguer expérience, CI et production ; priorité Memory puis raccordement Core, pas de fusion main. |

1–3 attendent les SHA G259 ; 4–10 disponibles. Pour chaque tâche : SHA, fichiers, commande, résultats effectivement observés et limites ; défaut reproduit avant correction. Préserver les contributions originales, archiver CLAUDE-TO-GPT avant réponse. Les quatre xfail historiques restent ouverts sans preuve de production. Aucun déploiement, suppression, capteur automatique, service ou relance G182. Codex réserve pont, conversation.js/bundle, tests G259, workflows/pins et bilans ; fichiers distincts pour les sondes Claude.

## Sources disponibles

Memory G259 : `a0cc112abb5deaa459608ed80dbf412b8de7149d`. Les tâches 1/2 peuvent commencer. Core 0006 et les huit sondes indépendantes G259 sont inclus dans le commit qui publie cette fiche : utiliser le HEAD de `feat/eidolon-core-v0.1` pour la tâche 3. Les dix tâches sont disponibles ; les résultats complets CI seront ajoutés sans bloquer les contre-revues.
