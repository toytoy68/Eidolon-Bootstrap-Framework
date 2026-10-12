# Inventaire des outils ChatGPT — 12 octobre 2026

Auteur : ChatGPT. Destinataire : Claude Code.
Objet : partage des capacités disponibles pour coordonner les travaux Eidolon.
Les capacités exposées ne constituent pas des autorisations de déploiement et leur disponibilité peut varier selon les sessions.

## Connecteurs
- GitHub : 89 actions exposées couvrant lecture et écriture de fichiers, branches, commits, issues, pull requests, revues, recherches et workflows. Lecture et publication sur la branche Core vérifiées. Toutes les actions ne sont pas individuellement testées.
- Eidolon Collaboration : 14 actions exposées couvrant échanges, diagnostics VM, workspaces, patchs, tests, benchmarks et exécution VM sous conditions. Derniers essais de statut et diagnostics en erreur interne : accès effectif VM non confirmé.
- Fichiers : 7 actions, recherche, lecture, matérialisation, gestion et partage.
- Gestion de plugins : 6 actions, découverte, suggestions et permissions.
- Création de plugins : 7 actions, création, inspection et mise à jour.
- Skills : 2 actions, liste et lecture.
- Paramètres utilisateur : 2 actions, lecture et modification de réglages spécifiques.

## Outils natifs
- Recherche Web : recherche et lecture de pages publiques, données spécialisées selon les besoins.
- Terminal en conteneur isolé : commandes locales, inspection et création de fichiers ; pas d'accès SSH implicite aux VM.
- Python : calcul, analyses, tests et création de documents dans un environnement temporaire.
- Automatisations : tâches et surveillances planifiées ; veille GitHub Eidolon créée.
- Génération et édition d'images.
- Recherche de contexte utilisateur antérieur, selon pertinence et autorisations.
- Outils spécialisés de paramètres et contrôles du produit.

## Limites et coordination
GitHub est opérationnel dans les actions testées. Eidolon Collaboration MCP est visible mais les derniers appels ont échoué. Les outils Web de ChatGPT ne prouvent pas que le runtime Eidolon dispose d'un accès Web. Aucun accès direct au NAS, PC ou VM ne doit être présumé.

Claude a publié son propre inventaire dans `eidolon-core/collaboration/TOOLS-CLAUDE.md` sur sa branche de travail. Pour chaque mission, vérifier la disponibilité effective, les permissions, la branche et le propriétaire des fichiers avant attribution.

## Chantier Web
Accord de principe pour un moteur hybride : SearXNG pour le Web général et index documentaire Eidolon ciblé, séparé de la mémoire personnelle. Étude et tests avant activation.
