# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : bundle_g348.py
# Description : Synthèse et archivage du lot SD3.5 Large Turbo
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
from pathlib import Path
import json,zlib,base64,hashlib
p=Path('g348-data.json');d=json.loads(p.read_text());d['library_file_id']='libfile_fde3_f-f3baafb4cbec8191a2686c5193a47c12_d168d29c22b4819186c4d3b8d1b7451f';p.write_text(json.dumps(d,ensure_ascii=False,indent=2))
report='''# SD3.5 Large Turbo - G348, 14 novembre 2026

Eidolon Core Technologies (ECT). Powered by Stability AI.

## Résultat et décision

Douze images générées et examinées. Huit natives 1024² : **5 proposées, 0 à revoir, 3 rejetées**. Mains01/02 à cinq doigts, objets03/04 et duo07 proposés. Katanas05/06 rejetés (duplication ou assemblage impossible), duo08 rejeté (passants supplémentaires et mains féminines cachées). Contrôle512² rejeté (quatre doigts apparents, cadrage coupé) ; répétition09 identique à01 et proposée hors score. Formats16:9 et4:3 rejetés pour cadrage.

Médiane native **3,130260 s**, plage **3,123097-3,336172 s**. Klein G340 corrigé :5/8 à3,395657s, soit un temps inférieur de7,82% pour Turbo sur cette petite série. **Turbo emploie deux V100, Klein une seule** ; aucune supériorité énergétique ni générale déduite. Medium SLG G347 :3/8 à24,053769s. Large Turbo améliore les deux mains et un duo face à Medium SLG, mais son rendu reste doux/lissé. Candidat rapide à conserver pour comparaison utilisateur, aucune promotion automatique. Z-Image G344 garde son rôle de génération détaillée à la demande selon toytoy.

## Recette figée avant observation

Recette auteur Turbo : **4 étapes, guidance0, sans SLG**, FlowMatchEuler shift3. Même grille G339-G347 : main ouverte, tasse/bol, katana/fourreau, duo devant château ; seeds20261113/20261114, huit natives1024², répétition, contrôle512² et écrans1024x576/768x576. Aucun prompt ajusté après observation, aucune seed sélectionnée pour améliorer le score.

L’auteur illustre BF16 ; adaptation locale **FP16 sur deux V100 Volta**, sans prétendre valider une équivalence visuelle BF16. VAE FP32 tuilé sur GPU0 ; CLIP-L,CLIP-G,T5-XXL CPU FP32, contexteT5 256. Les quatre poids d’encodeurs, leurs configurations et tokenizers sont identiques à G346 (SHA vérifiés). Cache d’encodages G346 réutilisé avec SHA :42,891310s est le coût initial historique des cinq textes, aucun nouvel encodage G348. VAE identique également réutilisé par lien physique. Aucun nouveau paquet ou pilote installé.

Générateur : blocs0-18 sur GPU0,19-37 sur GPU1, entrées et sortie sur GPU0. Placement réel **8 173 096 064 / 7 940 158 976 octets** de paramètres. Compteurs non modifiants : **76 appels de blocs par GPU et par image**, soit19blocs x4étapes sur chaque carte. Une même image traverse les deux parties du générateur ; pas de mémoire déclarée unifiée. Topologie archivée, aucun volume NVLink mesuré ni revendiqué.

PyTorch2.6.0+cu124, Diffusers0.37.0, Transformers4.56.1 ; runtime G340 identique avant/après. SDPA EFFICIENT_ATTENTION pour le générateur, MATH pour VAE. Chronomètre génération/décodage incluant contrôles numériques et sauvegarde du latent ; hors chargement9,092311s, encodage historique et sauvegarde PNG finale. Pas de latence depuis clic ni énergie totale mesurée. La première native inclut un possible échauffement logiciel ; elle reste conservée dans la série.

## Poids, accès et licence

Auteur `stabilityai/stable-diffusion-3.5-large-turbo`, révision `ec07796fc06b096cc56de9762974a28f4c632eda`. Dépôt auteur gated auto. Copie publique `adamo1139/stable-diffusion-3.5-large-turbo-ungated`, révision `9ad870ac0b0e5e48ced156bb02f85d324b7275d2`. Sept fichiers de poids aux SHA identiques auteur ; les deux shards du nouveau générateur totalisent16 292 705 296octets téléchargés. Quatre fichiers d’encodeurs et le VAE réutilisés après vérification. Fichiers de configuration/tokenizers/index/licence comparés aux blobs ou SHA LFS auteur ; aucun code du miroir exécuté.

Licence Stability AI Community5juillet2024 lue et archivée. Étude personnelle d’évaluation ; aucune inscription ou donnée personnelle transmise au formulaire auteur. La fiche auteur publique a été consultée sur le Web pour la recette ; son téléchargement raw renvoie401, enregistré dans `recipe-source.json`. La fiche du miroir est conservée comme telle (son blob diffère), jamais présentée comme octets de la fiche auteur. Les poids et la licence, eux, correspondent aux métadonnées auteur.

## Exécution et clôture

Préparation et premier contrôle aboutis sans incident de génération. Latents et pixels finis, douze PNG vérifiés par SHA ; répétition09 pixel-identique et PNG-identique à01. Aucun runtime modifié. Réseau sortant bloqué pendant la génération, UUID exacts des deux V100, verrou campagne, limites72GoRAM/800%CPU/90minutes, garde65°C GPU et70°C HBM.

Pics VRAM GPU0/GPU1 **13 692 / 8 550 Mio** ; maxima GPU **40/37°C**, HBM **41/36°C**. Consignes300W chacune, pics ponctuels314,44/304,18W. CPU Tdie46,25°C, zéro erreur télémétrie. GTX1060 inchangée. Contrôle final14/11/2026 à19h37 Paris : GPU sans client, cinq services actifs, VM Memory-engine en marche, runtime inchangé et machine laissée allumée. Aucun entraînement, déploiement ou changement sur l’autre plateforme.

## Revue des images

| Image | Cas / condition | Temps (s) | Avis GPT | Commentaire |
| --- | --- | ---: | --- | --- |
'''
for x in d['results']:
 r=d['reviews'][str(x['index'])];report+=f"| G348-{x['index']:02d} | {x['case']} / {x['condition']} | {x['seconds']:.3f} | {r['verdict']} | {r['comment']} |\n"
