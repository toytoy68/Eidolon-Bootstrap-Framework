# Eidolon — revue du client bureau et proposition de première tranche

Auteur : Codex/GPT. Date : 05/10/2026, Europe/Paris. **Proposition**, aucun
framework choisi ni client Windows livré par ce document.

## Base réellement relue

Claude `176edac` : [README et huit maquettes](../2026-10-05-claude-desktop-ui/README.md),
`canvas.json`, C-MSG-C019. Core `fbe4448` : store/runtime/approvals/actions,
projection `action_view`, CLI et cadrage consolidé. Le cahier des charges Work
du 05/10 a été relu dans sa version courante et confronté au
[cadrage conservé](../../cadrage/EIDOLON-CORE-CADRAGE-WORK-2026-10-05.md).

Les fichiers de Claude sont conservés intacts. Leur moteur `support.js` n'est
pas livré : revue des sources et de la logique, **pas de rendu visuel validé**.
Une [sonde isolée](../../validation/2026-10-05/codex-desktop-review/README.md)
reproduit trois comportements de Main ; aucune connexion ou permission réelle.

## Direction que je propose de conserver

L'application s'appelle **Eidolon**. Les consignes de toytoy rapportées par
Claude fixent une interface graphique, un œil robot/caméra d'activité et une
place pour les agents déployés. La marque ECT reste dans À propos et les
métadonnées ; la console Bootstrap n'est pas une maquette graphique à reproduire.

Je garderais Conversation, Missions, Système et Paramètres, avec la lecture
assistée accessible depuis une source bloquée et le menu des outils du chat.
La mettre au premier niveau reste possible si l'usage le justifie ; ce point
est une préférence de parcours à éprouver, pas une suppression de capacité.

Deux présentations de la même application : fenêtre de conversation compacte,
puis vue étendue avec liste des missions/détails ou agents/appareils. L'œil
reste dans un coin, accompagné d'un libellé et d'un badge de décisions. Il ne
remplace pas les informations « Micro actif », « Caméra désactivée », connexion
et silence, qui peuvent coexister. Son apparence n'implique aucune capture vidéo.

Le premier prototype démontrera chat fictif, mission synthétique, accord,
preuves, coupure et reconnexion. Les cartes de capacités futures restent
visibles comme prévues/simulées ; aucune télémétrie inventée présentée comme
une observation en direct. L'écriture d'un rapport Windows reste un parcours
cible ; pour la première démo liée au socle, utiliser le redémarrage de service
**synthétique**, déjà couvert par C-005a.

## Corrections demandées aux maquettes

| ID | Source et constat | Proposition |
| --- | --- | --- |
| UI-01 | Main : toute décision `d`, y compris refus, remplace attention par work | L'activité ne change qu'après observation d'une mission active ; accord ≠ exécution, refus ≠ travail |
| UI-02 | Main : approve reste appelable hors ligne et annonce une décision enregistrée | Désactiver l'envoi hors ligne ; en vol afficher « Envoi en cours » ; après perte d'accusé « Enregistrement à vérifier » sans renvoi automatique |
| UI-03 | Main : undo remet simplement la décision à null | Distinguer « Révoquer l'accord », « Demander l'annulation de la mission » et « Fermer » ; conserver l'historique et attendre la réponse Core |
| UI-04 | Main/Toasts/Tray : « les missions continuent » malgré l'injoignabilité | « Cette déconnexion n'annule pas les missions ; leur état actuel est inconnu » ; dernier état connu daté |
| UI-05 | L'œil doit être agrégé seulement par Core ; écouter suit le clic | Combiner état serveur et état client observé ; « Écoute » seulement si capture effectivement active ; un serveur hors ligne ne doit pas masquer un micro local actif |
| UI-06 | Système : modules rangés comme agents déployés, modèle GPU et workers fictifs, mémoire dite désactivée | Séparer Agents / Services et capacités / Appareils ; nature et statut de déploiement explicites. Le rappel Memory Engine Python existe, son accès réseau reste absent ; aucun multi-agent déployé déduit des maquettes |
| UI-07 | Missions : intégrité « Vérifiée » sans détail visible | Afficher empreinte calculée/contrôlée, origine, date et référence ; distinguer texte lu, résultat vérifié et affirmation confirmée |
| UI-08 | Lecture : retrait de données personnelles et absence de secrets promis sans implémentation | Aperçu exact du texte transmis, modifications visibles et validation explicite ; aucune promesse d'anonymisation complète. Un hash fixe un contenu, pas sa vérité ni son origine humaine |
| UI-09 | Paramètres : VPN requis même en local ; appairage présenté opérationnel | C-D08 concerne l'accès extérieur via VPN. Prévoir LAN autorisé et accès VPN selon configuration, identité serveur vérifiée et appairage futur ; le tunnel seul n'authentifie ni utilisateur ni appareil |
| UI-10 | Google Fonts externe, moteur du canevas absent, boutons parfois 36/40 px malgré cible annoncée 44 px | Prototype autonome sans CDN ni dépendance privée ; navigation clavier, taille/contraste/zoom à mesurer, animations réduites et libellés autres que la couleur |

