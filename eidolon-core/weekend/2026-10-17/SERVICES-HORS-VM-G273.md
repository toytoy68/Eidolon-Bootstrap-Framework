# Les cinq compléments hors VM — G273

Eidolon Core Technologies (ECT) • Local AI • Modular • Reliable • Reproducible

Les commandes ci-dessous visent une **candidate Linux de recette**, sous le compte
propriétaire prévu, depuis `eidolon-core/` avec `PYTHONPATH=src`. Les chemins en
majuscules sont à remplacer. Aucun service n’est installé par ce dossier.

## 1. Bibliothèque documentaire synchronisée

Le suivi surveille périodiquement une racine déjà autorisée dans `runtime.json`.
Il conserve des extraits versionnés dans `library.sqlite3`, séparément des reçus
`actions.sqlite3`. Le profil est déduit du client configuré, jamais d’un document.
Pour que l’interface lise cette bibliothèque, utiliser comme `--directory` le
`state_directory` de la configuration runtime, existant, privé et de mode 0700.

```sh
# Un passage explicitement autorisé, sans écriture dans Memory :
PYTHONPATH=src python -B -m eidolon_core.library_sync \
  --config /CONFIG/runtime.json --directory /ETAT/PROFILE-SERVICES \
  --client pc-toytoy --root documents --sync

# Consultation seulement : exige une bibliothèque déjà initialisée.
PYTHONPATH=src python -B -m eidolon_core.library_sync \
  --config /CONFIG/runtime.json --directory /ETAT/PROFILE-SERVICES \
  --client pc-toytoy --root documents

# Suivi périodique explicite, arrêt par SIGTERM/Ctrl+C :
PYTHONPATH=src python -B -m eidolon_core.library_sync \
  --config /CONFIG/runtime.json --directory /ETAT/PROFILE-SERVICES \
  --client pc-toytoy --root documents --sync --watch --interval 300
```

`--sync` extrait et écrit uniquement dans la bibliothèque privée. Sans cette option,
la commande lit la première page existante. L’intervalle doit être entre 60 s et
24 h ; cinq minutes est une proposition. `library-sync.service.in` est un brouillon
à adapter après inventaire et contrôle des permissions. Un seul scan coopératif
peut travailler dans ce dossier à la fois. Plusieurs racines peuvent être suivies
par des processus distincts ; un passage occupé est différé au prochain intervalle.

Chaque passage relit et hache les fichiers dans la limite d’extraction de 4 Mio : ajout/modification produit une
version, contenu inchangé réutilisé, doublons reconnus au sein du même profil et
format. Le cache du passage évite de réextraire les doublons nouveaux. Aucune
mutualisation d’extraits entre profils. Une disparition est marquée après un
passage complet ; **aucune source ni ancienne version n’est supprimée**. Une
modification détectée, un lien, une erreur d’accès, une interruption ou un dépassement
conserve la génération précédente. Reprise : nouveaux inventaire/hachages, pas
une confiance aveugle dans les dates. Aucun transfert de fichiers vers Internet.

Bornes : 1 000 fichiers, 5 000 entrées visitées, profondeur 16, 32 Mio de contenu
par première lecture (deux passes, donc jusqu’à 64 Mio relus), 10 000 versions.
Budget de 30 s vérifié entre opérations ; chaque extraction dispose aussi de sa
propre limite G272. Une opération de fichiers sur un montage défaillant peut rester
bloquée dans le noyau : ce budget n’est pas une garantie de délai dur NFS/SMB.
L’inventaire reste O(N), sans journal natif de changements. Une arborescence trop
grosse doit être répartie en racines plus petites ; rien n’est ignoré pour fabriquer
une synchronisation complète. Deux lectures ne constituent pas un snapshot atomique.

Depuis G275, un document vide, illisible par l’extracteur ou sans texte ne bloque
plus les autres fichiers : `not_extracted` donne les nombres par code et chaque
entrée porte `extraction_error`/`excerpt_available`. Le document est retenté au
passage suivant ; aucun extrait d’erreur n’est enregistré comme version. Au-delà
de 4 Mio, seules les métadonnées sont inventoriées (`sha: null`), avec identité,
taille et dates revérifiées ; aucun hachage du contenu trop grand n’est revendiqué.
Ces fichiers comptent dans les bornes d’inventaire. Les liens, fichiers spéciaux et
changements détectés restent fatals. Une ancienne version ne devient pas l’extrait
courant d’un fichier aujourd’hui inexploitable. Le schéma diagnostique est ajouté
au prochain scan explicite ; une consultation seule ne migre pas l’ancienne base.

