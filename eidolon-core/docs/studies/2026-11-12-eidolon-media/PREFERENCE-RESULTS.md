# Premier cycle de préférences réel — G329

12 novembre 2026 · Eidolon Core Technologies (ECT).
**La boucle technique fonctionne sur V10016Go. Aucun gain visuel général établi ;
le candidat, jamais promu, est désormais invalidé après correction utilisateur.** [Méthode](PREFERENCE-LOOP.md),
[jugements explicites](feedback-g329-decisions.json),
[preuves matérielles](preference-validation.json).

## Correction utilisateur — G330, état courant

G329-02 est **REJETÉE** à la suite de l'annotation directe de toytoy : raccords
doigts-paume et plis incohérents à la base des doigts ; replis déformés près du
pouce. La validation GPT initiale était trop permissive. Les scores révisés par
GPT sont distingués du signalement utilisateur, qui ne donnait pas de notes.

Registre réel X399 : révision13, **2 acceptées (01,04), 9 rejetées, 1 incertaine**.
Snapshot corrigé `LAB/preference-lab/dataset-g329/dataset-rev13.json` ; deux paires
restantes `01>00` et `04>05`. `02>03` retirée. Les douze anciennes décisions et le
snapshot de la révision12 sont conservés sans réécriture, avec vérification du hash.

Le candidat de six mises à jour est **INVALIDATED_BY_USER_REVIEW**, inéligible à
toute promotion ; déclaration dans `LAB/preference-lab/pilot-g329/invalidation.json`.
Il n'avait jamais été activé. Ses poids sont conservés comme preuve historique :
la correction ne défait pas l'apprentissage. Aucun nouveau LoRA entraîné dans G330.
Un nouvel entraînement depuis la base et une nouvelle évaluation sont nécessaires.

Contrôles réellement exécutés : 8 tests du registre réussis ici et 8 sur X399 ;
script de comparaison refusant l'ancien candidat avec `REVIEWS_CHANGED`, avant
tout chargement de modèle ou génération (GPU masqués pour ce contrôle).
Hashes des deux paires restantes revérifiés. Aucun service redémarré.
[Correction et preuves](feedback-g330-correction.json).

**Les sections suivantes décrivent l'historique G329 avant cette correction** :
les trois paires y désignent bien celles utilisées par le pilote initial.

## Existant réutilisé et développement

Réutilisés : service média, GPU dédié, queue/API/idempotence, modèle SDXL base
officiel et lanceur G328 avec ses sondes et contrôles. Ajoutés : registre de
préférences révisables, export de paires strictement comparables, collecte à
géométrie constante, préparation d'un environnement indépendant, pilote LoRA-DPO
et comparaison sur demandes préenregistrées hors apprentissage.

Le processus est piloté pendant la session GPT ; aucun évaluateur cloud appelé
par Eidolon, aucun service de fond autonome chargé de contacter ChatGPT.
Le transfert des exemples de contrôle dans ChatGPT est explicitement autorisé
par toytoy. Les images/poids privés restent hors du dépôt public.

## Collecte et décisions

12 images réellement générées en1024²,30étapes,DPM++2M/Karras/CFG6 :
main ouverte, tasse rouge + bol bleu, katana + fourreau ;4seeds par demande.
Inspection GPT des douze copies JPEG à résolution native1024², PNG originaux
conservés. Pas de revue aveugle, pas d'avis utilisateur présumé.

| Décision | Identifiants | Motif principal |
| --- | --- | --- |
| Acceptées | 01,02 | Une main et cinq doigts, pose conforme, réserves de finition |
| Acceptée | 04 | Tasse rouge à gauche et bol bleu à droite, objets séparés |
| Rejets nets | 00,03 | Six doigts ; deux mains au lieu d'une |
| Rejets nets | 05,07 | Collage de quatre objets ; catégories/couleurs mélangées |
| Rejets nets | 08,09,10,11 | Fourreau absent, objets fusionnés/multipliés/coupés |
| Incertaine | 06 | Bol à anse ou seconde tasse : ambiguïté, hors apprentissage |

Soit3 acceptées,8 rejets,1 incertaine. Les notes et raisons complètes sont
conservées. Trois paires sans réutilisation d'images :01>00,02>03,04>05.
Aucune paire katana : aucun accepté disponible. Le rejet07 reste conservé mais
n'est pas ajouté artificiellement au dataset par duplication du seul gagnant04.

## Entraînement réellement exécuté

Copie indépendante du venv média ; torch2.6.0+cu124 inchangé. Ajouts figés
Diffusers0.32.2,PEFT0.14.0,Accelerate1.3.0 et deux dépendances standard. Roues PyPI
hashées, configurations SDXL officielles épinglées. Le modèle7Go déjà présent
est réutilisé ; aucun téléchargement de nouveaux poids de base.

Six mises à jour effectives, trois paires/deux prompts, LoRA de rang4,
5 806 080 paramètres entraînables, lr1e-5,beta1000. Toutes les pertes et tous
les gradients sont finis. La première perte vaut0,693147, cohérente avec un
adaptateur initial sans effet ; la norme L2 totale de modification du LoRA
est0,0495234. Ces valeurs prouvent un calcul/mouvement des poids, **pas une
amélioration de qualité**. Bruit et timestep changent entre étapes : ne pas
interpréter la perte comme une progression visuelle monotone.

Durée mesurée51,02s après les contrôles initiaux, comprenant chargement,
préparation, mises à jour et export. Pic nvidia-smi8560Mio (8,36Gio), allocation
PyTorch maximale7150,31Mio ; GPU36°C/HBM38°C ; puissance échantillonnée211,91W,
consigne200W inchangée. Le compteur PyTorch et la VRAM totale n'ont pas le même
périmètre. GPU0 etGTX1060 sans calcul pendant les sondes.

