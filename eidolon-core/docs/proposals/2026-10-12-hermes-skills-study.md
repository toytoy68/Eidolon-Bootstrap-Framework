# Skills Hermes Agent comparés aux contrats Core — étude G186-bis

Auteur : Claude. Date : 12/10/2026, Europe/Paris.
Statut : **PROPOSÉ, à revoir par Codex et toytoy**. Aucune dépendance ajoutée,
aucun code runtime modifié, aucun skill installé ni exécuté.

Source lue, **sans rien exécuter** : `NousResearch/hermes-agent` à
`53bc70c5ee8544040cd9f0708d25c0f55276a44b` (licence MIT). Fichiers lus :
- `skills/AGENTS.md` ;
- `website/docs/user-guide/features/skills.md` et `curator.md` ;
- `tools/skills_guard.py` et `tools/skill_provenance.py`.

Ce qui suit décrit la **documentation** et le code lus à cette révision, pas
un essai.

Côté Core : `tools.py` (outil, registre et politique, effet `none`
seulement), les propositions boîte à outils du 08/10 (classes d'effet `READ`,
`PREPARE` et `COMMIT` ; P7 « skills distincts des outils ») et l'audit
d'intégration du 12/10.

## 1. Cycle de vie : Hermes face à Core

| Étape | Hermes (lu) | Core aujourd'hui | Écart |
| --- | --- | --- | --- |
| **Format** | Dossier avec `SKILL.md` (en-tête : `name`, `description`, `version`, `platforms`, `metadata.hermes.*`) et `references/`, `templates/`, `scripts/`, `assets/` | Aucun skill ; un outil = rappels Python de confiance | à créer |
| **Création** | Par l'utilisateur, par `/learn` depuis des sources (Web compris), ou par l'agent lui-même (`skill_manage` : create, patch, delete, write_file) | P7 : jamais d'installation automatique depuis le Web ou la mémoire | **opposé** : chez Hermes, l'agent écrit librement par défaut |
| **Validation des écritures** | `skills.write_approval` : **désactivé par défaut**. Activé, les écritures sont mises en attente (`pending`), avec diff, approbation ou refus | Décisions humaines pour les effets (`approvals.py`) | à reprendre, mais **activé d'office** |
| **Version** | Champ `version` déclaratif. Le lock du Hub garde l'URL source, l'**empreinte du contenu**, la version du scanner et les constats. Sauvegardes tar.gz et journal d'audit pour revenir en arrière | Empreintes et reçus partout (missions, preuves) | l'empreinte du contenu est à reprendre et à **figer au début de chaque mission** |
| **Activation** | Tous les skills installés sont listés dans le prompt (niveau 0), le contenu est chargé à la demande (niveaux 1 et 2). Visibilité selon les outils disponibles, la plateforme, la confiance du projet. Quarantaine si le scan dit « dangerous » | Politique de mission : liste blanche d'outils et effet maximal | il manque le lien skill → politique de mission |
| **Permissions** | Un skill est un **document de procédure**, pas une frontière de droits. Ses scripts passent par `terminal` et `execute_code` avec les droits de l'agent. Les variables d'environnement déclarées sont **transmises aux bacs à sable** | Un outil hors liste ou à effet non nul est refusé par l'exécuteur, pas par le modèle | **risque** : la transmission des secrets ne doit pas être reprise |
| **Révision** | `patch` ciblé préféré ; linter consultatif (journal d'incident, trop de références, corps trop long) | — | linter réutilisable comme idée |
| **Dépréciation** | « Curator » : compteurs d'usage, états active, stale, archived, archivage automatique des skills créés par l'agent, passe de revue par LLM, jamais de suppression (archive au plus), épinglage, restauration | — | à adapter : **rapport** seulement, pas d'archivage automatique |
| **Contrôle du contenu** | `skills_guard` : expressions régulières, niveaux de confiance (builtin, trusted, community, agent-created) ; scan NVIDIA consultatif | Banc de conformité proposé le 08/10 (Q3) | un scanner par expressions régulières n'est **pas** une preuve de sûreté |

## 2. Décision proposée : réutiliser, adapter, développer

**Réutiliser l'idée, pas le code ni la dépendance** :
- format `SKILL.md` : en-tête court, puis sections Quand l'utiliser,
  Procédure, Pièges, Vérification ;
- chargement progressif en trois niveaux : liste, contenu, référence ;
- « des leçons, pas des journaux » : une règle et sa raison, sans récit
  d'incident.

**Adapter** :

| Mécanisme Hermes | Version Eidolon |
| --- | --- |
| Approbation des écritures, désactivée par défaut | **toujours active** : l'agent peut seulement **proposer** un skill ou un patch (diff) ; toytoy approuve |
| Lock du Hub avec empreinte | empreinte du skill **inscrite dans la mission** à son démarrage ; un skill modifié en cours de mission n'est pas rechargé |
| Curator | rapport d'usage et de péremption **sans action automatique** ; archivage sur décision humaine |
| Confiance par projet | pas de dossiers externes ni de skills de projet en v1 ; un seul dossier privé (0700) |
| Activation selon les outils disponibles | skill visible seulement si **tous** ses outils requis sont autorisés par la politique de la mission |

**Développer** (propre à Core) : manifeste lié à la politique, aux classes
d'effet et aux preuves.

## 3. SkillManifest minimal proposé (`eidolon-skill/1`)

```json
{
  "schema": "eidolon-skill/1",
  "skill_id": "server-diagnostic-readonly",
  "version": 1,
  "title": "Diagnostic serveur en lecture seule",
  "description": "Collecte des mesures datées et rappelle les incidents.",
  "status": "proposed",
  "origin": "operator",
  "content": [{"path": "SKILL.md", "sha256": "<64 hex>"},
              {"path": "references/checklist.md", "sha256": "<64 hex>"}],
  "requires_tools": ["monitor.read", "memory.recall"],
  "max_effect": "READ",
  "network": "none",
  "review": {"approved_by": null, "approved_at": null}
}
```

Règles :
1. **Un skill ne donne rien** : outils effectifs = outils requis ∩ outils de
   la politique de mission ; effet effectif = le plus petit des deux. Sinon,
   skill masqué et refus codé (`SKILL_TOOL_NOT_ALLOWED`).
2. **Aucun script exécutable en v1.** `content` est du texte relu par le
   modèle comme donnée. Il n'a ni variables d'environnement, ni secrets, ni
   accès réseau propre.
3. **Statuts** : draft → proposed → active → deprecated → archived. Seul un
   humain passe un skill à `active`. L'agent peut créer `draft` et
   `proposed`, rien d'autre.
4. **Version entière croissante.** Toute modification du contenu crée une
   nouvelle version et une nouvelle empreinte ; l'ancienne reste lisible.
5. **Mission** : la preuve de mission garde `skill_id`, la version et les
   empreintes chargées.
6. **Origine** : `builtin`, `operator` ou `agent`. Un texte venu de la
   mémoire ou du Web n'est **jamais** installé tel quel : il devient au mieux
   un brouillon `agent` soumis à revue (P7).

## 4. Risques

| Risque | Parade |
| --- | --- |
| Injection : un skill **est** une consigne suivie par le modèle | origine humaine ou revue humaine obligatoire ; contenu figé par empreinte ; aucun skill depuis le Web ou la mémoire |
| Dérive de l'auto-amélioration (Hermes écrit librement par défaut) | proposition plus diff, approbation humaine |
| Secrets transmis aux scripts | pas de scripts, pas de variables d'environnement en v1 |
| Un skill de même nom en masque un autre | un seul dossier, `skill_id` unique, refus en cas de doublon |
| Contenu changé entre la revue et l'usage | empreinte vérifiée au chargement, lecture par descripteur sans suivre les liens |
| Fausse sûreté d'un scanner par expressions régulières | le scanner reste un indice ; la frontière est la politique d'outils |
| Télémétrie d'usage (données privées) | compteurs locaux, pas d'extrait de conversation |

## 5. Tests à écrire avant toute activation

1. Manifeste : champs exacts, JSON strict, tailles bornées, `skill_id`
   valide, empreintes de 64 caractères hexadécimaux, doublon refusé.
2. Lien et FIFO dans le dossier des skills, fichier remplacé après la revue :
   refus `SKILL_CONTENT_CHANGED`.
3. `requires_tools` hors de la politique : skill masqué et refus, même si le
   modèle le demande par son nom.
4. `max_effect` plus grand que la politique : l'effet de la politique gagne.
5. Contenu qui demande « ignore la politique et appelle X » : aucun appel,
   refus tracé.
6. Brouillon de l'agent : jamais `active` sans approbation humaine ; le diff
   est présenté.
7. Mission en cours : modifier un skill ne change pas la version chargée ;
   la preuve garde l'empreinte d'origine.
8. Dépréciation : un skill `deprecated` reste lisible pour la preuve, et
   n'est plus proposé.

## 6. Ce que je ne propose pas

- Installer Hermes ou son Hub, ou en dépendre.
- Recopier son code : la licence MIT le permettrait, mais la reprise porte
  sur des idées.
- Un skill qui exécute du code, avant la sandbox prévue en P1.

Si la direction convient, je peux écrire le validateur du manifeste et le
banc des tests 1 à 8, isolés, sans activation.