Le brouillon systemd ne fixe plus de quota CPU de 10 % avant mesure : `Nice=10`
reste proposé. Fixer ensuite un quota compatible avec le premier passage et son
budget mural ; une racine trop grande reste à partitionner.

Dans la conversation : choisir la racine, **Consulter la bibliothèque synchronisée**,
puis une source. Le bouton prépare son chemin dans le formulaire de lecture
actuelle ; l’aperçu/confirmation existant vérifie les octets présents à cet instant.
L’analyse et la mémorisation demeurent séparées. Les résultats sont paginés et
vidés à la fermeture. Un fichier absent reste indiqué comme tel.

**PC :** ce suivi lit des racines accessibles au processus Linux, y compris un
partage PC monté avec ses droits. Il ne constitue pas un agent Windows natif qui
surveille arbitrairement C:\\ ; la sélection ponctuelle PC par navigateur G272
reste disponible. Un profil peut lire les mêmes octets qu’un autre uniquement si
l’opérateur a explicitement autorisé cette racine aux deux profils.

Recette G19/G20 : version, doublon, reprise, fichier déplacé/absent, NAS indisponible,
lien, quota, deux profils, pagination et fermeture de session. Le cache est
reconstruisible ; conserver une sauvegarde privée si les anciens extraits doivent
survivre à la disparition des sources. `beta_state` ne copie **pas** cette nouvelle
base : arrêter le suivi et la sauvegarder séparément, avec sa configuration liée.

## 2. Conservation : inventaire et aperçu

```sh
PYTHONPATH=src python -B -m eidolon_core.retention_preview \
  --directory /ETAT/PROFILE-SERVICES --older-than-days 90 \
  --protected-root histories=/ETAT/CORE/conversations \
  --protected-root memory=/COPIE/MEMORY \
  --protected-root media=/ETAT/MEDIA \
  --protected-root backups=/SAUVEGARDES
```

**90 jours est un exemple, pas une politique adoptée.** Chaque rôle est facultatif
et ne peut apparaître qu’une fois ; `credentials` est également accepté. Les
racines supplémentaires sont inventoriées par métadonnées sans lire leur contenu,
avec limites de 10 000 entrées/profondeur 16 et refus des liens/fichiers spéciaux.
Leurs octets logiques et alloués sont distingués. Le relevé n’est pas atomique sur
un stockage actif ; arrêter les écrivains pour une preuve de sauvegarde cohérente.

Les reçus d’actions, clés d’idempotence, provenance et gabarits sont protégés.
Les versions documentaires encore pointées par l’inventaire, même absentes des
sources, le sont aussi. Seuls les **extraits d’anciennes versions** au-delà du délai
sont proposés pour revue d’une éventuelle rédaction/occultation. Les lignes et
empreintes nécessaires à la reprise doivent être conservées. Le rapport contient
son empreinte et celle des charges utiles candidates, sans prétendre autoriser une
suppression. Les octets logiques candidats ne sont pas une promesse d’espace disque
libérable. Aucun `--apply`, purge, VACUUM ou effacement de sauvegarde n’existe ici.

Recette G21 : comparer inventaire et tailles, contrôler les protections et vérifier
qu’aucun fichier n’a changé. Fixer ensuite les durées par catégorie et la politique
des sauvegardes avant de développer/activer une suppression coordonnée.

## 3. Sessions et clés des profils

Le bouton de fermeture existant verrouille localement : clé retirée de la session,
brouillons et captures remis à zéro. Changer de personne exige la clé de l’autre
profil ; aucune liste de clés n’est conservée dans le navigateur. Ce verrouillage
local ne révoque pas une copie de la clé qui existerait ailleurs.

**Préparer le retrait de cette clé**, puis **Confirmer le retrait de cette clé**
révoque le client connecté côté Core. Aucun client ne peut révoquer celui d’un
autre profil par ce parcours. Une coupure peut rendre le retrait non confirmé :
la session locale est fermée et l’opérateur doit vérifier. Une révocation bloque
les prochaines authentifications, sans annuler les effets déjà admis ou en cours.

