# Eidolon — rapport unique G272 et livraison PC/VM

**15–16 octobre 2026 · Codex/GPT · recette prévue les 17–18 octobre.**

Le lot hors VM est développé et publié sur la branche de travail Core. Il complète
G269–G271 avec l’extraction documentaire, l’enrôlement volontaire du profil connecté,
la remise à zéro des sessions et la copie arrêtée des états privés. Le dossier de
transfert est actualisé. **Aucune installation sur ton PC ou tes VM n’a été faite.**
La bêta opérationnelle reste conditionnée à la recette réelle. Les développements
historiques encore ouverts sont explicités en fin de rapport ; ils ne sont pas
assimilés à des tâches terminées.

## Livraison cumulée

| Fonction | Disponible dans les sources livrées | Limite importante |
| --- | --- | --- |
| Dialogue et mémoire | « Retenir ceci », aperçu exact, confirmation et reçu durable ; reprise idempotente du pont Memory | Information UNVERIFIED, aucune vérité déduite de la mémorisation |
| Profils | Clé appairée liée côté Core au profil, racines et droits ; isolation du rappel, des fichiers et reçus | Authentifie une clé ; trois profils réels et compte C187 à activer sur place |
| Index et maintenance | Passages incrémentaux, réemploi des vecteurs inchangés, bascule atomique ; activité Core authentifiée entre VM et report si charge/activité inconnue | Inventaire O(N), un écrivain d’alias ; aucun nettoyage de génération |
| Internet | SearXNG et lecteur HTTPS contrôlé, confirmation précise, quota persistant par profil | Services et réseau réels à qualifier ; aucune répétition automatique d’une tentative incertaine |
| Documents G272 | TXT/MD/CSV, PDF textuel, DOCX/ODT/XLSX/PPTX depuis PC ou racines NAS ; extrait, SHA, limites visibles et reçus paginés | PC 512 Kio, NAS 4 Mio, extrait 16 000 caractères ; aucun OCR ni calcul de formules |
| Documents vers dialogue/Memory | Analyse d’une source choisie ; mémorisation explicite séparée avec provenance | Un extrait n’est pas le fichier complet ; observation de dialogue bornée à 3 600 caractères |
| Enrôlement G272 | Présence/consentement, captures explicites, confirmation, annulation, reprise/refus, retrait et comparaison au profil connecté | Modèles non fournis ; sans calibration résultat non calibré ; aucun login, changement de profil ou droit biométrique |
| Confidentialité des sessions | Arrêt des capteurs, abandon des permissions/résultats tardifs et remise à zéro des brouillons à la fermeture/changement de session | Annulation distante au mieux si réseau coupé ; expiration des sessions vérifiée à l’accès ou au redémarrage |
| État privé G272 | Aperçu puis copie arrêtée vers un nouveau répertoire ; reçus/quotas/gabarits conservés, actions en vol UNKNOWN ; refus de réattribution | Ne sauvegarde pas conversations, appairages, corpus, secrets ou modèles ; aucune restauration aveugle |
| Diagnostic | Configuration seule ou contrôle explicite fichiers/permissions/secrets distincts ; modèles identité et modules optionnels | Ni démarrage ni réseau ; la présence d’un module ne prouve pas sa compatibilité effective |
| Windows | Binaire Tauri G270, résident/icône, réouverture, contrôle SHA et démarrage HKCU explicite | Même binaire testé précédemment, non signé ; WebView2 et matériel à essayer sur le PC |
| Exploitation | Configurations candidates, inventaires, unités séparées, reprise/rollback et **44 contrôles de recette** | Les 44 résultats de machines réelles restent **NOT_RUN**, aucun service activé |

Le module documentaire utilise un processus jetable avec limites de temps/mémoire,
contrôles d’archives et XML ; cela ne constitue pas une isolation noyau complète.
Les binaires importés et captures biométriques ne sont pas persistés par ces parcours.
Les extraits, reçus et gabarits sont des données privées dans l’état local. Le retrait
des gabarits du registre actif ne promet pas l’effacement de sauvegardes ou de pages
physiques. Les modèles biométriques ne sont pas téléchargés ni calibrés dans ce lot.

## Révisions et preuves

