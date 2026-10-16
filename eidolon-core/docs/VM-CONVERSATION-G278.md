# G278 — première conversation Windows, 16 octobre 2026

Signalements toytoy : « bonjour » affiché hors capacités avec un texte de salutation ; question de présentation affichée « Envoi incertain — NETWORK ». Base Core 2b8a172e8211bef2173e416919f061e0863090e8.

## Défauts reproduits

- Le transport navigateur interrompait toutes les requêtes à 10 secondes, alors que le modèle configuré dispose de 90 secondes. Ce message ne prouve pas une rupture SSH. L’API et l’authentification sont restées actives.
- Après un rejeu réussi, l’erreur NETWORK précédente restait attachée au message : « Reçu — NETWORK » était contradictoire.
- La salutation a produit une proposition non supportée, que Core a refusée. Sur le modèle réel avec mémoire : salutation `proposal`, question de présentation interrompue après 512 tokens (`INCOMPLETE`). Les mêmes questions sans mémoire donnent `answer`.
- Contexte configuré à 4096 : environ 14 Ko de requête, compteur d’entrée 2051 tokens pour les deux questions. Avec 8192 : entrées 4403 et 4292 tokens, deux réponses `answer` avec proposition nulle. L’entrée précédente était tronquée ; le prompt plus clair seul ne corrigeait pas le défaut.
- Le template exposé `{{ .Prompt }}` a été investigué, mais un témoin système répond correctement `SYSTEM_OK` : son aspect inhabituel ne suffit pas à expliquer la panne.

## Corrections

- Conversation/action distinguées explicitement dans le prompt. Aucun élargissement du catalogue ni réparation des sorties invalides.
- Attente du seul POST `/v1/conversations/turn` portée à 150 secondes ; autres lectures/contrôles à 10 secondes. Pas de renvoi automatique.
- Erreur précédente effacée lors du rejeu explicite, en conservant la même clé de requête.
- Budget opérateur retenu après essai : contexte 32768, requête bornée à 24000 octets (contre 64000), sortie toujours 512 tokens. Le fit existant retire d’abord l’historique ancien, puis les observations, puis la mémoire en signalant leur omission ; il ne coupe pas le message utilisateur. La limite d’octets est conservatrice, pas une mesure exacte du tokenizer.

## Preuves

55 tests Python et 58 sous-tests réussis sur Core ; 47 tests JavaScript ciblés réussis, zéro ignoré. Contrôle du bundle app.js à jour. Essais réels sur les deux phrases et témoin d’action shell interdite ; résultats finaux consignés ci-dessous. Ces essais ne clôturent pas la réserve de qualité mémoire V07 ni la recette complète Windows.

Les anciens tours restent enregistrés avec leurs résultats d’origine : le rejeu conserve leur résultat. Une nouvelle tentative de dialogue doit être un **nouveau message** après rechargement de l’application ; pas une réécriture de l’historique serveur.

Essai réel final 32768/24000 : bonjour ANSWER en 10,98 s, présentation ANSWER en 8,08 s, demande de suppression shell OUT_OF_SCOPE en 6,94 s ; toutes avec proposition nulle. Entrées 4403/4292/4292 tokens, sorties complètes (stop). Aucun outil exécuté. Configuration précédente sauvegardée avant activation.
