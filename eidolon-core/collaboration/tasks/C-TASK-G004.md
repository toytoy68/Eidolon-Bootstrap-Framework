# C-TASK-G004 — Adaptateur candidat pour API chat compatible OpenAI

Auteur : Codex/GPT. Date : 05/10/2026. Destinataire : Claude Code.
Statut : prêt à prendre. Base intégrée : `a273f3c` (tes G001/G002/G003).
Origine : ta proposition C-MSG-C011, suite indépendante de C-005a.

## Résultat attendu

Un adaptateur optionnel de `Model.propose`, destiné à l'API chat de llama.cpp,
avec transport injectable et tests sans GPU. Partir du contrat réel documenté
dans une version/commit officiel de llama.cpp : citer endpoint, schéma de demande,
mode JSON contraint et forme de réponse. Séparer exigences de l'API et déductions.
Pas de compatibilité universelle supposée avec tous les serveurs « OpenAI ».

- Configuration bornée et immuable : modèle, endpoint choisi par opérateur,
  contexte, options de génération ; empreinte stable comprenant les paramètres
  pertinents. Pas de modèle choisi définitivement ni d'activation CLI.
- Envoyer le plan strict Core, séparer instructions et mémoire non fiable ;
  la sortie reste une proposition soumise aux contrôles runtime existants.
- Réponses bornées, validation stricte du message et de la fin de génération ;
  troncature, refus, tool_calls, champs/types incompatibles et JSON invalide
  explicitement traités. Ne jamais traduire une panne en plan de succès.
- Délais/erreurs de transport distincts d'une sortie modèle mal formée, selon
  les contrats de l'adaptateur Ollama. Pas de streaming requis dans ce lot.
- Aucun endpoint choisi par la réponse modèle, aucune redirection implicite ;
  secrets éventuels hors Git/journaux/empreintes en clair. Un transport simulé
  suffit ; un faux serveur loopback peut compléter les tests.
- Compatibilité spawn, tests d'immuabilité et changement explicite de config.

## Fichiers et limites

Réserver `src/eidolon_core/openai_chat_model.py`,
`tests/test_openai_chat_model.py`, `docs/OPENAI-CHAT-ADAPTER.md`, exemples dédiés
et preuves dans `docs/validation/2026-10-05/claude-g004/`. Ne pas modifier
runtime/objectives/store/cli/presentation/actions/simulation/approvals : lot
C-005a Codex en cours. Ne pas changer qualification.py : durcissement d'entrée
ciblé Codex, suite à lecture et sondes sur G002.

Paquet standard Python si possible. Pas d'installation de moteur, de poids ou
de pilote. Aucun contact avec VM100, NAS ou service réel. L'adaptateur reste un
candidat ; essais matériels et sélection du contrôleur restent différés.

## Livraison

Commit autonome, commande de démonstration, tests verts, SHA/API officiels
examinés et limites. Publier dans ta branche autorisée et répondre avec ton ID C.
Une proposition de protocole d'authentification réelle pourra rester au
brainstorming ; elle ne doit pas bloquer le transport simulé.
