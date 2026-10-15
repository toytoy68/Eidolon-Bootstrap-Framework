# Eidolon — rapport unique G270 et dossier du week-end

**15 octobre 2026 · Codex/GPT · recette des 17–18 octobre.**

Les raccordements logiciels demandés après G269 sont développés et publiés : mémorisation dans le chat, profils liés aux clés appairées, activité et maintenance, passages incrémentaux, Internet, fichiers PC/NAS et client Windows résident. Le dossier est prêt à transférer. **Aucune installation sur ton PC ou tes VM n'a été effectuée ; la bêta réelle reste à qualifier sur ces machines.**

## Ce qui est livré

**Complément G271, 15 octobre au soir :** diagnostic avant lancement disponible
dans les sources G271, [procédure](DIAGNOSTIC-G271.md). Contrôle de configuration
seul ou contrôle explicite des fichiers locaux, sans démarrage ni écriture ;
détecte notamment un secret réutilisé sous des chemins distincts. 14 tests dédiés
et sept tests de paquet/preuves réussis localement. La qualification CI G270
ci-dessous reste attachée à ses révisions ; elle n'est pas attribuée à G271.
Le client Windows reste exactement le candidat G270 déjà livré.

| Parcours | Réalisation | Limite pour la recette |
| --- | --- | --- |
| Retenir ceci | Aperçu et confirmation dans le chat ; profil fixé par Core ; second jeton d'écriture Memory ; reçu durable et reprise sans doublon | Information OBSERVATION/UNVERIFIED ; une réponse perdue reste incertaine jusqu'à vérification ou reprise |
| Profils et mémoire | Clients appairés liés côté serveur ; ponts, ports et secrets distincts ; racines Memory liées explicitement ; rappel et reçus isolés | Authentifie une clé, pas une voix. Les trois profils privés et leurs véritables droits restent à activer sur place |
| Activité et maintenance | Reçu vivant Core ; lecture authentifiée entre VM sans compter le poll comme activité ; demande en cours considérée active | Mesure l'usage d'Eidolon, pas toutes les applications PC. Preuve absente/périmée ou charge inconnue = maintenance différée |
| Passages incrémentaux | Embeddings des seuls documents ajoutés/modifiés, réemploi des autres vecteurs ; génération complète et bascule atomique | Inventaire et copie restent O(N). Interruption entre opérations, aucune suppression de génération, un seul écrivain d'alias |
| Internet | SearXNG local et lecteur HTTPS contrôlé ; recherche/URL exacte confirmée ; quota durable par profil/jour UTC | SearXNG, moteurs et réseau réels à vérifier. Aucun renvoi automatique d'une tentative incertaine |
| Sources dans le dialogue | Bouton pour interroger le modèle sur le résultat choisi ; observation non vérifiée, datée et liée durablement au tour | Extrait borné à 3 600 caractères, troncature signalée ; aucun nouveau téléchargement implicite |
| PC et NAS | Lecture UTF-8 de racines autorisées, 64 000 octets maximum ; contrôle chemins/liens/changements ; sélection d'un texte PC, 16 000 octets maximum | Montages et droits réels à qualifier. Pas d'import Office/PDF binaire ni de synchronisation automatique de bibliothèques |
| Windows résident | Coquille Tauri compilée ; icône native « e », ouverture/fermeture, SHA exigé ; démarrage HKCU avec aperçu et retrait contrôlé | Binaire non signé ; WebView2, tray et matériel à essayer sur le PC. Tunnel géré par le lanceur SSH existant |
| Livraison | Sources épinglées, profils, unités Core/Memory/maintenance, procédures, rollback, inventaires et 36 cas de recette | Résultats sur machines réelles tous NOT_RUN ; aucun modèle, corpus ou secret inclus |

G269 reste acquis : C191 intégré avec son historique, correctifs Memory 0067, modèle/digest d'embeddings épinglés, relecture canonique, citations et contrôles de stockage. Le rappel historique en lecture seule reste distinct du pont explicitement autorisé à écrire.

## Révisions et preuves

- **Core candidat :** `fe7261826eb26e6b4f2c92a6f55636330cd3df1f`, branche `feat/eidolon-core-v0.1`.
- **Python/UI Core :** mêmes fichiers que `2c86b9dabe748206ee0a3050913f01c8a67cf237`. Les deux commits suivants corrigent et qualifient uniquement le script Windows et son workflow.
- **Memory :** `76d664013d4e018212682c5aa56305bea0c41db6`, branche `refactor/architecture-v1`, épinglé par la CI Core.
- Le manifeste indique également le commit documentaire final du paquet ; publication du rapport et qualification du code sont distinguées.

