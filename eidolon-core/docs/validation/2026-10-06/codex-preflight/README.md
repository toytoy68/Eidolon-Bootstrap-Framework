# C-009c — validation Codex/GPT, 06/10/2026

Base 7de3646 ; attribution G042–G044 publiée en 7c7631fd9991e9b406aafe3a3e170abeb38caa6d.
Exécution Linux, Python 3.12.14. États temporaires entièrement synthétiques.

## Commandes reproduites depuis eidolon-core/

```sh
PYTHONPATH=src:. python -m unittest tests.test_preflight tests.test_http_api tests.test_receipt_lookup -v
NODE_PATH="$CODEX_PRIMARY_RUNTIME_NODE_MODULES" node --test desktop/connected/tests/*.test.js
```

- [tests.txt](tests.txt) : **57 réussis**, 1,674 s (12 diagnostic, 25 API, 20 reçus).
- [node-tests.txt](node-tests.txt) : **18 réussis, deux sautés**, 5,586 s ;
  Chromium absent. Quatre tests contactent le serveur réel sur loopback.
- [example.json](example.json) et [example-human.txt](example-human.txt) :
  diagnostic exécuté avec base synthétique vide, jeton aléatoire temporaire
  privé et desktop/connected réel. Aucun secret conservé.

Les nouveaux tests interdisent toute création de socket/initialisation Store
pendant le diagnostic réussi ; ils comparent les octets des fichiers avant et
après. Échecs indépendants, état absent non créé, token public/mal formé/lien/FIFO,
gardes récupération fichier et SQL, version/identité invalides, base illisible,
assets absents/liens/trop grands, port hors limites. CLI réelle dans un processus
séparé : JSON propre, succès 0, refus 2. Présentation humaine ECT vérifiée.

Le chargement des assets est partagé avec ReadServer ; les tests de consultation
existants et du client connecté vérifient la compatibilité du démarrage normal.
Aucune suite globale supplémentaire revendiquée.

## Limites

Aucun Windows, tunnel SSH, serveur utilisateur, modèle ou GPU testé. Le rapport
reste une observation de prérequis, pas une réservation, un audit intégral de
la base ou du bundle, ni une garantie de démarrage. Les fichiers WAL/SHM peuvent
dépendre du producteur SQLite ; aucune écriture métier n’est effectuée.
