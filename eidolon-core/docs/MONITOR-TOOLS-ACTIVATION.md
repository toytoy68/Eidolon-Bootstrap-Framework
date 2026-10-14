# Activation explicite des outils de surveillance dans Core (G168)

Auteur : Claude. Date : 12/10/2026, Europe/Paris.

**Statut** : module et tests livrés. **Branchement dans `http_api.py` et dans
le catalogue de missions : proposé, non poussé** (fichiers partagés, accord de
Codex nécessaire).

## 1. Ce qui est livré

[monitor_activation.py](../src/eidolon_core/monitor_activation.py) ajoute à
**un** Runtime les outils `monitor.machine` et/ou `monitor.darme` du SDK de
Codex ([monitor_tools.py](../src/eidolon_core/monitor_tools.py), G161), et
seulement si un fichier d'activation privé le demande :

```json
{"schema": "eidolon-monitor-tools-activation/1", "tools": ["monitor.machine"],
 "approved_by": "toytoy", "reason": "état des machines dans la conversation"}
```

Règles du fichier :
- il est privé : 0600, au bon propriétaire, sans lien symbolique ;
- ses champs sont exacts ;
- les outils doivent figurer dans `monitoring_policy()` de Codex, avec
  l'effet `none`.

| Garantie | Test (`tests/test_monitor_activation.py`, 6 tests) |
| --- | --- |
| Registres et politiques par défaut **jamais** élargis, même après une activation ailleurs | `test_defaults_are_never_widened` |
| Seuls les outils listés sont ajoutés. Tout l'existant (outils, autorisations sur cibles) reste. L'identifiant de politique devient `…+monitor:monitor.machine` et chaque mission l'enregistre dans sa configuration. | `test_activation_adds_only_listed_tools…` |
| Paramètres fermés : exactement `{}`. Commande, chemin, cible et liste sont refusés. | `test_parameters_are_closed…` |
| Résultat = instantané + SHA-256. La vérification relit la preuve **sans nouvelle sonde** ; un instantané modifié est refusé. | `test_evidence_references_the_snapshot…` |
| Fichier non privé, outil inconnu, doublon, champ en trop : refusés | `test_activation_file_refusals` |
| Double activation : `CONFLICT` | `test_conflicting_tool_name_refused` |

## 2. Proposition pour `http_api.py` (à valider par Codex)

```diff
+    parser.add_argument("--monitor-tools-activation", metavar="FICHIER",
+                        help="active explicitement monitor.machine/monitor.darme pour la conversation (G168)")
 …
-            self.conversation_api = ConversationAPI(synthetic_runtime(Store(state)), dialogue_model=conversations(),
+            runtime = synthetic_runtime(Store(state))
+            if monitor_tools_activation is not None:
+                from .monitor_activation import activate, load_activation
+                activate(runtime, load_activation(monitor_tools_activation))
+            self.conversation_api = ConversationAPI(runtime, dialogue_model=conversations(),
```

Sans l'option, le comportement est **identique** à aujourd'hui.

## 3. Ce qui manque pour une vraie mission (proposition, catalogue de Codex)

Aujourd'hui, aucune proposition de conversation ne produit d'étape
`monitor.*` : le catalogue `objectives.py` ne connaît que les missions
synthétiques. Il faudrait :
1. un type de mission `machine_status.local` dans `objectives.define`, avec
   une intention exacte (aucun paramètre libre) et une requête canonique, par
   exemple « Lire l'état local des machines » ;
2. un planificateur déterministe qui produit **une** étape
   `{"tool": "monitor.machine", "parameters": {}}`, sur le modèle de
   `DiagnosticModel` ;
3. côté conversation, une proposition de ce type, validée par toytoy comme les
   autres. Le résultat affiché est l'instantané et son empreinte ; c'est une
   **lecture**, jamais une permission.

Ces trois points touchent `objectives.py`, `runtime.py` et le dialogue :
c'est à décider avec Codex. Je peux écrire les tests de parcours de la page
dès que le contrat est fixé.

## 4. Limites

- Les outils lisent le socket **local** (VM Core). Memory passe par le
  canal G166, pas par ces outils.
- `read_status()` refuse un statut sans mesures machine, ou dont les mesures
  ont plus de 60 s. C'est voulu côté SDK : la mission échoue alors, sans
  afficher de valeurs anciennes.
