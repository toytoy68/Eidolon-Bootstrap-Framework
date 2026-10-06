# Suites des revues G019/G020 — Codex/GPT

Date : 06/10/2026. Base : e2d01ff94a374078dd8bffcf99362049944671f1.
Revues indépendantes reçues : ff51313 (G019), cc9831f (G020).
Sources examinées et nouveaux tests identifiés dans sha256.txt.

## Corrections livrées

- D-G019-1 : avant chaque échange de WebReader, revérifier délai et annulation
  après les consultations persistantes. Le test reproduit trois consultations
  de six secondes et un budget de treize secondes : désormais zéro échange.
  Une annulation ou un délai pendant le contrôle d'une redirection arrête le
  second échange. Les résultats déjà reçus restent disponibles.
- L-G019-1 : contrôle de capacité avant fournisseur, origine et saut HTTP.
  Transaction de lecture cohérente, origines initiale/courante comptées ensemble,
  doublons retirés ; lignes libérées et journal préservés. Une reconstruction
  n'autorise plus à contacter un périmètre nouveau quand la table est déjà pleine.
  Un périmètre existant ne demande pas de place supplémentaire.
- R-G020-1 : commande de décision ou d'annulation, mission_id invalide donne
  INVALID_COMMAND: invalid mission_id, y compris validation directe et JSON.
  Aucun accès à Store n'est ajouté à ces validateurs purs.

## Vérifications exécutées

Les 13 nouvelles méthodes de tests sont exécutées sur une copie du paquet à
la base ci-dessus, puis sur le code corrigé. La base échoue : 30 assertions et
21 erreurs (sous-cas compris ; méthodes de capacité absentes sur la base).
[Sortie avant](before.txt). Un premier brouillon de fixture utilisait Retry-After
sur 200, ignoré par le transport ; il a été remplacé par un vrai 429 simulé,
puis les deux exécutions avant/après ont été reprises avec les mêmes tests.

111 tests ciblés réussis : nouveaux tests, pauses, recherche, régressions audit,
commandes d'annulation et de décision. [Sortie](targeted.txt).
Commande depuis eidolon-core/ :

```sh
PYTHONPATH=src:. python -m unittest tests.test_review_followup tests.test_research_pauses tests.test_research tests.test_audit_regressions tests.test_cancel_commands tests.test_commands -v
PYTHONPATH=src:. python -m unittest discover -s tests -v
PYTHONPATH=src:. python -m examples.research_pauses_demo --format human
```

Démonstration exécutée : pause 429 persistante après reconstruction, levée
explicite sans requête, puis nouvelle recherche simulée. [Sortie](demo-human.txt).
Une première invocation depuis la racine Bootstrap a échoué à importer examples ;
la commande ci-dessus a ensuite été exécutée depuis eidolon-core/.
Suite complète : 455 tests découverts, 449 réussis, 6 intégrations Memory
Engine sautées faute de copie du moteur (106,352 s). [Sortie](full-suite.txt).

## Limites maintenues

Contrôle de capacité sans réservation concurrente ; deux coordinateurs peuvent
encore se croiser avant écriture. Le crash réponse/commit, le disque défaillant,
la rétention des lignes et le journal préalable des appels restent à traiter.
Aucun délai dur : les contrôles sont coopératifs. Le contrôle des redirections
exige un lecteur qui appelle read_guarded/before_hop, comme WebReader.
Aucun déploiement, réseau externe, GPU, VM, NAS, modèle réel ou corpus privé.
Les tests d'intégration Memory Engine restent distincts et non exécutés ici.

G023 (abandon d'une vérification indisponible) appartient à Claude ; ce lot ne
modifie pas runtime.py/action_view.py. G024 doit contre-vérifier ces corrections.
