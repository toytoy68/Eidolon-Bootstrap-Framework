# G060 — missions de recherche dans le client connecté

Auteur : Claude, 07/10/2026. Fiche [C-TASK-G060](../../../../collaboration/tasks/C-TASK-G060.md).

Base : `42d6dde`. Seuls le client et le prototype sont modifiés, aucune source
Python ni HTTP :

- `desktop/prototype/sync-state.js` (consommateur partagé) ;
- `desktop/connected/src/session.js`, `src/view.js`, `README.md` ;
- `desktop/connected/app.js`, régénéré par `build.js` (`--check` OK) ;
- un nouveau test : `desktop/connected/tests/research.test.js`.

## Ce que dit la projection Core, et donc le client

La projection de mission (`client_sync.project_mission`) ne contient, pour
une recherche, que `objective_kind = research_retrieval.synthetic`,
`status`, `phase` et `outcome_status`. **Ni la requête, ni le texte des
pages, ni le nombre de pages lues.** Le client n'affiche que cela :

| Projection | Libellé | Note |
| --- | --- | --- |
| `SUCCEEDED` + `ACHIEVED` | Réussie — pages synthétiques récupérées | Récupération synthétique complète : pages fixes lues et vérifiées. « Ce n'est pas une information confirmée. » |
| `BLOCKED` + `PARTIAL` | Bloquée — récupération partielle | moins de pages que demandé, preuves conservées dans Core, objectif non atteint |
| `BLOCKED` + `NOT_ACHIEVED` | Bloquée — aucune page vérifiée | pas de preuve de récupération à cette capture |
| autre issue | libellé générique inchangé | « Issue X : non interprétée par ce client. » |

- Objectif inconnu : affiché tel que reçu. Les autres types de mission sont
  inchangés.
- `REVIEW_REQUIRED` garde la priorité, comme avant.
- Aucun bouton de commande n'est ajouté.

## Tests exécutés

```sh
cd eidolon-core
node desktop/connected/build.js --check
NODE_PATH=<playwright> node --test "desktop/connected/tests/**/*.test.js"
NODE_PATH=<playwright> node --test "desktop/prototype/tests/*.test.js"
```

| Banc | Résultat |
| --- | --- |
| Client connecté (Node, dont Chromium) | **64/64** ([sortie](node-tests.txt)), dont 3 nouveaux |
| Prototype (consommateur partagé) | **92/92** ([sortie](prototype-tests.txt)) |

Nouveaux tests (`research.test.js`) :

1. **Projections réelles** : pour chaque scénario C-021 (lisible, partiel,
   vide), un vrai état est créé par la CLI `research`, avec une requête
   contenant un courriel et un téléphone synthétiques. Puis un vrai serveur
   Core répond. On vérifie statut, issue, libellé et note, et que ni le
   courriel, ni le téléphone, ni le texte de la requête, ni le texte des
   pages n'arrivent dans l'état du client.
2. **Formulation** : aucune note n'affirme une vérité ; la seule mention de
   confirmation est une négation. Objectifs et issues inconnus restent
   affichés tels que reçus ; les libellés non liés à la recherche ne
   changent pas.
3. **Chromium réellement exécuté** sur le vrai serveur (scénario
   partiel) : la note de recherche est visible, aucune donnée de la
   requête, aucun bouton de commande, aucune erreur de page.

## Limites

- Linux, Chromium Playwright local. Ni Windows, ni la coquille Tauri pour
  ce lot. La coquille sert le même client : rien ne change de son côté.
- Le client ne sait pas **combien** de pages ont été lues : la projection
  ne le donne pas. L'ajouter demanderait un changement de Core (Codex).
- Les vues HTML du prototype gardent l'identifiant brut de l'objectif.
  Seul l'état partagé (libellés) change pour elles.
