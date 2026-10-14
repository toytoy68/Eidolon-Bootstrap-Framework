# Contre-revue du scénario « diagnostic + rappel Memory + DARME lecture seule »

Auteur : Claude. Date : 12/10/2026, Europe/Paris. Demande : G186-bis.
Base : [audit d'intégration](../AUDIT-INTEGRATION-CORE-MEMORY-DARME-2026-10-12.md).

Méthode :
- lecture du code actuel : `dialogue.py`, `conversation.py`,
  `query_cleanup.py`, `research_runtime.py`, `monitor_service.py` ;
- sondes dans `tests/test_integration_scenario_probes.py` ;
- **aucune VM**, aucun réseau, données synthétiques. Le benchmark G182 n'a
  pas été relancé et ses résultats ne sont pas touchés.

## 1. Constat d'ensemble

Aujourd'hui, les trois briques **ne sont pas reliées** :
- le dialogue reçoit la mémoire, mais ne peut proposer **que** le diagnostic
  synthétique en lecture seule ;
- l'état DARME ne va qu'au dashboard (`/v1/monitor/`), jamais au dialogue ;
- la recherche Web n'existe que sur des pages d'essai, hors du dialogue.

Le scénario T1 de l'audit n'est donc **pas exécutable** de bout en bout. Les
garanties ci-dessous valent pour le code actuel, et les écarts pour le
futur raccordement.

## 2. Ce qui tient (sondes vertes)

| Risque de l'audit | Vérifié |
| --- | --- |
| Fuite de la mémoire vers une mission | un texte rappelé ne peut pas devenir une cible de mission : refusé, ce n'est pas une proposition |
| Fuite de la mémoire vers le Web | un modèle qui propose `research.web` ou `web.search` reçoit `OUT_OF_SCOPE`, `TEMPLATE_UNSUPPORTED` ; une seule mission est proposable (`service.observe`) |
| T2 mémoire indisponible | `context.memory = "unavailable"`, aucune source citée (déjà couvert par les tests de G086) |
| T4 permission | une proposition ne s'exécute jamais seule (`authorizes_execution: false`) |
| T6 reprise | un tour rejoué ne rappelle pas le modèle ; la réponse enregistrée est rendue |
| Observations d'outils | seulement fournies par Core, au plus 5, bornées ; données, jamais consignes |

## 3. Écarts pour le raccordement

- **I1 — La fraîcheur n'a pas de champ** (`expectedFailure`).
  - Une observation d'outil n'a que `source`, `reference`, `state` et `text`.
  - Une mesure DARME passée au dialogue ne peut donc pas porter sa date sous
    une forme vérifiable : un `observed_at` est refusé.
  - Proposition : `observed_at` (UTC) et `stale` calculé **par Core** au
    moment de la synthèse, comme le fait déjà `monitor_service`.
  - Une mesure périmée est montrée « inconnue », jamais « actuelle » (T3).
- **I2 — Requête Web écrite par un modèle qui a lu la mémoire.**
  - `clean_query` le dit lui-même : les noms et la prose privée lui
    échappent (sonde : une phrase secrète passe intacte).
  - Proposition pour l'étape 5 de l'audit : la requête vient de
    l'utilisateur ou d'un modèle de requête Core, **jamais** d'un modèle qui
    a reçu MEMORY.
  - La requête exacte est montrée et approuvée avant envoi.
  - Une sonde négative doit vérifier qu'un extrait de la mémoire n'apparaît
    pas dans une requête sortante.
- **I3 — Séparer les colonnes du rapport.**
  - La réponse actuelle ne sépare pas « mesuré », « rappelé », « hypothèse »
    et « recommandation » (étape 6 de l'audit).
  - Proposition : un schéma de rapport avec ces quatre parties ; chaque
    mesure porte sa source et sa date, chaque souvenir son
    `information_id@revision`. Le validateur refuse une mesure sans date.
- **I4 — Incident pendant la collecte.**
  - Le dialogue sait éviter un second appel au modèle ; la future mission de
    diagnostic devra faire de même pour **chaque** outil de lecture (reçu
    par appel).
  - Un outil interrompu donne « inconnu », jamais une valeur précédente
    réutilisée sans le dire.

## 4. Tests à ajouter au moment du raccordement

1. T1 avec des données synthétiques : mesure fraîche, souvenir pertinent,
   rapport en quatre parties, toutes les références présentes.
2. T3 : mesure de 10 min avec une durée de validité de 2 min, affichée
   « inconnue ».
3. I2 : un secret présent dans MEMORY ne se retrouve dans **aucune** requête
   sortante (journal du transport simulé).
4. T5 : Web indisponible ; le rapport dit « pas de recherche faite ».
5. T6 : arrêt brutal entre deux outils, puis reprise : aucun outil rappelé
   deux fois, et l'outil coupé reste « inconnu ».
6. T8 : une correction demandée produit une proposition séparée, jamais
   exécutée.
