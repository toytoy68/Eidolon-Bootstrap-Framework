# Bilan de l'heure Codex — 07/10/2026

Demande toytoy vers 08 h 32 Paris : poursuivre une heure, renouveler la file
Claude quand elle est vide. Travail réservé à feat/eidolon-core-v0.1 ; pas
de main, installation système, service utilisateur ou déploiement.

## Livraisons

| Lot | Résultat | Contrat |
| --- | --- | --- |
| C-013 | Nettoyage borné avant providers/replis ; vide = aucun contact | QUERY-CLEANUP.md |
| C-014a | Garde globale optionnelle, intention durable, verrou POSIX, revue UNKNOWN | RESEARCH-GUARD.md |
| C-015 | Budget d'invocations par mission, 64 par défaut, réservation avant worker | INVOCATION-BUDGET.md |
| C-016 | SIGINT/SIGTERM de recette : nettoyage groupes possédés et temporaires | BETA-CHECK.md et beta_check.py |
| C-017 | Seuil transactionnel d'empreinte obligatoire pour les nouveaux reçus | HTTP-RECEIPTS.md |
| C-018 | Trois cas G049 corrigés, extracteur version 2 | HTML-EXTRACTION.md |

Claude G045–G049 intégrés avec leurs parents Git. G046 citations SSH
corrigées ; tolérance StartTime de 2 s rejetée (risque PID réutilisé).
G048 affichage des deux niveaux de liaison des reçus intégré. Les décisions
C-D10–C-D16 sont reçues comme décisions utilisateur rapportées par Claude.
G050–G053 publiés pour contre-revues et premier lot Tauri en consultation.

## Vérifications réellement exécutées

- `PYTHONPATH=src python -m unittest discover -s tests -v` : **699 tests,
  693 réussis, 6 intégrations mémoire non exécutées**, 128,732 s.
  Journal `python-final-html.txt` ; sources C-018 local 72c1d843085c25300b266874a13bd63ed7fcfbd2.
- Client connecté : **61 tests, 49 réussis, 12 Chromium ignorés** dans
  `node-tests.txt` ; `node desktop/connected/build.js --check` : à jour.
- HTML/extracteur/recherche : **62 tests ciblés réussis** (`html-tests.txt`).
  Corpus HTTP loopback de Claude rejoué après correctif (`g049-replayed.txt`).
- Seuil des reçus : **69 tests ciblés** (`receipt-boundary-tests.txt`).
- Paquet final construit hors réseau et installé en venv jetable : **40
  modules identiques aux sources et 24 contrôles de recette réussis**,
  temporaires retirés (`package-final.json`). Ancien passage conservé dans
  `package-smoke.json`, antérieur à C-018.
- Archive sources de 72c1d84 : **60 fichiers vérifiés**, contenu/manifeste
  cohérents (`bundle-build.json`, `bundle-verify.json`). Cela ne valide pas
  l'authenticité de la source, et le vérificateur le dit explicitement.
- Passages globaux intermédiaires : 687 réussis/6 ignorés avant C-017,
  puis 690/6 avant C-018 (`python-tests.txt`, `python-final.txt`).

La première invocation du corpus G049 avec PYTHONPATH=src seul a échoué
sur l'import examples ; relancée avec PYTHONPATH=src:. (commande correcte).
Les preuves détaillées C-013/C-014a/C-015 sont dans les dossiers voisins.

## Correspondances de publication

Les commits GitHub sont créés avec le même arbre vérifié que les commits
locaux ; leurs identifiants diffèrent par les métadonnées de création.

| Lot | Commit GitHub |
| --- | --- |
| C-013 | 51942215f671a6bc1e8b2c5c2b4717d52a579677 |
| C-014a | 887fa16f8145da2fb38cabb6ce0ee9443dafab9f |
| C-015 | 956c71ded36af11d21fa468262dbc717585bf3ec |
| C-016 | e6139cc11c592a8ad49bfa57ae42f876c661b30d |
| C-017 | 93cab33e1f28e578733d288c2b9d0d0ec3eb0031 |
| File Claude G050–G053 | df99fc8a0392dc06fd2b35b7e9d956a43adb08e2 |
| C-018 | 3278875abe26a0adbe1c9643799f719b5f782da4 |
| Décisions C068/C069 intégrées | e03f7d213100448f364ccd152477d9f2d036a9cf |

Le bilan final est publié après ces commits, par avance sans force et avec
vérification du SHA attendu puis relecture de la branche.

## Limites et suite

Aucune validation réelle Chromium, Windows, tunnel SSH, Debian 13, modèle,
GPU, NAS, serveur utilisateur ou Memory Engine. Aucun fournisseur Internet
activé ; tests de réseau limités à des fixtures et HTTP loopback contrôlé.
La garde est globale par journal, pas encore un journal atomique par saut.
Le budget ne remplace pas un quota de serveur ou une rétention globale.
Le seuil des reçus refuse une suppression isolée du hash, pas une réécriture
cohérente des événements et métadonnées. Anciennes données non migrées.

Le corpus G049 conserve des limites documentées : variante de titre
« Just a moment… » non reconnue, champ password dans template refusé par
prudence, texte brut avec BOM pas dédoublonné comme le texte sans BOM.
L'extracteur ne simule pas un navigateur. SIGKILL ne peut pas être intercepté.

Prochain lot Codex : conservation locale bornée du texte nettoyé (C-D15),
puis raccordement contrôlé recherche/runtime. G050–G053 restent attribués à
Claude ; les fichiers de tâches ne déclenchent pas une session.
