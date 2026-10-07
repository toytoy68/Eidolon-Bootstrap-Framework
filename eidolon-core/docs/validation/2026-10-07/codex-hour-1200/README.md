# Séance Core du 07/10/2026 — reprise de 12 h Paris

Codex/GPT. Demande toytoy : poursuivre une heure et donner encore du travail
à Claude. Début : 11 h 59 min 42 s Europe/Paris (+0200). Publication GitHub
autorisée sur `feat/eidolon-core-v0.1` ; aucun merge main ni déploiement.

## Livraisons publiées

| Lot | Résultat | Commit distant |
| --- | --- | --- |
| G077 | Trois tâches nouvelles Claude : G058/G059 contre-revues, G060 affichage recherche | a1669eb42a85efddfbad3ac014226066589c0019 |
| C-022/C-023 et G055/G056 | Diagnostic local sans reprise ; CSP/Referrer-Policy sur saturation ; rapports Claude intégrés | 0e0b5d9f233928f21b99ca90cd7c8561d50b2117 |
| C-024 et G078 | Lecture SQL des réservations de budget, proposition G056 adoptée | 7c8d97b7f2dfcd7c18e4be518e3a0ffa928257c7 |
| C-025 | Inspection historique stricte et bornée, rapports contradictoires refusés | 9709dece29fa6815ad93301d3edc7a2887c5d736 |

Les arbres locaux et distants sont comparés à chaque publication. Les commits
locaux équivalents sont respectivement 5545c56, 3e97f1f, a022297 et 6a182c4.
Le connecteur GitHub crée les commits distants sans push forcé ; les parents
Claude ont été conservés lors des intégrations.

## Validation exécutée par Codex

- [Suite Python](full-tests.txt) : **773 découverts, 767 réussis, six ignorés**,
  en 139,895 s, sur les sources C-027. La [capture C-025](c025-full-tests.txt)
  précédente reste conservée (767 découverts, 761 réussis).
- [Intégrations Memory Engine](memory-integration.txt) : **six réussies** avec
  la copie isolée 7d99ded07b7e10aa8029655ce4a939af6e0a6c44 ; corpus temporaires.
- [Client Node](node-tests.txt) : **49 réussis, 12 Chromium ignorés**. Inclut
  les cinq scénarios d’intégration HTTP du sous-dossier integration.
- [Paquet installé](package-smoke.json) : wheel construit hors réseau, venv
  jetable, **43 modules identiques**, **24 contrôles bêta**. Mission recherche
  de deux pages, reprise inchangée, une entrée nettoyée liée ; runtime-inspect
  et recovery-inspect exécutés sans mutation de la base source. Copie de
  récupération toujours historique, sans autorité d’exécution.
- [Parcours opérateur](operator-smoke.json) : six missions consultées par
  inventaire/diagnostic, fichiers source inchangés ; copie de revue historique
  conservant les six missions. [Script](operator-smoke.py).
- [Archive C-025 publiée](source-archive-verify.json) : 67 fichiers vérifiés ;
  trois scénarios de recherche reçus via HTTP et acceptés par le client JS,
  [sans données privées exposées](archive-http-smoke.json).
- Les preuves propres aux lots sont dans [C-022](../codex-runtime-inspect/README.md),
  [C-023](../codex-g055-followup/README.md), [C-024](../codex-g056-followup/README.md)
  [C-025](../codex-recovery-inspection/README.md) et
  [C-027](../codex-cli-readonly/README.md).

Commandes depuis eidolon-core :

```sh
PYTHONPATH=src:. python -m unittest discover -s tests -t . -q
PYTHONPATH=src:/chemin/copie-memory EIDOLON_MEMORY_INTEGRATION=1 python -m unittest tests.test_memory_engine -v
node --test desktop/connected/tests/*.test.js desktop/connected/tests/integration/*.test.js
python docs/validation/2026-10-07/codex-hour-1200/core-package-smoke.py
```

## Mesures et limites

Le banc G056 a été rejoué avant/après sans chevauchement : à 4095 réservations,
38,23 → 9,48 ms localement. Les six altérations isolées sont refusées ; le retrait
cohérent du compteur et de son événement reste hors garantie. Pas de nouveau
schéma, index, cache ni qualification des performances VM.

G055 conserve les observations WebKitGTK de Claude, non reproduites ici.
Aucun test Windows, VM utilisateur, SSH ou fournisseur réel. Aucun changement
Memory Engine. Le diagnostic ne confirme ni l’absence d’effet ni un droit de
reprise ; les copies historiques restent bloquées. Les limites du rollback
cohérent et des délais physiques du stockage restent explicites.

## Coordination Claude

G055 et G056 reçus pendant cette heure et intégrés, tête observée 8c5f649.
G057 puis les nouvelles G058/G059/G060/G061 sont prêts dans la file publiée.
G061 porte sur la contre-revue des nouveaux diagnostics ; file renouvelée par G079.
Un fichier de tâche ne démarre pas Claude et ne prouve pas sa présence continue.


## Compléments C-026/C-027

Le parcours opérateur DIAGNOSTIC-WORKFLOW relie les observations et leurs limites.
Sa préparation a mis en évidence les écritures implicites des consultations CLI :
les trois commandes client-missions/client-snapshot/client-poll utilisent maintenant
ReadOnlyStore sans initialisation/migration. Une table manquante est refusée, pas
recréée. 59 tests ciblés puis la suite globale et le paquet installé ont été rejoués.
Les protocoles et curseurs restent identiques.
