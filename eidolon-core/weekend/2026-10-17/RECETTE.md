> **G273 :** le dossier comporte maintenant 50 cas. Compléter G19–G24 selon SERVICES-HORS-VM-G273.md après la recette du socle. Aucun résultat machine n’est prérempli comme réussi.

> **Complément G272 :** après les raccordements ci-dessous, suivre DOCUMENTS-G272, PROFILS-ENROLEMENT-G272 et ETAT-PRIVE-G272. Les preuves comprennent maintenant G11–G18, soit 44 cas. Tous restent NOT_RUN dans le modèle.

> **G270 :** cette recette conserve les contrôles initiaux du socle G269. Le parcours complet profils/chat/Internet/fichiers/activité entre VM et résident Windows est dans [RACCORDEMENTS-G270.md](RACCORDEMENTS-G270.md). Les options `--memory-bridge-token-file` du socle et `--beta-runtime` du parcours profils sont exclusives.

# Recette du week-end — progression et arrêts

## 1. PC : contrôler et extraire les fichiers

Télécharger le ZIP et sa somme SHA-256 depuis le rapport de livraison. Comparer avec `Get-FileHash .\eidolon-weekend-2026-10-17-g273.zip -Algorithm SHA256`, puis extraire dans un **nouveau dossier**. Ne pas écraser une installation existante. Extraire ensuite `eidolon-sources-g273.zip` dans ce nouveau dossier pour obtenir `sources/`. Le sous-paquet `eidolon-windows-g270.zip` contient le binaire et les deux scripts à placer dans un dossier Windows privé stable.

Depuis la racine extraite, avec Python disponible :

```powershell
python .\sources\core\eidolon-core\tools\build_weekend_bundle.py --verify C:\CHEMIN\eidolon-sources-g273.zip
$EidolonKit = '.\sources\core\eidolon-core\weekend\2026-10-17'
& "$EidolonKit\inventory_pc.ps1" -Port 8767 > .\pc-inventory.json
Copy-Item "$EidolonKit\results.template.json" .\results-weekend.json
```

Attendu du vérificateur : `VERIFIED_BYTES`, `qualified=false`. Les empreintes prouvent les octets, pas la disponibilité des services. `inventory_pc.ps1` n'a pas été exécuté sous Windows pendant la préparation. Ne pas contourner la politique PowerShell de la machine ; exécuter selon la politique locale autorisée. Le numéro 8767 est un exemple : relever le port réel avant le tunnel.

## 2. VM : inventaire seulement, puis copie arrêtée

Transférer les sources dans un répertoire neuf de recette. Exécuter `inventory_vm.py --core-repo /DEPOT/CORE --memory-repo /DEPOT/MEMORY --service NOM-REEL.service` avec les chemins/noms relevés ; ne pas deviner un nom de service. Enregistrer la sortie en privé. L'archive source n'a pas de `.git` : le manifeste fournit son SHA ; l'inventaire Git vise les dépôts installés existants.

Avant toute écriture : relever les services/processus réellement actifs et leur commande/configuration, arrêter **les writers de la copie concernée**, constituer une sauvegarde vérifiable, restaurer cette sauvegarde dans une autre copie et comparer l'inventaire. Les outils `tools/claude_copy_inventory.py` du dépôt Core peuvent comparer des arbres arrêtés ; leur résultat n'est pas un snapshot atomique. Un état `UNKNOWN`, `INVENTORY_RESOURCE`, `CHANGED` ou `UNREADABLE` bloque l'adoption de cette copie.

Prévoir des emplacements distincts : sources candidates, corpus de recette, état Core de recette, état de maintenance privé, configuration privée, alias Qdrant de recette. Aucun chemin de production ne doit être remplacé dans ces commandes. Conserver le snapshot initial pour le rollback.

## 3. Environnement candidat

Utiliser un environnement Python dédié déjà préparé ou en préparer un explicitement après inventaire. Les dépendances sont dans `sources/memory/requirements.txt`, `requirements-dev.txt` et `requirements-qdrant.txt` ; le client Qdrant est épinglé à 1.15.1. Les moteurs de voix, reranker et biométrie ont leurs propres dépendances/caches et ne sont pas fournis. Ne pas télécharger de modèle implicitement à leur premier appel.

Pour le code Core et l'intégration Memory, définir `PYTHONPATH=/SOURCES/CORE/eidolon-core/src:/SOURCES/MEMORY`. Pour une commande Memory, se placer dans `/SOURCES/MEMORY`. Garder les chemins et comptes privés hors des dépôts.

