# G306 — E3 interrompu par le harnais à204/306 mises à jour

Auteur : Codex/GPT.11/11/2026,Europe/Paris.
Base examinée :04f1a5a15578afd591e94a08287f24cdcdb600b1,feat/eidolon-core-v0.1.
En réponse à G305 et demande toytoy « maj ? », puis question sur un harnais plus efficace.
Lot pris et clos : audit d'interruption, vérification des sauvegardes, rapport durable et publication de preuves. Aucun nouvel entraînement ni changement de source du service.

## Cause confirmée

Le service s'est arrêté le11/11/2026 à11h40min56s Europe/Paris.
Le rank0 exécutait la sélection séquentielle sur192questions ; le rank1 avait déjà appelé broadcast_object_list et attendait son résultat.
À204mises à jour, cette évaluation a dépassé1800s. Le superviseur a levé Rank progress stale1 waiting_peer, et NCCL a simultanément consigné un timeout BROADCAST de1800000ms. Le rank0 avait encore progressé jusqu'à168/192, quelques secondes avant l'arrêt.

C'est une erreur de conception de mon adaptation DDP du harnais. L'attente d'un pair au travail a été traitée comme une absence de progrès. Ni augmenter la puissance ni changer Ollama n'aurait corrigé cette cause. Le calcul utilise PyTorch/Transformers/PEFT/NCCL, pas Ollama.

Preuves : run__status.json, run__progress-rank0.json, run__progress-rank1.json, train-controller.log, nccl-timeout-excerpt.txt ; sources exactes préparées en G305.

## Résultats réellement disponibles

Deux passages sont entraînés et sauvegardés,204/306updates. Le troisième n'a pas commencé.
La sélection du premier passage102 est complète :

| Mesure | Parent | Step102 |
|---|---:|---:|
| Horaires ciblés |39/160|41/160|
| Acquis |26/32|25/32|
| Total |65/192|66/192|

Deux gains horaires, zéro perte horaire, p exact apparié exploratoire0,5 ; candidat102 non retenu.
Le début time_steps reste0/164 réponses horaires avant comme après102, sans troncature dans cette sélection.
Les192questions de sélection sont réutilisées des essais précédents ; pas de confirmation aveugle.

**Aucun score complet204, aucun rapport APRÈS et aucun canari après204 n'existent.**
Les168réponses intermédiaires de sélection204 étaient en mémoire et le code ne les persistait qu'après le bloc entier : elles ne sont pas récupérables. Ne pas les inventer à partir du checkpoint.
Le rapport neuf du parent vaut86/320horaires et26/32acquis. Ses questions sont différentes des rapports E1/E2(79/320au départ), donc ne pas comparer directement ces totaux.
Les352réponses neuves avant,384réponses de sélection(192parent+192step102),8canaris avant et grades sont publiés intégralement, avec UUIDGPU/LAN expurgés.
Les canaris avant ont été relus : préférenceverte,32processeurslogiques et absence de motdepasse correctement restitués ; la réponse mémoirepartagée/dédiée est simplifiée. Aucun test de non-régression conversationnelle après204 n'est disponible.

## Temps, énergie et matériel

204updates :262,812s de calcul en parallèle, environ4min23s.
Chargement/évaluations/calcul :7174,362s, environ1h59min34s.
D'après les états télémétriques du rank0 :2441,38s pour les deux rapports parent et4421,60s de sélection. Environ95,7% du temps a été passé à évaluer. Ces durées sont issues de l'échantillonnage des états ; les journaux complets restent sur serveur.

| Mesure | Rank0 V100 | Rank1 V100 |
|---|---:|---:|
| Limite configurée |200W|200W|
| Puissance moyenne, essai entier |85,62W|71,95W|
| Pic échantillonné |222,79W|214,44W|
| GPU maximal |38°C|40°C|
| HBM maximal |42°C|42°C|
| Énergie GPU intégrée |170,96Wh|143,75Wh|

CPU Tdie maximal43,125°C. Secteur : moyenne291,17W, pic542,5W, compteur Shelly+581,25Wh pendant la fenêtre.
Les pics NVML brefs sont des mesures instantanées ; les limites configurées sont bien200W. Les gardes n'ont pas déclenché.
Aucun nouveau défaut noyau, Xid ou changement des quatre compteurs ECC parGPU dans la télémétrie vérifiée. Aucun processus de calculGPU après arrêt.
Cela ne certifie pas toute la RAM128GiB : le préflight porte sur4GiBmlock et copies ciblées du boot courant.

## Conservation vérifiée

Douze checkpoints complets :20/40/60/80/100/102/120/140/160/180/200/204.
Les fichiers de ces checkpoints ont deux SHA256 identiques lors de la clôture.
81fichiers du bilan ont ensuite été contrôlés contre failure-audit-saved-G306.json.
Le parent respecte son SHA attendu c600d531e36d65b30c36b84bc65f6a44c0175550581b8ea5a1f1c224a27d5b30.
Checkpoint204 :344968tokens nonpadding,120218tokens supervisés ; couverture2passages complète.
Le smoke avait validé des réplicas identiques, et les normes de gradient des204pas concordent. Aucun hash des deux réplicas204 après entraînement n'a été écrit avant l'arrêt : ne pas affirmer cette preuve absente.

Aucun poids, donnée ou journal présent n'a été supprimé. Les fichiers publics sont des copies expurgées avec index SHA original/public ; les poids et training-state.pt restent sur serveur.
Le rapport exact a été sauvegardé pour toytoy ; son SHA256 est6ff12404f339ab93d99c8ea6ac95484e73dcee203ad28594a883331b7265fc8c.
Limites G305 conservées : rechecks live-integrity racine écrasés entrechargements ; copie train et préflight initial préservés. Le compte6392 inclut320paires nouvelles et6072antérieures exclues.

## Correction proposée, pas exécutée

1. Séparer le calcul DDP de l'évaluation : évaluateurs indépendants, un parV100, ou répartition explicite qui évite une attente NCCL longue durant une génération.
2. Persister chaque réponse et sa configuration immédiatement ; reprendre l'évaluation du checkpoint204 sans rejouer les204updates.
3. Mesurer des petits lots fixes de questions sur une qualification courte, en contrôlant réponses et bruit numérique avant de modifier les comparatifs.
4. Surveiller le progrès réel de chaque évaluateur, avec budget borné mesuré et gardes matérielles conservées.

lm-evaluation-harness d'EleutherAI est un candidat à évaluer pour la couche de tâches : sa documentation décrit backendTransformers,PEFT,évaluationmultiGPU et batchs. Ce n'est pas un remplacement direct déjà validé de notre protocole Eva ; aucune dépendance installée, aucun nouveau test lancé.
Source primaire consultée11/11/2026 :https://github.com/EleutherAI/lm-evaluation-harness/blob/main/README.md.

Aucune promotion, aucune relance automatique, aucune lecture du test final réservé, aucun arrêt/redémarrage/réveil pendant cette clôture. Surveillance périodique déjà désactivée, état conservé.
