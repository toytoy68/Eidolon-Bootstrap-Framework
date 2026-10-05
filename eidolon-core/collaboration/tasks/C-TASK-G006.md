# C-TASK-G006 — Transport HTTP de lecture candidat (C-002b)

Auteur : Codex/GPT. Date : 05/10/2026. Destinataire : Claude Code.
Base requise : `02af040f32d4f51afa4cb7879cd9945b2a6bc75e` ou descendant.
Statut : prêt à prendre ; tâche de développement, autorisée par toytoy.

## Résultat attendu

Un module `web_transport.py` importable, des tests et une démonstration exécutables
sans Internet. Il complète la politique `egress.py` `/2` : téléchargement borné,
preuve des octets reçus et des destinations vérifiées. Module candidat hors
runtime et hors CLI principale ; aucune capacité accordée à un modèle.

## Contrat minimal

- Entrée URL, politique explicite, résolveur et couche connexion injectables.
  Ne jamais accepter une Decision du modèle comme permission. Le transport
  appelle decide/follow et garde la même politique pendant toute la chaîne.
- GET uniquement ; connexion à l'IP sélectionnée sans seconde résolution DNS.
  En HTTPS, SNI et certificat validés pour le nom contrôlé, Host cohérent avec
  nom/port. Aucun proxy d'environnement, aucun cookie ni secret automatique,
  aucune option désactivant TLS. Pas de corps de requête ni d'en-tête arbitraire.
- Redirections par le code seulement, chaque destination recontrôlée, budget
  conservé. Refus d'une destination ne déclenche aucune connexion vers celle-ci.
- Bornes explicites de temps global, connexion/lecture, corps et en-têtes.
  Réponse interrompue/tronquée ou incohérente : erreur nommée, jamais résultat
  complet. Décompression désactivée ou bornée explicitement, pas de bombe zip.
- Résultat : URL finale canonique, chaîne de sauts (sans contenu confidentiel),
  adresse réellement sélectionnée, statut, type, date d'observation, taille et
  SHA-256 des octets conservés. Distinct de la vérité du texte et du succès
  d'une mission. Refuser sans recopier de réponse arbitraire dans les erreurs.
- DNS et transport peuvent bloquer : préciser ce que chaque délai borne vraiment.
  Ne pas annoncer de budget global garanti si un appel bloquant échappe au contrôle.

## Tests attendus

DNS changeant au second appel (absence de seconde résolution), LAN/IP du foyer
via nom et redirection, Host/SNI/port, faux certificat refusé, variables proxy
ignorées, erreurs HTTP, trop gros, troncature, délai et serveur lent, redirections
en boucle, contenu compressé refusé ou correctement borné. Transports simulés
et éventuellement serveur loopback uniquement ; ne pas affaiblir la politique
publique en production pour rendre ce dernier test possible.

Lire les sources officielles Python/TLS/HTTP pertinentes ; noter versions et
limites. La démo ne se connecte à aucun site réel. Ne pas développer analyse HTML,
navigateur, outil shell, authentification de service ou écriture distante.

## Fichiers et livraison

Réserver `src/eidolon_core/web_transport.py`, `tests/test_web_transport.py`,
`examples/web_transport_demo.py`, `docs/WEB-TRANSPORT.md` et les preuves sous
`docs/validation/2026-10-05/claude-g006/`. Lire `egress.py` sans le modifier ;
signaler toute correction nécessaire à Codex. Ne toucher ni au runtime, ni aux
accords, ni aux fichiers réservés dans G016. Commits explicites, réponse signée,
tests réellement exécutés et limites, aucune qualification réseau réel.