L’administration reste dans la CLI locale, sous le compte autorisé :

```sh
PYTHONPATH=src python -B -m eidolon_core.conversation_api --state /ETAT/CORE clients
PYTHONPATH=src python -B -m eidolon_core.conversation_api --state /ETAT/CORE \
  rotate-key --client-id pc-toytoy --replace-key
```

L’inventaire n’affiche aucun jeton ni son hash. La rotation remplace atomiquement
la clé, réactive un client révoqué et conserve son identifiant/profil/historique ;
ancienne clé immédiatement refusée pour une nouvelle requête. La nouvelle clé est
affichée une fois : la transférer par le canal privé d’appairage, pas dans Git ou
un journal partagé. Cette commande n’ajoute aucun administrateur Web et n’élargit
pas les permissions Memory/NAS d’un profil. Les comptes admin/casual réels restent
à configurer ; la reconnaissance multipersonne n’est pas un mécanisme de connexion.

Recette G22 : deux personnes, fermeture, ancienne réponse tardive, retrait,
ancienne clé refusée, rotation et conservation de la liaison au même profil.

## 4. Mesure et calibration voix/visage

Deux outils complémentaires sont livrés :

```sh
# Évaluer des comparaisons déjà mesurées :
PYTHONPATH=src python -B -m eidolon_core.identity_evaluation \
  --input /DONNEES/comparaisons.json --max-far 0.01

# Mesurer un corpus privé de captures existantes avec les poids épinglés :
PYTHONPATH=src python -B -m eidolon_core.identity_measure \
  --identity-config /CONFIG/identity.json --manifest /DONNEES/captures.json \
  --capture-root /DONNEES/CAPTURES --max-far 0.01
```

Le FAR cible de 1 % est un exemple à arbitrer. Le premier format est illustré par
`identity-evaluation.synthetic.example.json` : données **synthétiques**, aucune
preuve de précision. Le second suit `identity-captures.example.json` : 4 à 100
images ou captures **PCM16 mono 16 kHz sans en-tête WAV**, étiquetées par identifiant,
personne, session et séparation calibration/validation. Consentement explicite
attesté dans le manifeste. Aucun capteur n’est ouvert par cet outil.

Prévoir au moins deux prises de la même personne dans des sessions distinctes et
une autre personne dans **chacun** des deux ensembles. Une session ne doit jamais
apparaître dans les deux ensembles. Les captures binaires identiques sont refusées,
même renommées. Les comparaisons d’une même session sont exclues. Le modèle et le
prétraitement sont épinglés ; le rapport de mesure porte aussi l’empreinte de sa
configuration (dont le détecteur visage). Les chemins ne sortent pas dans le rapport.
Les vecteurs restent en mémoire et ne sont pas exportés ; aucun effacement physique
complet de la RAM native n’est promis.

Le seuil est choisi uniquement sur l’ensemble de calibration pour respecter le
FAR empirique demandé et réduire les faux rejets. À faux rejets égaux, retenir le
seuil le plus haut, puis l’abaisser de 15 % de l’écart au score de calibration
immédiatement inférieur (choix toytoy, côté authentiques). Les décisions de
calibration ne changent pas. Exemple 0,50/0,90 : 0,84 ; ce n’est ni 0,15 absolu ni
une garantie statistique de 15 %. Le rapport porte `genuine_side_margin: 0.15`. L’ensemble de validation fournit
ensuite faux positifs/négatifs, FAR/FRR et intervalles de Wilson à 95 %. Zéro erreur
sur trois essais ne signifie pas zéro risque ; les comparaisons partageant des
captures sont corrélées et ces intervalles ne constituent pas une garantie de
population indépendante. Qualité des étiquettes, diversité, usurpation et détection
du vivant restent à étudier. Seuil candidat, jamais activé ni transformé en droit.
`NO_THRESHOLD` est possible. Aucune précision sur toytoy/Sandrine/Matéo n’est annoncée.

Recette G23 : corpus consentant, sessions distinctes, modèles présents, bruit/lumière,
cas négatifs et refus des répétitions. Revoir les résultats avant toute calibration
configurée dans le runtime d’enrôlement.