| Campagne | Résultat | Preuve |
| --- | --- | --- |
| Memory complet, Python 3.13 | **3 151 réussis, 26 ignorés, 3 xfail, 12 sous-tests** | [Run 38779839256](https://github.com/toytoy68/Eidolon-Memory-Engine/actions/runs/38779839256) |
| Worker journal sur données isolées | **52 réussis** | Étape dédiée du même run |
| Qdrant ciblé en mémoire | **550 réussis, 1 xfail** | [Run 38779839389](https://github.com/toytoy68/Eidolon-Memory-Engine/actions/runs/38779839389) |
| Qdrant réel jetable 1.15.4, dont reprise des passages après redémarrage | **19 réussis** | [Run 38779839262](https://github.com/toytoy68/Eidolon-Memory-Engine/actions/runs/38779839262) |
| Core complet, Python 3.13 | **2 200 réussis, 8 ignorés, 1 328 sous-tests** | [Run 38781453713](https://github.com/toytoy68/Eidolon-Bootstrap-Framework/actions/runs/38781453713) |
| Propriétaires de jetons, vrais changements d'UID | **5 réussis** | Étape root dédiée du même run |
| Chromium, y compris fichier sélectionné transmis au dialogue | **208 réussis, aucun ignoré** | [Run 38781453744](https://github.com/toytoy68/Eidolon-Bootstrap-Framework/actions/runs/38781453744) |
| Windows natif et scripts | **5 tests Rust, compilation release, parsing/aperçus PowerShell, résident démarré sans Core, inscription/retrait HKCU : réussis** | [Run 38782802182](https://github.com/toytoy68/Eidolon-Bootstrap-Framework/actions/runs/38782802182) |
| Paquet extrait | **42 tests Memory + 24 Core réussis, 6 sous-tests Core** | Code extrait du paquet à SHA fixes ; modifications finales limitées à la documentation |

Les comptages se recouvrent : ne pas les additionner. Les 19 essais de serveur ignorés dans la suite Memory complète sont couverts par le job Qdrant dédié. Sept essais de montage privé et trois xfail historiques restent ouverts. Les huit exclusions Core et l'étape root distincte sont détaillées dans les journaux.

Les nouveaux tests locaux couvrent deux ponts Memory HTTP sur données synthétiques, isolation croisée, perte de réponse après écriture, reprise sans doublon, quota après redémarrage, fichier changé après aperçu, activité d'une demande longue et source transmise au dialogue. Les suites complètes locales rencontrent les restrictions connues : cinq cas Memory multiprocessus et 22 cas Core sockets Unix/changement d'UID. La CI permet ces essais ; aucun test n'a été supprimé pour masquer cette différence.

La première compilation Windows a réussi, mais le contrôle PowerShell a détecté deux apostrophes typographiques interprétées comme délimiteurs. Elles ont été corrigées ; le contrôle de syntaxe précède désormais la compilation. Le résultat corrigé figure dans le tableau. Le test du résident le laisse actif quatre secondes sans tunnel puis termine exclusivement ce processus de test. Cela vérifie son démarrage, pas le rendu visuel ni une session utilisateur prolongée.

## Dossier à utiliser

Commencer par [README.md](README.md), puis [RACCORDEMENTS-G270.md](RACCORDEMENTS-G270.md). Adapter configurations, chemins et comptes après [inventaire](MACHINE-INVENTORY.md). Les unités `.in` ne sont pas installables telles quelles. `check_results.py` refuse les validations manquantes ou sans preuve datée ; même 36 PASS n'autorisent pas automatiquement le déploiement.

Le paquet source est construit exclusivement depuis les objets Git publiés et vérifié fichier par fichier. Le paquet Windows provient du workflow lié dans le tableau ; contrôler son SHA. Exécutable livré : `3f7439082422469967df57b683cc43ded83510acbd1e65371a2b8f96fefae09b`. Les scripts du runner ont des fins de ligne CRLF ; leur contenu a été comparé au Git après normalisation des seules fins de ligne, et leurs octets Windows sont conservés dans le paquet. Les journaux historiques volumineux sont exclus. Certains anciens tests documentaires demandent un checkout Git complet. Dépendances et modèles sont à préparer séparément.

## Ce qui reste, par priorité

| Priorité | À réaliser | Dépendance |
| --- | --- | --- |
| **P0** | Inventaire des VM, sauvegarde et restauration sur copie, choix du compte C187, droits UID/montages | Machines et décisions d'exploitation réelles |
| **P0** | Configurer profils privés, secrets, tunnels et index de recette ; contrôler Ollama/Qdrant/SearXNG/NAS sous le compte cible | Les exemples ne prouvent pas la présence des services ni les droits effectifs |
| **P0** | Rejouer chat/Internet/fichiers, coupures, refus interprofils et maintenance avec le vrai corpus | Modèles, données et ressources réels non utilisés ici |
| **P0** | Windows/WebView2, icône et démarrage résident, micro/casque/caméra, fin effective des captures | Recette physique sur le PC |
| **P0** | Mesurer latence/CPU/mémoire, limite de maintenance de 120 s, endurance, redémarrage et rollback | VM, PC et observation dans la durée |
| **P1/P2 — autres chantiers** | Reconnaissance biométrique/enrôlement, formats bureautiques binaires, synchronisation de bibliothèques, médias/GPU avancés, rétention automatique et extensions DARME/mobile/robot/OS | Développements distincts de G270 ; non déclarés terminés |

Le lot ferme les raccordements G270 demandés, **pas l'ensemble du backlog historique du dépôt**. La recette sur les environnements réels reste nécessaire avant de déclarer la bêta exploitable.

## Collaboration et retour arrière

C191 reste la dernière contribution Claude observée. Dix contre-revues ciblées sont préparées dans `collaboration/G270-CLAUDE-REVIEWS.md` ; leur publication ne lance pas sa session et aucune réponse n'est inventée. Historique et messages précédents sont conservés.

Aucun accès VM utilisateur, création de compte, activation de service, migration du corpus, suppression de génération, fusion main ou relance G182. [ROLLBACK.md](ROLLBACK.md) détaille le retour arrière. Conserver les reçus et l'état privé : retirer une configuration ne doit pas effacer les preuves ni tenter d'annuler automatiquement un souvenir déjà écrit.
