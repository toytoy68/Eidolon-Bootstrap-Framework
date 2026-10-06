# Faisabilité du client Windows Eidolon — Tauri 2, PySide6, Electron

Auteur : Claude, 06/10/2026. Fiche [C-TASK-G010](../../collaboration/tasks/C-TASK-G010.md).
Statut : **étude et recommandation réversible**. Aucun framework n'est choisi ;
la décision appartient à toytoy. Aucun essai sous Windows n'a été fait.

Légende : **[doc]** documenté par une source officielle relevée ici ;
**[essai]** exécuté dans cette session (Linux) ; **[hyp]** hypothèse à vérifier ;
**[différé]** exige le poste Windows de recette.

## Sources consultées le 06/10/2026

Les sites de documentation sont bloqués depuis cette session. J'ai donc lu les
**sources officielles de documentation** dans les dépôts, au commit relevé.

| Sujet | Source | Version / commit |
| --- | --- | --- |
| Tauri | dépôt `tauri-apps/tauri`, tag `tauri-v2.12.1` | `30da1fd6e17d` |
| Documentation Tauri v2 | `tauri-apps/tauri-docs`, `src/content/docs/` | `712e12a755d3` |
| Plugins Tauri | `tauri-apps/plugins-workspace` HEAD | `2a9c29e00432` |
| Electron | npm `electron` 44.5.1 (MIT), tag `v44.5.1` | `b4404a4d56d0` |
| Documentation Electron | `electron/electron`, `docs/api`, `docs/tutorial` | `6b48d9813bd7` |
| PySide6 | PyPI 6.11.2 (LGPL-3.0 ou GPL-2.0/3.0) | métadonnées PyPI |
| Qt (zone de notification) | `qt/qtbase` branche 6.11, `qsystemtrayicon.cpp` | `44b6f67476c3` |
| Déploiement PySide6 | `qtproject/pyside-pyside-setup` 6.11, `deployment-pyside6-deploy.rst` | `941f86288e89` |
| Secrets Python | PyPI `keyring` 25.7.0 (MIT) | métadonnées PyPI |

## Contraintes d'Eidolon qui pèsent sur le choix

- **Reprendre le prototype** (HTML/CSS/JS, `desktop/prototype/`) sans le réécrire.
- **Ouvrir une décision depuis une notification**, sans jamais décider dans la
  notification (choix G009 validé par Codex).
- **Zone de notification**, démarrage automatique **choisi**, fermeture de
  fenêtre ≠ arrêt, reconnexion.
- **Secret d'appairage** stocké dans le coffre Windows, jamais en clair.
- **Rendu non fiable séparé des capacités natives** : la page ne doit pas
  pouvoir appeler le système librement.
- Installation **sans administrateur** si possible, désinstallation propre.
- Le runtime Core reste un **serveur POSIX** (`fcntl`) : aucun candidat ne le
  rend portable, et aucun montage du journal SQLite sur le poste n'est prévu.

## Comparaison

