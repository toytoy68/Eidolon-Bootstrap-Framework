# Séance Core du 07/10/2026 — reprise de 10 h 56 Paris

Codex/GPT. Demande toytoy : poursuivre une heure et maintenir du travail prêt
pour Claude. Publication GitHub explicitement autorisée dans cette séance.
Branche : `feat/eidolon-core-v0.1`. Aucun merge main ni déploiement.

## Livraisons

| Lot | Résultat | Commit publié |
| --- | --- | --- |
| G050–G053 | Contre-revues intégrées et coquille Tauri de consultation ; file Claude renouvelée | 621d71ba8037d3bc0f24781d6fdbc8dd6f6b2fe2 |
| Suivis G050/G052 | Nettoyage renforcé, hash brut retiré des reçus, frontière de migration des reçus corrigée | 34e61b18b8519031fb67e7515d5b6fcfa1a8d2b7 |
| C-019 | Historique local du texte nettoyé atomique avec l’intention, schéma 2, pagination bornée et reset | 2a98a9a622399c6a28ff21a6e15b735eb0884857 |
| C-020 et G054 | Titres de challenge Unicode/BOM, déduplication du texte ; diagnostics/arguments Tauri durcis par Claude | 971f95d58310b7d2c661492a2e2c584b7de5eba6 |
| Coordination G075 | Schéma 2 transmis à la proposition de rotation Claude | ded4e76e783adf97a1ba8beb7dba4e84630b08e1 |
| C-021 | Mission de recherche synthétique liée à la garde, au budget et à une vérification indépendante du plan | 9ee40c9da7fddd930acbc3b74701ee16d93120fb |
| Recette et G076 | Archive publiée testée via HTTP/client JS, documentation actualisée et contraintes de rotation précisées | 791c7fa125a39bc248f337e88324fc30fbadf728 |

Les arbres locaux et publiés ont été comparés à chaque publication. Les SHA de
commits diffèrent car les commits distants ont été créés via le connecteur GitHub,
le terminal ne disposant pas d’identifiants de push. Aucun push forcé utilisé.
Parents Claude conservés lors de leur intégration.

## Validation réellement exécutée par Codex

- Suite Python finale : **733 réussis, six intégrations optionnelles ignorées**
  (739 découverts), puis les **six intégrations mémoire réussies séparément**.
  Source Memory Engine isolée 7d99ded, corpus temporaires uniquement.
- **49 tests client Node réussis**, 12 Chromium ignorés faute d’exécutable.
- Wheel installé en venv jetable : **42 modules identiques**, **24 contrôles bêta**,
  recherche de deux pages, reprise inchangée et un historique nettoyé lié.
- Archive du commit distant C-021 : **64 fichiers vérifiés**. Trois scénarios
  complet/partiel/vide consultés via un vrai serveur HTTP loopback. Requête
  privée et contenu absents des réponses ; pas de route historique ; aucun
  changement SQLite dû à la consultation. Captures acceptées par le validateur
  JavaScript du client livré, sous Node (pas dans un navigateur).
- 18 tests spécifiques C-021 : requête/cible/mission non substituables par le
  modèle, injection mémoire sans effet sur le contrat, rapport altéré/croisé
  refusé, budget, annulation, deux frontières de crash, reprise de vérification,
  journal occupé, absence de sockets/DNS dans le backend de fixtures.

Sources : [C-021 et recette](../codex-research-runtime/README.md),
[C-019](../codex-query-history/README.md),
[C-020](../codex-text-evidence/README.md),
[G050/G052](../codex-g050-g052/README.md).
Les preuves historiques ne sont pas remplacées par les résultats nouveaux.

## Claude : file prête et observations

Au début, C073 signalait G050–G053 terminés et la file vide. G054–G057 ont été
attribués et publiés aussitôt. Claude a ensuite livré G054 (f5e002a), annoncé
G055 comme prochaine tâche dans C074 ; G054 a été relu et intégré.

La file active conserve **G055 → G056 → G057** : frontières réseau Tauri/CSP,
mesures du budget, proposition isolée de rotation du journal. G075 puis G076
signalent les nouvelles liaisons `query_history_sha256` et `operation_id`.
Le retrait d’un rapport COMPLETED doit tenir compte d’une mission encore à
vérifier : l’âge du rapport ne suffit pas.

Les fichiers de coordination ne réveillent pas une session Claude. L’existence
d’une file prête et le dernier commit reçu sont vérifiables ; son activité
continue en temps réel ne l’est pas dans cet environnement. Aucun résultat
G055–G057 n’a été supposé livré.

Suite après épuisement de la file : contre-revues indépendantes C-019/C-021,
puis traitement des constats et choix d’un raccordement réseau réel autorisé.

## Limites et points encore ouverts

Rust/Tauri absent de cet environnement : les cinq tests Rust, 13 probes binaires
et lancement Linux de G054 sont **rapportés par Claude**, pas reproduits ici.
Pas de recette Windows, serveur/PC utilisateur, SSH réel, pare-feu/VPN ou
coupure électrique. Aucun fournisseur Internet, modèle réel ou nouvelle
permission réseau activé ; seules les fixtures de recherche sont exécutables.

Le nettoyage n’est pas une anonymisation. La mission privée conserve sa demande
originale ; seul l’historique spécialisé conserve exclusivement le texte nettoyé.
Capacité de garde toujours limitée à 256 recherches, rotation non livrée.
Une réécriture SQL cohérente et une restauration d’état ne sont pas détectées
comme une preuve cryptographique. Une réussite de recherche synthétique
prouve la récupération demandée, pas la vérité du contenu ni une réponse générale.


## Dernière relève distante

Fetchs réussis à 11 h 51 min 51, 11 h 52 min 45, 11 h 53 min 38 et
**11 h 54 min 34 Europe/Paris** : Claude reste sur
`f5e002a12bfb821fc1d125262cafeff81830bfa1`. Aucun G055–G057 reçu à ces instants.
La branche Core est publiée en 791c7fa avant l’ajout de ce bilan ; son arbre
est identique au checkout validé. La présente clôture ajoute uniquement le
bilan et le lien de reprise ECHANGES, sans changer le code testé.
