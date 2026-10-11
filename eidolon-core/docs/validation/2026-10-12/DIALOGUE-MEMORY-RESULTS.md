# Recette dialogue avec mémoire distante — 12 octobre 2026

Rappel et raccordement :
- Client BridgeMemory depuis Core : cinq résultats en 1,56 seconde.
- Clé dédiée : commande shell refusée (code 1, aucun stdout).
- Mauvais jeton : HTTP 401.
- Coupure du tunnel : MemoryBridgeError ; reprise après redémarrage : cinq résultats.
- Sources installées MCP et unités systemd identiques aux versions publiées.

Conversation réelle sur l'API Core :
Gemma3 4B, CPU, contexte 4096, 256 tokens de génération, délai 300 secondes.
Après 244,10 secondes : mémoire sent, cinq éléments, réponse CLARIFICATION.
La question attendait une réponse factuelle ; ce résultat est un échec de la
recette de réponse, même si l'injection mémoire a fonctionné.
L'essai précédent avait dépassé l'échéance de 110 secondes (MODEL_UNAVAILABLE).
Les clients de recette ont été révoqués.

Sonde directe Ollama avec le même assemblage de prompt :
Qwen3 0.6B, think=false, contexte 4096, 256 tokens.
Après 68,29 secondes : sortie JSON proposal pour un diagnostic synthétique,
au lieu d'une réponse factuelle. Échec du contrôle kind=answer.
La sonde n'a soumis ni exécuté aucune mission. Le modèle reste non activé
dans l'API Core et non qualifié. Elle ne valide pas un parcours ConversationAPI.

Conclusion : transport, provenance et injection fonctionnent, mais la qualité
et la latence des deux candidats CPU ne sont pas acceptables comme preuve
d'un assistant mémoire fiable. Aucun taux de réponses correctes n'est déduit
du rappel à cinq résultats. Il reste à qualifier un moteur/modèle adapté.
Les résultats complets privés sont conservés sur Core, pas dans Git.
