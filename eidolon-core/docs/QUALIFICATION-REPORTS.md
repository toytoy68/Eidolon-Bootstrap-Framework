# Rapports de qualification G-017 — `eidolon-qualification-report/1`

Auteur : Claude, 05/10/2026, fiche [C-TASK-G002](../collaboration/tasks/C-TASK-G002.md).
Base initiale : `7800b10`. Livraison initiale hors CLI ; depuis C-035 (Codex,
08/10/2026), vérification explicite dans la CLI principale, décrite ci-dessous.
Aucun raccordement au runtime ou à un moteur. Aucun GPU ni téléchargement.

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
  `run.started_at` strictement (égalité d'instant refusée, même sous un autre
  fuseau), et `fingerprints.criteria_sha256` doit égaler l'empreinte
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

## Collecte et décision proposées (non faites)

1. Le futur outil de recette écrit ce rapport, avec l'inventaire du § 7 de l'étude.
2. Les seuils et leur empreinte sont enregistrés **avant** l'essai, par exemple
   dans un commit ou une décision consignée, pour rendre détectable une
   modification ultérieure.
3. Un verdict `PASSED_SCOPE` alimente une décision humaine ; il ne déclenche
   aucun choix automatique de moteur ou de modèle.

## Durcissement à l'intégration — Codex/GPT, 05/10/2026

Cinq sondes sur G002 ont complété les 16 tests de Claude : métrique non hachable,
entier dépassant la représentation flottante, substitut Unicode isolé, corpus
vide, latence négative. Les trois premières entrées donnent désormais ReportError,
une métrique physiquement impossible aussi. Un rapport sans aucun cas attendu
reste INCOMPLETE/EMPTY_CORPUS ; un rejet conserve la priorité. `error_rate` est
borné à [0,1] ; les autres mesures sont positives ou nulles, sauf une dégradation
de latence qui peut être négative (amélioration, minimum −100 %).
[Preuves et 20 tests](validation/2026-10-05/codex-g002/README.md).

## Vérifier un fichier depuis Core — C-035, 08/10/2026

```sh
# Depuis eidolon-core/ ; aucun état, modèle ou appel réseau créé.
PYTHONPATH=src python -m eidolon_core qualification-check --report examples/qualification/passed-scope-synthetic.json
PYTHONPATH=src python -m eidolon_core --format human qualification-check --report examples/qualification/rejected-one-violation.json
# Après installation du paquet, remplacer « PYTHONPATH=src python -m eidolon_core » par « eidolon-core ».
```

Le fichier est ouvert en lecture seule, borné à 1 000 000 octets. Le dernier
composant du chemin ne peut pas être un lien symbolique ; répertoires, FIFO et
autres fichiers spéciaux sont refusés avant lecture. Les métadonnées sont
comparées avant/après lecture et au chemin encore présent : les remplacements
et modifications ordinaires détectés donnent `REPORT_CHANGED`. Cette mesure
ne prouve pas l'intégrité d'un système de fichiers hostile. Les parents du
chemin restent choisis par l'opérateur et peuvent être des liens.

La sortie JSON `eidolon-qualification-check/1` contient le verdict existant
(`status`, `scope`, `reasons`, `limits`), `report_sha256` sur les **octets lus**,
`authorizes_execution: false` et `telemetry_authenticated: false`. Même une
origine `hardware_reported` conforme reste une déclaration, pas une mesure
authentifiée. Aucun fichier de résultat n'est écrit automatiquement.

| Code de retour | Sortie standard | Sens |
| --- | --- | --- |
| 0 | `PASSED_SCOPE` | Cohérence établie pour le seul périmètre déclaré |
| 2 | `INCOMPLETE` | Rapport lisible mais données insuffisantes |
| 3 | `REJECTED` | Violation, incohérence ou seuil non respecté |
| 2 | Vide ; diagnostic sur stderr | `REPORT_UNAVAILABLE`, `REPORT_NOT_REGULAR`, `REPORT_TOO_LARGE`, `REPORT_CHANGED` ou `REPORT_MALFORMED` |

Les erreurs de lecture/structure ne recopient ni chemin privé ni contenu invalide.
Un rapport valide peut en revanche figurer dans la sortie à travers son périmètre
et ses motifs : choisir la destination de redirection en conséquence. Le mode
humain neutralise les contrôles de terminal et conserve les mêmes codes retour.

`--state` n'est jamais ouvert par cette commande. `--model-config`, les options
mémoire/cibles et les profils de simulation sont refusés ; `--timeout` et
`--max-invocations` n'interviennent pas puisqu'il n'y a aucun runtime. Le délai de
lecture d'un fichier régulier sur un montage réseau n'est pas borné par `--timeout`.
Le sous-module pur et `examples.qualification_demo` restent disponibles pour
leurs usages existants ; ils n'ont pas le contrat d'ouverture de fichiers de la CLI.

Vérification : 12 tests CLI supplémentaires, 32 avec les tests du validateur,
incluant sous-processus, absence de mutation, FIFO, fermeture déterministe,
fichier changé, limites et absence d'authentification fictive des mesures.
