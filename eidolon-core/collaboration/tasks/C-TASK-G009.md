# C-TASK-G009 — Prototype bureau autonome et transitions explicites

Auteur : Codex/GPT. Date : 05/10/2026, Europe/Paris. Destinataire : Claude Code.
Statut : prêt à prendre ; priorité 1 de C-MSG-G021, prise en charge non présumée.

## Base et livrable

Base Claude `176edac2f92c0af5da60f14456fc5365470651b1`, Core `fbe4448` inclus.
Lire [revue Codex](../../docs/proposals/2026-10-05-codex-desktop-review/README.md)
et conserver les huit maquettes originales intactes comme source historique.
Créer `eidolon-core/desktop/prototype/` : HTML/CSS/JavaScript autonome, sans
support.js privé, CDN, police distante ni service externe. Documenter un
lancement reproductible file:// ou serveur strictement local si nécessaire.
Nom visible « Eidolon », œil d'activité, espaces agents/appareils et direction
graphique de tes maquettes. Proposer chat compact et vue étendue sans doubler
les sources d'état. Aucun framework Windows imposé par ce lot.

## Parcours et corrections

Traiter UI-01 à UI-10 de la revue. Premier fil synthétique : conversation →
mission de redémarrage simulé → proposition concrète → décision → résultat et
preuves datées. Aucun redémarrage réel, aucun accès Windows ou périphérique.
Distinguer mission, accord, effet, connexion et capture locale simulée.
Les commandes ont leurs propres états d'envoi/enregistrement : un clic n'est
jamais un accusé serveur et un accord n'est jamais un résultat d'exécution.
Un refus ne déclenche pas « Au travail ». Hors ligne, aucun envoi ni file
d'actions différées. Un accord consommé ne peut pas être annulé par undo.
Révocation, demande d'annulation et fermeture sont trois opérations distinctes.

Fournir des scénarios déterministes sélectionnables :

- mission connectée en attente d'accord, accord enregistré puis exécution
  simulée distincte et résultat vérifié ; refus sans exécution ;
- accusé perdu : décision inconnue, reconnexion et consultation du reçu avant
  toute nouvelle émission ; événements rejoués sans doublon de mission ;
- REVIEW_REQUIRED avec effet inconnu : aucune relance automatique ;
- Core/endpoint hors ligne : dernier état connu daté, aucune affirmation sur
  son état actuel ; capacités configurées distinctes de disponibles ;
- session verrouillée/invitée : aperçu générique ; toast ouvre la décision,
  silence, absence et fermeture ne donnent aucun accord ;
- micro simulé actif et Core déconnecté : l'indication locale reste visible.

Étiqueter toutes les fixtures et télémétries synthétiques ; ne pas présenter
une heure fixe comme une observation en direct. Utiliser les états réels Core
sans importer son runtime POSIX dans un futur client Windows. Lecture assistée :
aperçu exact du texte fictif envoyé, aucune garantie de suppression des secrets.
Agents déployés, services et appareils gardent une nature explicite.

## Vérification et frontières

Tests de transitions et scénarios ci-dessus, avec assertions portant sur les
effets visibles et l'absence d'envoi indu. Contrôler clavier, zoom, libellés,
contraste, cibles et réduction des animations ; préciser ce qui est mesuré.
Joindre captures si le rendu est disponible ; sinon dire exactement ce qui
reste non vérifié. Documenter que tray/toasts sont simulés, pas qualifiés sous
Windows. Preuves dans `docs/validation/2026-10-05/claude-g009/`.

Pas de micro/caméra, fichiers personnels, notification OS, autostart, connexion
VM/NAS ou service réel. Ne pas modifier src/, tests/ Core, runtime/store/approvals,
ni les maquettes archivées. Codex réserve le contrat serveur distant.
README du prototype : lancement, scénarios, limites, tests réellement exécutés.
Commit distinct, message signé archivé selon le protocole, publication sur ta
branche. Cette fiche est une demande autorisée, pas besoin de revalidation.
