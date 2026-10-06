# C-TASK-G018 — Inventaire paginé dans le prototype Desktop

Auteur : Codex/GPT, 06/10/2026. Statut : prêt après G015/G017.
Cible du contrat : `d3306151c634bae73af0bfd96e8c13e603f68c3c`, C-008e.
[Contrat](../../docs/MISSION-LIST.md) ·
[trace Core](../../docs/validation/2026-10-06/codex-mission-list/demo.json).

Développer un consommateur JS pur de eidolon-mission-list/1 et le raccorder au
banc du prototype existant. Aucune requête réseau, aucun accès SQLite, aucune
commande réelle. Ne pas modifier les sources/tests Python.

- Assemblage borné de pages d'une seule génération ; champs/types validés,
  entiers JS exacts, store_id et protocole contrôlés. Définir une limite totale
  visible (par exemple 200 missions), jamais prétendre avoir tout affiché si tronqué.
- Pagination sans perte/doublon ; répétition, réponse tardive, déconnexion et
  changement de génération. RESET_REQUIRED garde l'ancien inventaire explicitement
  périmé et exige une nouvelle lecture explicite ; aucune fusion de générations.
- Choisir une mission lance uniquement une lecture simulée client-sync/1 de cet
  identifiant. Ne jamais convertir next_cursor de la liste en curseur d'événements.
  Une ancienne réponse pour une autre sélection n'écrase pas la mission affichée.
- Montrer liste vide, objectif null, annulation demandée et REVIEW_REQUIRED
  sans confusion de statut, succès ou permission. Aucun bouton d'exécution.
- Conserver la trace Core observée avec son empreinte ; variantes séparées et
  badges réellement « observé » / « dérivé », pas seulement TRACE C-008a.

Tests de logique et au moins trois parcours UI si Chromium disponible : pagination
complète, reset entre pages, sélection changée pendant une réponse en vol.
Si les sources ne permettent pas de construire une capture cohérente de sélection,
utiliser une fixture dérivée explicitement étiquetée, jamais une fausse mesure Core.

Livraison : commit distinct ; docs/validation/2026-10-06/claude-g018/ avec preuves,
limites et commande reproductible. Pas de framework Windows choisi ici, pas de
paquet installé, aucun accès VM/Windows/NAS, pas de projet GUI parallèle.
