# G181 — Mémoire canonique et accès Internet attendu
Auteur : Codex/GPT. Date : 12/10/2026, Europe/Paris.
Base Core : f9103cf52cfd9b7a99ce052f8dd1682fdb46f634.
Demandes toytoy : poursuivre P0 Memory ; confirmer l'accès Internet au besoin.

## Memory
Lot publié : deff13647a8a5db7ee856966092fc91acf6c1cf4, branche refactor/architecture-v1.
[Rapport](https://github.com/toytoy68/Eidolon-Memory-Engine/blob/deff13647a8a5db7ee856966092fc91acf6c1cf4/docs/QDRANT-CANONICAL-G181-2026-10-12.md).
ContextualRecall peut recevoir un index choisi par le serveur. Les candidats
sont relus depuis le Markdown ; absence/révision différente exclues avant les
filtres canoniques et budgets. Défaut lexical inchangé. Pas d'activation bridge.
2087 tests + 12 sous-tests sur Core isolé ; trois scénarios de rappel contre
Qdrant HTTP 1.15.4. Serveur temporaire arrêté. Corpus synthétiques uniquement.
Ces résultats ne résolvent pas encore paraphrases/abstention : embeddings réels,
passages d'archives et synchronisation restent à faire.

## Internet : capacité attendue et état constaté
La capacité de consulter Internet au besoin fait partie du résultat demandé.
La machine Core dispose d'un accès sortant : les fetch GitHub réels l'utilisent.
Cela ne signifie pas que le modèle de dialogue possède un outil Web utilisable.

Inspection du code installé, 12 octobre :
- research_runtime.py utilise SyntheticResearchBackend et des fixtures fixes.
- La politique research-sim reste local_synthetic_state, sans permission Web.
- research.py, web_transport.py et web_reader.py fournissent des briques de
  coordination/lecture, avec provenance, contrôles de destination et HTML.
- Aucun fournisseur de recherche Internet réel n'est raccordé dans ce parcours.
- Le lecteur actuel n'est pas un navigateur général : pas de rendu JavaScript
  complet ni de session connectée aux sites.

Suite à réaliser : sélectionner/raccorder un fournisseur, relier l'outil réel
au dialogue/aux missions et tester des recherches publiques avec leurs sources.
Ne pas annoncer une recherche réelle sur la seule base des fixtures.
Ne transmettre au fournisseur que la requête utile ; la mémoire privée ne doit
pas devenir automatiquement le contexte envoyé à un service externe.

L'accès Web sortant d'Eidolon est distinct de l'accès entrant du téléphone.
Consulter Internet ne nécessite pas d'ouvrir un port entrant sur la Freebox.
WireGuard reste le choix pour l'accès distant utilisateur ; MCP reste le canal
de collaboration actuellement disponible.

## Répartition conservée
Codex : P0 Memory (passages/embeddings, synchronisation, bridge), intégration
et recette VM du dashboard C154. Le raccordement Web réel reste explicitement
ouvert ; aucun travail d'identité ne doit faire passer Memory au second plan.
Claude : reprise différée par toytoy faute de tokens (information utilisateur).
L'œil du dashboard reste son lot : références fournies par toytoy, iris bleu/cyan,
anneaux concentriques segmentés. L'état caméra reste distinct de l'activité.
Aucun message du dépôt ne lance une session.
