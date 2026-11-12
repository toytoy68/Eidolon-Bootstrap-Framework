# Boucle de préférences — G329

Eidolon Core Technologies (ECT) · 12 novembre 2026 · laboratoire expérimental.

## Autorisation et fonctionnement

Toytoy autorise GPT à examiner les prompts/images utiles au contrôle dans ChatGPT,
à gérer les jugements et à poursuivre les lots autorisés sans attendre une réponse
à chaque présentation. Génération et entraînement restent locaux. Cette exception
de confidentialité concerne les exemples nécessaires au contrôle ; elle n'ajoute
aucun service cloud au moteur et n'autorise pas une publication des images privées.

Un lot borné suit : collecte → inspection GPT → registre révisable → paires
compatibles → entraînement local isolé → comparaison sur demandes tenues à part
→ rapport. Les présentations sont informatives. Seuls les blocages techniques,
conflits de charge ou actes hors autorisation arrêtent le lot. Aucun mécanisme ne
lance de sessions ChatGPT en arrière-plan : l'examen GPT se fait pendant la session.

## Jugements et corrections ultérieures

Trois décisions : `ACCEPT`, `REJECT`, `UNCERTAIN`. Une validation signifie que
l'image passe la grille de ce lot, pas qu'elle est parfaite. Un rejet net doit
citer un défaut observé ; une anatomie douteuse sans certitude peut rester
incertaine. Pas de gagnant artificiel si toutes les images sont mauvaises.
L'avis GPT reste faillible, identifié comme tel, distinct d'une approbation humaine.

`media_feedback.py` fournit un registre privé en append-only : révision attendue,
chaîne de hashes, verrou d'écriture, identité immuable de l'image et priorité
des corrections utilisateur. Un nouvel avis conserve l'ancien ; GPT ne peut pas
écraser une décision utilisateur. La chaîne détecte une corruption, pas un
administrateur malveillant capable de tout recalculer. Pas d'endpoint ajouté.

À réception d'une correction, ajouter une révision `reviewer=user`, reconstruire
un snapshot et marquer les candidats dérivés de l'ancien hash comme obsolètes.
Un correctif de dataset **n'efface pas** un apprentissage déjà réalisé : le LoRA
concerné doit être réentraîné/revalidé. Les pilotes vérifient le hash des avis
avant et pendant l'exécution ; aucune promotion automatique n'est implémentée.

## Contrôle visuel renforcé après G329-02

Une main avec cinq doigts ne suffit pas pour être acceptée. Examiner à résolution
native les raccords doigts-paume, les espaces entre doigts, la continuité des
volumes et des plis autour des articulations, ainsi que la jonction pouce-paume.
Un pli isolé n'est pas une preuve anatomique ; un assemblage visuellement
incohérent élimine l'exemple positif. Si le défaut reste ambigu, classer INCERTAIN.
Séparer texture photographique convaincante et cohérence de structure. Ces
critères relèvent de la qualité d'image, sans revendication de validation médicale.

G330 applique la première correction réelle : révision13 et deux paires courantes.
Le candidat G329 reste archivé avec son invalidation, jamais comme parent promouvable.

## Construction des paires

Uniquement un accepté et un rejeté de confiance élevée, pour un même prompt,
modèle, géométrie et graphe de génération. Seuls seed et préfixe de sortie sont
neutralisés dans l'empreinte de configuration. Aucun mélange carré/16:9.
Les incertains et jugements de confiance insuffisante restent hors apprentissage.
Pas de produit cartésien : chaque image est utilisée au plus une fois par snapshot.
Les hashes des PNG sont revérifiés juste avant leur utilisation.

La séparation apprentissage/confirmation s'effectue par prompt, pas seulement
par seed ; partager un prompt ou une image entre les deux catégories est refusé.
Les demandes de confirmation préenregistrées dans QUALITY-PROTOCOL.md sont
vérifiées absentes des exemples d'entraînement. Les cas de collecte G328/G329
ne peuvent plus être revendiqués comme une évaluation indépendante du même thème.

## Environnement et pilote local

