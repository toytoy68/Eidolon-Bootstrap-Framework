# Rapports de qualification G-017 — `eidolon-qualification-report/1`

Auteur : Claude, 05/10/2026, fiche [C-TASK-G002](../collaboration/tasks/C-TASK-G002.md).
Base : `7800b10` (dernière tête Core). Statut : module livré **non raccordé** à
la CLI, au runtime ou à un moteur. Aucun GPU, moteur, modèle ni téléchargement.

Module : [`src/eidolon_core/qualification.py`](../src/eidolon_core/qualification.py).
Tests : [`tests/test_qualification.py`](../tests/test_qualification.py), 16 tests.
Fixtures synthétiques : [`examples/qualification/`](../examples/qualification/).
Source du contrat : le manifeste de mesure de
[l'étude des moteurs](INFERENCE-RUNTIME-COMPARISON.md), § 7, et le protocole R0–R5.

## Ce que le validateur établit — et ce qu'il n'établit pas

Il vérifie qu'un rapport est **bien formé, complet, cohérent et dans ses
critères fixés à l'avance**. Il ne vérifie **pas** que les mesures sont vraies :
un rapport inventé mais cohérent passe. L'authenticité relève de la collecte
(journaux bruts, empreintes, personne qui a mené l'essai), pas de ce module.

Son meilleur verdict est `PASSED_SCOPE` : conforme **pour le profil, le
moteur, le modèle et l'origine annoncés**, rien de plus. Ce n'est jamais une
qualification générale d'un modèle, d'un moteur ou d'une machine. Aucun champ
du rapport ne peut déclarer lui-même une validation : un champ inconnu comme
`validated` ou `qualified` rend le rapport mal formé.

## Verdicts

| Verdict | Quand | Priorité |
| --- | --- | --- |
| `ReportError` (exception) | JSON invalide, NaN/Infinity, clé dupliquée, champ inconnu ou manquant, unité ou métrique inconnue, profondeur > 8, taille > 1 Mo | Aucun verdict possible |
| `REJECTED` | Au moins une violation ; un cas FAIL ou ERROR ; un seuil dépassé ; critères fixés après le début de l'essai ou différents de leur empreinte ; données synthétiques et matérielles mélangées ; comptes incohérents ou cas en double | L'emporte sur tout le reste : des données manquantes ne masquent jamais une violation |
| `INCOMPLETE` | Cas attendus sans résultat ; mesure exigée par un seuil absente ou `null` | Seulement s'il n'y a aucun motif de rejet |
| `PASSED_SCOPE` | Aucun des motifs ci-dessus | — |

Chaque verdict porte la liste de ses motifs (`code`, `detail`) et le rappel de
ses limites.

## Règles notables

- **Une mesure absente reste absente.** `null` ou une métrique non fournie
  donnent `MEASUREMENT_MISSING`, jamais zéro.
- **Une violation n'est pas compensée** : une seule parmi mille succès donne
  `REJECTED` (testé).
- **Les critères sont fixés avant l'essai** : `criteria.fixed_at` doit précéder
  `run.started_at`, et `fingerprints.criteria_sha256` doit égaler l'empreinte
  canonique des seuils. Limite : si quelqu'un modifie les seuils **et** recalcule
  l'empreinte, le rapport reste cohérent. Seule une empreinte enregistrée
  ailleurs avant l'essai permet de le détecter (testé et documenté comme tel).
- **Pas de mélange d'origines** : `synthetic` et `hardware_reported` ne
  coexistent jamais dans un même rapport, que ce soit dans l'essai, un cas ou
  une mesure.
- **Unités imposées par métrique** : `ttft` en `ms`, débits en `tokens/s`,
  VRAM en `MiB`, puissance en `W`, latence P2P en `us`, rapport P2P en `ratio`,
  dégradation de latence en `percent`, taux d'erreur en `ratio`. Les opérateurs
  de seuil sont `<=` et `>=`, bornes incluses.
- Bornes : 10 000 cas, 64 seuils, 64 mesures, 64 violations par cas, textes de
  200 caractères, horodatages ISO 8601 avec fuseau.

## Format

Voir [la fixture conforme](../examples/qualification/passed-scope-synthetic.json).
Champs de premier niveau, tous obligatoires : `schema`, `run` (`id`,
`started_at`, `origin`), `scope` (`profile` parmi `1`, `2a`, `2b`, `3`,
`engine`, `model`, `statement`), `fingerprints` (corpus, configuration,
critères, en SHA-256 hexadécimal), `criteria` (`fixed_at`, `thresholds`),
`cases` (`expected`, `executed`, `results`), `measurements`.

Le manifeste de l'étude (§ 7) contient en plus l'inventaire matériel et
logiciel. Ce contrat-ci ne garde que ce qui est nécessaire au verdict ;
l'inventaire reste à joindre au rapport comme pièce de l'essai.

## Démonstration (hors CLI principale)

```sh
# depuis eidolon-core/
PYTHONPATH=src:. python -m examples.qualification_demo
PYTHONPATH=src:. python -m examples.qualification_demo chemin/vers/rapport.json
```

Les trois fixtures donnent `PASSED_SCOPE`, `REJECTED` (une violation dans un cas)
et `INCOMPLETE` (un cas et une mesure manquants). Ce sont des données
synthétiques : aucune n'a été produite par un GPU ou un moteur.

## Raccordement proposé (non fait)

1. Le futur outil de recette écrit ce rapport, avec l'inventaire du § 7 de l'étude.
2. Les seuils et leur empreinte sont enregistrés **avant** l'essai, par exemple
   dans un commit ou une décision consignée, pour rendre détectable une
   modification ultérieure.
3. Un verdict `PASSED_SCOPE` alimente une décision humaine ; il ne déclenche
   aucun choix automatique de moteur ou de modèle.
