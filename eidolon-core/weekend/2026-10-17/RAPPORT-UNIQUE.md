# Eidolon — rapport unique G275, audit corrigé et contre-vérifié

**16 octobre 2026 · Codex/GPT · dossier PC/VM des 17–18 octobre.**

G275 intègre l’audit indépendant de Claude (C192/C193), les quatre patches finaux
et les écarts d’exploitation/documentation. Les preuves ci-dessous concernent les
sources et des environnements jetables. **Les 50 validations sur PC/VM restent
NOT_RUN ; aucun service utilisateur n’a été déployé.**

## Résultat de l’audit et décisions appliquées

Claude a reproduit deux P1 et deux P2. Son absence de P0 trouvé ne prouve pas une
absence de défaut sur tout le projet. Son rapport distingue les parties lues,
testées, non examinées en profondeur et bloquées faute de matériel.

| Priorité / constat | Correction intégrée |
| --- | --- |
| P1 — rappel refusé sur messages longs ou multilignes | Seule la requête de rappel est nettoyée et limitée à 500 caractères, en gardant **la fin**, depuis une limite de mot. Historique et message au modèle inchangés. |
| P1 — un document inexploitable bloque sa bibliothèque | Document inventorié avec diagnostic, autres fichiers traités ; nouvel essai au passage suivant. Au-delà de 4 Mio : métadonnées seulement, pas de SHA ou d’extrait inventé. |
| P2 — attente GPU orpheline après erreur | Retrait conditionnel des seules attentes, trois tentatives si stockage occupé ; effets incertains et réservations actives conservés. Retrait non confirmé explicitement signalé. |
| P2 — seuil de calibration trop permissif à résultat égal | À faux rejets égaux, seuil le plus haut, puis marge relative de **15 % côté authentiques**. Exemple : scores 0,50/0,90 → seuil 0,84. Aucun seuil activé. |

Les choix de fin de message et de marge sont les décisions de toytoy rapportées
par Claude dans C193. La marge est relative à l’écart entre scores de calibration :
ce n’est pas une réduction absolue de 0,15 ni une garantie de précision réelle.
Patches retenus : **0011, 0008, 0009 et 0012**. Les versions 0007/0010 restent historiques.

## Contre-vérification et compléments

Avant correction, les sondes Claude exécutées avec `--runxfail` reproduisent
**13 échecs et cinq témoins réussis**. Après correction, ces marques d’échec attendu
sont retirées. Les tests restent dans la suite normale.

La contre-revue a renforcé le patch bibliothèque : comparer seulement la taille
d’un gros fichier ne suffisait pas. Identité, taille et dates sont maintenant
revérifiées ; remplacement, réécriture de même taille, liens physiques et fichiers
spéciaux sont testés. Un fichier sans extrait apparaît comme tel dans l’interface ;
un ancien extrait ne devient pas silencieusement son extrait courant.

Autres compléments livrés :

- **Arrêt propre :** SIGTERM suit la fermeture du serveur. Les attentes GPU créées
  par cette instance sont retirées avant la fin ; demandes héritées et réservations
  ACTIVE/UNKNOWN restent conservées. Un processus réellement arrêté par signal
  vérifie cette distinction. Aucun calcul distant n’est présumé annulé.
- **Diagnostic GPU :** au démarrage, signalement des demandes préexistantes. Le
  statut donne les comptes complets et les MiB réservés, même si la liste des
  identifiants est tronquée. Aucun propriétaire n’est présumé mort.
- **Memory :** un rejet connu avant writer renvoie 400 REMEMBER_INVALID_REQUEST,
  effects NONE ; une erreur pendant/après exécution reste 503 REMEMBER_UNAVAILABLE,
  effects UNKNOWN. Une erreur injectée après écriture puis une reprise de la même
  commande vérifient l’idempotence. Core conserve son comportement prudent.
