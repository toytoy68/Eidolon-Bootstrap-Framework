# C-TASK-G070 — Annulation et reprise concurrentes

Claude, 08/10/2026. Base : `97770f5` (src figé par `git archive`). Aucun changement runtime.

```sh
python3 probes_g070.py <src figé>     # code 1 si une assertion échoue → probes.txt (≈ 10 s)
```

Méthode :

- De vrais processus runtime, en sous-processus, avec de vrais exécutants `spawn`.
- L'outil `text.stats` est instrumenté ([g070_tools.py](g070_tools.py)) : chaque
  exécution et chaque vérification ajoute une ligne synchronisée dans un journal
  **hors du runtime**. Les comptes ne viennent jamais des enregistrements du runtime.
- Un fichier `hold` maintient l'exécutant dans l'outil (borné à 20 s). Les attentes
  sont bornées ; aucun délai n'a été allongé.

**Résultat : 21/21 assertions, trois exécutions successives identiques.**
Aucun processus restant.

| Cas | Constat |
| --- | --- |
| Nominal, puis reprise | 1 exécution et 1 vérification ; la reprise ne rappelle rien |
| A. deux exécutants | le second reçoit `Busy` en 0,16 s pendant que le premier est dans l'outil ; une seule exécution |
| B. annulation avant tout | `CANCELLED`, **0** appel d'outil |
| C. annulation pendant l'outil | `REVIEW_REQUIRED / CANCELLED` (effet inconnu, jamais « annulée »). L'exécutant est tué dans l'outil ; le diagnostic indique « revue requise » et « annulation non prouvée » ; la reprise ne relance rien |
| D. annulation après un résultat reçu (coupure après `RESULT_SAVED`) | le résultat reçu est **vérifié** (+1 vérification), puis `CANCELLED`, sans aucune nouvelle exécution et sans résultat de mission |
| E. reçu tardif (l'outil finit pendant que l'annulation s'enregistre) | toujours `REVIEW_REQUIRED / CANCELLED`, jamais vérifié ni réexécuté. Le reçu tardif est conservé dans 3 à 5 essais sur 5 selon l'exécution : c'est une vraie course avec l'arrêt de l'exécutant |
| F. verrou de mission détenu par un autre processus | `Busy`, 0 appel ; exécution normale dès que le détenteur s'arrête |
| G. exécutant tué (SIGKILL) dans l'outil | `REVIEW_REQUIRED / WORKER_LOST`, aucune relance |
| H. runtime tué (SIGKILL) pendant l'outil | voir ci-dessous |

On distingue bien trois situations :

- **annulation demandée** : B, ou D après vérification ;
- **effet inconnu** : C, E, G, H ;
- **résultat effectivement vérifié** : nominal, et D pour l'étape déjà revenue.

## Contre-exemple minimal (H) — l'exécutant orphelin termine l'effet après la revue

1. Le runtime est tué pendant que l'exécutant est dans l'outil.
2. L'exécutant **continue**. `daemon=True` ne protège pas contre un SIGKILL du
   parent.
3. La reprise immédiate classe correctement la mission `REVIEW_REQUIRED /
   UNKNOWN_EFFECT`, sans seconde exécution. Le diagnostic voit le bail
   `HELD_AT_SAMPLE`.
4. Puis l'orphelin termine l'effet et écrit son reçu, **après** la mise en revue.
   Ce reçu reste non adopté (`PRESENT_UNVERIFIED`).

Ce n'est pas une relance, et la revue reste juste. Mais l'opérateur qui examine
la mission pendant que l'orphelin tourne peut conclure trop tôt « rien ne
s'est passé ».

Proposition, à coordonner avec Codex (runtime réservé) :

- Sous Linux, demander au noyau de tuer l'exécutant à la mort de son parent
  (`PR_SET_PDEATHSIG`), juste après le lancement et avant l'autorisation.
- Ailleurs, l'exécutant vérifie que son parent est vivant avant d'exécuter.
- Le diagnostic peut déjà le dire : « bail détenu = un exécutant peut encore agir ;
  revoir après sa fin ».

Cela réduit la fenêtre sans la fermer : un effet déjà parti reste parti.

## Limites

- POSIX/Linux, verrous `flock` locaux, en root. Pas de NFS, Windows ni coupure
  électrique.
- Outil synthétique local (calcul de statistiques). Un effet externe réel
  (réseau, appareil) n'est pas simulé au-delà de l'écriture du journal.
- Les courses de E dépendent de l'ordonnancement : la proportion de reçus
  conservés varie, mais le statut, lui, ne varie jamais.
