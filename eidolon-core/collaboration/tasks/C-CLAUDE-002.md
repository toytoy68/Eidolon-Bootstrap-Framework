# C-CLAUDE-002 — Étude 2 × V100/NVLink puis adaptateur candidat

Auteur : Codex/GPT. Priorité : troisième. Statut : proposée à Claude.
Base : `3cb1ae551fcbeb16badbf6e2110901928ea0a618`, ou descendant propre relevé.
Liens : C-007, interface `contracts.Model`, C-BRAIN-006/007.

**Révision du 05/10 à la suite de toytoy (14 h 23, Europe/Paris)** : matériel
prévu **2 × V100 32 Go avec NVLink**. La première étape est désormais l'étude de
compatibilité et du partage GPU ; Ollama reste un candidat, pas le moteur acquis.
Cette révision prévaut sur l'intitulé initial de C-MSG-006.

### Étape 1 — Rapport de décision et protocole de qualification

Lire [la note matérielle et ses sources](../../docs/INFERENCE-2XV100-2026-10-05.md).
Livrer `docs/INFERENCE-RUNTIME-COMPARISON.md` avec une matrice sourcée : Ollama,
llama.cpp serveur et éventuellement une autre solution seulement si son support
Volta/compute 7.0 est démontré pour une version précise. vLLM actuel annonce 7.5+
à la date de notre lecture : ne pas l'annoncer compatible par défaut.

Distinguer GPU détecté, kernels/quantification compatibles, modèle effectivement
réparti et avantage NVLink mesuré. Identifier version du moteur, CUDA/driver,
format de poids, précision/cache, budget VRAM par GPU, contexte et parallélisme.
Précision de toytoy à 14 h 28 : **deux modules SXM2 sur carte adaptatrice PCIe,
NVLink câblé sur son PCB**. Analyser cette architecture, pas deux cartes V100 PCIe
standard. Référence/révision de l'adaptateur, liens effectivement câblés, exposition
hôte/VM et passthrough restent à relever sans les inventer ni bloquer le rapport.

Proposer une recette comparative ultérieure : un modèle sur un GPU ; un même
modèle partagé sur deux ; deux rôles indépendants avec un GPU chacun. Mesurer
qualité métier, temps du premier token, débit, VRAM par GPU, consommation,
repli CPU et erreurs. Tous ces résultats matériels restent **NON MESURÉS** ici.
Aucun téléchargement de poids ni accès aux machines. Décrire un manifeste de
mesure reproductible, sans présélection arbitraire d'un contrôleur.

### Étape 2 — Adaptateur de protocole isolé

Un adaptateur Ollama simulé peut être livré comme **candidat optionnel** si l'étude
ne révèle pas d'incompatibilité bloquante ; cela ne qualifie pas son efficacité
sur deux V100. Si l'étude justifie un autre protocole, proposer le raccordement
et un fichier propre avant de toucher aux modules communs. Core reste indépendant
et aucun fournisseur n'est activé dans la CLI de ce lot.


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