`prepare_preference_lab.py` est un **installateur explicite**, jamais appelé par
le service : copie indépendante du venv média, puis cinq roues PyPI officielles
figées, vérifiées contre leur SHA256 PyPI. Diffusers0.32.2, PEFT0.14.0,
Accelerate1.3.0, importlib_metadata8.6.1, zipp3.21.0 ; aucun changement torch/CUDA.
Configurations/tokenizers SDXL officiels à la révision déjà auditée
`462165984030d82259a11f4367a4eed129e94a7b`. Aucun nouveau poids de base téléchargé.
Le freeze du venv média d'origine est comparé avant/après. Reçus des téléchargements
et freeze du laboratoire conservés sur X399. PyPI et Hugging Face ne servent
qu'à l'installation ; les étapes d'entraînement/comparaison sont bloquées hors
localhost par cgroup, avec chargement exclusivement local et télémétrie HF désactivée.

`preference_pilot.py` réalise six tentatives de mise à jour LoRA de rang4 à1e-5,
beta DPO1000, batch d'une paire. Les poids de base sont gelés ; seuls les modules
LoRA q/k/v/out sont entraînables, en FP32, sur un UNet de base FP16. VAE FP32,
latents encodés de manière déterministe, textes précalculés ; gradient checkpointing
et attention découpée. Pas de BF16/FP8/xFormers/FlashAttention, pas de compilation.

La perte compare la différence d'erreur de débruitage préféré/rejeté au modèle
de référence (adaptateur désactivé). Même bruit et même timestep dans chaque paire.
Objectif inspiré de [Diffusion-DPO, CVPR2024](https://openaccess.thecvf.com/content/CVPR2024/html/Wallace_Diffusion_Model_Alignment_Using_Direct_Preference_Optimization_CVPR_2024_paper.html).
Implémentation de référence lue : Diffusers au commit
`560fb5f4d65b8593c13e4be50a59b1fd9c2d9992`, fichier
`examples/research_projects/diffusion_dpo/train_diffusion_dpo_sdxl.py`, SHA256
`14b44b76929e86e85b5ce4ffbf0252c901fea5a446dcf281d9e748d388019adc`.
Le script amont n'a pas été exécuté : ses publications Hub/WandB ne font pas
partie du pilote. La méthode et les scripts demeurent expérimentaux.

Le pilote n'est **pas** une recette de production ni une preuve de gain visuel.
Trois paires ne permettent pas de qualifier une amélioration générale. Il vérifie
que pertes/gradients restent finis, que les mises à jour ont un effet et qu'un
adaptateur safetensors peut être exporté puis rechargé. Tout candidat porte
`promotion_allowed=false` ; il n'est pas installé dans ComfyUI ni dans l'API.

## Garde-fous

Une V100 dédiée, consigne200W inchangée, consommation suivie. Démarrage seulement
à files vides et sans client GPU étranger. Plafond d'allocation PyTorch85% de la
carte ; processus40G RAM/6cœurs équivalents ; délai d'unité30min. Sondes des trois
GPU et CPU ; interruption contrôlée entre opérations si autre client GPU,
GPU≥65°C, HBM≥70°C ou erreur de sonde. Un kernel déjà en cours n'est pas préempté
instantanément. Le contrôle reste coopératif, pas un verrou global contre Eva.
Le chemin des modèles est monté en lecture seule dans les unités transitoires.

Une erreur/OOM/gradient non fini arrête le pilote et conserve un rapport d'échec.
Aucune relance automatique. Des pertes sur des bruits/timesteps différents ne
doivent pas être interprétées comme une courbe de qualité ou de progrès monotone.

## Commandes et données

Les scripts sont dans ce dossier. PYTHONPATH pointe sur `eidolon-core/src`.
Exécuter les calculs via une unité transitoire non privilégiée, limitée à localhost,
CUDA_VISIBLE_DEVICES=UUID GPU1, HF_HUB_OFFLINE=1, TRANSFORMERS_OFFLINE=1.

1. `feedback_collect.py --root LAB --output LOT --engine-pid PID` :12 images.
2. Inspection réelle ; rédiger les décisions, sans les déduire des métriques.
3. `feedback_build.py --campaign LOT --decisions AVIS.json --output DATASET`.
4. `preference_pilot.py --root LAB --dataset DATASET/dataset.json --output PILOT --engine-pid PID`.
5. `preference_compare.py --root LAB --dataset DATASET/dataset.json --pilot PILOT --output COMPARAISON --engine-pid PID`.

`LAB=/srv/eidolon/workspaces/media-20261112`. Les sorties doivent être nouvelles :
refus d'écrasement/reprise aveugle. Les étapes4/5 utilisent le Python distinct de
`LAB/preference-lab/venv`. Chaque opération est explicite ; les fichiers de revue
ne déclenchent ni entraînement ni publication. Résultats réels : PREFERENCE-RESULTS.md.
