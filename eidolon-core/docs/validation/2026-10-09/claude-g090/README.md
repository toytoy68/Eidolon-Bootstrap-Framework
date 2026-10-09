# G090 — Contre-revue des doublons conversation/mission

Auteur : Claude. Date : 09/10/2026, Europe/Paris. Fiche : C-TASK-G090.
Sonde **indépendante** des tests unitaires : [probe_g090.py](probe_g090.py).
Elle utilise du HTTP réel en boucle locale, de vrais processus pour les coupures
et un modèle simulé qui compte ses appels. Elle a été exécutée **sans
modification** sur deux versions :

- **avant** : `a3a97b2` (C110, avant les corrections) →
  [probe_before.json](probe_before.json) : **6/8** ;
- **après** : `8eb462c` (G090-R1, G088-R1 et R2 corrigés) →
  [probe_after.json](probe_after.json) : **8/8**.

| Scénario | Avant | Après |
| --- | --- | --- |
| Double clic, même clé (5 envois simultanés) | 1 mission | 1 mission |
| Double clic, nouvelle clé à chaque clic | 1 mission, 4 × `PROPOSAL_ALREADY_SUBMITTED` | idem |
| Deux clients concurrents | 2 missions (une chacun) ; soumission croisée `CLIENT_MISMATCH` ; lecture croisée 404 | idem |
| Réponse de tour perdue puis renvoi | 1 appel au modèle, même réponse | idem |
| **Même tour envoyé deux fois en même temps** | **2 appels au modèle** | **1 appel** ; la seconde demande reçoit `pending` |
| Redémarrage du serveur | reçu retrouvé, renvoi = même mission | idem |
| Proposition modifiée : ancien accord réutilisé | v2 avec l'empreinte de v1 → `PROPOSAL_CHANGED` ; l'ancienne clé ne rejoue que v1 ; v1 avec une nouvelle clé → `PROPOSAL_STALE` ; 1 mission | idem |
| **Processus tué pendant l'appel au modèle, puis renvoi** | **nouvel appel** au modèle après redémarrage | `pending` jusqu'à l'échéance de la tentative morte, puis `MODEL_ATTEMPT_INTERRUPTED`, **0** nouvel appel |

Les 2 écarts « avant » correspondent à G090-R1 (Codex G115). Leur correction
(commit `8eb462c`) ajoute :

- une admission durable d'une seule tentative par tour (schéma v2, migration
  explicite) ;
- un budget mural ;
- une politique d'arrêt.

Les sondes de Codex échouent maintenant sur leur assertion de défaut :
`probe_g090_concurrent_turn.py`, `probe_g088_shutdown.py` et
`probe_g088_slow_http_shutdown.py`.

## Notes de méthode

- `ConversationServer`, l'hôte de test, sert une requête à la fois. Le
  scénario « même tour simultané » appelle donc `handle()` depuis deux fils,
  comme le serveur de lecture multi-fil (`http_api`). Une première version de
  la sonde passait par HTTP, donc **en série**, et ne prouvait rien ; elle a
  été corrigée.
- Aucune garantie n'a été réécrite pour faire passer un scénario : les attendus
  sont ceux de la fiche G090.

## Limites

- Modèle simulé ; aucun vrai moteur. Un appel au modèle abandonné (délai ou
  arrêt) peut avoir consommé du calcul côté moteur : cet effet reste incertain.
- Concurrence entre processus éprouvée sur un seul hôte, avec un verrou SQLite
  et `flock` locaux.
