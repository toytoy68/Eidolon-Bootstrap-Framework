# Core — séance du 08/10/2026 après-midi

Codex/GPT. Demande de poursuite d'une heure reçue vers 16 h 11 Europe/Paris.
Clôture des travaux : vers 17 h 13 Europe/Paris, publication finale ensuite.
Base initiale Core : 0b439f02683f475e81d8ef8926d2548aa2a75396.
Branche autorisée : feat/eidolon-core-v0.1.

## Livraison C-046

Prototype de rotation v5, toujours hors runtime :

- import du lecteur Core pour valider exports et catalogue ;
- plafonds lecteur appliqués avant publication : 16 Mio par export, 1 000
  exports, 64 Mio cumulés, 2 048 entrées du dossier ; marge des fichiers temporaires ;
- horodatage entier sûr, booléens refusés ;
- validation d'un export orphelin avant commit de reprise ;
- budget coopératif de 5 secondes pour attente/copie SQLite, pas de délai dur
  sur une syscall ou un décodage JSON ;
- identité et version du journal revérifiées dans la transaction de retrait ;
- contrôle des résumés de chaîne contre les entrées recalculées par le lecteur.

Défaut reproduit avant correction : changer guard_id entre _publish et _commit
laissait retirer les lignes ; le test dédié échouait par absence de RotationError.
Après correction : JOURNAL_CHANGED, aucune ligne retirée, export conservé pour revue.

## Tests et preuves

| Vérification | Résultat / preuve |
| --- | --- |
| Suite runtime inchangée | 965 réussis, 6 opt-in mémoire ignorés sur 971 ; core-baseline.txt |
| Intégration Memory Engine réelle | 6 réussis séparément ; memory-integration.txt, référence a9e7daa1d46a2ade7ffbfc56580c6927d1138dd2 inchangée |
| Rotation | 37 réussis dont 12 nouveaux ; rotation-tests.txt |
| WAL, quatre coupures, trois reprises, retour schéma 2 | compatibility.txt, aucun échec ; wrapper compatibility.py |
| Plafond réel 1 000 exports | catalog-capacity.json : catalogue de 2 672 679 octets relu, prochain ajout refusé sans mutation |
| Client Node et intégration loopback | 59 réussis, 14 Chromium ignorés ; client-tests.txt |
| Paquet installé | installed-package.json : PASS, 55 modules identiques, contrôles bêta PASS |

Commandes depuis la racine du dépôt :

```sh
G062_SRC="$PWD/eidolon-core/src" python3 -m unittest discover \
  -s eidolon-core/docs/proposals/2026-10-07-research-retention -p 'tests_*.py' -q
python3 eidolon-core/docs/validation/2026-10-08/codex-afternoon/compatibility.py
python3 eidolon-core/docs/validation/2026-10-08/codex-afternoon/catalog-capacity.py
```

Client : depuis desktop/connected, node --test tests/*.test.js tests/integration/*.test.js.
Paquet : depuis eidolon-core, python3 docs/validation/2026-10-08/codex-hour-1111/installed-pauses.py.
Les sources historiques G068 et leurs preuves restent inchangées. Deux lectures
SQLite de tests_g062 avaient été laissées à la collecte automatique : fermeture
explicite ajoutée, car la collecte rendait les comparaisons de descripteurs instables
(4 au lieu de 7 ou 8, pas une fuite du nouveau producteur). Aucun oracle métier retiré.

## Identité graphique et collaboration

Logo officiel à e minuscule manuscrit adopté et publié dans 0b439f0, décision
dans assets/branding/LOGO.md ; original complet vérifié par empreinte Git.
Le README Core affiche maintenant ce logo. Icône Desktop précédente conservée.
G078–G083 publiés pour Claude dans d4b7251 : logo client, ICO, revue rotation,
contention HTTP, recette serveur/PC et assets du paquet. G072–G077 restent attribués.
Aucune lecture ni activation de session Claude déduite de la publication.

## Limites

Aucun source runtime ou test runtime modifié. Aucune fusion main, aucun
déploiement ou accès à la VM/PC de toytoy. Aucun fournisseur ou modèle réel
qualifié. Le prototype passe au schéma 3, toujours refusé par la garde Core :
l'intégration et le déclenchement réel restent ouverts avec contre-revue G080.
Aucune hausse de quota, suppression d'archives ni migration réelle automatique.
La mesure de lecture est un essai unique sur ce conteneur ; pas un benchmark
du NAS, de Windows, d'un disque ou d'une coupure électrique.


Intégration mémoire rejouée sur la tête distante lue a9e7daa, dans une copie
locale propre, sans modification du dépôt Memory Engine ni données personnelles.
Commandes depuis eidolon-core :

```sh
EIDOLON_MEMORY_INTEGRATION=1 PYTHONPATH=src:.:/chemin/memory-reference \
  python3 -m unittest tests.test_memory_engine -q
```

Les 965 tests runtime et les six opt-in réussis séparément couvrent les 971 tests
de la suite ; aucun unique passage de 971 avec mémoire n'est revendiqué ici.
