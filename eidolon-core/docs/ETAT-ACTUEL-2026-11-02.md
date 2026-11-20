# État vérifié — 2 novembre 2026

Auteur : Codex/GPT. Autorisation : toytoy demande les tâches réalisables sans console.
Lot : récupération DARME, CI et validation sous umask 077. Copie isolée ; production inchangée.

## Réconciliation

Base locale : 6528f0ef9451230048d38215b307efbd5df73612, dix commits après
2891e20a177819fa6e31f5359e6854407b091f72. Base GitHub : cf1bf6f787dc62501a42341e6897ca2582aa8831.
Fusion locale sans conflit : 0bcac9e (PAPERCLIP-001 conservé).
Archive Git complète vérifiée sur VM100 ; bundle incrémental des dix commits
copié sur X399, vérifié et restauré dans une branche recovery/darme-original.
Empreinte SHA-256 du bundle incrémental : fffdab725a39f5100f6df90c1c3240d9712cb839fc518cda393badff2c334e14.
Les changements sont proposés sur une branche de revue ; aucun reset du checkout exploité.

## Corrections constatées par exécution

Le premier passage sous umask 077 donne 2371 PASS et trois échecs :
- la clé publique de sauvegarde n'a pas le mode 0644 promis ; fchmod sur le
  descripteur nouvellement créé impose désormais les modes 0600/0644 du contrat ;
- deux fixtures ne créent pas réellement leurs fichiers/dossiers publics sous ce
  masque : permissions rendues explicites, sans affaiblir les refus testés.
Les filtres CI couvrent tools/** et deployment/** ; les PR vers la branche active
exécutent la suite ; rapport JUnit conservé.

## Preuves exécutées

- 62 tests ciblés et 4 subtests PASS après correction.
- Suite complète non-root, umask 077, Memory de référence be53d1c :
  **2375 passed, 8 skipped, 1331 subtests**, 234,79 secondes.
- Les sondes de propriétaires exécutées séparément avec changements réels d'UID : **5 passed**.
- Client connecté : build --check PASS ; **195 tests Node PASS, 42 skipped**.
- Six skips Python restants concernent dépendances/modèles de reconnaissance non installés.
- Un avertissement attendu de ZIP à entrée dupliquée est présent ; pas d'échec.
- Journaux privés : ~/eidolon-validation/audit-20261102/ sur VM100.
- Les résultats GitHub du commit publié sont à constater séparément.

## Déjà intégré / encore ouvert

G294/G295, sept xfail promus en PASS, avertissements de preuve et adaptation du
modèle Qwen exact sont déjà intégrés. Le problème de citation réelle hors sujet
(A06) reste ouvert ; le modèle actif n'est pas changé.
Les nouveaux modules DARME sont préservés et leurs tests font partie de la suite.
Cela ne prouve pas un confinement réseau OS ni le raccordement d'un transport
intermachines : A10 reste partiel. PAPERCLIP exige encore une recette intégrée.
Voix humaines, périphériques Windows et génération V100 restent hors recette.