Adaptateur safetensors exporté puis rechargé avec succès ; SHA256
`51a82b264852ef024f5b6239d835db558a0e95e22af561549cf532d2a28a227b`.
Chemin privé : `LAB/preference-lab/pilot-g329/candidate/`.
Poids de base gelés, montage en lecture seule ; SHA du fichier de base revérifié
avant la comparaison et toujours conforme. Aucun LoRA ajouté à l'API/ComfyUI.

## Comparaison indépendante du dataset

Trois prompts de confirmation préenregistrés G328, seed155921, jamais utilisés
pour ces mises à jour. Même pipeline Diffusers, scheduler DPM++/Karras,
30étapes,CFG6,1024² avant/après. Pas de comparaison causale contre ComfyUI.

| Cas | Base | LoRA | Observation GPT |
| --- | --- | --- | --- |
| Deux adultes devant château japonais | Rejet | Rejet | Positions inversées et armure absente dans les deux images |
| Pont à trois arches | Acceptable | Acceptable | Trois ouvertures visibles ; qualité comparable, pas de préférence nette |
| Vélo de profil | Rejet | Rejet | Vue de trois quarts, pièce flottante et incohérences mécaniques persistantes |

Les trois PNG changent avec l'adaptateur, mais aucun gain convaincant n'est
visible à cet examen. Il n'y a qu'une seed par cas : aucune démonstration
statistique et aucune absence de régression générale garantie. Verdict :
**candidat conservé comme pilote technique, non promu**.
L'entraînement lui-même n'a été exécuté qu'une fois : sa répétabilité bit à bit
n'est pas mesurée par ce lot.

Six générations finales de comparaison réussies ; trois autres images de base
avaient été produites lors de la tentative initiale. Les trois bases répétées
ont exactement les mêmes SHA256. Total du lot :12 images de collecte +9 images
de comparaison, dont3 répétitions, soit18 images distinctes présentées au rapport.
Pic comparaison13772Mio (13,45Gio),GPU37/HBM43°C,257,24W échantillonnés.
Collecte :9168Mio, pointe260,28W. Aucun OOM observé. Aucun relevé d'énergie secteur.

## Problèmes rencontrés et corrections

1. Premier rechargement offline refusé : `weight_name` obligatoire dans cette
   version de Diffusers. Nom `pytorch_lora_weights.safetensors` et chargement
   local explicites ajoutés. Échec/source/journaux préservés dans
   `preference-lab/compare-g329/`, nouvelle exécution dans `compare2-g329/`.
   Cette relance suit un diagnostic/correctif ; aucun retry automatique.
2. La copie du venv conservait les chemins d'origine dans pip/activate. Les
   installations avaient utilisé le bon interpréteur avec `python -m pip` ;
   l'environnement source n'avait pas été modifié. Les21 scripts copiés ont été
   relocalisés, et l'installateur corrigé avec test de non-modification des
   originaux/liens/binaires. `pip --version` pointe désormais sur le laboratoire.
3. Avertissements de dépréciation du callback Diffusers et buffer CLIP
   `position_ids` ignoré au chargement ; pas d'erreur de calcul associée.

## Validation et limites

Neuf nouveaux tests hors GPU couvrent intégrité, révisions, priorité utilisateur,
séparation train/holdout, exclusion des incertains/tous-mauvais, non-duplication,
hash/symlink des images et relocalisation du venv. Suite média235tests :
231réussis/4ignorés ici ;230réussis/5ignorés sur X399 (catégories codecs/CLI
complémentaires). Les tests simulés du registre sont distincts des calculs GPU
réels ci-dessus.

Génération et entraînement réalisés dans des unités transitoires bloquées hors
localhost ; chemins des poids montés en lecture seule pendant pilote/comparaison.
Pas de coupure physique du réseau. Pilote et comparaison finale terminés ; aucune
promotion automatique. Services critiques contrôlés actifs, aucun arrêt Eva,
aucun changement pilote/CUDA/Memory de production. Le contrôle d'activité ne
remplace pas une recette exhaustive de non-régression de production.

Contrôle additionnel dans une unité auxiliaire avec le même profil d'isolation :
localhost8189 accessible, connexion1.1.1.1:443 bloquée (témoin hors confinement
réussi), ouverture en écriture du checkpoint refusée par EROFS, sans écriture
effectuée. Ce contrôle confirme le profil système ; il ne reconstitue pas une
trace réseau exhaustive des unités de calcul déjà terminées. État final :67tâches
API,0nonterminal,queue Comfy vide,GPU1 à624Mio/0%,freeze venv d'origine inchangé.

## Suite technique

Le point limitant est maintenant le jeu de préférences :3paires et2prompts sont
insuffisants pour un apprentissage de qualité. Étendre les formulations, les
scènes et les exemples corrects, garder des cas de confirmation séparés et
répéter plusieurs seeds. Ne pas prolonger aveuglément des epochs sur ces seules
trois paires. Les katanas nécessitent d'abord de vrais exemples acceptables.
Le cycle de contrôle n'attend pas l'approbation de chaque présentation ; les
corrections ultérieures de toytoy seront enregistrées et invalideront les
candidats concernés. Le LoRA conserve les contraintes de licence du modèle de
base ; aucune distribution de ses poids n'est effectuée dans ce lot.

`LAB=/srv/eidolon/workspaces/media-20261112`.
