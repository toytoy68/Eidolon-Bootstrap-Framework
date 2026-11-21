# Eva E5 — réduction de dose

Parent : cycle5 accepté, inchangé. Max learning rate 1e-6 au lieu de 3e-6, autres paramètres conservés. Critères figés avant lancement. Aucun test final réservé évalué.

X1 : HH:MM vers minutes ; X2 : minutes vers jours entiers et reste ; X3 : minutes vers HH:MM. Objectif : améliorer les composants horaires sans dégrader la composition et les acquis.

## Résultats

### Pas 102

| Mesure | Parent recalculé | Candidat |
| --- | --- | --- |
| X1 /96 | 47 | 66 |
| X2 /96 | 80 | 82 |
| X3 /96 | 47 | 43 |
| report | 86 | 84 |
| day0 | 55 | 54 |
| anchors | 26 | 26 |

Gardes : {"full_report": true, "day0": true, "anchors": true, "no_Depart": true, "no_full_format_switch": true, "primitive_stability": false, "legacy_SG_stability": true}.

Décision enregistrée : {"last_step": 102, "guard_passed": false, "learning_passed": false, "qualified": false, "stopped_after102": true, "automatic_promotion": false}.
Qualification expérimentale : False. Aucun remplacement automatique. Diagnostic de transfert hors sélection dans role-transfer-summary.json, canaris relus dans canary-review.json.

Les scores horaires historiques ne sont pas une validation aveugle. Les gains appariés sont exploratoires. La perte de train ne suffit pas à établir une amélioration générale. Les gardes arrêtent la continuation si nécessaire.

Précontrôles : memtester4G sur le même démarrage, SHA doubles, rechargements, qualification DDP quatre updates, contrôle des gradients/masques et sauvegardes vérifiées. Cela ne certifie pas les128G de RAM.

Énergie secteur des seuls intervalles instrumentés : 117.023 Wh. Voir energy-summary.json pour durée et limites.

## Conclusion
X1 progresse de 47 à 66/96, X2 de 80 à 82, mais X3 recule de 47 à 43 : la garde de stabilité primitive échoue. Arrêt après 102 updates, sans seconde passe ni promotion. Le rapport complet recule de 86 à 84/320 et jour0 de 55 à 54/64 ; les acquis restent 26/32. Une sonde conversationnelle introduit aussi une erreur sur le nombre de processeurs logiques. Réduire la dose ne résout donc pas à lui seul les régressions.
