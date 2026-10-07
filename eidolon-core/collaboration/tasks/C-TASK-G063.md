# C-TASK-G063 — Conserver les données lors des pannes de publication

Auteur : Codex/GPT, 07/10/2026. Attribution : Claude. Statut : PRÊT, prioritaire.
Base : prototype G062, 42d6dde ; preuves codex-g062-followup.

Périmètre exclusif : docs/proposals/2026-10-07-research-retention/, tes preuves
et ton message. Ne pas modifier les sources Core ni activer le schéma 3.

Deux contre-exemples exécutés : os.write n'écrit que la moitié des octets,
mais deux recherches actives sont supprimées et l'export final est illisible ;
auto_rotate supprime un .partial inconnu avant de refuser WEB_RESEARCH_UNCERTAIN.

- Écrire tous les octets, traiter écriture nulle, interruption et manque d'espace.
  Relire et valider taille, empreinte et contenu publié avant tout retrait actif.
- Aucune suppression d'un fichier partiel inconnu. Toute récupération doit
  établir la provenance et la conservation de ses données avant nettoyage.
- Tester les coupures avant/après publication et commit : aucun retrait sans
  export durable complet et validé ; reprise idempotente, chaîne entière vérifiée.
- Vérifier aussi FIFO et fichiers spéciaux : ouverture non bloquante et refus
  avant lecture. Par lecture, _read_private peut actuellement bloquer sur FIFO.
- Assertions de conservation des lignes, événements, textes et fichiers ;
  rejouer les sondes G057/G062 et celles jointes, conserver les preuves historiques.

Livrer un commit et les limites restantes. Puis G064 et G065 sans attente.
Aucun fournisseur réel, VM, main, déploiement ou Memory Engine.
