# C-TASK-G057 — Concevoir la rotation explicite de la garde

Auteur : Codex/GPT, 07/10/2026 Europe/Paris. Attribution : Claude. Statut : PRÊT.
Base intégrée : `608e115b948675dac601b004d3a4d3f54b744adf` (G050–G053 inclus).

## Périmètre

`docs/proposals/2026-10-07-research-retention/`

Traiter G051-1/2 : contrat et prototype isolé export avant retrait, fichier privé publié exclusivement, refus si INTENT, coupures à chaque frontière, détection de copie/restauration et conservation des empreintes. Ne pas supprimer le journal actif, recréer un verrou absent automatiquement ni décider une durée de rétention. Aucun changement research_guard.py ; Codex travaille sur C-019.

## Livraison

Un commit distinct, message signé avec SHA, commandes exécutées, résultats et limites. Préserver les preuves précédentes. Enchaîner la tâche prête suivante si une dépendance bloque. Aucun main, déploiement, fournisseur réel ou accès aux données personnelles.

## Actualisation G075

C-019 publié en 2a98a9a : consulter docs/QUERY-HISTORY.md. Le schéma 2 comprend
cleaned_queries et une empreinte de liaison dans le descripteur. Conserver ces
liens et le texte lors d’un export ; ne pas transformer des lignes historiques
sans texte en requêtes connues. La lecture locale reste la seule exposition.


## Actualisation G076

C-021 publié en 9ee40c9 : `operation_id` optionnel lie le descripteur à une
mission. Conserver cette liaison. Un rapport COMPLETED peut encore servir
à vérifier un résultat RETURNED après reprise ; un export/retrait ne doit pas
rendre cette preuve indisponible sans contrat explicite. L’âge seul ne suffit
pas à conclure que la mission est terminée. Toujours prototype isolé.
