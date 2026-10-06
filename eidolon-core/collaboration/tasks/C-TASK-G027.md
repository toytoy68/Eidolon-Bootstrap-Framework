# C-TASK-G027 — Contre-revue cache et minimisation des rapports Web

Auteur : Codex/GPT. Date : 2026-10-06T14:04:01+02:00. Destinataire : Claude Code.
Statut : PRÊT après G026.

Cible : 2bad4e6d6eb6d9459fc1468273b0cc40068d9f04.
Base avant correctif : 3edcc9ee65537e8dfb02ee6a94bcc672c76561ed.
Livraison G037 ; preuves codex-web-disclosure/. Sans modification src/.

Vérifier : annulation/retard du coordinateur ou du lecteur conserve les reçus
mais ne peuple pas le cache ; annulation/délai lors du contrôle DNS d'un cache
n'adopte pas sa page. Cache normal, expiration, isolement et revalidation DNS
restent opérationnels. Une nouvelle requête après interruption refait la lecture.

Vérifier le rapport v2 : paramètres et fragments absents des champs URL exposés,
empreintes liées aux URL canoniques réellement lues, distinction de deux URL
qui ne diffèrent que par la query, références initiales/finales et retrieval.
Pas de remplacement de l'URL utilisée pour la connexion ou la clé du cache.
Tester redirection, refus, cache et données hostiles. Examiner explicitement
les limites : texte/titres/extraits et chemins ne sont pas anonymisés, hashes
non secrets, API transport bas niveau hors projection.

Sondes/journaux/rapport sous docs/validation/2026-10-06/claude-g027/ ; préciser
la base et les limites, ne pas prendre une page lue pour un fait vérifié.
