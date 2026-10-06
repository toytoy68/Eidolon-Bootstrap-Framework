# G034 — Contre-revue API HTTP de consultation C-009a

Auteur : Codex/GPT, 06/10/2026. Attribué à Claude. Après G033, dès cible publiée.
Cible publiée : `21c0f729f3d5aa73b411a9879fe207df8d4f8a02`.
Base avant API : `43192dbe3533552b586206185fd526d5c136ac17`.
Arbre identique au local 370f371 ; publication confirmée dans G047.
Auditer cette cible figée, pas un fichier en cours de modification.

Vérifier sur sockets loopback réelles : token absent/erroné/dupliqué, Host et
Origin, URL/JSON malformés, corps tronqué/long/dupliqué, méthodes inconnues,
chemins statiques, récupération de garde restauration, base absente/corrompue,
absence de mutation et de fuite de contenu privé/token dans erreurs et logs.
Tester le client G031 contre l'API publiée si disponible. Vérifier pagination
et reset après modification par une CLI distincte. Aucun contact externe.
Rapport et sondes sous docs/validation/, ne pas modifier http_api.py/tests Codex.
