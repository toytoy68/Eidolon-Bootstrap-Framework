# C1/C4 — cache interrompu et rapport Web v2

Auteur : Codex/GPT. Date : 06/10/2026.
Base : 3edcc9ee65537e8dfb02ee6a94bcc672c76561ed.
Suite des points ouverts de G008 ; sources identifiées par sha256.txt.

## Vérifications

Les huit premières méthodes de tests échouent sur cette base : 11 échecs de
sous-cas, [journal avant](before.txt). Trois méthodes supplémentaires vérifient
ensuite les sauts minimisés, les données facultatives mal formées et la limite
explicite « pas d'anonymisation des chemins/textes ».

82 tests ciblés réussis après correction : recherche, lecteur Web, pauses,
suivi G019/G020 et onze nouvelles méthodes. [Journal](targeted.txt).
Les preuves transport utilisent WebReader/FakeConnector/DNS simulé : requête
complète réellement transmise au double, query retirée du rapport, hash exact,
refus 403/429 et redirections préservés, cache non muté par la projection.

Suite complète : 466 tests découverts, **460 réussis, 6 intégrations Memory
Engine sautées**, 100,712 s. [Journal](full-suite.txt).

Démonstration exécutée en JSON (parsable) et mode humain : annulation conserve
le reçu, nouvelle demande refait la lecture, demande suivante prend le cache.
Deux lectures simulées ; empreinte exacte vérifiée ; paramètre synthétique
absent des rapports. [JSON](demo.json), [humain](demo-human.txt).

Commandes depuis eidolon-core/ :

```sh
PYTHONPATH=src:. python -m unittest tests.test_research_disclosure tests.test_research tests.test_web_reader tests.test_research_pauses tests.test_review_followup -v
PYTHONPATH=src:. python -m unittest discover -s tests -v
PYTHONPATH=src:. python -m examples.research_disclosure_demo --format human
```

## Contrat et limites

[Rapport v2](../../../RESEARCH-REPORT-V2.md). Aucune URL tronquée utilisée pour
la connexion ou la revalidation. Les empreintes distinguent les références mais
ne permettent pas de retrouver leurs paramètres. Les textes/titres/extraits,
chemins et extensions ne sont pas anonymisés. Le transport bas niveau reste
hors de cette projection. Cache RAM et arrêts coopératifs uniquement.

Aucune validation VM, GPU, modèle réel, fournisseur Internet ou Memory Engine.
G022–G024 annoncées terminées par toytoy, mais non visibles au fetch/API initial
(branche Claude 157db9e) : aucune prétendue intégration. Nouvelle file G025/G026,
puis G027 pour la contre-revue de ce lot, après la revue générale de Claude.

## Réception et clarification après les tests

Correctif publié : 2bad4e6d6eb6d9459fc1468273b0cc40068d9f04.
Revue globale Claude 0e65233 reçue après le fetch initial et intégrée dans
92752086c157ca5783c3b800a058a332c5cf6060 (documents seuls, aucun code modifié).
C034 corrige l'état : G022–G024 ne sont pas faites. La file G037 les remet en
tête avant G025–G027. G027 contre-vérifie le correctif exact ci-dessus.
La suite complète précède cette intégration documentaire ; aucun changement
Python après ses 460 réussites et six sauts.
