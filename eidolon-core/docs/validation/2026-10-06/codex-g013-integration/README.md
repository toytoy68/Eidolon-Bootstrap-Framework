# Intégration Claude G013

Auteur : Codex/GPT, 06/10/2026, Europe/Paris. Source :
`deef553f47d3e80ae3d2504200726a01881f0a1e`, base Claude `476acc1`.
Diff modèle/rendu/tests et message C023 relus sur worktree isolé.
Fusion dans la branche Core après la livraison C-008c ; aucun fichier Python
modifié par cette fusion. Contributions Claude conservées sans réécriture.

Exécuté dans cette session, Node 24.19.0/Linux :

```sh
node --test desktop/prototype/tests/model.test.js desktop/prototype/tests/commands.test.js
node docs/validation/2026-10-06/claude-g013/probe-command-adapted.cjs
```

[28 tests réussis](model-tests.txt), [sonde adaptée réussie](probe.json),
[empreintes](source-hashes.json). La sonde originale ciblait client.command ;
sa disparition ne prouve pas le correctif. La copie adaptée conserve les deux
scénarios et exige maintenant que chaque clé reste suivie et consultable,
sans deuxième DECIDE. Cette adaptation a été lue avant exécution.

Correction constatée : commande incertaine conservée après revoke/cancel,
réponses associées à leur clé, doublons/clé inconnue ignorés, NOT_FOUND non
résolutif, rétention bornée pour les seules commandes résolues. Les réponses
restent des fixtures de prototype ; pas de validation d'un transport distant.
L'outbox complet est une trace de test non bornée, pas un mécanisme de file
persistante de production.

La capture Claude 08 a été inspectée : demande d'accord incertaine distincte
d'une révocation confirmée, avec bouton de consultation dédié. Le voyant
« En veille » sous-estime cette incertitude ; accord donné à Claude pour afficher
« Reçu à vérifier » dans G012 sans toucher au statut métier ni aux preuves.

**Non reproduit ici :** les 11 tests Playwright/UI de G013 (39/39 selon Claude),
Windows, Chromium interactif, accessibilité système. Il s'agit d'une inspection
d'une capture fournie, pas d'un nouveau rendu graphique. G012 reste le futur
consommateur du protocole de lecture Core ; le prototype n'est pas connecté.

La contre-vérification D3 est rapportée par Claude dans C023 ; notre reproduction
avant/après reste celle du lot précédent. Aucune nouvelle sonde Web ici.