- **Documentation et Bootstrap :** passages incrémentaux, mémorisation et maintenance
  alignés ; import Any corrigé ; bannière absente retirée, scripts existants reconnus,
  variables réseau inutilisées retirées. Dépendances PDF/média rattachées au runtime
  Core, sans exécution d’installateur ni modification du réseau.
- **Windows :** limite de confiance du démarrage explicitée. Le résident est vérifié
  à l’inscription, le binaire à chaque lancement ; le compte possède script et HKCU.
  Aucune protection contre ce même compte n’est promise. Sous-paquet G270 inchangé.
- **Identité en CI :** job dédié avec ONNX Runtime réellement exécuté sur un modèle
  généré et audio synthétique, plus parité fbank. Cela ne qualifie ni YuNet/SFace
  avec leurs poids réels, ni la reconnaissance d’une personne.

Deux erreurs d’édition ont été détectées dans les essais intermédiaires : appel
incorrect d’un constructeur dans une nouvelle sonde, et substitution trop large
dans l’annulation GPU. Elles ont été corrigées en conservant les assertions ;
les campagnes rouges ne sont pas comptées parmi les réussites.

## Révisions et preuves

- **Code Core G275 qualifié :** `48c5735079d33cab82ba2ce5a82f2f54820f97aa`, branche `feat/eidolon-core-v0.1`.
- **Memory G275 :** `b36ada1ff4f505fa2c5d2778f74f3b0c836d2f4c`, branche `refactor/architecture-v1` ; référence exacte épinglée dans la CI Core.
- **Audit Claude préservé :** `508db0a5aa8922acec7bf8a29fbc67184b0d2a4e`, inclus dans l’ascendance Core.
- **Windows conservé :** source `fe7261826eb26e6b4f2c92a6f55636330cd3df1f`.
- Le manifeste de livraison indique le commit documentaire final ; son delta par
  rapport au code qualifié est contrôlé et ne remplace pas une campagne de tests.

