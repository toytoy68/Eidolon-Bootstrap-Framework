# G039 — Mesurer le coût de la consultation bêta

Auteur : Codex/GPT, 06/10/2026. Attribué à Claude à la demande de toytoy
à 19 h 08 (six tâches supplémentaires). Base initiale : 4d0f606.
Statut : attribué ; respecter les dépendances précisées ci-dessous.

Après API publiée. Banc reproductible sous docs/validation/2026-10-06/claude-read-performance/ : 10, 100 et 1000 missions synthétiques, pages de 20/100, snapshot/poll et reçu. Mesurer latences, taille des réponses, coût au repos (sans polling client automatique ajouté), et réponse quand SQLite est momentanément verrouillé. 3 répétitions, protocole et machine Python/SQLite/FS documentés. Aucune promesse de performances VM ou disque réel. Pas de modification du moteur ; proposer une optimisation uniquement avec un coût reproduit. Données/états temporaires nettoyés.

Un commit/message par livraison, sources et preuves séparées des constats
rapportés. Publier sur ta branche pour intégration. Ne pas modifier les fichiers
réservés Codex (http_api.py, receipt_lookup.py, tests Python associés).
Aucun déploiement, VM/NAS/GPU ou service personnel à contacter ici.
