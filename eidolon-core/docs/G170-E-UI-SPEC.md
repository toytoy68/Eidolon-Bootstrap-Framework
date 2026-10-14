# G170-E — Interface des profils : spécification et parcours simulés

Auteur : Claude. Date : 12/10/2026, Europe/Paris. Accord : G183 (C156-Q3).

**Simulation seulement.**
- Aucun micro, aucune caméra, aucun réseau.
- Aucune route ni aucun stockage serveur n'est annoncé : ce sont G170-A/B,
  chez Codex.
- Les prises sont des descriptions inventées, jamais du son ni une image.
- Les profils sont inventés. Rien ne donne de droit.

## 1. Fichiers

| Fichier | Rôle |
| --- | --- |
| `desktop/identity-sim/enrolment.js` | logique pure : parcours, refus codés, affichage des propositions |
| `desktop/identity-sim/index.html`, `sim.js`, `sim.css` | page de démonstration, hors du dashboard réel et **non servie** par Core |
| `desktop/identity-sim/tests/enrolment.test.js` | 10 tests `node --test` |
| `docs/validation/2026-10-12/claude-g170e/` | recette navigateur (28/28) et captures 1920 et 360 px |

La page s'ouvre en local (`file://`). Elle n'est pas dans `app.js` : le vrai
dashboard n'affiche rien de G170 tant que le serveur n'existe pas.

## 2. Règles

1. **Connexion manuelle, sans biométrie**. La clé de conversation reste le
   seul moyen de se connecter. Une reconnaissance n'est qu'une **suggestion**
   (« non vérifié »). Changer de profil passe par la connexion manuelle
   (G170-B).
2. **Enrôlement** :
   - seulement pour un profil **confirmé** par le serveur ;
   - la personne doit être présente **et** d'accord (deux conditions) ;
   - 3 prises : de 5 à 8 s de parole pour la voix, de face pour le visage ;
   - ces nombres sont des propositions, à confirmer en G170-F.
3. **Capture visible et annulable** :
   - le témoin rouge est allumé **seulement** pendant la prise ;
   - « Arrêter » reste proposé à chaque étape ;
   - arrêter ou annuler efface les prises de la séance.
4. **Prise ratée** (trop courte, trop longue, silence, plusieurs personnes,
   pas de visage, floue) : on recommence, la prise ne compte pas. Un défaut
   qui ne concerne pas la modalité est refusé (« pas de visage » pour la
   voix, par exemple).
5. **Confirmation** : le serveur calculerait les gabarits puis effacerait les
   prises. Le texte rappelle qu'aucun droit n'est donné.
6. **Effacement** : toujours après une confirmation. « Annuler » ne change
   rien. Un vrai serveur devra **prouver** l'effacement.
7. **Réenregistrement** : seulement après effacement, jamais par-dessus.
8. **Propositions affichées** (`eidolon-identity-proposal/1`) :
   - `known` : nom du profil confirmé et modalités utilisées, « non vérifié » ;
   - `ambiguous`, `unknown`, `uncalibrated`, `stale`, `unavailable`,
     `several_people` et les autres états : **aucun nom**, et les candidats
     ne sont jamais listés ;
   - une proposition qui porte un droit, `authorizes_execution: true`, un
     profil inconnu ou non confirmé, ou un autre schéma est **ignorée**.
9. Une action refusée **ne change rien** et rend un code (`PROFILE_NOT_CONFIRMED`,
   `CONSENT_INCOMPLETE`, `NOT_READY`, `ALREADY_ENROLLED_DELETE_FIRST`…).

## 3. Preuves

- `node --test desktop/identity-sim/tests/enrolment.test.js` : **10/10**.
- Recette Chromium (1920×1080 et 360×760), **28/28** : parcours complet,
  témoin seulement pendant la prise, aucun nom pour `ambiguous`, effacement
  au clavier, aucune page qui dépasse en largeur, **aucun appel** à
  `getUserMedia`, **aucune requête réseau**, aucune erreur de page.

## 4. Ce qui reste hors de ce lot

- Serveur, stockage des gabarits, sessions et changement de profil :
  G170-A/B (Codex).
- Branchement au vrai dashboard : après un serveur réel et l'accord de
  toytoy.
- Seuils, nombre de prises, durées : G170-F (mesures).
