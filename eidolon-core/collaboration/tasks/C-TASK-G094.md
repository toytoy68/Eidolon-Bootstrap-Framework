# C-TASK-G094 — Contrat conversation ↔ agents média et artefacts

Auteur : Codex/GPT. Attribution : Claude. Date : 09/10/2026, Europe/Paris.
Statut : PRÊT selon dépendances. Base initiale : 1a2a3a2584ce5ad222713606387f4c764326430e.

Étude de frontière immédiatement disponible, raccordement après G084/G087 et livraison Codex C-049/C-050. Définir la proposition Image/Vidéo avec référence opaque d’artefact, opération, paramètres figés et accord lié à la proposition. Codex possède media_*.py, stockage d’artefacts et transferts moteur ; Claude possède conversation/API de commande. Ne jamais transmettre un chemin navigateur à la CLI ni donner l’exécution au jeton de lecture. Préparer tests contractuels, aucune route upload improvisée en parallèle.

Mise à jour Codex du 09/10 : C-049/C-050/C-051 disponibles avec référence
`media-artifact-ref/1`, transfert source contrôlé, collecte/provenance et export.
[Contrat détaillé](../../docs/MEDIA-AGENTS.md),
[recette installée](../../docs/validation/2026-10-09/codex-hour-0710/README.md).
L'API reste locale à l'opérateur, sans authentification multiutilisateur. La
référence n'accorde aucun droit : associer côté serveur propriétaire, conversation,
proposition figée et accord de mission. Ne pas transformer `OUTPUTS_IMPORTED_UNVERIFIED`
ou `RESULT_UNVERIFIED` en `SUCCEEDED` sans preuve métier indépendante.

G084–G089 restent prioritaires après le lot déjà engagé. Préserver les tâches
antérieures et livrer par commit avec résultats exécutés et limites. Vérifier
la tête actuelle avant travail. Pas de main, déploiement ou modification du
Memory Engine. Une fiche ne démarre aucune session Claude.
