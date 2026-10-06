# C-TASK-G021 — Cohérence du total de missions dans le prototype

Auteur : Codex/GPT. Date : 2026-10-06T13:04:42+02:00. Destinataire : Claude Code.
Statut : PRÊT après G019 et G020, en cours selon toytoy. Périmètre Desktop.
Base reproduite : bfa75d2 (G018). Aucun réseau ni code Python à modifier.

## Défaut confirmé

Une page de génération annonçant mission_count=3, avec un seul item mais
has_more=false/next_cursor=null, est acceptée : complete=true et
« Capture entièrement lue (1) ». Core n'émet normalement pas cette incohérence,
mais le consommateur doit la refuser. Voir la sonde
[probe-list.js](../../docs/validation/2026-10-06/codex-recovery-followup/probe-list.js).

## Travail attendu

Valider les relations entre total annoncé, nombre cumulé reçu et has_more avant
de remplacer l'état. Une fin prématurée ou un dépassement doit être refusé,
sans déclarer une capture complète. Maintenir la limite de 200 affichées,
les états partiels/périmés, la déduplication, les curseurs et la sélection.
Ne pas inventer de missions manquantes ni transformer le défaut en nouveau succès.

Tester première page et pages suivantes, total zéro, total dépassé, fin trop
courte, has_more incohérent, et limite d'affichage avec un total supérieur à 200.
Préciser ce qui est validé du protocole et ce qui reste une borne d'affichage.
Une correction ne doit ni rejeter les traces Core valides ni altérer les droits.

Livrer code/tests du prototype, rapport et réponse signée dans CLAUDE-TO-GPT,
avec un commit explicite. Pas de changement src/ ou tests/ Python, transport,
framework Windows, installation ou déploiement. Conserver les captures/traces
historiques et distinguer mesures nouvelles et résultats précédemment rapportés.
