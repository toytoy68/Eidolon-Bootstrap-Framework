# G044 — Archive bêta de sources reproductible

Auteur : Codex/GPT, 06/10/2026, demande toytoy à 19 h 27 Paris.
Base : 7de3646ab2fe15c945b0a81425a98d1a58211bef. Attribué à Claude.

Après G035, sans bloquer G036. Ajouter tools/build_beta_bundle.py et ses tests : archive de sources Core depuis un commit Git explicite et propre, liste autorisée de chemins suivis, manifeste commit/empreintes, ordre et métadonnées déterministes. Aucune donnée état/token/cache, aucun fichier non suivi ni symlink, aucun sous-projet Bootstrap ; pas de binaire ni installation. Échouer si destination existe, ne rien écraser. Vérifier deux constructions identiques et absence de fichiers sentinelles non suivis/secrets synthétiques. Inclure documentation de démarrage et limites Windows/VM ; cette archive de développement ne vaut pas qualification bêta.

Publier un commit/message par lot avec preuves et limites. Aucun déploiement,
VM, NAS, GPU ni installation système. Ne pas modifier les fichiers réservés
Codex : http_api.py, preflight.py, receipt_lookup.py et leurs tests Python.
