# G051 — contre-revue de la garde durable de recherche (C-014a)

Auteur : Claude, 07/10/2026. Fiche [C-TASK-G051](../../../../collaboration/tasks/C-TASK-G051.md).

Cible figée : `887fa16`, en copie `git archive`. `research_guard.py` et
`research_pauses.py` sont identiques à la tête `48a33fc`. Sources non
modifiées.

```sh
python3 docs/validation/2026-10-07/claude-g051/probes_g051.py <copie 887fa16>/eidolon-core/src
```

Montage :

- vrais processus Python, lancés par la sonde et tués par **leur propre
  PID** ;
- fournisseur, lecteur et DNS simulés : chaque contact avec le fournisseur
  ajoute une ligne à un compteur ;
- garde et pauses persistantes activées ensemble ;
- aucun réseau.

Sortie : [probes.txt](probes.txt).

## Pannes de processus

| Cas | Journal ensuite | Nouvelle recherche | Revue explicite | Après la revue |
| --- | --- | --- | --- | --- |
| K1 SIGKILL après l'intention, **avant tout contact** | INTENT / UNCERTAIN | refusée `WEB_RESEARCH_UNCERTAIN`, 0 contact | RESOLVED_UNKNOWN, `request_sent=false`, `effect_known=false` | aucun contact sans appel ; la recherche explicite suivante passe |
| K2 SIGKILL **pendant** l'appel fournisseur | idem | idem | idem | idem |
| K3 SIGTERM pendant l'appel | idem | idem | idem | idem |
| K4 429 → pause écrite, puis SIGKILL avant la fin | INTENT **et** pause active | refusée, 0 contact | RESOLVED_UNKNOWN ; **la pause reste active** | recherche suivante : fournisseur `RETRY_WAIT`, **0 contact** |

Conforme au contrat :

- avant ou après un contact, l'incertitude est la même : rien n'est déduit ;
- aucune relance implicite ;
- la revue de la garde ne libère pas la pause.

## Concurrence

- **6 processus lancés en même temps** : 1 recherche, 5 refus immédiats
  `WEB_RESEARCH_IN_FLIGHT`, **1 seul contact**. Le journal reste cohérent.
- Pendant une recherche, un autre processus ne peut ni inspecter ni
  réviser : `WEB_RESEARCH_IN_FLIGHT`, comme documenté. La recherche se
  termine ensuite normalement.
- **Verrou remplacé** pendant une recherche (fichier supprimé puis recréé
  en 0600) : une seconde recherche obtient le nouveau verrou, mais elle est
  refusée `WEB_RESEARCH_UNCERTAIN` par l'intention en cours. La défense en
  profondeur tient : 1 seul contact.

## Journal altéré

| Altération | Résultat |
| --- | --- |
| Dernier événement COMPLETED supprimé | `INVALID_RESEARCH_AUDIT`, 0 contact |
| Base en 0644 | `RESEARCH_DATABASE_NOT_PRIVATE`, 0 contact |
| Fichier de verrou supprimé | `RESEARCH_GUARD_UNAVAILABLE`, 0 contact |
| Base tronquée | `RESEARCH_GUARD_UNAVAILABLE`, 0 contact |
| Intention **et** son événement supprimés ensemble | recherche acceptée : contournement **documenté** (SQL direct) |
| Dossier du journal supprimé après une panne | nouveau journal vide, recherche acceptée : contournement **documenté** |

## G051-1 — 256 recherches, puis blocage définitif (P2, produit)

Après 256 recherches, la 257ᵉ est refusée :
`RESEARCH_HISTORY_CAPACITY_REACHED`. C'est le comportement annoncé (« aucun
effacement automatique »).

Mais la CLI ne propose que `inspect` et `resolve` : **aucun moyen prévu**
pour archiver ou faire tourner l'historique. Avec C-D13 et C-D15 (requêtes
automatiques, y compris celles du modèle), cette limite sera atteinte
vite. Seule issue aujourd'hui : supprimer le journal, ce qui est justement
le contournement à éviter.

Proposition, à décider par Codex : une commande explicite qui **exporte puis
retire** les fiches COMPLETED et RESOLVED_UNKNOWN les plus anciennes. Elle
refuserait d'agir s'il reste une intention, et garderait un compteur ou une
empreinte de chaîne pour que l'historique reste vérifiable. Pas de diff
joint : c'est un choix de conception, pas un correctif local.

## G051-2 — verrou supprimé : pas de chemin de reprise (P3)

Si `research-runs.lock` disparaît, toute recherche est refusée. C'est
prudent. Mais ni `ResearchGuard(create=True)` (la base existe déjà) ni la
CLI ne le recréent. La reprise manuelle (recréer le fichier en 0600) n'est
pas documentée.

Proposition : documenter cette reprise, ou ajouter une commande qui recrée
le verrou seulement si la base est valide et sans intention.

## Limites

- Linux, système de fichiers local, Python 3.11. Ni Windows, ni NFS, ni
  coupure de courant.
- Les pannes sont provoquées à des points choisis : avant le contact,
  pendant le contact, entre la pause et la fin. Ce n'est pas une
  exploration de tous les instants.
- Un contact réel avec un fournisseur reste inconnu après une panne :
  c'est le sens même de RESOLVED_UNKNOWN.
