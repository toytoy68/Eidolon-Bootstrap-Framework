# Corpus d'évaluation de l'index documentaire Eidolon (E2, G196)

Auteur : Claude. Figé le 12/10/2026, **avant** tout téléchargement, toute
indexation et tout essai réel.
Fichier : [corpus-v1.json](corpus-v1.json), SHA-256
`e4a74463d5eb145e96d378facbe09be1e212db8185f0cca0f3d6fd5fcbadad4a`, vérifié
par `tests/test_doc_index_eval_corpus.py`.

## Contenu : 40 questions

| Type | Nombre | Ce qu'on attend |
| --- | --- | --- |
| Factuelles | 25 | la bonne page source, citée, et les éléments de réponse attendus |
| Procédures | 5 | la bonne commande ou la bonne méthode, citée |
| Négations | 5 | la réponse **garde** la négation ou la mise en garde de la source |
| Abstentions | 5 | entités **inventées** ou futures : toute réponse sourcée est un échec |

Thèmes : Wikipédia FR (15), Python (10), Debian (8), Proxmox VE (7).

## Pour ne pas inventer de vérités attendues

- Chaque question non-abstention porte
  `verification: "to_verify_on_frozen_snapshot"`. La page et la réponse
  attendues sont **vérifiées sur la révision figée** des sources avant toute
  notation.
- Si la source figée dit autre chose, la question est corrigée **avant** la
  notation, dans une nouvelle version du corpus, avec la raison écrite.
  Jamais après avoir vu des résultats.
- Les réponses attendues sont des faits stables et connus (capitales,
  dates, commandes). Une valeur qui peut varier, comme l'altitude du mont
  Blanc, est donnée sous forme de plage, avec une note.

## Licences et provenance (à consigner page par page lors de l'essai)

- Wikipédia FR : CC BY-SA, attribution. On garde le titre, la révision et la
  date du dump.
- Documentation Debian : licences libres variables selon le document, à
  relever page par page.
- Documentation Python : licence de la documentation PSF, **à vérifier**.
- Documentation Proxmox VE : **à vérifier** page par page.

## Notation

- La source citée doit correspondre au couple `expected_source.corpus` /
  `page_hint`.
- Chaque élément de `answer_must_contain` doit apparaître ; la comparaison
  ignore la casse. `also_accepted` donne des variantes acceptées.
- Mesures : rappel au rang 1 et au rang 5, abstention correcte, négation
  conservée, latence. Seuils à fixer **avant** l'essai.
