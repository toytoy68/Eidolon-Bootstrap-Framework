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

## Bilan final intégré — C-042–C-045 et G066–G071

**971 tests Python réussis, aucun ignoré, 279,392 s** : `python-final.log`.
Les six intégrations Memory Engine sont activées sur b33c3a0, corpus jetables.
`connected-integrated.log` : **59 réussis, 14 Chromium non exécutés**, zéro échec.
`installed-integrated.json` : **55 modules identiques**, inspections de liaison,
migration/rejet, idempotence et **25 contrôles bêta** réussis hors du checkout.

C-045 ajoute les lectures bornées SQL et le refus WAL. `g067-before.log` reproduit
l'acceptation des BLOB et le défaut WAL avant correction. Les essais intermédiaires
ont détecté un OSError non normalisé après disparition de la base (corrigé) et
deux points d'injection de tests devenus inopérants après modification des SELECT
(adaptés en conservant leurs assertions). `g067-corrected.log` : 102 PASS.
La première suite intégrée (`python-integrated-final.log`) a ensuite révélé un
ancien test exigeant WAL du lecteur HTTP. La transaction est désormais testée
avec le Store local ; la frontière HTTP teste le refus WAL. 37 tests ciblés
passent (`receipt-wal-corrected.log`), puis les 971 de la suite finale passent.

Le banc C-044 avait éprouvé la détection d'un changement en WAL ; le contrat
final C-045 est plus restrictif : la consultation refuse WAL avant connexion,
pour ne pas créer ses fichiers annexes. Aucun mode de journal n'est modifié.
G067-3 (distinction BUSY en HTTP) reste ouvert ; refus constant conservé.

### Contributions Claude et contre-vérification

- G066–G071 intégrés depuis e525610, sans réécriture des rapports/scripts.
- G068 : **4/4** tests de fermeture/snapshot rejoués (`g068-replayed.log`).
  Producteur toujours isolé ; divergences de taille/nombre/date restent à traiter.
- G069 : recette **23/23 rapportée par Claude**, pas rejouée intégralement ici
  (Chromium absent). Notre recette indépendante installée ci-dessus est distincte.
- G071 : **51/51** assertions rejouées sur le code intégré (`g071-replayed.log`).
- G070 : **20/21** ici (`g070-replayed.log`). Ne pas l'annoncer entièrement PASS.
  Le contrôle H combine bail détenu et présence dans /proc. Le premier est vrai,
  le second indisponible. `g070-environment.py` enveloppe seulement le prédicat
  alive du script original, en conservant toutes les assertions et leurs retours.
  Sa sortie (`g070-environment.log`) montre kill(pid,0) réussi, mais /proc/PID/stat
  absent pour l'orphelin. Le script le considère à tort comme mort. L'effet finit
  ensuite, le reçu est présent non adopté, aucune seconde exécution n'a lieu.
  Rejouer ce contrôle sur VM et distinguer « non observable » de « terminé ».
  Aucun correctif PDEATHSIG n'est prétendu livré ; cela reste une étude séparée.

### Publication et archive

Commit de code préparé : **c3746df25212b5279e648431b6287608173be352**.
Arbre : **c1c8ec0c6bc2360668a1a5d1ed28941fb4ef5a9e**, identique au local testé.
Git HTTPS sans identifiant en écriture dans cette session ; objets préparés par
le connecteur GitHub, avec fadc3bc et la branche Claude e525610 comme parents.
La référence finale ajoute le présent bilan, les derniers journaux et la file.

`archive-check.json` : **95 fichiers identiques aux objets Git**, trois verdicts
de qualification et deux contrôles de configuration exécutés après extraction,
sans création d'état ni appel modèle. Archive SHA-256 :
`646f1a42ad85d5619a9baf0bf89f0fa1a6be8f903426a4365b74118846610ca3`.

```sh
python tools/build_beta_bundle.py --commit c3746df25212b5279e648431b6287608173be352 --output /tmp/eidolon-beta-c3746df.tar.gz
python docs/validation/2026-10-08/codex-hour-0435/archive-check.py --archive /tmp/eidolon-beta-c3746df.tar.gz --commit c3746df25212b5279e648431b6287608173be352
```

Les pourcentages 80 % bêta observateur / 40 % vision complète restent des
estimations de périmètre. Qualification VM/Windows/modèle réel encore à faire.
