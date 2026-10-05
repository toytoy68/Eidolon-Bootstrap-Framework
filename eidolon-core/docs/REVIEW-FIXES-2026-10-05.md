# Corrections de la revue C-REV-001 — 05/10/2026

Auteur : Codex/GPT. Revue source : Claude, relayée par toytoy via le patch
`c848c6933e7f243ac8f2127f9b21b98150bdbc23`. Base examinée par Claude :
`60c2be708263354bdc2c7128392f189c2f5b271f`. Import publié dans
`b45ac76d53727b7e7927b1b641d970825c518949`, avec attribution et co-auteur conservés
au message de commit. SHA différent car le commit a été recréé pour publication ;
les sept fichiers du patch ont été repris à l'identique lors de cet import.
Le code corrigé est celui du commit
introduisant ce bilan ; les journaux ci-dessous ont été produits sur cet arbre.

## Vérification indépendante

Environnement Codex : Python 3.12.14, Linux, CPU, données synthétiques uniquement.
La [sortie des sondes avant correction](validation/2026-10-05/codex-c-rev-001/before.txt)
reproduit F-01 à F-05 avec le script de Claude conservé tel quel. F-06 était une
lecture de code chez Claude ; deux nouveaux tests synchronisent explicitement
la fin d'écriture du reçu avant l'annulation ou l'échéance dans le worker corrigé.
Ils vérifient la conservation du reçu et l'absence de succès automatique.

## Traitement des six défauts

| ID | Correction implémentée | Preuve / limite |
| --- | --- | --- |
| F-01 | JSON décodé revalidé avant persistance ; débordement flottant, substitut isolé et objet non sérialisable deviennent ContractError | Échec durable MODEL_INVALID, aucune exécution, reprise idempotente ; cas imbriqué et texte brut invalide couverts |
| F-02 | `result.evidence` référence les appels par ID, tentative, SHA-256 et vérificateur ; aucune duplication de sortie | Cinq sorties vérifiées de 600 ko, reprise après relecture SQLite, résultat compact ; stockage des sorties encore inline |
| F-03 | Décision `abandon` → ABANDONED, appel UNKNOWN et EFFECT_UNKNOWN conservés | État terminal sans relance, audit de l'acteur/motif, CLI JSON/humain ; abandonner n'arrête pas un orphelin |
| F-04 | Verrou par appel/tentative acquis par l'enfant avant le signal prêt ; exécution autorisée seulement après WORKER_SPAWNED durable ; réconciliation sous ce même verrou | Parent réellement tué par SIGKILL, reprise refusée pendant l'enfant vivant même si le PID enregistré est faux ; après fin observée, vérification sans rejeu |
| F-05 | Panne/délai modèle → BLOCKED/MODEL_UNAVAILABLE ; contrat invalide → FAILED/MODEL_INVALID | Reprise explicite avec modèle rétabli, même configuration et identité ; aucun outil au premier échec |
| F-06 | Reçu borné publié par renommage atomique, lu après arrêt/jonction même sur annulation/délai ; conservation en `late_receipt` | Reçu présent n'implique ni VERIFIED ni SUCCEEDED ; réconciliation observée puis vérification sans réexécution |

Le filet d'exception recharge l'état persistant et journalise INTERNAL_ERROR :
BLOCKED avant un effet, REVIEW_REQUIRED si la phase durable est EXECUTING.
Un test simule un échec d'enregistrement après retour outil : aucune relance.
Une panne persistante du stockage ne peut pas être journalisée par ce stockage ;
l'erreur remonte. L'annulation à la frontière du succès possède maintenant un
code d'erreur explicite. Son sondage ne désérialise plus toute la mission : il
lit le seul indicateur SQLite (une connexion par sondage reste utilisée).

## Résultats réellement exécutés par Codex

Depuis `eidolon-core/`, sur l'arbre corrigé :

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:. python -m unittest tests.test_core -v
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:. python -m unittest tests.test_review_regressions -v
```

- **34 tests Core existants réussis**, 16,440 s : [journal](validation/2026-10-05/codex-c-rev-001/core-tests.txt).
- **13 tests de régression réussis**, 9,222 s : [journal](validation/2026-10-05/codex-c-rev-001/regression-tests.txt).
- **6 intégrations Memory Engine réussies**, 0,901 s : [journal](validation/2026-10-05/codex-c-rev-001/memory-integration.txt).
  Copie isolée du moteur au commit `7d99ded07b7e10aa8029655ce4a939af6e0a6c44`,
  commande du README avec `EIDOLON_MEMORY_INTEGRATION=1`. Corpus temporaires créés
  par les services coordonnés ; fichiers métier comparés avant/après rappel.
  Dépôt moteur resté propre. Ce n'est pas une validation de sa dernière branche distante.
- **CLI de démonstration humaine réussie** : [sortie](validation/2026-10-05/codex-c-rev-001/demo-human.txt),
  70 caractères, 72 octets, source UNVERIFIED et revue requise conservées.

Les 34 tests sous Python 3.13.16 rapportés par Claude concernent la base avant
corrections ; ne pas les compter comme une validation Python 3.13 de ce lot.
Aucun test VM, Windows, réseau, GPU ou modèle réel n'a été exécuté.

## Choix et limites assumés

- **F-02 : correction bornée**, sans magasin d'artefacts pour l'instant. Le plan
  autorise cinq reçus de moins de 1 Mo. Les sorties restent dans SQLite ; les
  gros documents/médias demanderont des objets référencés, des budgets et une
  politique de rétention avant leur prise en charge.
- **F-04 : exclusion locale**, pas `PR_SET_PDEATHSIG`. Le verrou et le protocole
  prêt/autorisation couvrent la course avant lancement sans confondre disparition
  du parent et arrêt de l'enfant. Les PID sont diagnostiques. Un enfant peut
  continuer son effet après la mort du parent ; c'est la réconciliation permettant
  une reprise qui est bloquée. Aucun contrôle des descendants/services distants.
- Les appels antérieurs sans verrou de worker ne peuvent pas activer de reprise
  (`no-effect` / `observed-result` refusés) ; `abandon` reste disponible. Ne pas
  copier/déplacer un état actif ou supprimer ses verrous. Stockage local coopératif.
- **F-06 : transit atomique**, pas journal durable supplémentaire. Le dossier
  temporaire privé peut subsister après SIGKILL du parent. Le reçu ne devient
  durable que dans SQLite ; aucune récupération implicite du fichier temporaire.
- Un reçu tardif n'est pas effacé par `no-effect` ; choisir un résultat observé
  à vérifier ou abandonner. Les propositions sans décision n'expirent pas.
- Aucun changement des permissions : seul l'outil pur livré est autorisé.
  Le test d'orphelin simule un effet par un marqueur dans son dossier temporaire.

## Suite

C-001 reste la prochaine tranche : critères indépendants de la proposition du
modèle, issue métier distincte de l'état d'exécution et cas rouges A–D. Les
[30 cas proposés par Claude](validation/2026-10-05/claude-c-rev-001/cas-rouges-A-D.md)
sont des spécifications proposées, pas 30 tests implémentés. Les contributions
au brainstorming ne sont pas automatiquement devenues des décisions utilisateur.
Le choix tentative/successeur, les tours de planification et les classes d'effet
restent à travailler dans les lots correspondants. Une nouvelle revue des
frontières worker/reçu/réconciliation est demandée à Claude.
