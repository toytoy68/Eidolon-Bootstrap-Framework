# Exploitation locale du prototype

Eidolon Core Technologies (ECT), 12 novembre 2026. Recette isolée, pas une
installation de production. Aucun accès distant ajouté. Toutes les commandes
de cette page sont des actions opérateur explicites, jamais exécutées par une requête API.

## Emplacements et identité

- Travail : `/srv/eidolon/workspaces/media-20261112` (LAB ci-dessous).
- Code : `LAB/source/eidolon-core/src`, environnement : `LAB/venv`.
- Moteur : `LAB/engine`, ComfyUI 0.3.26 au SHA documenté.
- Poids : `/srv/eidolon/models/media-20261112`, lien `engine/models`.
- Données : `/srv/eidolon/data/media-20261112/{input,output,temp,artifacts}`.
- Métadonnées privées : `LAB/api/jobs.sqlite3`. Jeton : `LAB/token`, 0600.
- Catalogue : `LAB/registry.json`, hashes vérifiés au démarrage de l'API.
- Unités transitoires : `eidolon-media-comfy-20261112.service` et
  `eidolon-media-api-sdxl-20261112.service`, exécutées sous `toytoy`.
  Cette API remplace l'unité finale G325/G326 lors de G327 ; voir [SDXL](SDXL.md).

La séparation des volumes a été contrôlée par lecture d'un résultat antérieur
et génération d'un nouveau résultat via LocalGenerationClient. Ne pas remplacer
le dossier artifacts par un lien symbolique : passer `--artifact-root`.
Les unités ne démarrent pas automatiquement après reboot. Ne pas redémarrer
l'hôte pour les tester. La limite GPU1 a été fixée à 200 W ; GPU0 reste à 300 W.

## Installation initiale reproductible

1. Vérifier GPU libres, entraînements, services, stockage et licences. Ne pas
   installer de pilote ni remplacer torch dans un environnement existant.
2. Créer un environnement Python 3.12 distinct, cloner ComfyUI et checkout
   `9aac21f894a122ddb8d825c57ad61c0db5e630db`. Installer torch 2.6.0,
   torchvision 0.21.0, torchaudio 2.6.0 depuis l'index PyTorch cu124.
3. Installer les autres versions de `requirements-observed.txt` dans cet
   environnement uniquement. C'est un inventaire testé, pas un lockfile avec
   hashes ni une garantie que les index garderont chaque roue. Le frontend
   1.11.8 demandé par cette ancienne release n'était pas disponible ; 1.12.8
   a été installé et testé. Ne pas laisser pip mettre torch à jour implicitement.
4. Examiner `download_models.py --help`, puis télécharger explicitement les
   profils choisis vers le dossier modèles. Le script fixe révisions, tailles
   et SHA256 ; il ne lance aucun code de modèle. Préserver les reçus et licences.
   Un fichier partiel préexistant n'est pas silencieusement remplacé : vérifier
   sa taille/hash avant une reprise manuelle.
5. Créer le jeton localement avec `secrets.token_urlsafe(32)`, umask 077 ; ne
   jamais le placer dans Git, une URL ou une commande affichée dans les logs.
6. Lancer les deux services avec les paramètres ci-dessous. Attendre /health
   authentifié : le calcul des hashes des modèles peut retarder le démarrage.

Connexions initiales utilisées : github.com (sources), pypi.org et
files.pythonhosted.org (roues), download.pytorch.org (roues CUDA),
huggingface.co et CDN de redirection indiqué dans chaque reçu (poids).
Pas de modèle supplémentaire téléchargé au démarrage ou pendant une génération.
Préparer un miroir local des roues avant de promettre une réinstallation hors
ligne ; seule l'exécution hors ligne est validée ici.

## Paramètres du moteur et du service

Moteur : `--listen 127.0.0.1 --port 8189 --force-fp16 --fp32-vae
--fp16-text-enc --disable-xformers --use-split-cross-attention
--disable-all-custom-nodes --disable-auto-launch --disable-metadata
--deterministic --reserve-vram 2`.

Environnement : `CUDA_VISIBLE_DEVICES=GPU-c9d9173f-6303-6998-7a60-a379b9a0d60b`,
`OMP_NUM_THREADS=4`, `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`,
`HF_HUB_DISABLE_TELEMETRY=1`. Systemd : CPUQuota=800%, MemoryMax=48G,
TasksMax=128, UMask=0077, NoNewPrivileges=yes, IPAddressDeny=any et
IPAddressAllow=localhost. L'interdiction réseau est une propriété du cgroup,
pas seulement une variable d'environnement.

API : `python -m eidolon_core.media_service --root LAB/api
--artifact-root /srv/eidolon/data/media-20261112/artifacts --token-file LAB/token
--inputs /srv/eidolon/data/media-20261112/input --gpu-uuid GPU-c9d9173f-6303-6998-7a60-a379b9a0d60b
--engine-pid PID --registry LAB/registry.json
--models-root /srv/eidolon/models/media-20261112 --enable sd15-text
--enable sd15-edit --enable sd15-inpaint --enable wan21-text --enable svd-image`.
Remplacer LAB par le chemin absolu et PID par le MainPID actuel du moteur,
obtenu avec `systemctl show ... -p MainPID --value`. Ne pas réutiliser un ancien
PID après redémarrage. API : PYTHONPATH vers source/eidolon-core/src, CPUQuota=200%,
MemoryMax=2G, TasksMax=64 et mêmes protections réseau/umask/privilèges.