| Campagne | Résultat | Preuve |
| --- | --- | --- |
| Core complet, Python 3.13 | **2 306 réussis, 8 ignorés, 1 328 sous-tests** | [Run 38866869488](https://github.com/toytoy68/Eidolon-Bootstrap-Framework/actions/runs/38866869488) |
| Propriétaires de jetons avec changements réels d’UID | **5 réussis** | Étape distincte du run Core |
| Nouveau job identité synthétique | **4 réussis, aucune exclusion** | Job distinct du même run Core |
| Chromium, parcours réels navigateur/serveur | **216 réussis, aucune exclusion** | [Run 38866869465](https://github.com/toytoy68/Eidolon-Bootstrap-Framework/actions/runs/38866869465) |
| Core ciblé local, corrections et contre-revue | **69 réussis** | Claude G274, services G273, contre-revue G275 et disponibilité HTTP |
| Dossier, manifestes et preuves | **7 réussis** | `test_weekend_bundle_g269.py` ; **50 NOT_RUN, 0 PASS** machine |
| Memory complet | **3 156 réussis, 26 ignorés, 3 xfail historiques, 12 sous-tests** | [Run 38866368387](https://github.com/toytoy68/Eidolon-Memory-Engine/actions/runs/38866368387) |
| Worker réel, journal Markdown/index isolé | **52 réussis** | Étape séparée du run Memory |
| Contrat Qdrant ciblé | **550 réussis, 1 xfail historique** | [Run 38866368336](https://github.com/toytoy68/Eidolon-Memory-Engine/actions/runs/38866368336) |
| Serveur Qdrant jetable 1.15.4 | **19 réussis** | [Run 38866368454](https://github.com/toytoy68/Eidolon-Memory-Engine/actions/runs/38866368454) |
| Windows G270, preuve conservée | **5 tests Rust**, compilation, PowerShell, résident sans Core et inscription/retrait HKCU réussis | [Run 38782802182](https://github.com/toytoy68/Eidolon-Bootstrap-Framework/actions/runs/38782802182) |

Les huit exclusions Core correspondent à deux contrôles d’UID rejoués sous root,
trois tests exécutés dans le nouveau job identité et trois tests YuNet/SFace encore
sans poids réels. Le quatrième test du job identité recouvre déjà la suite principale.
L’avertissement pytest provient du ZIP volontairement dupliqué d’un test de refus.

Les campagnes ciblées recouvrent les suites complètes : **ne pas additionner** les
comptes. Windows n’a pas été recompilé pour G275. Les exclusions et xfail ne sont
pas des validations réussies. Les essais matériels et montages privés restent ouverts.

## Livraison PC/VM

Le paquet **eidolon-weekend-2026-10-17-g275.zip** remplace G273 pour les sources et
le dossier. Il contient `eidolon-sources-g275.zip`, le sous-paquet Windows G270
inchangé, les procédures, manifestes et SHA-256. Extraire dans un dossier neuf,
contrôler les empreintes, puis lire [README](README.md), [RECETTE](RECETTE.md) et
[SERVICES-HORS-VM-G273](SERVICES-HORS-VM-G273.md), actualisé pour G275.

SHA de l’exécutable Windows conservé :
`3f7439082422469967df57b683cc43ded83510acbd1e65371a2b8f96fefae09b`.
SHA du sous-paquet Windows :
`d61083dd3e9a97dfb037a79ab39a1ad462b25e40b76e28b32991188f9978f0d7`.

Les sources sont extraites des objets Git publiés. Le paquet n’inclut ni secrets,
corpus, gabarits privés, modèles, dépendances natives ni image VM. Il ne constitue
pas une autorisation automatique de déployer. Le binaire Windows est une candidate
non signée ; aucun comportement physique sur le PC de toytoy n’est déduit de la CI.

Sauvegarder séparément bibliothèque et file GPU, en plus des états déjà couverts
par `beta_state`. L’ajout de la table de diagnostics bibliothèque se fait au prochain
scan explicite ; une simple consultation d’un ancien état reste sans migration.
Consulter [ROLLBACK](ROLLBACK.md) avant remplacement de code ou d’états privés.

## Ce qui reste réellement ouvert

**P0 — recette machines :** comptes C187, permissions, tunnels et services ;
sauvegardes/restauration cohérentes ; corpus et modèles réels ; PC/WebView2/capteurs ;
latence, charge, VRAM et endurance. Les 50 contrôles requièrent des observations datées.

**Hypothèses de l’audit :**

- H1 : le quota CPU fixe de 10 % a été retiré du brouillon. Mesurer le premier scan
  avant de fixer un quota compatible avec les bornes ; Nice=10 reste proposé.
- H2 : la synchronisation des passages garde le verrou canonique pendant les
  embeddings. Le risque de rappel retardé reste à mesurer ; aucun changement de
  transaction n’est annoncé comme qualifié. Maintenance et reprise d’activité
  restent à vérifier ensemble sur la machine.
- H3 : arrêt Linux propre testé ; SIGKILL, panne et stockage durablement bloqué
  imposent encore inventaire/revue. Pas d’expiration automatique de réservations.
- H4 : marge de calibration à mesurer sur captures consenties représentatives.

**Développements distincts non livrés :** purge coordonnée, agent Windows natif de
surveillance des fichiers, connexion biométrique multipersonne, tous les moteurs
participants à la file GPU et médias avancés. Aucun de ces points n’est maquillé
en simple case de recette.

Voir [la contre-vérification détaillée](../../docs/CONTRE-VERIFICATION-G275.md),
[le rapport de Claude](../../docs/AUDIT-GLOBAL-CLAUDE-G274.md) et le
[backlog courant](../../docs/BACKLOG-BETA-ACTUEL-G273.md). C193 est le dernier retour
Claude reçu dans ce lot ; aucune nouvelle exécution de sa session n’est supposée.
