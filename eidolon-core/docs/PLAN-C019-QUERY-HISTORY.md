# C-019 — conservation locale des requêtes nettoyées

Auteur : Codex/GPT, 07/10/2026. Statut : prochaine tâche, non implémentée.
Décision utilisateur C-D15 rapportée par Claude C068 : conserver le texte
nettoyé envoyé pour relecture. C-D16 garde toutes les catégories actuelles.
Base de reprise publiée : 11bfc353b224088da7ef24ffe6caf71691c5bb6a.

## Résultat attendu

Un historique local explicite du texte **après** query_cleanup, avec empreinte,
version du nettoyage et état d'émission factuel. Une intention avant appel ne
prouve pas qu'un fournisseur a reçu la requête ; les interruptions restent
inconnues tant qu'elles ne sont pas revues. Le texte brut ne doit atteindre
ni ce stockage, ni le journal de garde, ni les diagnostics ou exceptions.

## Critères de sortie du premier lot

- Stockage privé et borné, limite figée hors modèle ; pas d'éviction cachée
  d'une intention active. Échec persistant = aucun nouveau contact.
- Liaison entre texte nettoyé, empreinte du reçu et identifiant de tentative ;
  distinguer requête vide, intention, appel terminé et résultat inconnu.
- Lecture locale pour toytoy avec pagination bornée ; aucune exposition
  automatique du texte dans l'API HTTP de consultation actuelle.
- Tests avec motifs personnels synthétiques, reprise après crash, saturation,
  SQLite indisponible et interférence concurrente ; zéro fournisseur réel.
- Choisir et documenter des bornes opérationnelles avant activation ; ne pas
  présenter une durée de rétention comme décidée par toytoy.

## Coordination

Codex réserve ce prochain lot ; Claude conserve G050–G053. Une contre-revue
G050/G051 peut modifier le contrat d'intégration : lire le dernier message
Claude avant de coder. La garde actuelle ne devient pas un journal par saut
sans une nouvelle conception transactionnelle explicite. Cette fiche ne
raccorde pas la recherche au runtime, n'accorde aucun accès réseau et ne
crée aucun service. Exécution à la prochaine reprise de travail.
