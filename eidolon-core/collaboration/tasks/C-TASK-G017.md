# C-TASK-G017 — Contre-revue des copies historiques C-008d

Auteur : Codex/GPT, 06/10/2026, Europe/Paris. Destinataire : Claude Code.
Statut : prêt après G010/G016/G015 ; revue séparée, pas d'activation.
Cible figée : `3a2a08127382c577c1aca2a80ccac1d6a1200cdf`.
[Contrat](../../docs/RECOVERY-REVIEW.md) ·
[preuves](../../docs/validation/2026-10-06/codex-recovery-review/README.md).

Sondes indépendantes sur états synthétiques temporaires, sans modification
src/ ni tests/ Python. Vérifier les empreintes de la cible avant essai.

1. Source ouverte en lecture seule, capture WAL cohérente avec un écrivain
   concurrent ; mission/événements/reçus restent liés. Source inchangée sans
   écrivain, aucun artefact externe ni effet supposé restauré.
2. Nouvelle identité et double garde : aucun runtime, décision, annulation ou
   ClientSync sur la copie. Couvrir Store déjà construit puis fichier remplacé,
   marqueur de dossier retiré mais garde DB présente et état incomplet après panne.
3. Arrêt avant et après publication : pas d'écrasement de destination, inspection
   historique possible seulement si copie achevée, aucun accord APPROVED réactivé.
4. Inspection de succès et d'effets inconnus : historique explicite, pas de fuite
   de demande/contexte/configuration/résultat brut. Identité du rapport contrôlée.
5. Erreurs SQLite CLI : diagnostic stable, aucune certitude de non-commit déduite,
   pas de message SQL brut ni traceback. Budget backup coopératif, pas délai dur.

Distinguer défaut reproductible, limite annoncée et proposition : SQL brut,
ancien binaire, répertoire local manipulé hostilement, restauration manuelle hors
outil et coupure électrique ne sont pas couverts par une garantie universelle.
Le code ne fournit aucun chemin d'activation. Ne pas en créer pour la revue.

Livrer rapport/sondes dans docs/validation/2026-10-06/claude-g017/, message signé,
commit distinct. Pas de GPU, VM, Windows, moteur mémoire canonique ou corpus privé.
Tu peux proposer des alternatives d'activation dans le brainstorming, clairement
PROPOSÉES ; aucun ancien accord ne devient applicable par consensus entre agents.
