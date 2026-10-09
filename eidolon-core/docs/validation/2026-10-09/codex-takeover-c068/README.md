# Reprise Codex C-068/C-069 — correctifs C122, stockage et réponses tardives

Date : 09/10/2026. Base examinée : `8d50015da393c040ee3ec5adaeac395a6b5278fd`.
Prise en charge publiée : `eb247dbde298fbcfead9179c60969ea6d1d65de5`.
Toytoy signale Claude arrêté (limite atteinte) et autorise Codex à reprendre.
Ce rapport concerne le code de ce commit ; il ne reprend pas à son compte les
1 332 tests Python du lot C-067.

## Changements

- **G124-R1** : chaque réponse d'annulation reste liée à sa sélection et à sa
  requête. Une réponse ancienne (succès ou erreur), une autre sélection même
  pour la même mission, une fermeture ou une reprise de conversation ne peuvent
  réécrire le nouveau bloc. Les lectures de reçu ne concurrencent pas l'envoi ;
  seule la dernière lecture s'applique. Un statut inconnu ou la disparition
  d'un reçu déjà observé ne permet aucun renvoi. Le motif reste figé avec la clé.
- **G123-R1** : `media_links.job_id` est figé lors du lien opérateur, persisté
  et comparé à chaque lecture, avant de montrer l'état, l'observation ou les
  fichiers. Même requête + autre identifiant ne suffit plus. Les rafraîchissements
  de la page ignorent aussi les réponses dépassées.
- **G099-R1** : `media_links` participe au digest logique et aux comptages des
  sauvegardes, y compris au format v4 avant migration.
- **G125** : les codes numériques SQLite BUSY/LOCKED (y compris étendus) sont
  distingués des bases absentes, corrompues et des requêtes interrompues.
  API de lecture : `STATE_BUSY`. Conversations : codes existants
  `CONVERSATION_STORE_BUSY`, nouveau `CREDENTIALS_BUSY`, et `STATE_BUSY`
  pour la base des missions. Les détails SQL ne sont pas transmis.
  Le client garde les données datées et ne lance aucune nouvelle tentative
  automatique. Un stockage occupé après envoi ne prouve pas l'absence d'effet.

## C-069 — même protection pour les missions et la reprise du chat

La revue du même client a reproduit dix cas supplémentaires : reçu de mission
appliqué à une nouvelle proposition, double clic pendant le calcul d'empreinte,
réponse d'un ancien tour après reprise, reprises concurrentes, clé de remplacement
invalide et anciens reçus revenant après un nouveau résultat. Les dix échouent
sur C-068 et passent après C-069 dans V8. Les réponses sont désormais attachées
à la session, à la proposition et à la soumission d'origine ; une validation
déjà envoyée/enregistrée ne réémet pas de commande. Un changement de conversation
invalide les réponses en vol. L'ordre d'arrivée des réponses ne peut remplacer
une proposition plus récente ni effacer son reçu.

## Migration explicite v4 → v5

Le nouveau schéma ajoute un identifiant nullable. Une ancienne liaison v4
conserve proposition, chemins et dates mais reçoit `job_id = NULL`.
Son résultat est `LEGACY_UNVERIFIABLE`, sans état étranger ni fichier exposé.
Il n'y a ni lecture du dossier pour deviner l'identifiant historique, ni
reliaison implicite via `media-link`. La nouvelle liaison existante est
idempotente seulement avec la même identité et les mêmes chemins.

Utiliser la commande existante `migrate --backup <nouveau-fichier>` après
arrêt du serveur. La sauvegarde précède la migration ; aucun service ni
migration n'a été exécuté sur une machine utilisateur dans ce lot.
**La migration et les changements Python restent à valider en environnement
Python/SQLite avant usage réel.**

## Vérifications réellement exécutées

L'environnement système de cette session était indisponible. Aucun terminal,
Python, Node, Chromium, SQLite, Git CLI ou build/install Python n'était
accessible. GitHub était accessible par son connecteur.

Les sources JavaScript ont été évaluées dans l'isolate **V8** disponible,
avec un chargeur CommonJS minimal et des substituts de `node:test`,
`node:assert/strict`, `fs` et `path` strictement réservés aux tests.
Le banc conversation fournit SHA-256 en JavaScript (vecteur « abc » contrôlé
et empreinte de la fixture Core identique) et des identifiants déterministes
de test. Il ne remplace pas la cryptographie de production.

| Vérification | Résultat |
| --- | --- |
| 16 tests conversation préexistants, sources de base | 16 PASS |
| 11 nouveaux cas de concurrence/renvoi, sources de base | 11 FAIL attendus, défauts reproduits |
| Dix cas supplémentaires C-069, source C-068 | 10 FAIL attendus |
| Fichier conversation final, 16 anciens + 23 nouveaux | 39 PASS |
| Fichier session final, 28 anciens + 2 nouveaux | 30 PASS |
| Bundle original calculé par la vraie fonction `build.js:bundle()` | identique octet textuel au `app.js` publié |
| Bundle final recalculé par cette même fonction | génération et syntaxe JavaScript vérifiées |

Les transports sont scriptés ; aucun vrai serveur ou navigateur n'est
impliqué. Ces **69 cas V8** ne sont pas « 69 tests Node » ni une validation
Chromium. Voir les JSON conservés à côté et les deux bancs V8 pour la méthode.

## Tests préparés, non exécutés

13 nouveaux tests Python : substitution du travail à requête identique,
substitution simultanée de collecte, ancienne liaison v4, digest et neuf
colonnes de lien, sauvegarde devenue périmée avant migration, interruption
de migration, codes SQLite, verrous réels de conversations/appairage/missions,
base absente, lecture HTTP après libération du verrou.

À exécuter depuis `eidolon-core/` dans un environnement normal :

```sh
PYTHONPATH=src:. python -m unittest tests.test_conversation_media_results tests.test_conversation_storage tests.test_conversation_store tests.test_conversation_media_binding tests.test_conversation_api tests.test_conversation_cancel tests.test_http_api tests.test_http_conversations tests.test_media_worker tests.test_sqlite_errors -v
node --test desktop/connected/tests/conversation.test.js desktop/connected/tests/session.test.js
node desktop/connected/build.js --check
```

Puis suite Python complète avec Memory activée, tests client/Chromium,
paquet installé et migration d'une copie v4. Le nombre de modules change
(ajout de `sqlite_errors.py`) : les anciennes empreintes/recettes C-067
ne qualifient pas cette révision.

## Suite

G122/G123 complets : dialogue et soumission authentifiée reliés au worker,
puis résultats dans la page. G127 : recette de ce parcours. G126 :
contre-revue indépendante à reprendre par Claude quand disponible.
Aucun de ces travaux n'est déclaré achevé par ce lot. Aucun modèle, GPU,
VM ou Windows n'a été qualifié ; main et Memory Engine inchangés.