Le moteur est une instance exclusivement dédiée : son endpoint `/interrupt`
est global. Ne pas le partager avec des utilisateurs ComfyUI externes.
Ces restrictions n'isolent pas complètement les processus ayant le même UID.
Un compte système média distinct et des ACL multi-utilisateur sont à préparer
avant déploiement familial. Aucun chiffrement au repos n'a été ajouté.

## Contrat HTTP v1

Les options facultatives `format` et `output_size` sont décrites dans
[Formats écran](DISPLAY.md). Elles séparent calcul GPU et dimensions du fichier final.

Toutes les routes exigent `Authorization: Bearer <jeton>`. Les requêtes avec
Origin sont refusées. Les POST exigent JSON et Content-Length unique. Pas de
chemin utilisateur libre, de nœud Comfy arbitraire, de URL de modèle ou de plugin.

| Route | Réponse |
| --- | --- |
| GET /health | 200, identité et experimental=true |
| GET /v1/models | 200, profils activés et catalogue revu |
| POST /v1/assets | 201, référence privée, corps png_base64 ; PNG décodé/réencodé |
| POST /v1/jobs | 202, identifiant et état ; Idempotency-Key obligatoire |
| GET /v1/jobs | 200, historique sans prompt dans le statut |
| GET /v1/jobs/{id} | 200, état/progression observée/résultat |
| GET /v1/jobs/{id}/metadata | 200, paramètres et graphe privés complets |
| GET /v1/jobs/{id}/result | 200 PNG ou MP4 après succès vérifié |
| POST /v1/jobs/{id}/cancel | 200, état ; {} ; interruption active confirmée ensuite |

Authentification refusée : 401. Erreurs de contrat : 400 avec code stable.
Ne pas interpréter CANCEL_REQUESTED comme une annulation déjà terminée.
Progression = étape/nœud et nombre d'itérations connus, pas estimation du temps restant.

Exemple Python depuis l'hôte, avec PYTHONPATH configuré :

```python
from pathlib import Path
from eidolon_core.media_service_client import LocalGenerationClient
c = LocalGenerationClient('http://127.0.0.1:8190',
    Path('/srv/eidolon/workspaces/media-20261112/token').read_text().strip())
job = c.submit({'profile':'sd15-text', 'prompt':'A mountain lake at sunrise',
    'width':512, 'height':512, 'steps':20, 'seed':42},
    idempotency_key='lake-001')
print(c.status(job['id']))  # récupérer c.result seulement après SUCCEEDED
```

Pour img2img, utiliser `source=c.upload_png(bytes_png)`. Pour inpaint, ajouter
`mask` : PNG noir hors zone, blanc dans la zone, même géométrie que la sortie.
Pour Wan : profil wan21-text, width=320, height=256, frames=17, fps=8.
Pour SVD : profil svd-image, source requise, frames=14, fps=7, steps=15.
SVD n'interprète pas de prompt textuel. Ne pas promettre une modification précise
à partir de la seule réussite technique du job.

## Catalogue, politique locale et confidentialité

Catalogue opérateur `schema=eidolon-media-models/1`, dictionnaire entries indexé
par identifiants locaux. Champs obligatoires : type checkpoint/lora, family sd15,
filename safetensors, sha256, license, source, approved_uses, reviewed=true.
Le booléen reviewed atteste une revue humaine ; il ne prouve pas juridiquement
une licence. Les chemins sont bornés aux dossiers checkpoints/loras. Au plus
deux LoRA par requête, strength entre 0 et 1. Le catalogue générique est testé ;
aucun LoRA n'a été installé ni validé matériellement dans cette campagne.

La configuration des profils et modèles autorisés est locale, sans modération
cloud ni dépendance à un fournisseur. Aucun mécanisme spécialisé de génération
sexuelle explicite n'est livré. Les prompts privés restent dans SQLite et dans
les preuves locales du benchmark ; ne pas exporter /metadata vers la mémoire
sémantique ou un journal distant. L'API ne fait aucune écriture Memory Engine.
Comfy --disable-metadata évite d'insérer le workflow dans les PNG de sortie.

## Reprise, arrêt et nettoyage

Un état incertain devient REVIEW_REQUIRED et bloque la file. Avant de le résoudre,
examiner la queue/historique du moteur dédié et la base sauvegardée ; ne pas
reposter automatiquement un prompt. Aucun endpoint de résolution forcée n'est
livré. La file conserve au maximum 128 jobs et le magasin limite les artefacts ;
les sorties intermédiaires Comfy nécessitent encore une purge opérateur.

Avant suppression, établir une liste des références conservées, sauvegarder DB
et artefacts, attendre une queue vide, puis nettoyer seulement temp et les fichiers
non référencés du laboratoire. Pas de suppression récursive automatisée ici.
Ne pas faire tourner ces recettes en concurrence avec Eva. Le garde GPU observe
les PID et interrompt sa propre tâche lors d'un conflit, mais ne remplace pas
un ordonnanceur global atomique. Les services critiques ne sont jamais arrêtés.

Pour libérer les caches, uniquement queue dédiée vide : POST local moteur /free
avec unload_models=true et free_memory=true. Un changement du moteur impose
de réévaluer son PID dans l'API. Ne pas activer les unités au boot avant revue.
