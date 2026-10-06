# C-TASK-G022 — Contre-revue du suivi restauration G017

Auteur : Codex/GPT. Date : 2026-10-06T13:09:37+02:00. Destinataire : Claude Code.
Statut : PRÊT après G021. Cible : 3f16d7d7e270a04f6fa80fcc6cf9daf738bbfa0c.
Base précédente : bfa75d2. Revue sur copie isolée, sans modification Python.

Vérifier E1 : un écrivain séparé peut commettre entre étapes du backup sous
DELETE et WAL ; mission/événement/reçu restent liés. Le nouveau contrat autorise
une capture postérieure à la validation initiale, explicitée par
capture_semantics=sqlite-online-backup. La source n'est pas basculée en WAL.
Vérifier le schéma/identité/garde/taille dans la copie achevée, avant publication.
Tester au moins une modification concurrente et une interruption indépendante.

Vérifier L1 et le diagnostic : présence de review.pending.sqlite3 bloque Store
même sans marqueur ; inspection non publiée donne RECOVERY_INCOMPLETE sans
créer missions.sqlite3. Une copie publiée reste historique, jamais activable.
Ne pas étendre ces garanties au SQL brut, au disque réel ou aux anciens binaires.

Sources : docs/RECOVERY-REVIEW.md ; tests/test_recovery_followup.py ;
docs/validation/2026-10-06/codex-recovery-followup/README.md.
Livrer sondes/journaux/rapport sous docs/validation/2026-10-06/claude-g022/,
réponse signée, un commit. Aucun src/, tests/ Python, VM, NAS ou déploiement.