- **Core qualifié :** `688d7a5f5189704a7eaacc581e6e9d327e9fa883`, branche `feat/eidolon-core-v0.1`.
- **Memory inchangé :** `76d664013d4e018212682c5aa56305bea0c41db6`, branche `refactor/architecture-v1`, épinglé dans la CI Core.
- Le commit documentaire final figure dans `MANIFEST.json` du paquet source et
  `LIVRAISON.json` du paquet extérieur. Les ajouts finaux sont les guides,
  exemples inactifs, TODO et bilan ; les preuves ci-dessous restent attachées
  au commit de code qualifié, sans attribution rétroactive à un autre SHA.

| Campagne réellement exécutée | Résultat | Référence |
| --- | --- | --- |
| Core complet G272, Python 3.13 | **2 251 réussis, 8 ignorés, 1 328 sous-tests** | [Run 38813812182](https://github.com/toytoy68/Eidolon-Bootstrap-Framework/actions/runs/38813812182) |
| Propriétaires de jetons, vrais changements d’UID | **5 réussis** | Étape root distincte du même run |
| Desktop/Chromium G272 | **215 réussis, aucun ignoré** | [Run 38813812174](https://github.com/toytoy68/Eidolon-Bootstrap-Framework/actions/runs/38813812174) |
| Tests locaux ciblés G272/G271, API et dossier | **69 réussis, 6 sous-tests** ; ensuite 7 tests dossier réussis après passage à 44 cas | Linux local, données temporaires synthétiques |
| Exemples d’identité | Deux configurations validées au schéma ; poids/modèles **NOT_RUN** | Validateur réel `identity_runtime.validate` |
| Memory complet déjà qualifié au SHA conservé | **3 151 réussis, 26 ignorés, 3 xfail, 12 sous-tests** ; worker **52 réussis** | [Run 38779839256](https://github.com/toytoy68/Eidolon-Memory-Engine/actions/runs/38779839256) |
| Qdrant ciblé / serveur jetable 1.15.4 | **550 réussis, 1 xfail** / **19 réussis** | [Ciblé](https://github.com/toytoy68/Eidolon-Memory-Engine/actions/runs/38779839389) · [Serveur](https://github.com/toytoy68/Eidolon-Memory-Engine/actions/runs/38779839262) |
| Windows G270 conservé | **5 tests Rust**, compilation release, parsing/aperçus PowerShell, résident sans Core, inscription/retrait HKCU réussis | [Run 38782802182](https://github.com/toytoy68/Eidolon-Bootstrap-Framework/actions/runs/38782802182) |

Les huit exclusions Core sont deux tests de changement de propriétaire (rejoués
dans l’étape root), un comparatif kaldi-native-fbank, deux essais ONNX synthétiques
sans leurs dépendances et trois essais OpenCV/YuNet/SFace sans les poids. Les
41 tests navigateur ignorés dans le job Python sont couverts par le job Chromium
dédié, sans exclusion. L’unique avertissement Python provient de la construction
volontaire d’une archive ZIP à noms dupliqués pour tester son refus.

Les comptages se recouvrent : ne pas les additionner. Memory et Windows n’ont pas
été réexécutés dans G272 ; leurs fichiers concernés et leurs octets livrés sont
conservés. La CI Windows ne prouve pas le rendu visuel, le fonctionnement physique
du matériel ni une longue session réelle. Les sept exclusions de montage privé
Memory et trois xfail historiques restent des dettes de qualification ; les 19
exclusions serveur de sa suite générale sont couvertes par le job Qdrant dédié.

Les premiers runs G272 ont signalé une ancienne attente qui conservait les
brouillons média après fermeture, désormais remplacée par le test de leur remise
à zéro et de leur absence après réouverture. Quatre autres échecs venaient du
contrôle lexical des commandes de mission qui prenait le libellé « annuler les
prises » pour une commande de mission ; le bouton indique maintenant précisément
« Abandonner les prises et arrêter les capteurs ». Ces contrôles restent actifs.
Les runs corrigés figurent ci-dessus ; les échecs initiaux ne sont pas cachés.

Les nouvelles preuves couvrent extraction native d’un PDF synthétique, ZIP/XML
malformés, changements NAS, pagination de gros reçus, isolation/rejeu/expiration
d’enrôlement, annulation pendant inférence, copie arrêtée, refus interprofils et
permissions accordées après fermeture. L’essai navigateur d’enrôlement injecte un
encodeur synthétique dans le serveur de test : **aucune précision biométrique réelle
n’est démontrée**. L’absence d’un modèle est également testée avec le vrai worker.

## Paquet à transférer

L’archive **`eidolon-weekend-2026-10-17-g272.zip`** contient :

- `eidolon-sources-g272.zip`, construit depuis deux commits Git publiés, avec
  inventaire SHA-256 fichier par fichier ;
- `eidolon-windows-g270.zip`, octets conservés du candidat Windows qualifié ;
- `dossier-weekend/`, les guides, exemples, inventaires, 44 cas et ce rapport ;
- `LIRE-D-ABORD.md`, `LIVRAISON.json` et `SHA256SUMS.txt`.

Commencer par [README.md](README.md), puis [RECETTE.md](RECETTE.md) et
[RACCORDEMENTS-G270.md](RACCORDEMENTS-G270.md). Nouveaux parcours :
[documents](DOCUMENTS-G272.md), [enrôlement](PROFILS-ENROLEMENT-G272.md),
[copie d’état](ETAT-PRIVE-G272.md). Le diagnostic et le rollback restent dans le
même dossier. Les `.service.in` ne sont jamais installées telles quelles.

SHA de l’exécutable Windows conservé :
`3f7439082422469967df57b683cc43ded83510acbd1e65371a2b8f96fefae09b`.
Ses scripts conservent les octets CRLF du runner, comparés au Git après
normalisation des seules fins de ligne. Le paquet n’inclut ni modèle, dépendance
native, secret, corpus, état privé ou image VM. Les historiques volumineux sont
exclus ; certains anciens tests documentaires exigent un checkout Git complet.

`check_results.py` exige 44 preuves datées et les SHA exacts ; même un dossier
complet ne positionne jamais `beta_authorized` à vrai. Les empreintes de livraison
vérifient les octets, pas une signature d’éditeur ni la disponibilité des services.

## Reste à faire, par priorité

| Priorité | Travail | Dépendance |
| --- | --- | --- |
| **P0** | Inventaire, compte C187, sauvegarde complète et restauration sur copie | Accès machines et décision d’exploitation |
| **P0** | Trois profils réels, droits UID/montages, secrets/tunnels, services et corpus de recette | VM100/VM110, PC et configurations privées |
| **P0** | Rejouer chat/mémoire/Web/documents, coupures et refus croisés ; qualifier Windows/capteurs | Recette physique, modèles et services réels |
| **P0** | Mesurer latences, RAM/VRAM, maintenance, endurance, redémarrage et rollback | Observation dans l’environnement cible |
| **P1** | Qualifier poids/calibration et conservation des gabarits | Personnes consentantes, matériel et politique d’usage ; option désactivable pour la bêta initiale |
| **P1 — développement restant** | Identité multipersonne/authentification, synchronisation automatique de bibliothèques, rétention coordonnée | Contrats/politiques à arrêter avant effets automatiques ; ces fonctions ne sont pas livrées par G272 |
| **P1/P2** | Médias/GPU avancés, vidéo longue, galerie et arbitrage commun des ressources | Moteurs retenus, mesures réelles et développements complémentaires |
| **P2** | Mobile, robotique, OS/DARME et extensions de la vision | Chantiers distincts du premier périmètre bêta serveur/PC |

Le [backlog actuel consolidé](../../docs/BACKLOG-BETA-ACTUEL-G272.md) rapproche les
anciennes cases TODO des livraisons. G262/G264/G266 et C191 ne sont plus en attente
d’intégration. **Tout le backlog historique n’est pas terminé.** Les fonctions
explicites de ce lot sont prêtes pour recette ; l’absence de VM n’est pas utilisée
pour déclarer artificiellement finis les autres développements.

## Collaboration et garde de reprise

C191 reste le dernier message Claude observé. Les dix contre-revues G270 restent
publiées ; aucune nouvelle réponse ni session Claude n’est inventée. Le canal et
l’historique sont conservés. Aucun accès aux VM utilisateur, compte créé, service
activé, corpus migré, génération supprimée, fusion main ou relance G182.
Pour toute reprise, conserver les reçus et réconcilier les effets avant restauration :
retirer la configuration n’annule pas un souvenir déjà écrit.