| Besoin | Tauri 2 | Electron | PySide6 / Qt |
| --- | --- | --- | --- |
| Reprise du prototype HTML | Oui, WebView2 [doc] ; prototype servi depuis une origine web sans erreur [essai] | Oui, Chromium embarqué [doc] ; même essai [essai] | Non, sauf via QtWebEngine (paquet Addons, 168 Mo) ; sinon réécriture en QML ou widgets [doc] |
| Moteur de rendu | WebView2 du système, préinstallé sous Windows 11, mis à jour par Windows [doc] | Chromium livré avec l'application [doc] | Qt natif ; QtWebEngine en option |
| Zone de notification | `TrayIconBuilder`, menu au clic gauche désactivable [doc] | `Tray` ; GUID lié à la signature, sinon au chemin [doc] | `QSystemTrayIcon`, tous Windows supportés [doc] |
| Notification qui ouvre la décision | Plugin `notification` : **actions réservées au mobile** [doc] ; rappel au clic sur le bureau non documenté **[hyp, bloquant]** | `actions` Windows, `toastXml`, `Notification.handleActivation` [doc] | `showMessage` + signal `messageClicked`, pas de boutons [doc] |
| Démarrage automatique choisi | Plugin `autostart`, `enable()` explicite [doc] | `app.setLoginItemSettings({ openAtLogin })` [doc] | Rien d'intégré ; clé `Run` du registre à écrire soi-même [hyp] |
| Mises à jour | Plugin `updater` ; **signature obligatoire, non désactivable** [doc] | `autoUpdater` : Squirrel.Windows ou MSIX [doc] | Rien d'intégré [doc : absent] |
| Installation sans admin | NSIS par défaut pour l'utilisateur courant, dans `%LOCALAPPDATA%` [doc] | Squirrel.Windows par utilisateur [doc] | Nuitka (`pyside6-deploy`) produit l'exe ; installeur à choisir à part [doc] |
| Signature de code | Pas obligatoire pour lancer ; sans elle, avertissement SmartScreen au téléchargement ; depuis 2024, EV ne donne plus de réputation immédiate [doc] | Signature recommandée ; sur macOS, obligatoire pour les mises à jour [doc] | Idem Windows (outil de signature externe) [hyp] |
| Secrets du système | Stronghold (coffre chiffré propre, pas le coffre Windows) [doc] ; crate `keyring` vers le Gestionnaire d'identifiants **[hyp, bloquant]** | `safeStorage` via DPAPI : protège des autres comptes, **pas des autres applications de la même session** [doc] | `keyring` (Python, MIT) vers le coffre Windows [hyp] |
| Séparation rendu / natif | Permissions et capacités par fenêtre/WebView, CSP, autorité à l'exécution [doc] | `contextIsolation`, `sandbox`, `nodeIntegration` à désactiver [doc] ; plus de surface à fermer soi-même | Pas de rendu web si QML/widgets ; avec QtWebEngine, pont `QWebChannel` à borner [hyp] |
| Licences | MIT / Apache-2.0 [doc] | MIT ; Chromium et dépendances sous leurs licences [doc] | LGPL-3.0 : liaison dynamique et remplacement des bibliothèques Qt à permettre [doc] |
| Taille publiée (pas une mesure d'installation) | Pas de moteur embarqué ; installeur hors ligne WebView2 : ~127 Mo si choisi [doc] | Zip Windows x64 v44.5.1 : **158,0 Mo** (en-tête HTTP lu) [essai] | Roues Windows x64 : Essentials **76,9 Mo** + Addons **168,2 Mo** (PyPI) [essai] |
| Chaîne d'outils | Rust + Node ; à apprendre | Node seul | Python, proche de Core ; Nuitka pour l'exe |

Les tailles ci-dessus sont des fichiers publiés, pas une mesure sur Windows.
Mémoire et taille installée restent **[différé]** : je n'extrapole pas Linux à Windows.

## Ce que je contredis, et ce que je confirme

**Je confirme Tauri comme premier candidat**, comme Codex. C'est le seul qui
reprend le prototype sans embarquer de moteur, avec une installation par
utilisateur par défaut, des mises à jour signées obligatoirement et un modèle
de permissions par fenêtre.

**Mais je refuse d'en faire un choix tant que deux inconnues restent ouvertes**,
parce que les sources lues ne les règlent pas :

1. **Ouvrir la décision au clic sur une notification Windows.** La
   documentation du plugin ne décrit les actions que sur mobile. Si aucun
   rappel de clic n'existe sur le bureau, il faudra un plugin tiers ou du code
   Rust natif. Electron, lui, documente ce parcours sous Windows.
2. **Secret d'appairage dans le coffre Windows.** Tauri documente Stronghold,
   un coffre chiffré propre à l'application, pas le Gestionnaire
   d'identifiants. La voie probable est la crate `keyring`, non vérifiée ici.

Si l'une de ces deux inconnues échoue au premier essai, **Electron devient le
repli**. Il documente les deux, au prix d'un moteur embarqué de 158 Mo et
d'une surface plus large à verrouiller (`contextIsolation`, `sandbox`, pas de
`nodeIntegration`).

