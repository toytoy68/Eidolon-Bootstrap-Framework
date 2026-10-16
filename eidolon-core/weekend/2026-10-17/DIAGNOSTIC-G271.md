# Diagnostic avant lancement — G271

Ce diagnostic Linux permet de vérifier une configuration avant d'instancier Core.
Il ne démarre aucun service et ne crée ni état, ni verrou, ni compte. Utiliser les
sources G272 (commande introduite en G271) ; le paquet G270 précédent ne contient pas cette commande.

Depuis `eidolon-core/`, contrôler d'abord le fichier JSON préparé :

```sh
PYTHONPATH=src python -B -m eidolon_core.beta_preflight \
  --config /CHEMIN/runtime.json
```

La commande lit uniquement ce fichier : JSON strict et borné, champs attendus,
liaisons clients/profils, ports et chemins de jetons distincts, fournisseur Internet
explicite. Les chemins déclarés ne sont pas ouverts. Elle permet donc de préparer
le fichier sur une machine Linux différente des VM cibles. Les exemples du dépôt
peuvent être vérifiés tels quels dans ce mode ; cela ne prouve pas leur installation.

Sur la machine cible, **sous le compte qui exécutera Core**, ajouter :

```sh
PYTHONPATH=src python -B -m eidolon_core.beta_preflight \
  --config /CHEMIN/runtime.json --local-files --format human
```

Ce second mode ouvre les répertoires configurés sans parcourir leur contenu et
lit les jetons. Il vérifie configuration 0600, état 0700, propriétaires, lecture
privée des jetons et absence de réutilisation d'un même secret entre profils ou
entre lecture/écriture. Les jetons doivent être dans un parent 0700, être des
fichiers 0600 uniques, sans lien. Les racines de fichiers doivent pouvoir être
ouvertes sans suivre de lien. Aucun corpus utilisateur n’est lu ou listé.

Les lignes `profile_1`, `profile_2` suivent l'ordre des profils dans le JSON ;
les racines suivent l'ordre de `file_roots`. Aucun nom de personne, chemin privé,
secret ou empreinte de secret n'est imprimé. `CREDENTIAL_REUSED` désigne un secret
déjà rencontré ; `UNAVAILABLE_OR_INVALID` exige de vérifier le fichier indiqué
par le rôle et l'ordre dans la configuration. Le diagnostic ne corrige rien.

| Résultat | Code de sortie | Ce qui est établi |
| --- | --- | --- |
| `CONFIG_VALID` | 0 | Configuration syntaxiquement et structurellement valide |
| `LOCAL_FILES_VALID` | 0 | Contrôles locaux supplémentaires réussis à cet instant |
| `BLOCKED` | 2 | Au moins un contrôle a échoué ; détails par ligne |
| `USAGE_ERROR` | 64 | Arguments manquants, inconnus ou mal formés |

JSON est le défaut ; `--format human` utilise la présentation Eidolon. `-B` évite
la création de caches Python pendant le diagnostic. Les primitives de lecture
requises sont Linux : ce module n'est pas un diagnostic Windows natif.

## Limites et preuves

Les états `LOCAL_FILES_VALID` et `CONFIG_VALID` ne signifient jamais « bêta prête ».
Le champ `beta_authorized` reste faux. La base existante et sa liaison de
configuration ne sont pas ouvertes ; les clients réellement appairés, l'identité
et les droits des ponts Memory, les services réseau, modèles/corpus, contenus et
droits effectifs des montages, Windows et matériel restent `NOT_RUN`.
L'ouverture d'un dossier ne prouve pas la lisibilité de tous ses fichiers.

Ce contrôle n'est pas un instantané atomique : les fichiers peuvent changer entre
deux vérifications ou ensuite. Core conserve ses propres contrôles au lancement
et pendant les accès. Aucun résultat n'est injecté dans les 50 preuves de recette.

Validation locale du lot : 14 tests dédiés, dont un processus audité qui refuse
réseau, écritures, lancement de processus, accès SQLite et listage des données.
Sept tests du paquet et des preuves sont également rejoués : 21 réussis au total.
Les chemins, jetons et fichiers utilisés sont synthétiques ; aucune VM consultée.

## Extension G272 : identité optionnelle

Avec `identity_config`, `--local-files` lit également cette configuration privée,
vérifie les SHA des modèles déclarés et la présence des modules numpy/onnxruntime
ou cv2 selon la modalité. Aucun moteur n’est lancé ni modèle téléchargé. Les poids
sont lus pour leur empreinte ; les corpus utilisateurs ne sont toujours pas lus.
Une dépendance trouvée n’est pas une preuve de compatibilité de son ABI ou du
modèle. Précision et calibration restent explicitement NOT_RUN. Le mode configuration
seule ne lit pas cette configuration secondaire et ne valide donc pas son contenu.
