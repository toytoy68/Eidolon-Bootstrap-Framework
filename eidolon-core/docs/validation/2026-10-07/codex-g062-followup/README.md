# Contre-revue Codex du prototype G062

Base : 42d6dde, intégrée via 7b46ab0. Données synthétiques uniquement.
Les 13 tests Claude sont rejoués ; les trois anciens contre-exemples G057 sont
refusés sans retrait (journaux joints). Le lecteur C-028 accepte les exports v2.

Deux défauts nouveaux reproduits par independent-probes.py :

1. os.write écrit réellement seulement la moitié des octets et retourne cette
   longueur : deux recherches retirées, résultat archived=2, JSON final illisible.
2. Un fichier partiel inconnu disparaît alors que la garde contient une INTENT
   et que auto_rotate refuse WEB_RESEARCH_UNCERTAIN.

Sortie exacte : independent-results.jsonl. Ces défauts touchent uniquement la
proposition isolée, jamais activée dans le Core. Correctifs attribués à G063.
La possibilité d'un blocage FIFO de _read_private est relevée par lecture,
pas présentée ici comme un essai exécuté.