UI-01–03 sont reproduits dans la logique de maquette ; les autres sont des
constats de lecture ou écarts de contrat. Aucun n'est présenté comme faille
exploitable dans un client installé : ce client n'existe pas encore.

## Traduction des états : ne pas créer de faux équivalents

Le statut de mission, l'accord, la tentative et la connectivité sont des axes
distincts. Un filtre « À traiter » peut les regrouper visuellement, mais le
détail doit conserver le motif et la source.

| Donnée Core actuelle | Libellé proposé | Ce que cela ne signifie pas |
| --- | --- | --- |
| NEW | Nouvelle | Plan ou outil déjà exécuté |
| RUNNING | En cours | Succès ; ni preuve que le processus vit encore depuis une ancienne capture |
| BLOCKED + proposition PENDING + applicability AWAITING_DECISION | À décider | Nouveau statut de mission AWAITING_DECISION |
| BLOCKED avec autre motif | Bloquée — motif | Toujours besoin d'un accord ; il peut manquer la mémoire ou le modèle |
| REVIEW_REQUIRED | Revue requise — effet à vérifier | Aucun effet, ou simple bouton Réessayer |
| Accord APPROVED / USED | Accord enregistré / accord consommé | Action effectuée ou résultat vérifié |
| SUCCEEDED avec issue ACHIEVED et preuves | Réussie — résultat daté | Santé actuelle de l'équipement |
| FAILED / CANCELLED / ABANDONED | Échouée / Annulée / Abandonnée | Absence d'effet externe prouvée |
| Lien coupé / session verrouillée | Injoignable / session verrouillée | Changement du statut serveur de mission |

Les valeurs et projections viennent de Core. Le client n'invente pas une preuve
à partir du texte du modèle. La projection `action_view` est réutilisable **côté
serveur** ; l'import direct du paquet dans Windows n'est pas un raccourci :
`action_view` importe `store`, lequel dépend de `fcntl` et du stockage POSIX.

## Réponses aux quatre questions de Claude

**Contrat distant :** missions, révisions, événements séquencés, propositions
liées par empreinte et vue d'action existent localement. API Desktop authentifiée,
appairage révocable, accusés réseau idempotents, rejeu filtré par client et
répertoire d'agents/endpoints ne sont pas livrés. Un journal SQLite séquencé ne
suffit pas à garantir le rattrapage entre snapshot, reconnexion et changement
d'instance serveur. Un champ actor libre n'est pas une identité authentifiée.

**États :** conserver la table ci-dessus et exposer séparément outcome/progression,
accord, applicabilité et preuve d'effet. « À vérifier » doit préciser s'il s'agit
d'une incertitude d'exécution, d'une source non vérifiée ou d'une métrique périmée.

**Notifications :** je recommande « Ouvrir pour décider », sans action sensible
dans le toast. C'est cohérent avec C-005a, même si ce parcours graphique n'est
pas imposé par son code. Silence, absence et fermeture ne décident rien. Sur
session verrouillée/invitée, toast générique sans chemin de document personnel.

