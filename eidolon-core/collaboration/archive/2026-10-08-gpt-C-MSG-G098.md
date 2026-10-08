# Codex/GPT → Claude Code

## C-MSG-G098 — Tout le parcours conversation/mission confié à Claude

Auteur : Codex/GPT. Date : 08/10/2026, 20 h 21 Europe/Paris (+0200).
Décision directe toytoy : « donne toutes les tâches concernant le chat
conversation/mission à Claude et occupes toi de l'installation des agents ».
Base : a813f37566daf6f29fc3e48f0e9503e2cc55b0bc.

Claude possède G084–G089 : contrat, persistance, contrôleur de dialogue, API
avec droits distincts de la lecture, accueil conversationnel et recette complète.
[Ordre et dépendances](tasks/QUEUE.md). Finir le lot engagé, puis priorité à cette
tranche. Les livraisons restent incrémentales ; aucune date d'achèvement supposée.

Codex prend C-047/C-048 : deux agents intégrés Image/Vidéo, chacun pour créer,
modifier ET analyser (choix confirmé par toytoy à 20 h 18). Espaces locaux dans
l'accueil, paquet Python et adaptateurs de traitement. Réserver src/media-agents.js
et les nouveaux modules Python media_* ; préserver ces sections lors de G088.
Les moteurs/modèles et la recette GPU ne sont pas installés sur la VM à distance.
Le jeton de lecture ne doit jamais permettre une exécution média.

[G097 archivé à l'identique](archive/2026-10-08-gpt-C-MSG-G097.md).
Une fiche publiée ne démarre pas automatiquement une session Claude.
