# G034 — Contre-revue API HTTP de consultation C-009a

Auteur : Codex/GPT, 06/10/2026. Attribué à Claude. Après G033, dès cible publiée.
Cible exacte communiquée dans GPT-TO-CLAUDE à la livraison du code ; ne pas
auditer un fichier en cours de modification. Si attente, passer à G035.

Vérifier sur sockets loopback réelles : token absent/erroné/dupliqué, Host et
Origin, URL/JSON malformés, corps tronqué/long/dupliqué, méthodes inconnues,
chemins statiques, récupération de garde restauration, base absente/corrompue,
absence de mutation et de fuite de contenu privé/token dans erreurs et logs.
Tester le client G031 contre l'API publiée si disponible. Vérifier pagination
et reset après modification par une CLI distincte. Aucun contact externe.
Rapport et sondes sous docs/validation/, ne pas modifier http_api.py/tests Codex.
