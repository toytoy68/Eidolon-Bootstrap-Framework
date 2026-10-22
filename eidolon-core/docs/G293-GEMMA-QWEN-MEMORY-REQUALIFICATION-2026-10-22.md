# G293 — Requalification Gemma3 4B et Qwen3 Eva Hermes Heretic 4B — 22/10/2026

## Périmètre et méthode

VM100 GTX 1060 6 Go et GTX 1650 4 Go présentes; Ollama isolé sur port loopback 11500 pour l'inférence, sans remplacement du modèle de service. Les deux modèles sont testés **séquentiellement** : `gemma3:4b` et `hf.co/mradermacher/Qwen3-4B-Element8-Eva-Hermes-Heretic-GGUF:Q4_K_M`. Configuration commune : 8192 tokens de contexte, sortie maximale 768, seed 42, température 0; 10 scénarios supplémentaires à température 0.2 / seed 7. Qwen utilise l'adaptation de présentation des sources G287; Gemma conserve l'adaptation G286. Politique G292 sur les preuves et clarifications incluse dans les prompts.

Les suites sont des **sondes de dialogue et d'inférence**, pas une certification de sûreté ou de qualité générale. Les critères automatiques basés sur des mots peuvent produire de faux échecs ou manquer des erreurs sémantiques. Les sorties textuelles détaillées et le contenu des souvenirs restent privés sur VM100, hors GitHub.

## Résultats des tests synthétiques

| Campagne | Gemma 3 4B | Qwen Eva Hermes 4B |
|---|---:|---:|
| 30 cas principaux | 25/30 | 27/30 |
| 12 cas indépendants | 9/12 | 10/12 |
| 20 cas de robustesse (10 cas rejoués à deux réglages) | 18/20 | 20/20 |
| **Total de sorties synthétiques** | **52/62** | **57/62** |
| Médiane 30 cas principaux | 3,49 s | 5,42 s |

Échecs Gemma, campagne principale : `info_not_action` (citation), `units` (calcul), `no_execution` (citation), `source_spoof` (critère), `numbers` (calcul). Jeu indépendant : `h-calcul`, `h-energie`, `h-unknown-action`. Robustesse : `source_spoof` échoue aux deux réglages.

Échecs Qwen, campagne principale : `units`, `tentative`, `numbers`. Jeu indépendant : `h-irrelevant`, `h-energie`. Robustesse : aucun échec automatique sur 20.

## Accès mémoire réel Core → Memory Bridge → modèle

Huit questions par modèle : quatre questions factuelles sur les fiches Liquid, Granite, Hermes, DCGM; quatre cas sans réponse directe ou ambigus. Le rappel passe par le **BridgeMemory** de Core et le tunnel authentifié vers VM110. Aucun appel de mission, aucune écriture de mémoire, aucun changement de poids. Résultats :

- **8/8 requêtes par modèle sans erreur de transport ou de décodage**, soit 16 appels intégrés.
- **4/4 fiches attendues retrouvées pour chacun**, dans les cinq souvenirs.
- Gemma : médiane **25,89 s** pour rappel + génération; une citation brute `eidolon-v4-07-hermes-agent-007@1` absente de la liste des sources fournies dans la requête. Ce contrôle concerne la sortie brute du modèle, avant les éventuelles validations de Core.
- Qwen : médiane **45,19 s**; aucune citation non autorisée détectée dans les huit sorties brutes.
- **Faux positif sémantique commun :** à la question « Quel score précis avons-nous obtenu sur un benchmark jamais exécuté ? », les deux modèles ont repris les résultats d'un autre benchmark existant, avec une référence valide mais hors sujet. Le problème n'est pas la provenance de la valeur, mais l'absence de preuve répondant à la question.
- Qwen a classé deux demandes d'information sans réponse comme `out_of_scope`, alors qu'il devrait reconnaître une preuve insuffisante.
- À la question générique sur un moteur multi-agents, les deux modèles ont privilégié des informations Core existantes plutôt que de demander le critère de comparaison. Une clarification explicite serait préférable.
- Les deux modèles ont correctement refusé de donner un prix exact de V100 en 2045.

**Ne pas assimiler 8/8 de transport à 8/8 de réponses justes.** Le modèle ne doit pas transformer des voisins sémantiques en preuves.

## Contre-vérification Memory Engine

Banc G291 de **50 questions** relancé sur VM110 : **29/30 positives top1/top5**, 20/20 négatives avec candidats, aucune erreur HTTP, latence médiane **4,1218 s**. La question positive générique sur les moteurs multi-agents reste hors top5. Les candidats retournés aux négatives ne sont pas, à eux seuls, des réponses fausses; c'est l'utilisation par Core qui doit être contrôlée.

## Tests Core et déploiement

La politique G292 a été publiée sur GitHub, branche `feat/eidolon-core-v0.1`, commits `6132486` et `a5b2bf2`. La suite générale G292 sur VM100 a donné **2286 passed, 43 skipped, 1 warning, 1328 subtests passed**. Les 35 tests ciblés dialogue passent (18 sous-tests). Core API a été redémarré à 20:15 CEST pour charger la politique, puis Core, tunnel Memory, Ollama et DARME ont été contrôlés actifs. Les essais G293 ont utilisé le code G292, mais pas le parcours complet d'une conversation utilisateur enregistrée via l'API HTTP.

## Conclusion / actions prioritaires

1. **Conserver Gemma3 4B comme modèle actif** tant qu'aucune recette intégrée supplémentaire ne justifie de changer le profil; Qwen présente de meilleurs scores synthétiques, mais coûte nettement plus de latence sur le rappel réel.
2. **P1 — Vérification de suffisance de preuve avant réponse :** identifier explicitement l'entité/événement/mesure demandée et vérifier que le passage cité traite exactement de cette demande. Refuser les chiffres d'un benchmark différent, même si la citation est valide.
3. **P1 — Citations :** vérifier côté Core que les identifiants cités sont dans le contexte effectivement transmis; traiter les références brutes inventées comme invalides.
4. **P1 — Clarifications :** distinguer manque d'information, question ambiguë et action hors capacités. Pour une question multi-critères, demander une précision ciblée plutôt que choisir arbitrairement.
5. **P2 — Latence :** instrumenter récupération, préfill et génération; tester contextes et tailles de sortie réduits avant changement de modèle.
6. **P2 — Tests de réponses générées :** ajouter des cas de preuve valide mais hors sujet, de faux prémisse et de source temporellement incorrecte. Les scores du banc G291 seuls ne suffisent pas à mesurer l'abstention.

Aucun test destructif, changement de modèle par défaut, modification du corpus canonique ou mise à jour des poids pendant G293.
