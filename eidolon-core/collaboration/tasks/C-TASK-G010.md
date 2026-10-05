# C-TASK-G010 — Faisabilité du client Windows Eidolon

Auteur : Codex/GPT. Date : 05/10/2026, Europe/Paris. Destinataire : Claude Code.
Statut : prêt à prendre ; après G009 ; G008 reçu dans e55dc5d.
Base de cadrage : Claude `176edac2f92c0af5da60f14456fc5365470651b1` et C-MSG-G021.

## Question et livrable

Comparer Tauri 2, PySide6/QtQuick et Electron pour emballer le futur client
Eidolon. Codex propose Tauri comme premier candidat, pas comme décision.
Contredis cette préférence si les sources et contraintes le justifient.
Livrer `docs/desktop/WINDOWS-CLIENT-FEASIBILITY.md` ; preuves éventuelles dans
`docs/validation/2026-10-05/claude-g010/`. Sources officielles, versions/commits,
date de consultation, distinction documenté / essayé / hypothèse / différé.

Comparer sur le même besoin :

- reprise du prototype, tray, notifications, autostart choisi, fermeture de
  fenêtre versus arrêt explicite, reconnexion et mises à jour ;
- installation sans administrateur si possible, signature, distribution et
  désinstallation, dépendances Windows et licences à identifier ;
- stockage des secrets OS, vérification du serveur, appairage révocable,
  séparation du rendu non fiable et des capacités natives, IPC bornée ;
- cycle de vie du connecteur local documents/médias et droits de session,
  distinction interface fermée / connecteur indisponible / mission serveur ;
- effort de maintenance, recette Windows, taille/mémoire à mesurer plutôt
  qu'estimer. Ne pas extrapoler une mesure Linux à Windows.

Le runtime Core reste serveur POSIX (store dépend de fcntl) : Python dans le
client ne suffit pas à le rendre portable. Aucun montage du journal SQLite
Core sur le poste. Préparer un tableau de décision avec inconnues bloquantes,
une recommandation réversible et le protocole d'essai du premier paquet.
Un petit spike isolé est possible s'il résout une inconnue précise ; pas de
nouvelle application complète en parallèle de G009, ni d'installateur déployé.

## Sortie attendue

Expliquer ce qui peut être validé sans Windows et ce qui exige le poste de
recette : tray réel, autostart, signature, mises à jour, zoom/clavier/lecteur
d'écran, verrouillage et secrets. Ne pas annoncer ces essais réalisés.
Aucun contact VM/NAS/Windows, aucun achat ni choix définitif de framework.
Un commit distinct et une réponse contradictoire dans ton canal. Les éléments
sans décision restent ouverts ; ni silence ni accord entre agents ne vaut
arbitrage de toytoy sur une extension de périmètre.
