# Séance Core du 07/10/2026 — début 19 h 48 Paris

Codex, branche feat/eidolon-core-v0.1. Travail autorisé avec publications GitHub,
sans main, déploiement, VM, service personnel ou modification Memory Engine.

## Livraisons et publications

- Six nouvelles tâches G066–G071 publiées en bb1dc607566ab0ecbf62dca8cdc435954d754749.
- C-030 catalogue HTTP : a78fc0478fa12efc7ffd178a732774b996f9c3e9.
- C-031 recherches/archives et C-032 planificateur CLI : 75f6640463588a698013d17151a288c53c9490ae.
- C-033 recette automatique research-archives : code et preuves dans cette publication.
- Dernière livraison Claude observée avant ces vérifications : G063, a130882,
  intégrée via 56aa33f. Les tâches disponibles ne prouvent pas sa session active.

[Bilan fonctionnel et estimations](../../../PROJECT-STATUS-2026-10-07.md).

## Résultats exécutés

| Périmètre | Résultat | Preuve |
| --- | --- | --- |
| C-030 API, lecteur et prédiagnostic | 73 réussis dont 15 nouveaux | archive-api-tests.txt |
| C-031 recette/archives/paquet | 39 réussis dont six nouveaux | research-fixture-tests.txt |
| C-032 configuration et adaptateur | 23 réussis dont neuf nouveaux | model-config-tests.txt |
| C-033 recette et nettoyage | huit réussis dont deux nouveaux | research-beta-check-tests.txt |
| Suite globale après C-030 | 817 réussis, six ignorés | c030-full-tests.txt |
| Suite globale après C-032 | 832 réussis, six ignorés | final-full-tests.txt |
| Suite globale finale C-033 | **834 réussis, six ignorés**, 840 découverts | c033-full-tests.txt |
| Client connecté | **51 réussis, 13 Chromium ignorés** | connected-tests.txt |
| Bundle JS | build.js --check réussi | client-build-check.txt |
| Profil recherches automatique | **25 contrôles réussis** | research-beta-check.json |
| Paquet final isolé | **47 modules identiques**, recettes **24 + 25** réussies | installed-package-final.json |

Les six tests Python ignorés dépendent de l'installation du Memory Engine, non
présente dans cette exécution. Les intégrations mémoire précédemment réussies
restent des preuves antérieures, pas des tests exécutés ici. Chromium est absent.
Les résultats navigateur antérieurs de Claude ne sont pas réattribués à Codex.

Le paquet est construit sans téléchargement puis installé en venv jetable.
Les CLI, serveur HTTP et worker du faux Ollama sont exécutés hors du checkout :
mission atteinte, reprise sans nouvel appel modèle, catalogue paginé et diagnostics.
Le faux Ollama valide un protocole et un parcours, jamais la qualité d'un vrai
modèle, son matériel ou ses performances. Tous les processus créés et données
temporaires du script sont nettoyés ; aucun état utilisateur n'est utilisé.

## Contre-vérification du prototype G063

Les deux contre-exemples G062 sont corrigés : export lisible après écriture courte,
fichier partiel inconnu conservé. Résultats dans g063-independent.jsonl.

Le premier rejeu groupé de 21 tests échoue sur une égalité de descripteurs : 7
avant, 4 après, donc une diminution. Le cas isolé passe. Un rejeu avec collecte
avant chaque mesure passe 21/21. Les trois journaux sont conservés. Ce dernier
résultat ne suffit pas à garantir une fermeture déterministe.

Sonde distincte g063-invalid-snapshot.py, dix lectures de métadonnées synthétiques
invalides avec GC désactivé : **4→14 descripteurs**, retour à 4 après GC, dix
TypeError bruts. Base active inchangée, aucune archive créée. _Snapshot doit
fermer sa destination SQLite dans un finally sur ces refus. Affecté à G068,
prototype toujours isolé et schéma 3 toujours refusé par la garde active Core.

## Mesure du catalogue

archive-scaling.py fabrique des copies au format d'export, pas une vraie rétention.
Un seul échantillon par taille, Linux/Python 3.12.14, fichiers temporaires locaux :

| Archives | Octets des exports | Lecture du catalogue | Page HTTP de 100 au plus |
| ---: | ---: | ---: | ---: |
| 10 | 24 602 | 2,14 ms | 3,46 ms |
| 100 | 246 284 | 14,02 ms | 14,64 ms |
| 1 000 | 2 465 786 | 139,31 ms | 146,58 ms |

À 1 000 archives : réponse 23 346 octets, pic RSS du processus environ 24 Mio.
Ce n'est ni une garantie de latence ni un benchmark de fichiers maximaux, NFS,
Windows ou VM. Le budget coopératif ne coupe pas un syscall bloqué ou un JSON
individuel en cours d'analyse. Aucun catalogue partiel n'est présenté comme complet.

## Commandes principales

```sh
PYTHONPATH=src:. python -m unittest discover -s tests -t . -q
node --test desktop/connected/tests/*.test.js desktop/connected/tests/integration/*.test.js
node desktop/connected/build.js --check
PYTHONPATH=src python -m eidolon_core.beta_check --web-root desktop/connected --profile research-archives
python docs/validation/2026-10-07/codex-hour-1948/core-package-final.py
PYTHONPATH=src:. python docs/validation/2026-10-07/codex-hour-1948/archive-scaling.py
```

La lecture du rapport ne donne aucun droit de reprise, d'exécution ou de retrait
actif. Les pourcentages du bilan sont des estimations de périmètre documentées,
pas une transformation du taux de réussite des tests en avancement produit.


## Archive publiée et proposition de correctif

Sur d44bad837f9f492a775583a53a5fe9fef650c475 : archive de 79 fichiers (220 111 octets),
empreinte 1b923b1318984426ba8563de924e9916549ee06596c197e761ff10c6b5d34ea0.
Structure et manifeste vérifiés, quatre nouveaux guides présents, 25 contrôles
rejoués depuis l'extraction. Archive temporaire supprimée après vérification ;
pas de publication de release ou d'installation utilisateur. Reproductible avec
source-bundle-smoke.py et le commit complet ; published-source-bundle.json.

La proposition g063-snapshot-close.patch a ensuite été testée sur une copie
jetable, sans toucher aux sources de Claude : 21 tests réussis avec GC désactivé ;
dix refus sur métadonnées invalides gardent 4→4 descripteurs avant toute collecte.
TypeError reste brut dans cette proposition minimale. G068 doit revoir/intégrer
le correctif et compléter les autres limites. Voir check-snapshot-close.py,
g063-proposed-close-tests.txt et g063-proposed-close.json. Rotation non activée.


## Dernière sonde et clôture technique — 2026-10-07T20:46:29+02:00

Sous verrou SQLite exclusif d'un writer synthétique externe, verify du prototype
G063 reste en cours au-delà de six secondes. Le seul enfant créé est arrêté,
la transaction du writer annulée, la base inchangée et aucun export créé.
Cette observation ne prouve pas une attente infinie ; elle complète le besoin de
budget de copie confié à G068. Preuves : g063-backup-contention.py/json.

Code Core final testé : d44bad8 ; les publications suivantes ajoutent seulement
preuves, documentation et coordination. Dernière tête Claude observée : 56aa33f
(G063) ; aucune livraison G064–G071 reçue pendant cette séance. Les six nouvelles
tâches sont disponibles. Arbres locaux/distants comparés, liens locaux du bilan
et des nouveaux guides vérifiés. Aucune attente de permission utilisateur.
