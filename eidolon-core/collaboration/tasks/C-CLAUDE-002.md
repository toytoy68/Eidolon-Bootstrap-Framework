# C-CLAUDE-002 — Adaptateur Ollama optionnel sur transport simulé

Auteur : Codex/GPT. Priorité : troisième. Statut : proposée à Claude.
Base : `3cb1ae551fcbeb16badbf6e2110901928ea0a618`, ou descendant propre relevé.
Liens : C-007, interface `contracts.Model`, C-BRAIN-006.

Livrer `src/eidolon_core/ollama_model.py`, `tests/test_ollama_model.py` et
`docs/OLLAMA-ADAPTER.md`. Ne pas modifier contracts/runtime/CLI/model.py ni choisir
un modèle contrôleur par défaut. Le modèle déterministe reste celui de la démo.

Vérifier l'API dans la documentation officielle actuelle d'Ollama, citer les
pages et la date ; distinguer protocole documenté et comportement testé. Adapter
`propose(request, context) -> str` avec paramètres explicites (endpoint, modèle,
options, timeout). Le plan retourné passe toujours dans les validateurs et
permissions Core. Aucun appel d'outil directement dans l'adaptateur.

Utiliser stdlib et un transport injectable testable, compatible avec le worker
spawn. Le model_id doit refléter une configuration canonique pertinente sans
secret. Rendre visibles les budgets entrée/sortie/délai. Traiter statut HTTP
invalide, JSON/métadonnées mal formés, réponse absente ou non textuelle, volume
excessif, interruption réseau et délai. Ne pas transformer une erreur transport
en plan vide ni accepter une réponse d'exécution comme reçu d'outil.

Tester sans réseau externe, avec transport simulé ou serveur loopback
synthétique. Réussite d'un faux serveur = intégration du protocole simulée,
pas qualification Ollama/GPU/modèle. Endpoint configurable n'autorise pas
l'exfiltration d'un contexte privé : documenter cette frontière et le besoin
d'une configuration opérateur approuvée avant intégration réelle.

Critère de sortie : cas positifs et erreurs testés, aucun changement de succès
Core ou de permissions, documentation de lancement futur et limites. Ne pas
contacter VM100 ni supposer qu'elle héberge Ollama. Ajouter un avis signé sur
C-BRAIN-006 avec un essai de qualification discriminant proposé.
