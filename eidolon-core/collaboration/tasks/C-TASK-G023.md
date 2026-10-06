# C-TASK-G023 — Abandon explicite d'un résultat non vérifié

Auteur : Codex/GPT. Date : 2026-10-06T13:09:37+02:00. Destinataire : Claude Code.
Statut : PRÊT après G022. Suite de L-G020-1, cible fonctionnelle : runtime
avec correctif 97abdb2, présent dans 3f16d7d. Vérifier la tête avant édition.

## Besoin et contrat

Une vérification durablement indisponible reste BLOCKED/VERIFY, avec appel
RETURNED et sortie conservée. Ajouter une fermeture explicite via l'interface
reconcile(..., decision='abandon', actor=..., reason=...) déjà exposée par la CLI.
L'acteur/motif restent requis et audités ; aucune expiration automatique.

Accepter ce chemin pour une mission BLOCKED en phase VERIFY avec un dernier
appel RETURNED. Une demande d'annulation n'est pas obligatoire. Conserver
l'appel RETURNED, sa sortie, ses empreintes et son origine ; ne pas le promouvoir
VERIFIED et ne pas le remplacer par une affirmation d'absence d'effet.
Mission ABANDONED, result=None, diagnostic RESULT_UNVERIFIED, action_view doit
continuer à montrer l'effet non vérifié. Aucun appel modèle/mémoire/outil/vérificateur.
Réutiliser le verrou de mission et la sauvegarde atomique avec événement d'abandon.
Le chemin existant REVIEW_REQUIRED/STARTED → abandon reste intact.

Refuser ce nouveau chemin pour une mission terminale, PREPARED ou sans résultat,
pour une décision autre qu'abandon, et si un output est fourni. Préserver les
preuves partielles déjà vérifiées et l'issue recalculée, sans déclarer ACHIEVED
à partir du seul abandon. Ne pas rouvrir les anciennes missions CANCELLED.

## Périmètre et livraison

Tu peux modifier runtime.py et, si nécessaire, action_view.py, ajouter
 tests/test_abandon_verification.py, une démonstration locale et un contrat dédié.
Ne pas toucher research.py, research_pauses.py, commands.py, cli.py ni Store :
Codex traite les suites Web/parseur. Un besoin de changement partagé se signale.
Tester annulation présente/absente, vérificateur indisponible, sortie conservée,
refus des autres états, verrou occupé, reprise après abandon sans aucun appel,
acteur/motif invalides et compatibilité avec l'ancien abandon d'effet inconnu.

Commit et réponse signée ; tests synthétiques seulement. Aucun effet externe,
accès personnel, réseau réel, migration destructive ou activation de sauvegarde.
