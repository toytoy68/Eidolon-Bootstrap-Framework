> G275 en qualification : les corrections de l’audit sont décrites dans [CONTRE-VERIFICATION-G275.md](../../docs/CONTRE-VERIFICATION-G275.md). Le bilan G273 ci-dessous est conservé jusqu’au remplacement par le rapport final G275 ; il ne qualifie pas les modifications G275.

# Eidolon — rapport unique G273 et dossier PC/VM

**16 octobre 2026 · Codex/GPT · recette prévue les 17–18 octobre.**

Les cinq chantiers hors VM demandés sont implémentés et publiés sur la branche
`feat/eidolon-core-v0.1`. Ils complètent le socle G269–G272. Aucun service n’a été
installé sur les machines de toytoy, aucun corpus réel migré et aucun modèle
biométrique ou budget GPU réputé mesuré. Le dossier rassemble **50 cas de recette,
tous NOT_RUN sur les machines cibles**.

## Ce qui a été développé dans G273

| Chantier | Réalisation et intégration | Limite conservée |
| --- | --- | --- |
| Bibliothèques | Suivi périodique de racines autorisées, hachage, versions, cache des doublons, reprise et génération conservée si échec ; consultation paginée via API appairée et interface | Extraits privés uniquement, aucune écriture Memory automatique ; racines Linux/NAS ou partage PC monté, pas d’agent Windows natif |
| Conservation | Inventaire des volumes, reçus/gabarits et racines protégées ; aperçu des anciens extraits devenus candidats, avec empreintes | Aucun exécuteur de purge ; durées métier à fixer ; clés de reprise/provenance protégées ; octets logiques différents d’espace disque récupérable |
| Profils/sessions | Fermeture locale avec clé/brouillons/captures retirés, changement par clé explicite ; retrait de sa propre clé en deux étapes ; inventaire et rotation opérateur atomique | La rotation garde le même client et son profil ; aucun administrateur Web ni connexion biométrique ; effets déjà admis non annulés par révocation |
| Calibration | Mesure d’images/PCM existants avec modèles épinglés, étiquettes et consentement ; refus des captures réutilisées et des sessions mélangées ; choix du seuil sur calibration, FAR/FRR sur validation et intervalles indicatifs | Les données synthétiques ne qualifient pas une personne ; seuil candidat jamais activé ; aucun droit biométrique, test du vivant ou résistance à l’usurpation établi |
| GPU partagé | File SQLite durable, budgets déclarés, priorité dialogue/vieillissement ; raccordement au dialogue réellement sélectionné et au lancement explicite du worker média ; refus d’admission tardive après abandon | Coopératif, sans mesure GPU ni préemption ; clients externes/STT/TTS hors file ; exceptions et médias asynchrones gardent une réservation jusqu’à revue |

La synchronisation relit le contenu, pas seulement les dates. Ajout et modification
créent des versions ; disparition signale une absence, sans effacer les sources ou
anciens extraits. Un verrou évite deux scans concurrents dans le même état. Une
seconde passe contrôle les octets, sans prétendre constituer un snapshot atomique.
Le budget limite taille, profondeur, fichiers et versions ; une racine trop grande
est refusée et doit être répartie. Le suivi peut s’arrêter proprement et reprendre.

La conservation distingue les données encore nécessaires à la reprise et les
extraits anciens. Historiques, Memory, médias, sauvegardes et clés peuvent être
inventoriés par métadonnées sans lecture de leur contenu ; ils restent protégés.
Les durées d’exemple ne sont pas adoptées à la place de l’utilisateur.

La file GPU conserve les réservations après perte de réponse ou décès du processus.
Une réponse dialogue synchrone rend sa place ; une réponse média peut seulement
accuser réception d’un travail asynchrone, donc requiert une revue. Les réservations
média historiques restent à libérer séparément. Les modèles résidents doivent être
comptés dans les budgets, et les VRAM de plusieurs GPU ne sont pas additionnées
implicitement. Une attente orpheline peut nécessiter une annulation opérateur.

