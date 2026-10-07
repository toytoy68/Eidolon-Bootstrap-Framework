# C-021 — raccordement recherche/runtime sur fixtures

Codex/GPT, 07/10/2026. Base locale 069ca57, Python 3.12.14/Linux.
Aucun fournisseur réel, modèle réel ou machine utilisateur contacté.

## Résultats reproduits

| Vérification | Résultat | Preuve |
| --- | --- | --- |
| Suite Python finale | 733 réussis, 6 optionnels ignorés (739 découverts) | final-tests.txt |
| Contrats/reprises recherche | 18 réussis | research-tests.txt |
| Intégration Memory Engine | 6 réussis | memory-integration.txt |
| Wheel installé en venv temporaire | 42 modules identiques aux sources, 24 contrôles bêta | package-smoke.json |
| Profil installé research-sim | Deux pages, succès, reprise inchangée, un historique nettoyé lié | package-smoke.json |
| Client Node, avant C-021 (client inchangé) | 49 réussis, 12 Chromium ignorés | ../codex-beta-hour/node-tests.txt |

Commandes : `PYTHONPATH=src python -m unittest discover -s tests -q`,
`PYTHONPATH=src python -m unittest tests.test_research_runtime -q`,
`python docs/validation/2026-10-07/codex-research-runtime/research-package-smoke.py`.
Le script construit sans téléchargement, installe sans dépendance externe,
compare chaque module puis utilise les exécutables installés. Tous les états
et sockets loopback de la recette sont temporaires et nettoyés.

Mémoire : source de référence isolée 7d99ded07b7e10aa8029655ce4a939af6e0a6c44,
six cas opt-in sur corpus synthétiques. Aucun fichier du dépôt mémoire modifié.
`full-tests.txt` conserve la première passe (738 tests), remplacée pour le verdict
par `final-tests.txt` après ajout du cas de journal occupé.

## Garanties exercées

Le modèle et la mémoire ne peuvent remplacer la requête, le nombre de pages
ou l’identité de mission. Le rapport est lié à une intention achevée et son
empreinte est relue sans appel fournisseur. Un rapport modifié ou celui d’une
autre mission est refusé. Le budget réserve la vérification ; annulation et
coupures ne relancent pas aveuglément une recherche. Une garde occupée conserve
le résultat reçu et permet de réessayer seulement la vérification.

La réussite décrit une récupération de fixtures, jamais la vérité des textes.
Le partiel/vide garde les preuves et bloque l’objectif. Aucun droit réseau
n’est accordé. La requête originale reste dans la mission privée ; seul
l’historique spécialisé contient exclusivement le texte nettoyé.

## Limites

Pas de recette Windows, VM, SSH réel, coupure électrique ou navigateur ici.
La garde est limitée à 256 recherches et G057 prépare encore sa rotation.
Contre-revue indépendante de C-019/C-021 encore à réaliser. Les sources
synthétiques ne qualifient ni un fournisseur Web ni un modèle réel.
