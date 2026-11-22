# V100 — Vérification de l'identité des sorties Flash Attention (2026-11-22)

Statut : contrôle qualité préliminaire exécuté sur Eidolon-OS, **non suffisant pour adoption en production**.

- GPU1 Tesla V100 SXM2 16 Go, 200 W inchangés ; Ollama 0.32.15 isolé, même modèle Qwen2.5 Coder 7B Q4_K_M, num_ctx 8192, num_predict 384, temperature 0, seed 42.
- Trois prompts distincts exécutés une fois avec Flash Attention OFF et une fois ON. Les réponses complètes et SHA256 ont été enregistrés sur l'hôte dans `/srv/eidolon/work/v100-optimization/quality-results.json`.

| Prompt | Identité des textes | Premier caractère divergent | Similarité SequenceMatcher |
| --- | --- | ---: | ---: |
| Analyse CSV | Non | 101 | 0,937 |
| Diagnostic PCIe | Non | 283 | 0,356 |
| Tri fusion | Oui | aucun | 1,000 |

**Conclusion :** 1 réponse sur 3 strictement identique. Une divergence de texte à température zéro ne prouve pas à elle seule une erreur numérique ou une dégradation sémantique : les calculs flottants peuvent changer un choix de token et entraîner des suites différentes. Les deux réponses divergentes doivent être évaluées fonctionnellement.

**Limite importante :** les six générations se sont toutes terminées à la limite de 384 tokens. Plusieurs textes sont tronqués ; **ce jeu ne permet pas de valider l'exactitude ni la complétude**. Prochain contrôle : 1024+ tokens, tests unitaires exécutables pour le code, prompts long contexte, comparaison qualité avec critères objectifs.

Un instantané ECC et pages retirées a été enregistré sur l'hôte à 20:25:39. Aucune erreur Xid récente n'a été relevée dans le journal interrogé. Le test de stabilité 30 minutes et le watchdog thermique 1 Hz ne sont pas encore réalisés.

Après test : Ollama principal actif, GPU0 et GPU1 à 200 W, VRAM au repos. Aucune activation globale de Flash Attention.
