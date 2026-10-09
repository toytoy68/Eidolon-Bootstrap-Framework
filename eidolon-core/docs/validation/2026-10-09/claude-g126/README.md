# G126 — Contre-revue indépendante du worker média (C-064 à C-067)

Auteur : Claude. Date : 09/10/2026, Europe/Paris. Fiche : C-TASK-G126.
Base : branche Claude après la fusion C123 et l'intégration de `02448dd`.
`media_*.py` n'est **pas** modifié.

## Méthode

[probes_g126.py](probes_g126.py) et [crash_g126.py](crash_g126.py).

Contrairement aux tests de Codex, qui remplacent `current_proposal` par un
faux, les sondes passent par le **vrai parcours** :

- dialogue simulé ;
- proposition figée et stockée par le vrai dépôt des conversations (v6) ;
- soumission par la vraie API authentifiée ;
- espace média créé par `workspace-init` (C-067).

Seul le moteur est simulé : un objet qui compte ses appels.

```sh
PYTHONPATH=src python3 -m unittest discover -s docs/validation/2026-10-09/claude-g126 -p 'probes_*.py' -v
```

## Résultats exécutés : 12/12 ([probes-g126.txt](probes-g126.txt))

| # | Propriété | Résultat |
| --- | --- | --- |
| P1 | une proposition plus récente rend l'ancienne non soumissible | `PROPOSAL_STALE`, aucun ticket |
| P2 | accord donné puis proposition remplacée **avant** le lancement | **le ticket v1 s'exécute** (`RETURNED`, 1 appel) : voir G126-R1 |
| P3 | un numéro de ticket n'est pas un droit | autre client : `MEDIA_TICKET_UNKNOWN`, 0 appel ; résultat refusé ; route 404 |
| P4 | clé rejouée avec un autre contenu | `MEDIA_COMMAND_KEY_REUSED` ; nouvelle clé : `MEDIA_PROPOSAL_ALREADY_SUBMITTED` ; un seul ticket |
| P5 | 4 **processus** lancent le même ticket en même temps | **1 seul appel moteur** ; les autres : `RETURNED` (relecture) ou `WORKER_BUSY` |
| P6 | processus tué (`os._exit`) pendant l'appel moteur | ticket `ATTEMPTED` durable, réservation GPU **conservée** ; relancer ne rappelle pas le moteur |
| P7 | échéance HTTP après soumission (`MEDIA_HTTP_DEADLINE`) | `REVIEW_REQUIRED`, réservation conservée, aucun second appel |
| P8 | fichier source modifié avant le lancement | refus, ticket toujours `ACCEPTED`, 0 appel ; fichier rétabli : le même ticket s'exécute une fois |
| P9 | réservation GPU déjà tenue | `RESOURCE_RESERVED` avant tout essai, ticket `ACCEPTED`, 0 appel |
| P10 | aucune réussite déduite | `success_claim: false` partout ; texte d'analyse HTML gardé tel quel, non vérifié ; aucun chemin dans la route |
| P11 | `workspace-init` coupé à chacune des 5 étapes | `REVIEW_REQUIRED`, réinitialisation refusée, le serveur refuse l'espace partiel |
| P12 | configuration remplacée ou identité d'espace fausse | démarrage du serveur refusé |

## Constat

**G126-R1 (moyen, à décider).**

1. L'humain valide une demande v1 : un ticket `ACCEPTED` est créé.
2. Avant que l'opérateur lance quoi que ce soit, l'humain obtient une v2 de
   la même demande, dans la même chaîne de versions.
3. `run_once` du ticket v1 s'exécute quand même (`RETURNED`, 1 appel moteur).

L'accord v1 était explicite et une v2 non validée n'est pas un accord. Mais
la page montre désormais la v2. L'humain peut croire avoir remplacé sa
demande.

Options :

- **(a)** `run_once` refuse un ticket dont la proposition n'est plus la
  courante (`MEDIA_PROPOSAL_SUPERSEDED`, ticket laissé `ACCEPTED`, 0 appel).
  C'est le plus prudent.
- **(b)** Garder le comportement, mais l'annoncer : la page montre « la
  demande v1 validée reste en file ».

Je recommande (a) : c'est la couche de Codex (`media_worker.py`). Côté page,
j'afficherai l'état choisi.

## Limites

- `worker.check()` (C-065) n'accepte pas de moteur simulé : il exige une
  vraie configuration de workflow. P9 observe donc le refus sur `run_once`.
- Fichier source **supprimé** non sondé séparément, seulement modifié. Le
  même chemin de refus est attendu.
- Aucun vrai moteur, GPU, ComfyUI ni Ollama.
