# Recette comparative mémoire / dialogue — VM100, VM101, VM110

Statut : PROTOCOLE PROPOSÉ, NON EXÉCUTÉ. Ne pas fusionner dans main.

## Objectif

Distinguer trois causes possibles de réponses erronées : sélection des souvenirs
(lexical_v1), interprétation par Qwen3 14B, et injection de contexte dans Core.
Ne pas qualifier la pertinence à partir du seul nombre de sources.

## Conditions de recette

- VM100 : Core v0.1 et ConversationAPI ; deux instances distinctes ou deux démarrages
  successifs avec le même modèle, l'un avec BridgeMemory, l'autre sans mémoire.
- VM101 : Ollama qwen3:14b, options constantes (num_ctx=4096,
  num_predict=512, temperature=0.3).
- VM110 : corpus ChatGPT **isolé** `/home/toytoy/eidolon-corpus-gpt-test`.
- Toujours utiliser de nouvelles conversations et des clés de tour uniques.
  Les comparaisons avec/sans mémoire ne doivent pas partager l'historique.
- Ne jamais publier les passages privés, les jetons, les réponses complètes
  contenant des données personnelles ni les identifiants de conversations.

## Cinq questions à exécuter dans les deux conditions

1. « Quel est le rôle d'Eidolon-Core dans l'architecture ? »
2. « Quelle VM héberge Memory Engine et quelle VM héberge Core ? »
3. « Quel GPU est actuellement affecté aux tests de modèles ? »
4. « Kharos est-il un composant logiciel d'Eidolon-Core ? »
5. « Quelles décisions matérielles ont été confirmées et lesquelles restent projetées ? »

## Relevés obligatoires

Pour chaque essai : modèle et paramètres, présence de mémoire, statut de la
réponse, `context.memory`, `context.memory_items`, `context.partial`,
nombre de références, temps total, et résultat de la vérification manuelle.

La vérification manuelle utilise quatre notes indépendantes (0/1/2) :
- Exactitude factuelle : 0 faux, 1 partiel, 2 correct.
- Séparation des domaines (SF vs technique) : 0 mélange, 1 ambigu, 2 net.
- Incertitude : 0 affirmation sans preuve, 1 réserve partielle, 2 calibrée.
- Traçabilité : 0 références absentes/inventées, 1 partielles, 2 vérifiables.

Une source transmise par Core n'est pas une citation effective de la réponse.
Ne pas confondre `sources=5` avec une réponse correctement étayée.

## Critères de réussite

- Aucun accès réseau ou écriture hors des interfaces autorisées.
- Les références et `needs_review` restent dans le contexte non fiable.
- Une panne mémoire est explicitement signalée ; le dialogue reste disponible.
- Aucune amélioration de classement sémantique n'est affirmée sans évaluation.
- Ne pas promouvoir une mémoire de test vers la mémoire principale.

## Étape suivante

Analyser les cinq couples de réponses, puis inspecter la provenance et les
`selection_reasons` des passages retenus. Décider seulement ensuite si un
filtrage par projet, une recherche hybride ou un reranking est nécessaire.