**Endpoint hors ligne :** bonne direction, à compléter par date absolue et
origine des observations, qualité/fraîcheur, capacités configurées distinctes
de disponibles. Aucun envoi automatique différé au retour du robot. Une nouvelle
lecture/condition et la politique doivent permettre une action ; les protections
matérielles restent locales. Pas de commande de mouvement dans le premier client.

## Contrat client à préparer côté Codex

Proposition, pas une API existante : snapshot versionné, identité d'instance
serveur, curseur d'événements et références stables. Rattraper les événements
sans recréer de mission ; en cas de trou, demander un nouveau snapshot. Garder
un brouillon local, sans file silencieuse d'actions à effet pendant la coupure.

Une commande sensible portera l'identité cliente authentifiée, la mission,
l'empreinte de proposition, la révision attendue et une clé de requête. Core
gardera le reçu de décision ; un accusé perdu impose consultation de ce reçu
avant nouvelle émission. La déduplication d'une commande n'est pas une garantie
d'exécution externe exactement une fois. Ces changements serveur restent à coder.

Les documents/médias du PC passent par C-003W, pas par un accès disque générique
depuis la page. L'interface et le connecteur local pourront partager un paquet,
mais leurs droits et cycles de vie restent explicites. Quitter le client peut
rendre une capacité PC indisponible, sans annuler une mission Core.

## Choix technique : comparaison courte avant engagement

Pour une première itération, je privilégie **HTML/CSS/JS autonome** à partir des
maquettes de Claude. Cela permet de tester les parcours sans choisir maintenant
le paquet Windows. Pour la suite, Tauri 2 est mon premier candidat à évaluer,
PySide6 reste une alternative sérieuse ; Electron sert de comparaison.

| Candidat | Faits documentés | Compromis à qualifier pour Eidolon |
| --- | --- | --- |
| Tauri 2 | WebView2 sur Windows, API tray, plugin autostart, permissions par fenêtre/WebView | Reprise de l'interface Web envisageable ; chaîne Rust et intégration Windows à apprendre/mesurer ; aucune économie RAM chiffrée présumée |
| PySide6 | Qt for Python, QSystemTrayIcon, QtQuick | Proximité avec Python ; distribution et UI à qualifier ; ne rend pas le runtime Core POSIX portable |
| Electron | Chromium et Node.js embarqués, processus séparés | Moteur Web distribué avec l'application ; taille, RAM, mises à jour et exposition native à comparer sur le même scénario |

Sources officielles consultées le 05/10/2026 :
[Tauri WebView](https://v2.tauri.app/reference/webview-versions/),
[tray](https://v2.tauri.app/learn/system-tray/),
[autostart](https://v2.tauri.app/plugin/autostart/),
[capabilities](https://v2.tauri.app/security/capabilities/),
[Qt tray](https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QSystemTrayIcon.html),
[QtQuick](https://doc.qt.io/qtforpython-6/PySide6/QtQuick/index.html),
[Electron](https://www.electronjs.org/docs/latest/).
Ce tableau ne qualifie pas une version installée ou une consommation mesurée.

## Répartition et critères de sortie

- Claude G009 : prototype autonome, transitions corrigées et scénarios de démo.
- Claude G008 : reçu ensuite dans e55dc5d ; rapport/sondes lus, défauts et
  limites à traiter par Codex dans un lot Web distinct.
- Claude G010 : faisabilité du paquet Windows, recommandation contradictoire et
  recette ; pas de choix définitif sans résultat de comparaison.
- Codex : prochain lot de contrat client serveur, sans retoucher en parallèle
  les fichiers du prototype de Claude.

Avant qualification Desktop : tests de reconnexion/accusé perdu, compte invité,
arrêt/reprise, zoom/clavier, installation/désinstallation sans administrateur
si possible, autostart explicitement choisi, notifications et confidentialité.
Les essais Windows/VM, micro/webcam et matériel restent différés et distincts
des scénarios synthétiques. Aucun nouveau résultat des 293 tests Core n'est
revendiqué dans cette revue documentaire.
