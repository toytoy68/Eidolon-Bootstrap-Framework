# G222 — Compte rendu unique de la séance du 14 octobre 2026

Périmètre : préparation de qualification et correction des défauts détectables par revue GitHub, **sans VM, sans Claude et sans fusion main**.

## Travaux publiés

1. Memory `db79c14` : correction d'une assertion contradictoire dans `test_worker_preflight.py` ; le test exigeait simultanément deux listes de revue différentes.
2. Memory `e10f740` et `41ebc80` : validation des types, révisions et séquences des actions ; cinq cas négatifs ajoutés.
3. Memory `64066e5` et `502dd00` : différenciation explicite des actions `INDEX_UPSERT` (intention existante) et `ENQUEUE_UPSERT` (manifeste sans intention) ; tests adaptés.
4. Memory `5105108` : protocole de qualification isolée et de reprise, suites ciblées, recette PC B01–B12, critères d'arrêt.

## Preuves

Publications GitHub confirmées. Aucune exécution `pytest` n'a été possible dans l'environnement de cette séance : `git ls-remote` a échoué avec `Could not resolve host: github.com`. Le connecteur GitHub permet la lecture et l'écriture de fichiers mais n'exécute pas les tests.

Les corrections sont **candidates**, non qualifiées. Les chiffres des suites Claude antérieures ne s'appliquent pas à ces commits. Aucun changement de la maturité globale n'est revendiqué.

## Risques et ordre de reprise

1. Restaurer un environnement de tests : VM/MCP ou clone GitHub accessible.
2. Compiler et exécuter tests ciblés sur SHA figé, corriger toute régression.
3. Rejouer suites complètes Memory/Core et les 19 scénarios du worker.
4. Intégrer et qualifier I1/W1 Core, encore en patchs Claude.
5. Implémenter le worker à effets Qdrant uniquement après vérification canonique, droits et modèle d'embedding.
6. Recette PC → Core → Memory, puis décision bêta.

**Interdits maintenus** : modification du corpus réel, activation de suppressions Qdrant, déploiement VM, fusion main. Claude reste indisponible jusqu'au soir du 15 octobre.