## Socle précédent conservé

G269–G272 fournissent déjà le chat, la mémorisation avec aperçu/confirmation/reçu,
les profils liés aux clés, les ponts Memory isolés, l’index Qdrant et les passages
incrémentaux, la maintenance conditionnée à l’activité/charge, SearXNG/HTTPS avec
quotas, les fichiers PC/NAS, l’extraction PDF/Office/texte, l’enrôlement volontaire
du profil connecté, le diagnostic et la copie arrêtée des reçus/quotas/gabarits.
Le binaire Windows résident G270 reste conservé à l’identique.

Les imports G272 restent bornés à 512 Kio depuis le navigateur, 4 Mio depuis une
racine autorisée et 16 000 caractères extraits. Aucun OCR ni calcul de formules.
L’analyse et la mémorisation d’un extrait sont séparées ; les observations restent
UNVERIFIED. Les gabarits retirés du registre actif peuvent subsister dans d’anciennes
sauvegardes : aucune promesse d’effacement physique général.

## Révisions et preuves

- **Code G273 qualifié :** `00fe9cbfa59ef31fa6b245c87e05cb843a17829d`.
- **Memory conservé :** `76d664013d4e018212682c5aa56305bea0c41db6`, branche `refactor/architecture-v1`.
- **Windows conservé :** source `fe7261826eb26e6b4f2c92a6f55636330cd3df1f`.
- Le manifeste du paquet indique le commit documentaire final. Le code, tests,
  interface et configurations de recette sont comparés au commit qualifié ; les
  mises à jour finales de bilan ne sont pas assimilées à une autre campagne.

