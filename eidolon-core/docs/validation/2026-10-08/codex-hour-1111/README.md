# Core — reprise du 08/10/2026 à 11 h 11 Europe/Paris

Codex/GPT. Base fadc3bc7084d38b4a3585606332c10c9007246c9, branche
feat/eidolon-core-v0.1. Python 3.12.14, Linux. Référence Memory Engine b33c3a0
isolée, sources non modifiées ; corpus jetables uniquement.

## C-042 — correction G064

- G064-3 reproduit avant correction (`g064-3-before.json`).
- Schéma pauses 2 et identité `pd-…` ; liaison au Store, refus de remplacement
  à l'ouverture et avant exécution ; contrôles par connexion dans les pauses.
- Schéma 1 consultable ; adoption explicite auditée, sans levée ni appel.
- Coupures pendant la migration, entre les commits et après commit éprouvées
  dans des processus terminés par os._exit. Reprise de migration explicite,
  audit conservé, INTENT incertaine jamais réconciliée automatiquement.
- G064-4 : erreurs SQLite de liaison normalisées (BUSY, SCAN_TIMEOUT, UNAVAILABLE).
- G064-2 : liste.md dit « Cohérence vérifiée à la génération » ; idempotence conservée.

[Contrat et limites](../../../PAUSE-BINDING.md). Une copie ancienne de même
identité reste hors détection, comme la réécriture cohérente des trois bases.
Les tests ne simulent pas une coupure électrique ni un disque réel.

## Preuves C-042

`c042-targeted.log` : **100 tests réussis**, dont 24 nouveaux tests de liaison.
`python-full.log` : **949 tests réussis, aucun ignoré**, 285,960 s. Les six tests
Memory Engine utilisent son vrai code sur données temporaires synthétiques.

```sh
PYTHONPATH=src:.:/chemin/memory-reference EIDOLON_MEMORY_INTEGRATION=1 \
  python -m unittest discover -s tests -t . -q
PYTHONPATH=src:. python -m unittest tests.test_research_pause_binding \
  tests.test_research_pauses tests.test_research_initialization \
  tests.test_research_runtime tests.test_research_archive -q
```

Première recette du paquet (`installed-pauses.stderr`) : installation réussie,
modules comparés, ancienne base refusée puis migrée avec pauses/audit conservés,
migration idempotente. Arrêt sur un défaut préexistant : `research --create-only`
crée une mission NEW mais renvoie 2. Ce journal n'est pas un PASS de recette.
Correction CLI et nouvelle recette suivront dans un lot distinct.

Aucun modèle réel, GPU, VM, PC Windows ou tunnel SSH testé. Aucune fusion main,
aucun déploiement. Contributions Claude originales conservées.

## C-043/C-044 et G066

G066 reçu et intégré avec son historique (d87b6d2 / 1e9d8b8).
`connected-tests.log` : 59 réussis, 14 Chromium ignorés, aucun échec.
Les 73/73 rapportés par Claude restent attribués à son environnement.

C-043 corrige le retour de création sans exécution (`create-only-before.log`
échoue avant correctif, `create-only-after.log` passe 43 tests), puis lie la
levée manuelle des pauses au Store. C-044 ajoute `research-binding-inspect` :
identités uniquement, sans initialisation, mutation ou permission de reprise.
55 tests liés passent (`binding-diagnostic.log`), puis 11 tests dédiés passent
avec contrôle de changement d'identité en WAL (`binding-inspect-final.log`).

`installed-final.json` : première recette installée complète PASS, 53 modules
identiques et 25 contrôles bêta ; cette étape précède C-044 et sera complétée.
`integrated-targeted.log` conserve une erreur de sélection du module de test
inexistant tests.test_http_archives. La commande corrigée avec
`tests.test_archive_page` passe 109 tests (`integrated-corrected.log`).
