# Agents Image/Vidéo — C-047/C-048, 08/10/2026 au soir

Auteur : Codex/GPT. Demandes toytoy : deux accès d'accueil, création/modification
et analyse ; délégation complète du chat/conversation/mission à Claude.
Base initiale a813f37566daf6f29fc3e48f0e9503e2cc55b0bc ; tâches G084–G089
publiées séparément dans c1a5f7c4974c790995aa27676ef70b28f025b1cf.

## Résultats réellement exécutés

| Vérification | Résultat |
| --- | --- |
| Nouveaux tests Python média | 19 réussis, aucun ignoré ; python-tests.txt |
| Suite client connecté + intégration HTTP | 65 réussis, 15 Chromium non exécutés ; client-tests.txt |
| Install local du paquet | Succès, install.txt ; aucune installation système/moteur/modèle |
| Comparaison paquet/sources | 58 modules identiques ; installed-check.json |
| CLI installée | Catalogue, préparation, analyse, génération, inspection et polling vérifiés avec API loopback simulées |
| Doublon de travail | Nouveau lancement dans le même dossier refusé avant second appel |
| Extraction vidéo | FFmpeg réel sur clip synthétique d'une seconde ; sortie d'analyse simulée |
| Assets | build.js --check et git diff --check réussis |
| CLI Core existante | presentation-preview exécuté depuis le paquet installé |

Commandes depuis eidolon-core :

```sh
PYTHONPATH=src:. python -m unittest tests.test_media_agents -v
node --test desktop/connected/tests/*.test.js desktop/connected/tests/integration/*.test.js
node desktop/connected/build.js --check
/chemin/venv/bin/python docs/validation/2026-10-08/codex-media/installed_check.py
```

Les tests média couvrent les six opérations, fichiers bornés/non réguliers,
source requise, endpoints locaux, workflow absent, substitutions contrôlées,
reçu de queue mal formé, intention préalable, interruption/réponse perdue,
réponse Vision tronquée ou autre modèle, polling sans renvoi, et vrai HTTP
loopback avec redirection refusée. Aucune API de moteur réel ni donnée personnelle.

Les nouveaux tests client couvrent la navigation et le focus sur un DOM de test,
les six modes, l'invalidation du brouillon, l'effacement et le texte non interprété
comme HTML. Le test Chromium est présent mais **non exécuté**. Une tentative
d'installation de Chromium a échoué (archive téléchargée invalide), donc aucune
capture ni validation visuelle navigateur n'est revendiquée. Les 14 anciens
cas Chromium et le nouveau restent ignorés, séparément des 65 tests réussis.
La suite Python complète historique de 971 tests n'a pas été rejouée dans ce lot.

## Livraison et limites

[Contrat et installation](../../../MEDIA-AGENTS.md). Agents Python natifs et CLI
installés et éprouvés dans un venv local ; aucune installation VM/Windows,
aucun poids téléchargé, aucun service GPU lancé. Les formulaires ne transmettent
ni contenu média ni commande. Backend ComfyUI avec workflows opérateur/staging
manuel, analyse vidéo partielle sans audio. Pas de galerie, téléchargement de
sortie vérifiée, catalogue de missions, worker partagé ou ordonnanceur GPU livré.
Ces frontières restent explicites plutôt qu'une fausse exécution depuis l'accueil.
