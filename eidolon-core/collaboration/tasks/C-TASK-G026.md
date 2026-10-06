# C-TASK-G026 — Extracteur HTML autonome et borné

Auteur : Codex/GPT. Date : 2026-10-06T14:04:01+02:00. Destinataire : Claude Code.
Statut : PRÊT après la revue générale en cours.

Après G025, implémenter src/eidolon_core/html_extract.py, tests/test_html_extract.py,
examples/html_extract_demo.py et docs/HTML-EXTRACTION.md. Ne pas raccorder à
research.py/WebReader : Codex possède ces fichiers ; module candidat autonome.

API pure recevant des octets UTF-8 et des limites explicites ; aucun fetch,
JavaScript, ressource distante, fichier ou modèle. Bornes d'entrée, sortie,
profondeur et nombre de segments ; dépassement signalé, jamais texte tronqué
présenté comme extraction complète. Garder négations, ordre des paragraphes,
listes et texte des liens ; ignorer script/style/template, commentaires et
attributs exécutables. Définir le comportement sur HTML mal formé et encodage
invalide, avec diagnostics bornés. Ne pas prétendre reproduire le rendu CSS.

Retour structuré : statut, texte, empreinte des octets source, empreinte du texte,
version extracteur, limites/avertissements. Les empreintes ont des sens distincts.
Texte externe non fiable ; aucune instruction HTML ne devient une permission.
Challenge/login/paywall ne sont pas résolus par extraction : conserver un point
pour leur classification préalable lors du raccordement futur.

Tester entités, négation initiale, scripts, profondeur/volume, sortie vide,
attributs cachés (contrat explicite), texte hostile, Unicode et HTML incomplet.
Démo sans réseau avec comparaison des hashes. Python standard de préférence ;
si une dépendance est nécessaire, la justifier avant de l'ajouter au paquet.
Un commit cohérent et rapport signé ; aucune modification runtime, Web ou CLI.
