# Intégration G005 et vues d'action — Codex/GPT — 05/10/2026

## Bases

Core `02af040f32d4f51afa4cb7879cd9945b2a6bc75e`, contre-revue Claude
`0e601e7` intégrée avec son historique dans `767389c`. Répartition publiée
`ffd4354` : Claude reçoit C-TASK-G006 (transport Web candidat), Codex traite
O-G5-1/O-G5-2, conserve le comportement prudent pour O-G5-3.
Python 3.12.14, Linux/POSIX, mondes synthétiques temporaires.

## Résultats

- `probes-reproduced.txt` : les huit sondes originales de Claude exécutées telles
  quelles ; sortie identique à `claude-g005/probes-output.txt` après la première
  ligne portant la version Python. Aucun message « SONDE EN ERREUR » ni stderr.
  Ce sont des sondes avec journal, pas huit tests unitaires supplémentaires.
- `view-tests.txt` : **14 tests** de la nouvelle projection réussis : appels
  réels du runtime synthétique, annulation après consommation avant autorisation,
  interruption et reprise, résultat conservé avant vérification, déclaration
  humaine sans effet, historique de tentative, condition/configuration changées,
  état du service après succès, sortie CLI éphémère et empreinte incohérente.
- `core-tests.txt` : 241 tests découverts, **235 réussis**, 6 intégrations opt-in
  sautées ; celles-ci sont exécutées séparément dans `memory-tests.txt`.
- `memory-tests.txt` : **6 intégrations réussies** contre les vraies API du moteur
  sur corpus synthétique, copie `7d99ded07b7e10aa8029655ce4a939af6e0a6c44` inchangée.
- `demo.jsonl` et `demo-human.txt` : six scénarios complets vérifiés, JSON et
  présentation commune Eidolon. Les compteurs contrôlés concernent des services
  fictifs, aucun service réel.

## Reproduction

Depuis `eidolon-core/` :

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:. python docs/validation/2026-10-05/claude-g005/probes.py
PYTHONPATH=src:. python -m unittest tests.test_action_view -v
PYTHONPATH=src:. python -m unittest discover -s tests -t . -v
PYTHONPATH=src:. python -m examples.action_view_demo
PYTHONPATH=src:. python -m examples.action_view_demo --format human
```

Le script de Claude laisse ses dossiers temporaires ; pour la reproduction
consignée ici, TMPDIR pointait vers un répertoire temporaire englobant nettoyé
après la sortie de tous les processus. Sa sonde de remplacement supprime
uniquement la base du simulateur dans ce répertoire, jamais un fichier du dépôt.
Les corpus mémoire sont préparés via les services coordonnés, sur copie isolée :

```sh
EIDOLON_MEMORY_INTEGRATION=1 PYTHONDONTWRITEBYTECODE=1 \
  PYTHONPATH="src:.:$EIDOLON_MEMORY_SOURCE" \
  python -m unittest tests.test_memory_engine -v
```

## Portée

La projection lit le snapshot, sans agir ou ajouter d'événement ; elle ne valide
pas la santé actuelle et ne donne aucune autorisation. Le runtime d'exécution,
les services simulés, les accords et le store sont inchangés par cette tranche.
O-G5-1/O-G5-2 corrigés dans la lisibilité ; O-G5-3 ne déclenche aucune relance
automatique. [Contrat](../../../ACTION-VIEW-G005.md).

Aucun GPU, modèle réel, DNS/HTTP réel, pare-feu, VPN, VM ou donnée utilisateur.
La mission historique vérifiée reste historique même si la fixture repasse DOWN.
Une déclaration humaine d'absence d'effet n'est pas transformée en preuve.
