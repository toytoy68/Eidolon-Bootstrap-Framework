# Eidolon — État consolidé du dépôt

Mise à jour : 14 octobre 2026 après les CI terminées à 18 h 53 Europe/Paris, lot G229, Codex/GPT.

**Deux branches publiées, trois workflows verts. J2 reste ouvert ; aucune recette VM/PC ni décision de bêta.**

## G230 — Suite du 14 octobre après 19 h 55

Memory publié : `180f3a72064636964e718e2d81e88e198aeac01f`. Consommateur borné du
journal raccordé au worker verrouillé, reprise après accusé perdu/arrêt du processus
sans ré-embedding, transitions conditionnelles SQLite et vérification durable
avant récupération d'INTENT. Planification avec digest/modèle/génération disponible.
[Rapport Memory](https://github.com/toytoy68/Eidolon-Memory-Engine/blob/180f3a72064636964e718e2d81e88e198aeac01f/docs/G230-JOURNAL-RECOVERY-2026-10-14.md).

38 nouveaux tests passent ; une reprise après arrêt réel est vérifiée sur Qdrant
local sur disque. Suite complète locale : 2346 réussis, 12 sous-tests, 6 échecs
AF_UNIX connus, avant l'ajout du dernier test interprocessus. CI publiée à confirmer.

Core : `spawn` remplace le `fork` résiduel dans la sonde du registre ; 44 tests
et 18 sous-tests ciblés réussis avec `-W error`. La CI complète est épinglée
sur la nouvelle révision Memory. Aucun runtime ou service n'est activé.

J2 reste ouvert : inventaire/pagination, couverture intégrale des 19 scénarios,
coordination alias/droits et recette du serveur Qdrant réel. Les résultats G229
ci-dessous restent des preuves historiques sur les anciens SHAs.

## Décision et périmètre

Toytoy a validé à 18 h 18 Europe/Paris cet ordre : cohérence Memory/Qdrant,
intégration Core, qualification, bilan, puis recette VM/PC. Claude annoncé
à nouveau disponible vers **22 h 58** ; cela ne programme ni ne lance une session.
Pas de fusion main, déploiement VM ou modification du corpus réel.

## État par composant

| Composant | État du code | Limite restante |
| --- | --- | --- |
| Core dialogue/missions/SOUL/autorisations | Intégrés dans la branche de développement | Modèle réel et recette intégrée VM/PC |
| Memory canon/journal | Implémentés et testés en isolation | Coordination journal/index et reprise multi-services |
| Worker Qdrant | Verrou obligatoire, lecture canonique par descripteur, preuve digest/modèle/génération dans G229 Memory | Contrat complet de 19 scénarios sur le chemin réel, réconciliation et serveur réel |
| Dashboard Claude jusqu'à C178 | Fusion publiée, historique conservé | Vraie recette Windows |
| Monitoring Memory distant | Module intégré dans la branche publiée | Provisionnement SSH privé et recette VM non faits |
| GPU dashboard | Contrat et rendu sur exemples intégrés | Collecteur réel non raccordé par ce lot |
| Voix/vision | Services existants ; lexique et prononciation Claude intégrés | Micro/caméra physiques et contention GPU |
| Identité | Prototypes, adaptateurs et simulateur intégrés | Aucun droit accordé, aucun capteur ni modèle activé |
| Recherche Web et index documentaire | Prototypes optionnels intégrés, hors runtime par défaut | Politique/budgets durables et recette réseau |
| Image/vidéo | Modules, adaptateurs et parcours de préparation existants | Moteurs/configuration et recette de bout en bout |

## G229 — intégration de Claude

Base Core : `bb3bef6fc933f5482582418e0e3a35087e411bf4`.
Branche Claude intégrée : `2b52d8c31f58c62b8ea4afe0e440196dc9b07eed`.
Les 90 commits propres à Claude sont intégrés par une fusion à deux parents ;
les 31 commits Core postérieurs à leur ancêtre commun restent conservés.
Aucun conflit source. Un conflit documentaire introduit par notre déclaration
G229 dans ECHANGES a été résolu en conservant les deux contributions.
Le bundle JavaScript régénéré est identique au bundle fourni par Claude.

Les derniers I1/W1 Core sont conservés. Deux sondes historiques Claude ont été
actualisées : W1 n'est plus un échec attendu ; I1 vérifie la fraîcheur calculée
et le refus d'une étiquette imposée par l'appelant. Le test d'arrêt HTTP capture
explicitement la déconnexion attendue, joint son thread et ferme la connexion.
Les tests de registre emploient spawn plutôt que fork dans un processus multithread.

## Qualification GitHub Actions sur les commits publiés

| Suite | Révision testée | Résultat |
| --- | --- | --- |
| [Memory complet](https://github.com/toytoy68/Eidolon-Memory-Engine/actions/runs/38600958582) | `d74d772` | 2315 tests et 12 sous-tests réussis, 93,51 s |
| Worker expérimental (même exécution) | `d74d772` | 19 scénarios réussis, 1,47 s ; ne clôture pas le contrat réel |
| [Qdrant ciblé](https://github.com/toytoy68/Eidolon-Memory-Engine/actions/runs/38600958856) | `d74d772` | 60 tests réussis, 1,52 s |
| [Core complet avec intégration Memory](https://github.com/toytoy68/Eidolon-Bootstrap-Framework/actions/runs/38601095316) | `ff0b65e` + Memory `d74d772` | 1763 tests et 1299 sous-tests réussis, 7 ignorés, 8 avertissements, 281,55 s |

Les lots se chevauchent : ne pas additionner leurs comptes. Aucun échec dans ces workflows.
Les six intégrations Memory sont activées et les dépendances de sauvegarde sont présentes.
Les sept tests Core ignorés nécessitent numpy, ONNX ou OpenCV et des modèles d'identité.
Les huit avertissements pytest proviennent du `fork` restant dans
`test_profile_registry_probes.py::RegistryProbes::test_eight_concurrent_imports_publish_exactly_once` ;
ce fichier distinct du registre déjà corrigé devra aussi passer à `spawn`.
Les actions checkout/setup-python émettent en outre des avertissements Node 20/24.
Ces avertissements sont enregistrés, pas supprimés par filtrage.

## Historique des preuves locales

- Memory G229 : 66 tests ciblés réussis, dont trois régressions reproduites avant correction. Rejeu complet final sur le code `556443c` : **2309 réussis, 12 sous-tests, 6 échecs liés aux sockets interdites**, 86,05 s. Ces six scénarios passent désormais dans la CI publiée ; aucun n’a été masqué.
- Core après fusion, première suite locale : **1699 réussis, 51 ignorés, 1 xfail, 21 échecs, 1 avertissement**, 1288 sous-tests, 264,20 s. Vingt échecs sont liés aux sockets AF_UNIX interdites dans l'environnement ; le dernier est un succès inattendu du test W1 encore marqué expectedFailure. Cette suite n'est PAS verte.
- Rejeu après correction des sondes I1/W1 et du test HTTP : **57 réussis, 24 sous-tests, aucun avertissement**, avec `-W error`. Inclut les six intégrations contre le véritable code Memory sur corpus synthétique.
- Autre lot ciblé registre/identité/index documentaire/activation monitoring : **65 réussis, 18 sous-tests**, `-W error`.
- JavaScript connecté : **139 réussis, 26 ignorés**, aucun échec ; les essais Chromium sont ignorés faute de moteur disponible. Ce n'est pas une recette visuelle Windows.
- Les comptes se chevauchent : ne pas les additionner.

La CI Core a lu Memory au commit exact
`d74d772be25fe7d0e266711f58fba44248ba412a` et exécuté les six intégrations
au lieu de les ignorer. Les dépendances age/OpenSSL/FFmpeg restent installées
par la CI ; age est absent localement (45 tests de sauvegarde ignorés).
Les six autres skips locaux sont des moteurs d'identité optionnels absents.

## Publication et recette

Le contrôle automatique avait refusé la première publication faute de confirmation
explicite. Toytoy l'a donnée à **18 h 44 Europe/Paris**. Les deux branches de
développement sont publiées, avec des arbres identiques aux fichiers préparés :

- Memory : `d74d772be25fe7d0e266711f58fba44248ba412a`.
- Core : `ff0b65e0caf700ff99524611495e09106b6f3240`, avec les parents
  `bb3bef6` (Core) et `2b52d8c` (Claude C178).

**J2 reste ouvert**. J3 exige B01–B12 sur VM/PC ; J4 est la décision de bêta.
L'indisponibilité MCP bloque la recette distante, pas l'analyse du dépôt.

## Suite prioritaire

1. Terminer J2 : contrat réel, reprise journal/index, contrôle de dérive à révision égale.
2. Contre-revue indépendante Claude du lot G229 et de l'intégration (fiche dédiée).
3. Restaurer MCP puis exécuter B01–B12 avec sauvegardes et SHAs figés.
4. Entretien CI : retirer le `fork` restant des sondes de registre et mettre à jour les actions Node.

Les anciens rapports sont conservés comme preuves datées, sans réécriture rétroactive.
