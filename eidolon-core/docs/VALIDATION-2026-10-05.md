# Bilan de la première tranche — 5 octobre 2026

Développement autorisé de Core v0.1, branche `feat/eidolon-core-v0.1`.
Code fonctionnel/testé : commit `4ada989e8ca1f469a39a1a389530f2f2c0267c03`,
arbre `e91fb4523ce3ff5f385d0c93edeed35c63e5cb4c`. Documentation et preuves ajoutées
dans le commit suivant. Le connecteur GitHub a publié les commits ; les arbres
Git locaux et distants sont comparés pour vérifier l'identité des fichiers.

## Bases examinées

- Bootstrap main : `9cc70cc67494af19452d8a67c385e8e96c5558a2`.
- Memory Engine : `3a86ef0707d24f8126df385e462f911c52891d3e`, branche
  `refactor/architecture-v1`. Recontrôle distant en fin de recette : même tête,
  aucune évolution depuis l'audit du 05/10.
- Aucun AGENTS.md applicable trouvé. Aucun installateur exécuté. Code du moteur
  inchangé ; `git status --porcelain` vide dans son clone dédié.

## Résultats directement observés dans Work

Linux, Python **3.12.14**, SQLite **3.53.1** ; PyYAML **6.0.3** pour l'intégration.
Aucun modèle réel, GPU, VM ou service externe utilisé pour la recette.

| Vérification | Résultat | Preuve |
| --- | --- | --- |
| Tests Core simulés | **34 réussis**, 0 échec/saut, 14,717 s | [journal](validation/2026-10-05/simulated-tests.txt) |
| Intégration réelle API mémoire, données synthétiques | **6 réussis**, 0 échec/saut, 0,957 s | [journal](validation/2026-10-05/memory-integration-tests.txt) |
| Paquet installable | Installation editable sans téléchargement de dépendance réussie ; point d'entrée exécuté | pyproject.toml, sortie CLI ci-dessous |
| CLI installée, mémoire simulée | SUCCEEDED, 1/1 vérifié | [résultat JSON](validation/2026-10-05/demo.json) |
| Démo avec vrai Memory Engine | SUCCEEDED, 1/1 vérifié | [résultat JSON](validation/2026-10-05/memory-demo.json) |
| Trois défauts connus mémoire | A5-01, A5-02, A5-03 reproduits, toujours ouverts | [sondes](validation/2026-10-05/memory-known-defects.txt) |

**40 tests réussis sur deux suites distinctes.** Ce nombre n'est pas celui de
la suite complète du Memory Engine, qui n'a pas été relancée ici. Les durées
sont celles de ces exécutions, sans prétention de benchmark représentatif.

Résultat attendu des deux démonstrations :

```json
{
  "characters": 70,
  "utf8_bytes": 72,
  "sha256": "e1336e1ecbe9efd2e830d241a6476420e58a1a63dbb210ffc79c24236fe8d9cc"
}
```

La source reste UNVERIFIED, needs_review=true. L'empreinte concerne le texte
synthétique, pas une preuve d'achat, d'interdiction réelle ou de vérité sémantique.
IDs, dates et chemins temporaires des sorties archivées varient à chaque recette.

## Comportements vérifiés

- Plan non vide, clés strictes, paramètres/références vérifiés, précontrôle du
  plan entier avant l'outil. Outil absent, refusé ou à effet externe : aucun appel.
- Une affirmation modèle « SUCCEEDED », un JSON invalide ou un résultat outil
  faux ne deviennent jamais un succès. Progression seulement après vérification.
- Mémoire absente/mal formée : BLOCKED avant plan ; vide : aucune réussite.
  Retour de la mémoire : reprise avec même identité. Réserves/provenance conservées.
- Délais modèle/mémoire/outil/vérification. Perte du worker et échec de démarrage
  diagnostiqués. Délai/annulation d'outil : revue obligatoire.
- Annulation avant appel, pendant appel, entre étapes et à la frontière du succès.
  Preuves déjà obtenues conservées, étape suivante non démarrée.
- Neuf frontières d'arrêt réel du processus : RECALL_STARTED, CONTEXT_SAVED,
  MODEL_OUTPUT_SAVED, PLAN_SAVED, CALL_STARTED, TOOL_RETURNED, RESULT_SAVED,
  RESULT_VERIFIED, SUCCEEDED. Relecture indépendante du journal après `os._exit`.
- Intention sans reçu : pas de relance ; reçu présent : revérification sans
  nouvel appel. Réconciliation humaine auditée ; résultat humain faux refusé.
- Exécution concurrente coopérative refusée, annulation persistée malgré le
  verrou. Révision périmée refusée et snapshot/événement atomiques.
- Changement de configuration bloqué ; proposition ancienne conservée sans
  expiration ni décision automatique.
- Intégration mémoire : parité exacte du bundle avec ContextualRecall, tous les
  fichiers métier identiques avant/après, références message/offsets conservées,
  REFUTED exclu par le moteur, readiness bloquante respectée.

## Reproduction

Depuis `eidolon-core/`, voir aussi le [README](../README.md) :

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:. python -m unittest tests.test_core -v
EIDOLON_MEMORY_INTEGRATION=1 PYTHONDONTWRITEBYTECODE=1 \
  PYTHONPATH="src:.:$EIDOLON_MEMORY_SOURCE" \
  python -m unittest tests.test_memory_engine -v
PYTHONPATH=src python -m eidolon_core --state /tmp/eidolon-core-demo demo
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="src:.:$EIDOLON_MEMORY_SOURCE" \
  python -m examples.memory_engine_demo
```

Installation vérifiée dans un venv isolé utilisant les dépendances système déjà
présentes : `python -m pip install --no-build-isolation --no-deps -e .`, puis
`eidolon-core --state <dossier-temporaire> demo`. Aucun paquet installé globalement.

## Ce que cette validation ne couvre pas

Recette Debian/VM, Python 3.13, reboot, coupure électrique, stockage physique,
modèle réel, pertinence sémantique, corpus utilisateur, outils à effets, sécurité
d'un plugin hostile, intégration Hermes/Qdrant ou déploiement. Les scénarios
d'injection prouvent le maintien des frontières du simulateur et des contrats,
pas la qualification d'un futur LLM. Les trois défauts mémoire ne sont pas corrigés.

La prochaine tranche proposée porte sur les critères de réussite des missions
et les contrats du contrôleur, voir la [TODO Core](../TODO.md). Aucun travail
ne reste suspendu à une disponibilité VM pour reproduire cette tranche.
