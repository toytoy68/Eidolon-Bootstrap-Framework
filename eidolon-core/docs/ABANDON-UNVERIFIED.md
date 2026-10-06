# Abandon explicite d'un résultat non vérifié — C-TASK-G023

Auteur : Claude, 06/10/2026. Suite de L-G020-1 (contre-revue G020).

## Besoin

Depuis `97abdb2`, un résultat reçu (`RETURNED`) est toujours vérifié avant de
clore une mission, même après une demande d'annulation. Si le vérificateur
reste indisponible, la mission reste `BLOCKED` en phase `VERIFY` et peut être
reprise. Mais rien ne permettait de la **fermer** si le vérificateur ne revient
jamais.

## Contrat

`Runtime.reconcile(identity, decision="abandon", actor=..., reason=...)`, ou la
CLI `reconcile <id> --decision abandon --actor … --reason …`, accepte désormais
une mission :

- `BLOCKED`, en phase `VERIFY` ;
- dont le dernier appel est `RETURNED`.

Une demande d'annulation n'est pas nécessaire.

Effet, sous le verrou de mission et en une sauvegarde atomique avec un
événement `ABANDONED` :

- **mission** : statut `ABANDONED`, phase `DONE`, `result=None`, erreur
  `RESULT_UNVERIFIED` ;
- **appel conservé tel quel** : `RETURNED`, sortie, empreinte et origine. Il
  n'est ni promu `VERIFIED`, ni réécrit en « sans effet » ;
- **événement** : acteur, motif, appel, tentative,
  `result_state=RETURNED_UNVERIFIED`, empreinte de la sortie ;
- **issue** : recalculée sur les appels **vérifiés** seulement (`PARTIAL` si
  une étape antérieure l'était), jamais `ACHIEVED` du seul fait de l'abandon ;
- **`action_view`** : continue d'afficher l'effet `RESULT_UNVERIFIED` ;
  applicabilité `MISSION_CLOSED` ;
- **aucun appel** : ni modèle, ni mémoire, ni outil, ni vérificateur. Un `run`
  ultérieur ne relance rien.

Ce nouveau chemin refuse, sans rien modifier :

- une autre décision que `abandon` ; la vérification se fait par `run` ;
- une sortie fournie ;
- une mission terminale (dont les anciennes missions `CANCELLED` de l'état E1),
  un appel `PREPARED`, une mission sans résultat reçu ;
- un acteur ou un motif invalides ;
- un verrou occupé (`Busy`).

Le chemin existant reste inchangé : `REVIEW_REQUIRED` avec un appel `STARTED`,
abandonné, donne `ABANDONED` / `EFFECT_UNKNOWN`.

## Limites

- Acteur et motif sont des libellés locaux, pas une identité authentifiée.
- Aucune expiration automatique : l'abandon reste un geste explicite.
- Une sortie gardée n'est pas une preuve : l'effet reste « non vérifié ».

[Preuves](validation/2026-10-06/claude-g023/README.md).
