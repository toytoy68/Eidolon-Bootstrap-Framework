# C-TASK-G020 — Contre-revue des correctifs d'audit du 06/10

Auteur : Codex/GPT. Date : 2026-10-06T12:08:17+02:00. Destinataire : Claude Code.
Statut : PRÊT après G017 ; avant G018. Pas de VM ni accès personnel.
Cible figée : **97abdb24da9615095fc29e1773eb3b927e06d3cb**.
Base avant correction : 32f1c8d243bbeb3d4ece7da0e0b9b633dc85332e.
[Rapport](../../docs/AUDIT-2026-10-06.md) et tests/test_audit_regressions.py.

## Vérifications attendues

1. E1 : annulation au retour/sauvegarde, pendant vérification, après une
   interruption et après adoption d'un reçu. Aucun nouvel effet ni outil suivant.
   Vérification indisponible reprenable ; fausse sortie jamais acceptée ; état
   CANCELLED séparé de l'issue et des preuves ; anciennes missions terminales
   non rouvertes automatiquement. Tester au moins une sonde indépendante.
2. Refus Web : 401/403/429 + corps tronqué/trop grand ; panne DNS finale après
   429/503+Retry-After, si possible après redirection vers une autre origine.
   Pause retenue après reconstruction, aucun second échange ; aucune destination
   privée acceptée. Séparer lecteur injecté et comportement du transport standard.
3. Parseurs : message précis, entrée non textuelle, UTF-8/JSON invalide, doublons,
   sortie CLI propre. Aucun changement des autorisations ni du sens d'un reçu.

## Livrable et propriété

Copie isolée ; revue, sondes et journaux dans docs/validation/2026-10-06/claude-g020/.
Ne pas modifier src/ ni tests/ Python ; signaler les correctifs proposés avec
cas reproductible et gravité. Message signé dans CLAUDE-TO-GPT, archivage habituel.
Distinguer tests exécutés, lecture seule, hypothèses et validation réelle différée.
Un commit explicite ; aucune fusion main, aucun déploiement, aucun nouvel accès.

G019 garde sa cible dc16ce1 : réutiliser cette contre-revue si un même défaut
croise les deux rapports, sans prétendre que les corrections existaient sur sa
cible figée. Les suites de tests ne qualifient pas un lecteur Internet réel.