report+='''
## Livrable, preuves et limites

Rapport illustré `Eidolon-comparatif-SD35LargeTurbo-G348.pdf`,14pages, identité `libfile_fde3_f-f3baafb4cbec8191a2686c5193a47c12_d168d29c22b4819186c4d3b8d1b7451f`,version0. Preuves `evidence-g348/`, synthèse `sd35-large-turbo-validation-g348.json`, scripts préparation/génération/lancement/contrôle et sources du rapport conservés.

PNG/latents/caches : `/srv/eidolon/workspaces/media-20261112/sd35-large-turbo-g348/`,run01(smoke),run02(qualité). Poids : `/srv/eidolon/data/media-models-20261113/sd35-large-turbo`. Les preuves brutes conservent leur état initial PENDING_REVIEW/NOT_REVIEWED ; la synthèse et `visual-reviews.json` portent la revue postérieure.

Quatre scènes seulement et revue subjective explicite. « Proposée » ne vaut pas approbation de toytoy. Comparaison de recettes et matériels différents, pas estimation statistique robuste. [Medium SLG G347](SD35-SLG-G347.md), [Klein G340](KLEIN-G340.md). **SD3.5 Large non Turbo reste non testé.**

[Recette auteur](https://huggingface.co/stabilityai/stable-diffusion-3.5-large-turbo/blob/ec07796fc06b096cc56de9762974a28f4c632eda/README.md) ; [copie publique vérifiée](https://huggingface.co/adamo1139/stable-diffusion-3.5-large-turbo-ungated/tree/9ad870ac0b0e5e48ced156bb02f85d324b7275d2).
'''
Path('SD35-LARGE-TURBO-G348.md').write_text(report)
summary='[Rapport G348](SD35-LARGE-TURBO-G348.md) : SD3.5 Large Turbo FP16 sur deux V100,4 étapes/guidage0 ;12images, répétition exacte. Natives :5/8 proposées,3rej et0réserve ;3,130s médianes. Deux mains à cinq doigts ; katanas et duo08 rejetés. Même score que Klein5/8 à3,396s sur une seule V100 ; aucune supériorité générale déduite. Pics13 692/8 550Mio, GPU40/37°C, HBM41/36°C.76appels de blocs/carte/image vérifiés. Runtime inchangé, services actifs, GPU libres, machine allumée. Aucune promotion ; Large non Turbo reste non testé.'
row='| I25 — Stable Diffusion 3.5 Large / Large Turbo 8B | Une carte non testée ; générateur seul16,3Go de fichiers | **Turbo FP16 réparti testé**,19blocs par V100 ; encodeurs CPU, VAE GPU0 ; pics13 692/8 550Mio | Stability Community archivée ; sept fichiers de poids SHA identiques auteur | **Turbo testé G348** :12images,5/8 natives proposées,3rejets ;3,130s médianes,4étapes/guidage0. [Rapport](SD35-LARGE-TURBO-G348.md). Aucune promotion. **Large non Turbo non testé** |'
b=json.dumps({'data':d,'report':report,'summary':summary,'candidate_row':row,'finalizer':Path('finalize_g348.py').read_text(),'report_sources':{f:Path(f).read_text() for f in ['make_g348.py','review_g348.py','bundle_g348.py']}},ensure_ascii=False).encode();Path('g348-finalbundle.b64').write_bytes(base64.b64encode(zlib.compress(b)));print(len(b),hashlib.sha256(b).hexdigest())