**PySide6 n'est pas recommandé pour ce client.** Il garde la proximité avec
Python, mais oblige à réécrire l'interface ou à embarquer QtWebEngine. Il n'a
ni actions de notification, ni mises à jour, ni démarrage automatique
intégrés, et impose les obligations de la LGPL à la distribution. Sa force
(Python) ne règle rien ici : Core reste POSIX et sur le serveur.

## Tableau de décision

| Critère | Poids | Tauri 2 | Electron | PySide6 |
| --- | --- | --- | --- | --- |
| Reprise du prototype | fort | ✔ | ✔ | ✘ (réécriture ou QtWebEngine) |
| Notification → décision | fort | **? bloquant** | ✔ [doc] | ~ (clic seul) |
| Secret dans le coffre Windows | fort | **? bloquant** | ~ (DPAPI, même session) | ~ [hyp] |
| Installation sans admin | moyen | ✔ | ✔ | ~ (installeur à part) |
| Mises à jour signées | moyen | ✔ obligatoire | ✔ | ✘ intégré |
| Surface et poids | moyen | ✔ léger | ✘ lourd | ~ |
| Courbe d'apprentissage | faible | ✘ Rust | ✔ | ✔ |

## Ce qui se valide sans Windows, et ce qui exige le poste de recette

**Sans Windows** (ici, ou sur le serveur) : logique et rendu du prototype
(fait : 58 tests, Chromium) ; prototype servi depuis une origine web (fait :
[essai](../validation/2026-10-06/claude-g010/spike-origin-http.json)) ; lecture
des contrats de chaque outil ; compilation d'un squelette Tauri ou Electron
pour Linux (sans valeur pour Windows).

**Sur le poste de recette uniquement** [différé] : vraie zone de notification ;
clic sur une notification qui ouvre la décision ; démarrage automatique et sa
désactivation ; installation et désinstallation sans administrateur ;
SmartScreen avec et sans signature ; mise à jour signée de bout en bout ;
coffre Windows ; verrouillage de session ; mise à l'échelle 200 %, clavier,
Narrateur ou NVDA ; mémoire et taille installée mesurées.

## Protocole du premier paquet (proposé, non réalisé)

Un essai court qui tranche les deux inconnues avant tout développement :

1. Squelette Tauri 2.12 avec le prototype tel quel (aucune connexion, CSP
   conservée), installeur NSIS par utilisateur, WebView2 en `downloadBootstrapper`.
2. **Inconnue 1** : notification synthétique ; clic → la fenêtre s'ouvre sur
   la mission. Résultat noté : documenté, plugin tiers, ou code natif.
3. **Inconnue 2** : écrire, relire et effacer un secret factice dans le
   Gestionnaire d'identifiants via `keyring` ; vérifier qu'un autre compte
   Windows ne le lit pas.
4. Mesures : taille installée, mémoire au repos et avec la fenêtre ouverte,
   temps de démarrage. Les mêmes mesures avec un squelette Electron
   équivalent, pour comparer sur le même poste.
5. Désinstallation : plus rien dans `%LOCALAPPDATA%`, plus de clé `Run`, plus
   de secret.
6. Sans signature d'abord (avertissement SmartScreen noté), signature ensuite
   seulement si toytoy le décide (coût d'un certificat).

Critère de sortie : les deux inconnues sont levées (Tauri confirmé) ou l'une
échoue (Electron essayé sur les mêmes étapes).

## Points ouverts pour toytoy (aucun n'est décidé ici)

- Accepter un avertissement SmartScreen sur ton propre poste, ou acheter un
  certificat de signature.
- Accepter la chaîne Rust pour Tauri, ou préférer Electron, plus lourd mais en
  Node seul.
- Le poste de recette pour l'essai : ton PC Windows 11 principal, ou une
  machine virtuelle dédiée.

## Limites de cette étude

Documentation lue dans les dépôts, pas sur les sites publiés : une page peut
différer de sa version en ligne. Aucune mesure sous Windows. Le connecteur de
documents du PC (C-003W) n'est pas étudié ici au-delà de la séparation
rendu/natif. Aucun achat, aucun installeur produit ni déployé.
