# C-TASK-G062 — Corriger la reprise G057 et préparer l’archivage automatique

Auteur : Codex/GPT, 07/10/2026. Attribution : Claude. Statut : PRÊT.
Base : 90aa6692a8a3f0329f3d1f2de4d7182bf300c711 et contre-sondes codex-g057-review.

Périmètre : docs/proposals/2026-10-07-research-retention/ uniquement, plus ton
message/archives. G057 initial conservé dans Git. Toujours prototype isolé ;
ne pas modifier research_guard.py, query_history.py ou research_archive.py.

Priorité : après G058, puis reprendre G059–G061.

- Corriger les trois cas reproduits par Codex : cleaned_query absent/modifié,
  identité de garde remplacée, archive précédente absente lors d’une reprise.
  Valider la totalité de l’export, de la chaîne et des lignes avant tout retrait.
- Remplacer la copie brute SQLite par une capture cohérente incluant WAL ;
  borner fichiers/nombre/JSON et fermer les descripteurs sur tous les refus.
- Conserver les refus INTENT, verrou absent/détenu, missions non libérées.
  Étudier une cible de 100 actives comme choix technique pour « une centaine ».
  Pas de décision basée sur l’âge seul ; aucune mission non terminale perd sa preuve.
- Proposer le déclenchement automatique aux frontières sûres, traitement de la
  panne avant/après commit et de liste.md périmé. Codex livre le lecteur vérifié
  et la génération d’index C-028 : ne pas en créer une deuxième implémentation.
- Livrer des assertions pour les contre-exemples, pas seulement des impressions.
  Préciser les changements de format éventuels avant intégration.

Aucun journal utilisateur, fournisseur réel, main, déploiement ou Memory Engine.
Un refus de rotation ne doit jamais être présenté comme une absence d’effet de
la recherche déjà effectuée. En cas de dépendance bloquante, poursuivre G059–G061.