Tests ciblés, sur données temporaires synthétiques uniquement :

```sh
# Depuis Memory :
python -m pytest -q -W error -p no:cacheprovider tests/test_index_runtime_g269.py tests/test_qdrant_passages_g269.py tests/test_remember_g269.py
# Depuis Core/eidolon-core, PYTHONPATH incluant Memory :
EIDOLON_MEMORY_INTEGRATION=1 python -m pytest -q -W error -p no:cacheprovider tests/test_maintenance_host_g269.py tests/test_weekend_bundle_g269.py
```

Le corpus privé ne sert pas de fixture. Les tests Qdrant ci-dessus utilisent un client en mémoire ; ils ne qualifient pas le serveur installé. Les tests `test_qdrant_server_*` exigent explicitement un binaire jetable et leur environnement séparé ; ne pas leur donner le serveur de production.

## 4. Stockage et pont de rappel

Depuis Memory :

```sh
python -m services.memory_bridge --root /COPIE/RECETTE --check-storage
```

Codes : READY 0, BLOCKED 2, BUSY 3, UNAVAILABLE 4, UNSUPPORTED 5, ERROR 6 ; erreur d'usage 64. Le JSON et le code doivent correspondre. Cette commande ne crée ni verrou, ni modèle, ni réseau. Elle exige la préparation préalable des répertoires/verrous canoniques sur la copie. Ne pas les fabriquer arbitrairement sur le corpus vivant. Elle ne vérifie ni l'index, ni la pertinence, ni le token.

Pour qualifier le mode readonly, répéter sous le **compte prévu** avec le montage/les permissions réelles : un vrai essai d'écriture doit être refusé, un rappel doit rester possible. La réussite sous root ne prouve pas l'isolation.

## 5. Index sémantique et passages

Copier `index.example.json` vers un chemin privé absolu `index.json`, changer l'alias pour une valeur neuve réservée à la recette, vérifier ports, modèle installé, digest et dimensions. Les mêmes dimensions ne suffisent pas à rendre deux modèles compatibles.

```sh
python -m core.indexing.runtime --config /CONFIG/index.json check-config
python -m core.indexing.runtime --config /CONFIG/index.json rebuild --persistent-root /COPIE/RECETTE/memory/persistent --stopped-copy --create-alias
python -m core.indexing.runtime --config /CONFIG/index.json status
```

`check-config` : hors réseau, `CONFIG_VALID`, `services_checked=false`. `rebuild` : écrit dans Qdrant et prend le verrou coopératif de la copie ; un writer unique doit contrôler cet alias. `--stopped-copy` est une attestation de l'opérateur, pas un gel des fichiers. En cas d'échec, conserver la génération incomplète pour revue ; aucune suppression automatique. Une archive trop grande est refusée, pas tronquée en silence.

Lancer ensuite le pont au premier plan, token fort déjà fourni par le mécanisme privé habituel (ne pas le coller dans le terminal, le guide ou les résultats) :

```sh
python -m services.memory_bridge --root /COPIE/RECETTE --read-only-storage --index-config /CONFIG/index.json --port 18765
```

Le port doit être libre et distinct de la production. Le pont écoute sur 127.0.0.1. Il requiert `EIDOLON_MEMORY_BRIDGE_TOKEN`, comme avant G269. Pour ce seul contrôle historique du socle, raccorder Core au pont via les options existantes `--memory-bridge-token-file` et `--memory-bridge-port`, après vérification de `--help` et de la configuration réelle. Le token Core d'accès client reste distinct.

Vérifier une question directe, une paraphrase et une question sans réponse attendue. Contrôler le texte cité, l'identité, la révision, la position du passage, la négation, le statut UNVERIFIED et la fraîcheur. Couper uniquement les services jetables de recette et vérifier une erreur explicite. Aucune qualité sémantique chiffrée n'est revendiquée par les tests synthétiques. **Ne pas relancer G182** : récupérer ses journaux existants séparément.

## 6. « Retenir ceci » : parcours opérateur candidat

Cette tranche est une CLI, pas encore un bouton de conversation. Utiliser d'abord `remember.example.json` sur la copie. Lire l'aperçu, vérifier le texte, l'acteur, la date et l'identifiant stable :

```sh
python -m core.information.remember --input /CONFIG/remember.json
python -m core.information.remember --input /CONFIG/remember.json --root /COPIE/RECETTE --approve-sha256 EMPREINTE_EXACTE_DE_L_APERCU
```