| Campagne | Résultat | Preuve |
| --- | --- | --- |
| Core complet G273, Python 3.13 | **2 274 réussis, 8 ignorés, 1 328 sous-tests** | [Run 38842661447](https://github.com/toytoy68/Eidolon-Bootstrap-Framework/actions/runs/38842661447) |
| Propriétaires de jetons, vrais changements d’UID | **5 réussis** | Étape distincte du run Core |
| Desktop/Chromium G273 | **216 réussis, aucune exclusion** | [Run 38842661515](https://github.com/toytoy68/Eidolon-Bootstrap-Framework/actions/runs/38842661515) |
| Nouveaux scénarios locaux G273 | **23 réussis**, dont véritables commandes CLI | `tests/test_offline_services_g273.py` |
| Dialogue, API et nouveaux services locaux | **66 réussis, 24 sous-tests** | Après correction du chemin d’arrêt ; inclut les tests G273 |
| Dossier et manifeste local | **7 réussis** ; modèle de recette **50 NOT_RUN, 0 PASS** | `test_weekend_bundle_g269.py`, `check_results.py` |
| Memory au SHA conservé | **3 151 réussis, 26 ignorés, 3 xfail, 12 sous-tests** ; worker **52 réussis** | [Run 38779839256](https://github.com/toytoy68/Eidolon-Memory-Engine/actions/runs/38779839256) |
| Qdrant ciblé / serveur jetable 1.15.4 | **550 réussis, 1 xfail** / **19 réussis** | [Ciblé](https://github.com/toytoy68/Eidolon-Memory-Engine/actions/runs/38779839389) · [Serveur](https://github.com/toytoy68/Eidolon-Memory-Engine/actions/runs/38779839262) |
| Windows G270 | **5 tests Rust**, compilation, contrôles PowerShell, résident sans Core et inscription/retrait HKCU réussis | [Run 38782802182](https://github.com/toytoy68/Eidolon-Bootstrap-Framework/actions/runs/38782802182) |

Les nombres se recouvrent : ne pas les additionner. Memory et Windows ne sont pas
réexécutés pour G273 ; leurs révisions/octets sont conservés. La CI ne valide pas
le rendu physique du PC, le matériel ni la précision des modèles d’identité.

La qualification complète a détecté une régression introduite dans le chemin
« appel après arrêt de Core » : le signal d’annulation GPU était référencé dans
deux méthodes où il n’existait pas. Les références ont été retirées ; le signal
reste limité à l’attente qu’il commande. Le test existant est conservé et rejoué.
Le contrôle des exemples a également détecté une limite JSON demandée au-delà du
plafond du lecteur commun ; corrigée à 1 Mio, avec test des véritables entrées CLI.
Les campagnes initiales rouges restent consultables, sans les présenter comme des
réussites. Le contrôle des captures réutilisées et celui des racines API mal typées
ont aussi été ajoutés avant clôture.

Les exclusions attendues Core concernent deux tests de propriétaire rejoués sous
root et six essais de dépendances/modèles biométriques indisponibles. Le ZIP à noms
dupliqués est construit volontairement par un test de refus et produit un avertissement.
Le job Chromium dédié doit rester sans exclusion. Les exclusions de montage privé
et xfail historiques Memory restent explicitement ouvertes.

## Dossier et transfert

Commencer par [README.md](README.md), [RECETTE.md](RECETTE.md), puis
[SERVICES-HORS-VM-G273.md](SERVICES-HORS-VM-G273.md). Les guides G270/G271/G272
restent applicables à leurs fonctions. Le nouveau guide fournit les commandes,
les limites et G19–G24. Les exemples GPU et conservation sont illustratifs ; le
manifeste de captures est inactif (`consented: false`). Aucun poids ni compte réel
n’est inclus. Le service de suivi `.in` reste un brouillon à adapter et valider.

Le paquet `eidolon-weekend-2026-10-17-g273.zip` contient les sources Core/Memory
épinglées, le sous-paquet Windows G270 inchangé, le dossier complet, le manifeste
et les sommes SHA-256. Les sources sont extraites des objets Git publiés ; leur
vérificateur inventorie les octets, pas une autorisation de déployer.

SHA de l’exécutable Windows :
`3f7439082422469967df57b683cc43ded83510acbd1e65371a2b8f96fefae09b`.
Ses scripts conservent les octets CRLF du runner qualifié. Le paquet ne contient
ni dépendances natives, modèles, secrets, corpus, état privé ni image VM. Certains
anciens tests documentaires nécessitent un checkout Git complet, les historiques
volumineux étant exclus de la livraison.

Pour les sauvegardes, ajouter désormais `library.sqlite3` et `gpu-queue.sqlite3`
aux composants à inventorier séparément : `beta_state` ne les copie pas. Ne pas
restaurer une ancienne base de clés sans réconcilier révocations/rotations, ni
remplacer une file GPU par une file vide tant qu’un moteur peut encore travailler.
Le [rollback](ROLLBACK.md) couvre ces précautions de reprise.

## Reste à faire

**P0 :** compte C187 et inventaire réel ; sauvegardes/restauration cohérentes ;
profils privés, permissions, tunnels et services ; corpus et modèles réels ; PC,
WebView2 et capteurs ; mesures de charge/VRAM/latence et endurance. Les 50 preuves
demandent une exécution réelle et une observation datée.

**P1 après recette :** adoption des durées de conservation et des budgets mesurés ;
calibration représentative consentie. Les extensions encore non livrées sont la
purge coordonnée, un agent de surveillance Windows natif autonome, la connexion
biométrique multipersonne, la participation de tous les moteurs au planificateur,
et les médias avancés. Elles ne sont pas maquillées en simples essais VM.

Le [backlog G273](../../docs/BACKLOG-BETA-ACTUEL-G273.md) remplace la vue courante
G272 en conservant son historique. C191 reste le dernier message Claude observé ;
les dix contre-revues G273 publiées ne prouvent pas une réponse nouvelle ou le lancement
de sa session. Aucun accès VM utilisateur, activation, création de compte,
suppression de génération, fusion main ni relance G182 dans ce lot.
