# Passages dans Qdrant, abstention et fraîcheur d'index (G218-4, G218-5)

Auteur : Claude. Date : 13/10/2026, Europe/Paris.
Statut : **proposition**. Aucun code actif, aucune écriture Qdrant, aucun
réglage sur le corpus final figé. Base Memory : `64c6ed1`.

Sondes jointes :
[patch Memory 0031](../../collaboration/memory-patches/0031-claude-g218-passage-integration-probes.patch).

## 1. Constat sur le code actuel

| Élément | Aujourd'hui (`qdrant_index.py`, `passages.py`) | Conséquence pour les passages |
| --- | --- | --- |
| Point Qdrant | un point par information, `uuid5("information:" + id)` | une mise à jour **écrase** le point : pas de point périmé |
| Descripteur | `embedding_id`, dimensions, empreinte du manifeste | **pas d'identité du découpeur** (taille, recouvrement, version) |
| Découpage | fenêtres fixes de caractères (1 200, recouvrement 160) | **une insertion au début change tous les passages** (sonde 0031) |
| Identité de passage | hachage de (document, révision, réglage, bornes, texte) | une nouvelle révision ne réutilise **aucune** identité, même pour un texte inchangé |
| Vérification | `verify_passage` avec document et révision de confiance obligatoires | un passage périmé est refusé à la lecture (sonde 0031) |

## 2. Intégration proposée, par étapes

1. **Génération distincte.**
   - Les passages vont dans une **nouvelle collection**, derrière un alias
     séparé (par exemple `eidolon_<scope>_passages`), jamais mélangée à
     l'index par information.
   - La bascule de l'alias se fait seulement après une reconstruction
     complète et un comptage vérifié, comme `rebuild()`.
2. **Descripteur étendu.**
   - Ajouter `chunker` (par exemple `"passage-v1:1200:160"`) à côté
     d'`embedding_id`.
   - Toute différence donne `INDEX_INCOMPATIBLE`, et la seule réponse est
     une reconstruction (scénario déjà couvert par la recette du worker).
3. **Points.**
   - Identifiant de point : `uuid5("passage:" + passage_id)`.
   - Charge minimale : `document_id`, `revision`, `start`, `end`,
     `text_sha256`, `size`, `overlap`, `passage_id`.
   - **Pas de texte en clair** dans Qdrant : le texte cité est relu dans le
     Markdown.
4. **Points périmés.**
   - Une nouvelle révision crée de nouveaux points, et les anciens restent.
     La règle « pas de suppression automatique » s'applique.
   - Deux défenses :
     - **à la lecture**, chaque résultat est vérifié par
       `verify_passage(..., document_id, revision)`, avec la révision
       **relue dans le canon**. Un passage périmé est écarté et compté ;
     - **au retrait**, les anciens points disparaissent avec leur génération
       à la reconstruction suivante, via `retirement_plan`, après revue.
   - Signal : si plus de X % des résultats d'une requête sont écartés comme
     périmés, la réponse porte `INDEX_STALE`.
5. **Coût.**
   - Une modification ré-encode **tout le document** (sonde 0031). Le
     worker doit donc budgéter par document.
   - Un découpage par paragraphes, plus stable, serait une version
     `passage-v2` séparée, à décider plus tard.
6. **Droits.**
   - Le filtre de profil s'applique **avant** l'envoi au modèle, à partir
     du canon relu.
   - Le filtre de charge Qdrant n'est qu'une optimisation, jamais une
     autorisation.

## 3. Calibration de l'abstention

**Principe** : on règle sur un jeu de **développement**, et on mesure
**une seule fois** sur le jeu de test figé. Aucun ajustement après cette
mesure.

| Jeu | Rôle | État |
| --- | --- | --- |
| `dev-calibration-v1.json` (patch 0008) | réglage du seuil : 8 directes, 8 paraphrases, 8 hors sujet | figé par SHA, disjoint du test |
| corpus de test Memory v1 | mesure finale uniquement | figé, **jamais** utilisé pour régler |
| dev v2 (à créer) | élargir à au moins 60 questions, dont des questions « proches mais absentes » | à figer avant tout réglage |

**Méthode :**

- **Un seuil par `embedding_id` et par `chunker`.** Les scores bruts ne se
  comparent pas d'un modèle à l'autre (décision G201). Le seuil est stocké
  dans le descripteur de génération.
- **Critère de choix** : le seuil le plus bas qui garde **au plus 5 %** de
  réponses sur les questions hors sujet du jeu de développement. On note
  ensuite la couverture obtenue sur les questions positives.
- **Rapport de mesure** :
  - précision et rappel de l'abstention ;
  - exactitude sur les réponses données ;
  - courbe couverture/exactitude ;
  - intervalle de confiance (bootstrap). Avec 24 questions, l'incertitude
    est forte : il faut le dire.
- **Réglage invalidé** à chaque changement de modèle, de découpeur ou de
  normalisation : le seuil appartient à la génération.

## 4. Fraîcheur de l'index

Trois états distincts, jamais confondus avec la fraîcheur des observations
DARME (60 s) ou générales (300 s) :

| État | Condition | Effet sur la réponse |
| --- | --- | --- |
| `INDEX_PENDING` | au moins une intention `INTENT` ou `PUBLISHED` dans le journal | la recherche sémantique ne couvre pas ces documents ; on le dit |
| `INDEX_STALE` | la plus ancienne intention en attente dépasse le seuil de retard, **ou** trop de résultats sont écartés comme périmés (section 2.4) | avertissement explicite ; pas de bascule lexicale silencieuse |
| `INDEX_UNAVAILABLE` | Qdrant injoignable, descripteur absent ou incompatible | dégradation visible, décidée et affichée |

**Seuil de retard** : il se calibre sur la latence **mesurée** du worker
en environnement de test isolé, pas sur une valeur choisie à l'avance.
Proposition : deux fois le 99ᵉ centile de « `published()` → `indexed()` »,
avec au moins 60 s. À mesurer quand le worker existera.

## 5. Sondes à ajouter quand le code existera

- Point de passage sans texte en clair ; charge minimale exacte.
- Descripteur sans `chunker` ou avec un autre `chunker` : refus.
- Requête dont tous les résultats sont périmés : `INDEX_STALE`, aucune
  citation.
- Seuil d'abstention absent du descripteur : la recherche sémantique
  refuse de répondre au lieu d'utiliser un seuil par défaut.
- `INDEX_PENDING` signalé dès qu'une intention est en attente.
