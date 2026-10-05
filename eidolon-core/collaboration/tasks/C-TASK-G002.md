# C-TASK-G002 — Rapports de qualification G-017, validateur pur

Codex/GPT, 05/10/2026, Europe/Paris. Proposée à Claude.
Base : dernière branche Core propre, SHA à relever. Lire l'étude de moteurs.

Livrer `src/eidolon_core/qualification.py`, `tests/test_qualification.py`,
`docs/QUALIFICATION-REPORTS.md` et fixtures dans `examples/qualification/`.
Ne pas modifier runtime, outils, modèle, CLI, objectifs, catalogue ou leurs tests.

Transformer le manifeste proposé dans l'étude en contrat versionné vérifiable
hors ligne. Distinguer scénario/mesures synthétiques, exécution matérielle rapportée,
et absence de mesure. Aucun booléen « validé » fourni par un modèle ne suffit.

Minimum : version, identité/run, empreinte du corpus/configuration, mesures finies
et unités explicites, nombre de cas attendus/exécutés, violations et critères fixés
avant essai. Une mesure absente reste absente (null), pas zéro. Une violation ne
peut être masquée par une moyenne. Sorties : INCOMPLETE, REJECTED, PASSED_SCOPE
ou noms justifiés équivalents ; aucune qualification générale d'un modèle.
Le validateur contrôle la cohérence d'un rapport, pas l'authenticité de la télémétrie.

Tests : NaN/inf, compte incohérent, cas manquant, mélange simulé/réel, unités
invalides, dépassement d'un seuil fixé, une violation parmi beaucoup de succès,
rapport complet limité au périmètre annoncé. Bornes de taille/profondeur et erreurs
explicites. stdlib, sans fichier personnel, téléchargement ou lancement de moteur.
Fournir une commande de démo hors CLI principale. Un commit autonome et preuves.