Rejouer la seconde commande à l'identique : même reçu, un seul souvenir. Changer le texte en conservant le request_id doit provoquer un conflit ; le souvenir original doit rester intact. Une empreinte différente de l'aperçu refuse avant création du writer. En cas d'interruption, conserver la commande d'origine et examiner le journal avant reprise. Le souvenir reste UNVERIFIED. L'aperçu révèle le texte : résultats privés uniquement.

L'index de passages exige ensuite une synchronisation explicite `sync` (G270) pour inclure le nouveau souvenir. Une première construction utilise `rebuild`. Le journal d'écriture métier n'alimente pas directement le journal d'index dans cette tranche ; la maintenance documentaire le découvre par réconciliation.

## 7. Maintenance : d'abord observer, puis un seul tick

Depuis Core/eidolon-core, `PYTHONPATH` incluant Memory :

```sh
python -m eidolon_core.maintenance_host --policy /CONFIG/host-policy.json --capture-only
python -m eidolon_core.maintenance_host --policy /CONFIG/host-policy.json --check-only
```

Sans reçu d'activité authentique et récent, `LAST_ACTIVITY_UNKNOWN` doit apparaître ; le contrôleur traitera l'activité comme récente et différera. `CHECK_ONLY` / `NOT_EXECUTED` ne signifie pas qu'un tick serait éligible. L'observation CPU est load1/nombre de CPU, pas un pourcentage d'occupation. La source doit couvrir l'activité des utilisateurs de Core : ne pas confondre absence de frappe locale sur VM et inactivité de l'assistant.

Pour un tick explicite **sur la copie**, préparer un second alias `projection=documents`, sa configuration et sa reconstruction. Préparer un dossier d'état privé 0700 **hors du corpus** et `maintenance.json` avec chemins absolus et liste exacte des Information autorisées. L'index `archive_passages` est refusé par ce worker.

```sh
python -m eidolon_core.maintenance_host --policy /CONFIG/host-policy.json --activity /CONFIG/activity.json --runtime /CONFIG/maintenance.json --execute
```

Un seul tick, aucun retry interne automatique au lanceur. En dehors de 04–08 Europe/Paris, si boot ou activité <30 min, charge élevée/inconnue : report DEFERRED. L'initialisation explicite peut créer les checkpoints avant cette décision ; `--execute` n'est pas un dry-run. Tester la reprise avec les mêmes checkpoints. Aucune permission de suppression n'est accordée ; les orphelins pourront produire REVIEW_REQUIRED, à examiner.

Les `.service.in`/`.timer.in` sont des **brouillons**. Avant adoption : fixer compte C187, chemins, source d'activité réellement alimentée et seuils, vérifier les directives systemd sur la VM. Le contrôleur ouvre `.write.lock` en écriture : la proposition isole le corpus en readonly avec exception limitée au verrou stable préexistant. Tester ce montage et l'UID avant activation. Ne pas ouvrir tout le corpus en écriture pour contourner un échec. Aucun `enable --now` n'est fourni.

## 8. PC : expérience réelle

Le lanceur `desktop/connected/launchers/eidolon-tunnel.ps1` est en aperçu par défaut. Utiliser les vrais hôte/compte/port relevés, vérifier la clé SSH, puis seulement l'option `-Connect`. Le port distant et local doivent respecter les contraintes Host de l'API. Ne pas exposer l'API sur le LAN pour contourner le tunnel.

Suivre [WINDOWS-WEEKEND.md](../../docs/WINDOWS-WEEKEND.md), W1–W21, avec micro, casque, webcam, débranchements/rebranchements, refus de permissions et échelles 125/150 %. Compléter P01–P10. Le guide [BETA-ACCEPTANCE.md](../../docs/BETA-ACCEPTANCE.md) conserve sa portée historique « observateur » ; sa réussite ne couvre pas chat/mémoire/voix.

## 9. Clôture et décision

Enregistrer dates, versions exactes et preuves par cas dans `results-weekend.json`, puis :

```sh
python check_results.py /CHEMIN/results-weekend.json
```

Code 1 = incomplet ; 2 = document invalide ; 0 = preuves complètes à revoir. Le champ `beta_authorized` reste toujours false. Un humain décide ensuite du périmètre opérationnel. Suivre [ROLLBACK.md](ROLLBACK.md) pour tout retour arrière ; préserver les journaux et les créations de la recette jusqu'à la clôture.
