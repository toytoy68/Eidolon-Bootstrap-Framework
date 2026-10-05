# Contrat du catalogue de cibles — `targets/1`

Auteur : Claude, 05/10/2026, fiche [C-CLAUDE-001](../collaboration/tasks/C-CLAUDE-001.md).
Base : `9620c47`. Statut : module livré **non raccordé** : ni le runtime, ni la
CLI, ni `Policy` ne l'utilisent. Liens : C-001, C-002, C-003W, C-BRAIN-002, C-BRAIN-005.

Module : [`src/eidolon_core/targets.py`](../src/eidolon_core/targets.py).
Tests : [`tests/test_targets.py`](../tests/test_targets.py), 11 tests, sans réseau.

## Ce que le catalogue garantit

- Un **inventaire configuré par l'opérateur** : identifiant stable, nom, type,
  alias, destination déclarée, capacités nommées et classe d'effet de chacune,
  références de secrets.
- Une **résolution qui ne devine jamais** : identifiant ou alias, normalisé
  (NFKC, casse ignorée, espaces de bord retirés). Elle rend une seule des
  issues `FOUND`, `TARGET_ABSENT`, `TARGET_AMBIGUOUS` (avec la liste triée des
  candidats, sans en choisir un) ou `CAPABILITY_ABSENT` (cible trouvée, capacité
  non déclarée).
- Un **manifeste canonique** et une **empreinte SHA-256** indépendants de l'ordre
  de la configuration. Toute modification d'une destination, d'une capacité,
  d'une classe d'effet, d'une portée, d'un alias ou d'une référence de secret
  change l'empreinte.
- **Aucune entrée/sortie** : pas de DNS, de socket, de montage ni de lecture de
  fichier. Un test remplace `socket` par une fonction qui échoue.

## Ce que le catalogue ne garantit pas

- Une capacité déclarée **n'est pas une permission** et ne prouve pas que la
  cible est joignable. Aucun champ « autorisé » n'existe.
- `destination` et `scope` sont des **intentions** déclarées. Ils n'empêchent ni
  la traversée de chemin, ni le changement de résolution DNS, ni les
  redirections vers une adresse privée.
- Une référence de secret est un **nom** (`[a-z][a-z0-9_-]{0,62}`). Le catalogue
  ne le résout pas et refuse ce qui ressemble à une valeur (`:`, `/`, `@`,
  espaces). Il ne peut pas détecter un vrai secret qui aurait cette forme.

## Format

```json
{"schema": "targets/1", "targets": [
  {"id": "nas-main", "name": "NAS principal", "kind": "nas_storage",
   "aliases": ["NAS", "stockage"],
   "destination": "smb://nas-main.example.invalid/archives",
   "capabilities": [{"name": "files.read", "effect": "local_read",
                     "scope": {"roots": ["archives"]}}],
   "secret_refs": {"credential": "nas-main-reader"}}]}
```

| Champ | Règle |
| --- | --- |
| `id` | `[a-z][a-z0-9-]{0,62}`, unique |
| `name` | texte de 1 à 200 caractères, sans caractère de contrôle ou invisible |
| `kind` | `web_public`, `lan_service`, `nas_storage`, `windows_session` |
| `aliases` | 16 au plus ; un alias égal à l'identifiant d'une **autre** cible est refusé ; un alias partagé par deux cibles est permis et se résout en `TARGET_AMBIGUOUS` |
| `destination` | facultatif, texte de 500 caractères au plus, jamais interprété |
| `capabilities[].name` | 2 à 4 segments : `files.read`, `memory.recall`, `service.restart` ; unique par cible ; 32 au plus |
| `capabilities[].effect` | `none` < `local_read` < `egress_read` < `mutation` |
| `capabilities[].scope` | objet JSON de 4 000 octets au plus, conservé tel quel |
| `secret_refs` | 8 au plus, `{usage: nom}` |

Tout champ inconnu, plus de 64 cibles ou un schéma autre que `targets/1` est
refusé par `ContractError`. Une référence de cible qui n'est pas une chaîne de
1 à 200 caractères sans caractère de contrôle est aussi refusée : une chaîne
venue d'un modèle reste une donnée, jamais une commande.

## API

```python
catalog = Catalog.from_config(config)      # ContractError si mal formé
catalog.resolve("nas")                     # Lookup(status, reference, target, capability, candidates)
catalog.lookup("nas-main", "files.read")   # cible puis capacité déclarée
catalog.get("nas-main")                    # Target ou None, par identifiant exact
catalog.manifest(); catalog.fingerprint()  # forme canonique et SHA-256
```

## Raccordement proposé (non fait, fichiers du lot Codex)

1. `Runtime.configuration()` ajoute `"targets": catalog.fingerprint()`. Une
   reprise après modification du catalogue bloque alors avec
   `CONFIGURATION_CHANGED`, sans mécanisme nouveau.
2. Le plan désigne une cible par référence et une capacité par nom. Le
   précontrôle appelle `lookup` : tout autre statut que `FOUND` refuse le plan,
   et `TARGET_AMBIGUOUS` devient une demande de clarification avec les candidats.
   Pour C-001a, cela suit ta règle : refus au précontrôle.
3. `Policy` reste l'autorité sur les permissions. Elle reçoit
   `(target.id, capability.name, capability.effect)` et décide par liste
   explicite, en refusant par défaut. `Policy.allows` raisonne aujourd'hui sur
   `tool.effect == "none"` : il faudra une règle par classe d'effet.
4. Le journal d'un appel conserve `target.id`, `capability.name`, `effect` et
   l'empreinte du catalogue, pour qu'un accord ou une revue porte sur une
   configuration précise (C-BRAIN-003, C-BRAIN-005).

## Contrôles restant obligatoires ailleurs

**Dans `Policy`** : liste d'autorisations par (cible, capacité), refus par
défaut ; mutation jamais autorisée sans accord humain lié à la cible, à la
capacité et aux paramètres ; usage unique de cet accord.

**Dans chaque connecteur** :
- Web public : résoudre le nom, refuser les adresses privées, de lien local et
  de bouclage, se connecter à l'adresse vérifiée, recontrôler chaque
  redirection, vérifier TLS, borner taille et durée.
- LAN et NAS : n'atteindre que la destination du catalogue ; authentifier la
  cible, pas seulement l'adresse.
- Fichiers (NAS, Windows) : canonicaliser le chemin sous une racine de `scope`,
  refuser liens et jonctions sortants, lire par descripteur ouvert, rapporter
  taille, date de modification et SHA-256 des octets lus.
- Secrets : résolus dans l'exécutant seulement, jamais écrits dans la mission,
  le journal ou un reçu.
- Disponibilité : une observation datée, séparée du catalogue (C-BRAIN-005).

## Limites

Aucune cible réelle n'est décrite ; les exemples utilisent `.example.invalid`.
Ni l'adresse de VM100, ni le NAS, ni le PC n'ont été contactés. Les tests
prouvent le comportement du module, pas la sûreté d'un futur connecteur.
