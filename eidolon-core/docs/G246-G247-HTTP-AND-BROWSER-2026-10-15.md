# G246/G247 — Trajet HTTP complet et qualification navigateur

15 octobre 2026, Codex/GPT. Core base 2fc0564a9228beb358723423cf7cc97155128f1f.
Memory épinglé : 2b64d1e48ecc7b0769c5e724ea94f831c0d3fb6b.

G246 assemble réellement les composants : Markdown temporaire, Qdrant local,
ContextualRecall, serveur HTTP borné, jeton synthétique dans un fichier privé,
BridgeMemory et Dialogue. Aucun mock du transport ou du client. Trois tours
vérifient le rappel vide périmé, la reconstruction concordante avec citation,
puis la dérive à révision inchangée sans citation. Le modèle de dialogue et
l'embedding restent synthétiques ; aucune pertinence sémantique n'est revendiquée.
Test local réussi avec -W error. CI complète à confirmer.

G247 ajoute un workflow indépendant pour Chromium avec Playwright 1.62.1
(version présente dans le runtime examiné). Navigateur officiel installé dans
le runner jetable, précontrôle bloquant si Python/navigateur manque. Le test
local du précontrôle a effectivement échoué faute de binaire Chromium.
Le bundle app.js doit correspondre aux sources. Les suites connected et
integration tournent avec concurrence 2 ; le rapport TAP doit indiquer zéro
exclusion, sinon le workflow échoue. Captures et rapport conservés sept jours.
Aucun serveur du domicile, compte utilisateur ou navigateur personnel utilisé.

Cette recette comble une limite réelle du premier workflow Node : 140 réussis,
26 ignorés, sur 166 recensés. Le précédent texte « 166 réussis » est corrigé
explicitement dans le bilan G244. Les anciens succès Python/Node ne prouvaient
pas les 26 parcours Chromium. La nouvelle recette n'est pas déclarée verte
avant récupération de ses résultats.

## Résultat distant confirmé

Le workflow initial 38681782990 a exécuté les 172 tests, puis échoué uniquement sur le contrôle final utilisant `rg`, absent du runner. Remplacement par Node, déjà prérequis. [Réexécution 38682562906](https://github.com/toytoy68/Eidolon-Bootstrap-Framework/actions/runs/38682562906) sur Core `d56a65c96c0dd8da814733daac2d7a308ef81e1b` : **172 réussis, 0 échec, 0 ignoré**, workflow vert. Les six tests d'intégration supplémentaires expliquent le passage de 166 recensés à 172. Aucun test ignoré n'est compté comme exécuté. La qualification Python complète et les limites restent détaillées dans le [bilan courant](PROJECT-STATUS.md).
