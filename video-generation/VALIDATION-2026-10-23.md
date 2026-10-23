# Validation des corrections vidéo — 23 octobre 2026

Base relue : PR #2, branche `claude/video-generation-v100`, commit
`ba237a81b253f1d3670dabd2a52fabfe1a55b971`.

## Résultat

**28 tests PASS**, Python 3.12.14, sans GPU ni téléchargement de modèles.
Commande :

```bash
python3 -m unittest discover -s video-generation/tests -v
```

`bash -n` valide les deux scripts et `sources.lock`. `git diff --check` passe.
ShellCheck n'est pas installé dans cet environnement : aucun résultat ShellCheck
supplémentaire n'est revendiqué.

## Corrections et preuves

- **Mémoire Ollama** : `keep_alive: 0` par défaut. Tests du payload, du repli HTTP
  400 sans `think` et de l'option de conservation sur GPU séparé. Une vraie
  libération de VRAM n'a pas été mesurée ; d'autres modèles/requêtes peuvent
  encore occuper le GPU.
- **Fichiers de sortie** : rejet des chemins Unix/Windows, traversées et noms
  invalides ; création exclusive refusant écrasements et liens symboliques.
  Lecture par blocs et nettoyage sur erreur. Tests avec fichiers temporaires,
  symlink, fichier préexistant et erreur de transport simulée.
- **Paramètres** : rejet des géométries invalides, nombre d'images hors 4n+1,
  FPS invalides, délais non finis, entrées `--set` inconnues et passes High/Low
  vides. Vérification des trois graphes, de leurs dry-runs et des frontières
  de débruitage pour 2, 3, 4, 20 et 31 étapes.
- **Suivi** : une entrée d'historique sans `completed: true` n'est plus traitée
  comme un succès. Les erreurs d'exécution remontent ; le timeout précise
  que la tâche distante n'est pas annulée.
- **Versions** : torch fixé à `2.14.0+cu126` ; contraintes torch/torchvision/
  torchaudio enregistrées dans la configuration pip du venv et l'environnement
  du service. Test avec un exécutable pip simulé, sans installer PyTorch.
- **Sources** : ComfyUI et quatre extensions fixés à des SHA dans `sources.lock`.
  Un dépôt Git temporaire réel vérifie le retour à la révision fixée et le
  refus de modifications locales suivies. Les dépendances Python transitives
  et les modèles distants restent sans verrou complet de versions/hashes.
- **Installation** : les paquets sont installés avant l'utilisation de curl ;
  `pip check` et validation GPU précèdent la création/activation du service.
  Tests de l'ordre et de l'arrêt sur échec, avec fonctions système simulées.
- **Test GPU de l'installateur** : chaque GPU visible reçoit une multiplication
  fp16 ; les NaN/Inf provoquent un échec. La logique a été testée avec un faux
  module torch à deux GPU et un résultat non fini, pas sur CUDA réel.
- **Documentation** : retrait du gain garanti de 5×, précision des limites
  mémoire et du fonctionnement sur un seul GPU des trois workflows.
- **Hygiène** : suppression du `.pyc` suivi et ajout des exclusions Python locales.

Un faux serveur HTTP a exécuté le parcours client en sous-processus : appel
Ollama, soumission `/prompt`, lecture `/history`, récupération `/view` et
vérification du contenu téléchargé. Le fichier de ce test est un payload
simulé, **pas une vidéo générée**.

## Limites et recette restante

La tentative de diagnostic sur Core a échoué avant exécution : le connecteur
Eidolon demande une réauthentification (`UNAUTHORIZED`,
`oauth_refresh_token_missing`). Aucun changement n'a été appliqué aux VM.

Non effectués : installation réelle complète, résolution des dépendances dans
le venv cible, démarrage ComfyUI, validation serveur des graphes, chargement
UMT5 FP8/GGUF/LoRA, génération et décodage vidéo, mesures de temps, de RAM et
VRAM, test multi-GPU/NVLink. Les SHA fixés rendent les sources identifiables ;
ils ne certifient pas leur compatibilité matérielle.

La PR doit rester expérimentale et en brouillon jusqu'à la recette V100.
Le README fournit une première génération 5B courte à graine fixe, puis une
progression vers les profils normaux et le 14B. Les trois workflows restent
sur un GPU ; aucun partage automatique de 64 Go n'est ajouté.