## 5. File GPU partagée

`gpu-queue.example.json` configure **un seul pool logique** dans un répertoire
privé 0700. Les MiB sont déclarés par l’opérateur : capacité utilisable, réserve
résidente et coûts supplémentaires dialogue/média. Les nombres de l’exemple sont
illustratifs, pas des mesures V100. Ne pas additionner la VRAM de deux cartes comme
si tout moteur savait les utiliser ensemble. Les poids qui restent chargés doivent
entrer dans la réserve résidente ; ces outils ne les déchargent pas.

```sh
# Initialisation/contrôle du registre privé ; aucun moteur contacté :
PYTHONPATH=src python -B -m eidolon_core.gpu_queue --config /CONFIG/gpu.json status
```

Au lancement Core, ajouter `--gpu-queue-config /CONFIG/gpu.json` à la commande
`http_api` avec `--conversations`. Au lancement explicite du worker média, ajouter
le **même** argument global à `media_worker_cli`. Le wrapper dialogue encadre le
modèle réellement sélectionné, y compris les profils de modèles. Le worker média
réserve avant l’essai moteur ; ses autorisations existantes restent nécessaires.
Les autres clients Ollama/ComfyUI/STT/TTS ne participent pas automatiquement.

Priorité dialogue 100, média 10 ; chaque tranche d’attente de 30 s ajoute un point.
L’ancien média peut donc passer devant de nouveaux dialogues après environ 45 min.
Pas de préemption d’une inférence en cours ; FIFO à priorité égale ; pas de saut
d’une demande prioritaire trop grosse pour la place restante. Attente interactive
bornée à 30 s ou au budget de dialogue s’il est inférieur : elle est retirée avant
appel moteur en cas d’abandon. Le vieillissement concerne surtout les demandes
laissées explicitement dans la file via la CLI, pas un appel déjà retiré après délai.

Une réponse synchrone dialogue rend sa réservation ; une exception conserve un
état `UNKNOWN`. Une réponse HTTP média peut seulement confirmer une mise en file
chez ComfyUI : sa réservation est donc conservée jusqu’à vérification opérateur.
Les exceptions d’admission retirent une attente sans libérer une réservation
ACTIVE/UNKNOWN ; le retrait est retenté trois fois en cas de blocage SQLite.
Si le stockage reste indisponible, le retrait reste non confirmé et exige une revue.
L’arrêt propre Core (SIGTERM/Ctrl+C) retire les attentes créées par cette instance,
sans annuler les attentes héritées ni libérer les moteurs admis. Un processus tué
brutalement ne fait pas expirer les réservations. Une attente orpheline en tête
peut bloquer la file ; les états préexistants sont signalés au démarrage Core.
`status` fournit les comptes complets et les MiB réservés, même si la liste des
identifiants est tronquée à 1 000 ; aucun propriétaire n’est déclaré mort.
L’inspecter puis utiliser `cancel-waiting` sur son identifiant.

```sh
PYTHONPATH=src python -B -m eidolon_core.gpu_queue --config /CONFIG/gpu.json \
  cancel-waiting --key IDENTIFIANT_EN_ATTENTE
PYTHONPATH=src python -B -m eidolon_core.gpu_queue --config /CONFIG/gpu.json \
  release --key IDENTIFIANT --lease EMPREINTE_DE_RESERVATION --engine-idle-reviewed
```

Une réservation active exige son jeton exact. **La réservation média historique
`resource_pool` reste distincte** : vérifier l’arrêt du moteur puis libérer aussi
celle-ci avec sa procédure existante. Ne jamais annoncer une libération GPU réelle
sur la seule base d’un fichier. Le registre garde au maximum 10 000 demandes,
dont 1 000 en attente ; au-delà il refuse, sans nettoyage implicite. Changement des
budgets sur un registre existant refusé : vérifier tous les moteurs puis préparer
un nouveau registre pour une nouvelle politique.

Recette G24/P08 : charge réelle, réserve des modèles, priorité, limites VRAM,
coupure/processus tué, attente orpheline et reprise opérateur. Les tests livrés
exercent de vrais processus/SQLite et des modèles synthétiques, pas les GPU.
