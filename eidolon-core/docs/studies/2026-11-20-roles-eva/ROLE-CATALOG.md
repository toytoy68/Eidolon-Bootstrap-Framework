# Catalogue de rôles — validation locale du 20 novembre 2026

Organisation : Eidolon Core Technologies (ECT).

## Sens des statuts
- **Compatible** : chargement et génération exécutés sur la recette indiquée.
- **Contrat synthétique réussi** : toutes les questions du sous-ensemble indiqué passent ; aucune extrapolation terrain.
- **Candidat** : utilité plausible, décision d'intégration différée.
- **Recette rejetée** : échec observé du chemin testé, sans condamner toutes les variantes du modèle.
Aucun modèle de cette étude n'obtient une autorité autonome de sécurité, de redémarrage système ou de commande moteur.

| Famille / rôle | Affectation et statut | Conditions et limites |
| --- | --- | --- |
| Dialogue personnel français | Eva source 4B : référence de travail ; parent entraîné cycle5 conservé séparément | Quatre conversations relues. Source GGUF, parent NF4 et candidat E5 sont des identités différentes. |
| Alternative chat / synthèse | Gemma4 12B, Qwen3 14B : candidats | Gemma4 échoue au format demandé sur la correction en une phrase ; Qwen14 cite quelques outils inadéquats pour la température. |
| Raisonnement / planification | Qwen3-30B-A3B Thinking 2507 : candidat dédié | 8192 tokens de budget ; 12/12 robot et 12/12 système sur ce corpus ; Darme 10/12. Latence médiane du premier contenu final ~3,27 s, hors boucle de contrôle rapide. |
| Lecture de journaux / aide à Darme | Qwen14, Phi-4 mini, Eva : candidats sous vérification | Aucun ne satisfait tout le contrat Darme. Les règles, permissions, décisions et reçus d'exécution restent déterministes et indépendants. |
| Soutien système actif | Qwen14 / Eva pour explication ; Qwen30 pour analyse approfondie | Vérifier fraîcheur des mesures, preuve de panne et autorisation en code. Aucun outil réel accordé dans ces tests. |
| Robot Wall-E : intention / dialogue embarqué | LFM3 1,7B, LFM2.5 1,2B, Prism 2B : compatibles, candidats exploratoires | Aucun contrat complet sur les petits modèles. N6000, réseau déconnecté, batterie et robot physique non testés. Moteurs et arrêt d'urgence hors LLM. |
| Autres petits assistants | SmolLM3, Falcon3, Qwen2.5 1,5B : compatibles mais non retenus pour une fonction active | Confusions de contexte, de format ou conseils erronés relevés ; corpus trop court pour classement général. |
| Perception visuelle | WeVisOne-VL-2B : prototype local FP32 | Comptage / boîte / OCR / absence sur scène synthétique ; segmentation finie et IoU 1 sur deux géométries et une répétition. FP16 rejeté pour masques NaN. |
| Mémoire / recherche | EmbeddingGemma 2 : prototype du lot précédent, FTS5 témoin | Encodeur distinct d'un LLM conversationnel. Corpus réel, dates et ACL restent à évaluer. |
| Code / STT / TTS / images / vidéo | Catégories séparées du catalogue | Aucune nouvelle qualification de ces chaînes dans cette étude. |

## Ordre d'intégration proposé
1. Faire respecter les contrats et les permissions hors modèle ; interdire l'exécution sur information périmée ou incomplète.
2. Consolider Eva sur les acquis avant toute promotion. Confirmer sur un jeu inédit, hors sélection.
3. Comparer les candidats sur davantage de conversations et de scénarios système avec variations et injections.
4. Mesurer les petits modèles sur le N6000 réel, puis la perception sur images réelles ; garder la supervision et l'arrêt matériel.

Les tests logiciels antérieurs ne comptent pas comme validations de qualité LLM. Les modèles téléchargés mais non exécutés ne sont pas marqués validés.
