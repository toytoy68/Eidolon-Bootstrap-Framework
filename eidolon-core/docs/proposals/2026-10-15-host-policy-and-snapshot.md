# Politique hôte versionnée et lecture bornée de l'instantané (Claude, G256-6 et G256-7)

Auteur : Claude. Date : 15/10/2026, Europe/Paris. Base Core : `1ac4292`.
Statut : **proposition expérimentale**. Rien n'est raccordé au lanceur réel :
aucun capteur, aucun minuteur, aucun service.

Fichiers :

- `tools/claude_host_policy.py` : contrat, adaptateur vers `run_maintenance_tick`
  (G254) et commande de vérification sans effet ;
- `tools/claude_observation_snapshot.py` : lecture bornée d'un fichier JSON ;
- `tests/test_claude_host_policy_g256.py` : 56 tests.

## 1. Le contrat de politique (G256-6)

L'opérateur écrit ce fichier. **Aucun champ n'a de valeur par défaut** : un
champ absent arrête tout. Les nombres ci-dessous sont des exemples de test,
pas des recommandations.

```json
{
  "schema": "eidolon-host-maintenance-policy/1",
  "expected_source": "host.proc",
  "max_observation_age_seconds": 60,
  "max_load_age_seconds": 60,
  "load_unit": "load1_per_cpu",
  "load_limit": 0.7
}
```

| Règle | Pourquoi |
| --- | --- |
| Version inconnue (`/2`), champ en trop ou manquant : refus | Une politique mal comprise ne doit jamais tourner. |
| Âges et limite : nombres finis strictement positifs (pas de booléen, de texte, de NaN, d'infini ni de débordement) | Les mêmes pièges que pour les observations (C183). |
| **L'unité de charge** est un nom choisi par l'opérateur | Une charge `load5_per_cpu` comparée à une limite prévue pour `load1_per_cpu` serait un faux « charge correcte ». |
| **La limite vient de la politique, jamais de l'instantané** | Un instantané qui apporte sa propre `limit` est refusé : il ne peut pas relâcher le plafond de l'opérateur. |

Forme de la charge dans l'instantané : `{"observed_at", "ratio", "unit"}`.
L'adaptateur la convertit vers la forme G254 (`limit` pris dans la
politique) et appelle `run_maintenance_tick` **une seule fois**. Tous les
refus ont lieu **avant** la fabrique du contrôleur.

## 2. Lecture de l'instantané (G256-7)

`read_json_snapshot(dossier, nom, max_bytes=…)` lit un objet JSON ou refuse,
avec un code public :

| Cas | Code |
| --- | --- |
| Chemin relatif, `..`, nom hors `[A-Za-z0-9._-]+.json`, octet nul | `SNAPSHOT_PATH` |
| Lien symbolique **dans n'importe quel dossier** du chemin | `SNAPSHOT_PATH` |
| Feuille en lien symbolique, absente ou illisible | `SNAPSHOT_UNAVAILABLE` |
| FIFO, périphérique, fichier à plusieurs liens physiques | `SNAPSHOT_NOT_REGULAR` (ouverture non bloquante : une FIFO ne bloque pas) |
| Fichier modifiable par le groupe ou par tous | `SNAPSHOT_WRITABLE_BY_OTHERS` |
| Plus de `max_bytes` (avant et pendant la lecture) | `SNAPSHOT_TOO_LARGE` |
| Remplacé, réécrit, allongé ou supprimé pendant la lecture | `SNAPSHOT_CHANGED` |
| BOM, UTF-8 invalide | `SNAPSHOT_ENCODING` |
| Clé dupliquée, même imbriquée | `SNAPSHOT_DUPLICATE_KEY` |
| `NaN`, `Infinity`, texte après l'objet, tableau au sommet | `SNAPSHOT_INVALID_JSON` |
| Imbrication au-delà de 4 niveaux, ou récursion du décodeur | `SNAPSHOT_TOO_DEEP` |

L'hôte doit écrire l'instantané **par renommage atomique** (fichier
temporaire puis `rename`). Un test fait tourner un écrivain qui remplace le
fichier en boucle pendant 300 lectures. Chaque lecture réussie donne une
version complète, jamais un mélange de deux versions.

## 3. Preuves

- 56 tests (politique, lecteur, commande de vérification).
- 22 sabotages : **18 tués**, 4 équivalents. Les équivalents sont des
  gardes doublées qui se couvrent l'une l'autre :
  - taille avant / pendant la lecture ;
  - identité après lecture par descripteur / par nom (le `ctime` change
    déjà au remplacement) ;
  - `limit` refusée deux fois.
- Le retrait de `O_NONBLOCK` fait **bloquer** la suite sur la FIFO : c'est
  exactement le blocage que la garde évite.
- Défaut trouvé par le test de course et corrigé : un fichier remplacé
  entre l'ouverture et le `fstat` a 0 lien. Il est maintenant classé
  `SNAPSHOT_CHANGED`, et non plus « fichier anormal ».

## 4. Limites

- Aucune authentification de la source : `source` reste une étiquette de
  provenance (G254).
- Le propriétaire du fichier n'est pas imposé, car le compte de service
  n'est pas encore décidé. À ajouter quand il le sera.
- Ne remplace pas la recette VM.
