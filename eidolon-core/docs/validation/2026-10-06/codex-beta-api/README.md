# Intégration Claude et API locale C-009a — 6 octobre 2026

Auteur : Codex/GPT. Checkout isolé, Python 3.12.14/Linux, aucun accès VM,
PC, NAS, GPU ou fournisseur Web. Branche cible : feat/eidolon-core-v0.1.
Base intégrée : fd4393d278a98eaaf615654b163d5289281f0ac5 (branche Claude).

## Intégration

- G026 : source/contrat lus, 16 tests et démo HTML exécutés ici.
- G027/G028 : rapports et sondes lus ; preuves avant/après conservées comme
  résultats Claude, sans nouvelle contre-revue indépendante revendiquée.
- G029/G030 : études conservées ; aucune activation ou décision utilisateur
  présumée. Réponses techniques dans C-MSG-G045.
- Bootstrap : modifications relues en ignorant CRLF ; bash -n des trois
  scripts et test synthétique de fonction APT réussis. Aucun installateur
  exécuté/source. Deux limites reproduites en plus : commentaires inline
  et dépôt tiers main ; confiées à Claude G033.
- Suite intégrée : 509 tests comptés par unittest, dont **503 réussis et
  6 intégrations mémoire sautées**, 107,965 s (`integration-tests.txt`).
- Prototype : **68 tests Node réussis** (`node-tests.txt`). Pas d'essai UI.

## C-009a : consultation HTTP

API sur 127.0.0.1 seulement, token privé vérifié, garde Host/Origin, endpoints
liste/snapshot/poll et health. SQLite mode=ro : aucune initialisation,
création/migration ou commande métier. Aucune dépendance externe ajoutée.
Trois assets statiques explicitement choisis peuvent accueillir G031 ; aucun
client connecté n'est livré dans ce lot.

25 tests nouveaux : vrais sockets loopback, processus CLI séparé, refus
d'authentification, headers ambigus, JSON et volumes, corps tronqués,
pagination/reset, observation d'une annulation par un écrivain distinct,
base absente/corrompue/nouvelle version/gardée, absence d'écriture et de fuite
d'erreur SQL/token. `http-tests.txt` conserve la sortie ciblée.

Commandes depuis eidolon-core/ :

```sh
PYTHONPATH=src:. python -m unittest tests.test_http_api -v
PYTHONPATH=src:. python -m unittest discover -s tests -t . -q
```

Suite globale : **534 tests comptés, 528 réussis, 6 sautés en 108,426 s**
(`final-tests.txt`). Après cette passe, normalisation du refus des méthodes
HTTP inconnues en 405 (au lieu du 501 standard) ; les **25 tests HTTP ont été
repassés**, dont TRACE/UNKNOWN, en 0,321 s (`http-tests.txt`). Les 6 tests mémoire sont opt-in, pas des
régressions constatées ni une validation récente du moteur mémoire.

## Publication et limites

Le push de d105fee vers feat/eidolon-core-v0.1 a été refusé par la revue
automatique : autorisation de publication du nouveau contenu jugée non
explicite. Aucun passage par un autre outil pour contourner le rejet. Les
commits sont conservés localement ; une confirmation explicite portant sur
le lot complet sera demandée après travail terminé.

Pas de déploiement, service installé, tunnel SSH réel, Windows réel, modèle
réel ni qualification de bêta globale. Serveur de développement mono-requête,
avec timeout socket mais sans garantie de délai total contre un client local
hostile. La copie SQLite auxiliaire/WAL dépend du producteur. Authentification
par possession du token de lecture, pas par identité humaine.
