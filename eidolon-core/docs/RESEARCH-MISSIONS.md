# Missions de recherche synthétique — C-021

07/10/2026, Codex/GPT. Le profil `research-sim` raccorde le coordinateur de
recherche à la boucle de mission réelle : rappel, plan, autorisation, worker,
journal, vérification et résultat. Tous les fournisseurs, pages et DNS sont
**des fixtures locales fixes** ; aucune socket ni requête Internet n’est créée.

## Parcours local

Depuis `eidolon-core/`, Linux/Python 3.11+ :

```sh
PYTHONPATH=src python -m eidolon_core --state /tmp/eidolon-research-demo --profile research-sim research 'notice jean@example.invalid' --required-pages 2
PYTHONPATH=src python -m eidolon_core --state /tmp/eidolon-research-demo --profile research-sim --format human research 'notice synthétique' --required-pages 2
PYTHONPATH=src python -m eidolon_core --state /tmp/eidolon-research-demo --profile research-sim run m-ID
PYTHONPATH=src python -m eidolon_core.query_history --directory /tmp/eidolon-research-demo/research-fixture/guard
```

`--create-only` crée une mission sans lancer le rappel, le modèle ni la recherche.
Remplacer `m-ID` par l’identifiant obtenu. `run` sur une réussite ne rejoue rien.
L’API/client de consultation peuvent lire l’état de ces missions avec leur
protocole existant ; aucune commande distante n’est ajoutée.

Quatre scénarios fixes, choisis **hors modèle** avant la création :

| Option globale | Avec deux pages requises |
| --- | --- |
| `--research-scenario readable` (défaut) | Deux textes distincts, mission `SUCCEEDED` / objectif `ACHIEVED` |
| `--research-scenario partial` | Une page, mission `BLOCKED` / objectif `PARTIAL` |
| `--research-scenario empty` | Aucun résultat, mission `BLOCKED` / objectif `NOT_ACHIEVED` |
| `--research-scenario blocked` | Fournisseur fictif refusé, pause durable, mission bloquée |

Utiliser un dossier d’état distinct par scénario pour les essais. Le choix du
scénario, l’identité de garde et les empreintes de fixtures sont figés dans la
configuration. Modifier ce choix pour une mission existante bloque sa reprise.
Une requête devenue vide après nettoyage n’appelle pas le fournisseur fictif.

## Critères indépendants du plan

L’utilisateur/CLI fixe la requête et une cible de **une ou deux pages**. Le
contrat `research_retrieval.synthetic` fixe un seul outil et ses paramètres.
Un plan ne peut ni remplacer la requête, ni réduire la cible, ni utiliser
l’identité d’une autre mission. Les champs de contexte provenant de la mémoire
ne remplacent jamais ce contrat : `_core_research` est renseigné par le runtime.
Une mémoire vide n’empêche pas ce type explicite de récupération.

Le profil purement local par défaut (`text`) n’accorde pas cette capacité.
`ResearchFixturePolicy` n’autorise que `research.retrieve.synthetic` avec
l’effet `local_synthetic_state`. Cela ne crée aucune permission `web.read`,
aucun catalogue de destinations et aucun accès réseau général.

Le nettoyage, la garde et les pauses du coordinateur sont réellement utilisés.
La garde C-019 conserve la requête nettoyée avant l’appel et lie son descripteur
à `operation_id=m-ID`. Le vérificateur relit le rapport lié à cette tentative,
son empreinte, la requête nettoyée et les textes des fixtures. Il refuse un
rapport modifié ou réutilisé pour une autre mission ; il ne fait aucun appel
fournisseur et peut terminer après une demande d’annulation, selon le contrat
existant du runtime.

## Résultats et reprise

Une exécution normale réserve quatre invocations : mémoire, planificateur,
outil de recherche, vérificateur. Avec une limite de trois, aucun outil ne
démarre : il faut préserver une place pour la vérification. Les appels internes
au coordinateur restent bornés par ses propres limites ; ils ne deviennent pas
chacun une invocation du budget de mission.

Un résultat partiel/vide peut être **vérifié comme observation**, sans satisfaire
la cible. Les preuves restent dans `calls[0].output`, la mission est bloquée et
`result` reste nul. Reprendre ne relance pas ces pages déjà observées ; une
nouvelle recherche nécessite une nouvelle mission. La suppression de preuves
ou l’abaissement du critère ne sont pas des commandes de reprise.

Après une coupure entre réception et enregistrement de l’outil, les mécanismes
habituels de reçu/réconciliation s’appliquent. Après `RESULT_SAVED`, seule la
vérification est reprise. Si le journal est temporairement occupé ou absent,
la vérification reste indisponible et le résultat `RETURNED` est conservé ;
une reprise consomme une nouvelle invocation de vérification, sans recherche.
Une intention de recherche incertaine conserve son
blocage global ; revoir la mission ne résout pas automatiquement la garde.

## Périmètre des données et limites

L’historique spécialisé C-019 et les rapports de recherche ne contiennent que
la requête nettoyée/son empreinte. **La mission reste un document local privé** :
elle contient la demande d’origine, le plan et le contexte mémoire, comme les
autres types de mission. Elle ne doit pas être publiée comme un rapport nettoyé.
Le CLI humain affiche la demande ; l’API de consultation conserve sa projection
minimale existante. Le nettoyage n’est pas une anonymisation.

La réussite prouve la récupération des pages synthétiques demandées, pas une
réponse générale, la vérité des sources ou leur indépendance éditoriale. Aucun
modèle réel, accès Web/NAS, fournisseur configurable ou opération utilisateur
externe n’est activé. Le futur raccordement réel reste conditionné par les
permissions egress, le périmètre de destination et une recette distincte.

La garde reste limitée à 256 recherches, et la rotation G057 n’est pas livrée.
Les anciennes versions sans ce type d’objectif ne doivent pas reprendre ces
missions. POSIX uniquement ; Windows, VM et coupures électriques non validés.
