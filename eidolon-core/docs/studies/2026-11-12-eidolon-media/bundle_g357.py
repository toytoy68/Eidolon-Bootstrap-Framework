# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : bundle_g357.py
# Description : Rapport et preuve du banc de retouche G357
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
from pathlib import Path
import json,hashlib,zlib,base64,re
R=Path(__file__).parent;d=json.loads((R/'g357-data.json').read_text());lib=json.loads((R/'g357-library.json').read_text());d['library_file_id']=lib['library_file_id'];clean=lambda s:re.sub(r'</?b>','',s)
report='# SDXL Inpainting - G357, 14 novembre 2026\n\nEidolon Core Technologies (ECT).\n\n## Résultat\n\n21 générations locales : 8 retouches natives par passe, deux répétitions et trois contrôles. Chaque passe obtient 0/8 propositions, 1 réserve et 7 rejets. La formulation ciblée n’améliore aucun verdict. Une main retrouve cinq doigts mais reste à revoir ; l’autre garde quatre doigts, le comptage des récipients reste faux, le fourreau manque et la tenue demeure noire.\n\n'+'\n\n'.join(map(clean,d['summary_paragraphs']))+'\n\n## Méthode\n\n'+'\n\n'.join(map(clean,d['method_paragraphs']))+'\n\n'
report+='''## Provenance et chaîne

Modèle exact : `diffusers/stable-diffusion-xl-1.0-inpainting-0.1`, révision `115134f363124c53c7d878647567d04daf26e41e`. Tous les fichiers de la variante FP16 proviennent de ce dépôt public auteur, sans exécution de code distant. Fichiers LFS contrôlés par taille/SHA256, petits fichiers par blob Git, puis tous revérifiés par SHA avant chaque chargement. Modèle dédié UNet 9 canaux ; ce n’est pas un simple masque appliqué au SDXL texte-vers-image.

[Carte auteur figée](https://huggingface.co/diffusers/stable-diffusion-xl-1.0-inpainting-0.1/tree/115134f363124c53c7d878647567d04daf26e41e) ; [licence indiquée par l’auteur](https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/blob/main/LICENSE.md). Attribution Diffusers team / Stability AI ; CreativeML Open RAIL++-M du 26 juillet 2023 conservée. Étude privée, non-intégration, aucun poids redistribué. Images sources G356 : RunDiffusion / KandooAI ; provenance et conditions du modèle source conservées dans G356.

Les champs EMA historiques du fichier de configuration UNet sont ignorés par Diffusers et restent visibles dans les journaux. Aucun patch du modèle, du scheduler ou du runtime. Le VAE est chargé FP16 et la pipeline utilise son option `force_upcast` pour l’encodage/décodage FP32 ; les valeurs finies sont contrôlées. SDPA MATH, quatre threads, fraction mémoire CUDA 0,88. Unités systemd temporaires, GPU0 seul à 300 W, réseau sortant interdit pendant l’inférence, verrou de campagne et garde GPU/HBM 65/70 °C. Aucun service d’inférence extérieur.

Les masques ont été dessinés avant toute retouche sur les quatre sources, puis conservés sans modification. La seconde passe est une adaptation après observation de la première, et non un essai aveugle pré-enregistré. Seul le prompt positif change dans chaque paire ; source, masque, seed, négatif vide, force, scheduler et guidage sont identiques. Les prompts intégraux sont conservés dans la synthèse et les intentions de chaque génération.

Le collage binaire est volontairement explicite et sans adoucissement : `Image.composite(raw, source, mask)`. Les pixels hors masque proviennent exactement de la source. La sortie brute n’offre pas cette garantie : le contrôle masque vide change 1 048 507 des 1 048 576 pixels, avec un écart moyen par canal de 2,398/255. Ce n’est pas une garantie de raccord visuel ; le collage peut montrer les différences de teinte et de texture au bord du masque.

## Poids

| Composant | Octets | SHA256 |
| --- | ---: | --- |
'''
for x in d['model']['files']:
 if x['name'].endswith('.safetensors'):report+=f"| {x['name']} | {x['bytes']} | {x['sha256']} |\n"
report+='\n## Mesures appariées\n\n| Passe | N natives | Médiane (s) | Proposées / réserves / rejets | MAE brute hors masque min-max (/255) | Écart maximal observé (/255) |\n| --- | ---: | ---: | --- | --- | ---: |\n'
for phase in ['baseline','focused']:
 q=d['summary_by_phase'][phase];report+=f"| {phase} | 8 | {q['median_seconds']:.6f} | {q['proposed']}/{q['review']}/{q['rejected']} | {q['raw_outside_mae_min']:.6f}-{q['raw_outside_mae_max']:.6f} | {q['raw_outside_max']} |\n"
q=d['summary'];report+=f"\nToutes phases confondues : pic VRAM {q['peak_mib']:.0f} Mio, GPU/HBM {q['gpu_c']:.0f}/{q['hbm_c']:.0f} °C, puissance échantillonnée {q['power_w']:.2f} W pour une limite configurée à 300 W. GPU1 et GTX1060 au repos. Aucune erreur de télémétrie ; une mesure de puissance instantanée ne donne pas l’énergie totale.\n\n## Revue complète\n\n| Passe / image | Avis GPT | Motif |\n| --- | --- | --- |\n"
for x in d['results']:
 n=d['reviews'][x['phase']][str(x['index'])];report+=f"| {x['phase']}/{x['index']:02d} | {n['verdict']} | {n['comment']} |\n"
report+='\n## Vérifications et limites opérationnelles\n\n21 générations, 19 appels UNet chacune ; deux répétitions exactes pour les versions brute et recomposée. 84 fichiers PNG vérifiés par SHA (sources et masques de chaque essai inclus) ; quatre originaux G356 et masques figés vérifiés. Aucun paquet/pilote modifié, configurations et sources runtime inchangées. Cinq services Core actifs, VM Memory-engine en marche, aucun client GPU restant. Machine laissée allumée.\n\nL’utilitaire de clôture a initialement été lancé avec le Python système sans PIL, puis avec le venv sans chemin du paquet Core. Résolu en utilisant le venv existant et un chemin explicite vers les sources du résumé télémétrique ; aucune génération affectée ni installation effectuée. Incidents de clôture documentés séparément des journaux de génération.\n\nProchain essai discriminant possible : varier force/guidage et taille du masque, puis vérifier une retouche à partir d’une autre architecture. Ces variantes ne sont ni exécutées ni validées dans ce lot. Le score de retouche ne remplace pas le classement des modèles de génération.\n'
report+=f"\n## Conservation\n\nPDF illustré de 14 pages : `{d['library_file_id']}`. Originaux/masques/sorties : `/srv/eidolon/workspaces/media-20261112/sdxl-inpaint-g357/`. Poids : `/srv/eidolon/data/media-models-20261113/sdxl-inpaint-g357/`. Synthèse : `sdxl-inpaint-validation-g357.json`, preuves : `evidence-g357/`. Aucun avis utilisateur attribué, aucun entraînement ni promotion.\n"
summary='[Rapport G357](SDXL-INPAINT-G357.md) : SDXL Inpainting 0.1 dédié, une V100, 21 générations ; 8 retouches avec prompts initiaux et 8 avec prompts ciblés, 0/8 proposées + 1 réserve dans chaque passe. Médianes 11,836/11,841 s ; 10 564 Mio, GPU/HBM 44/51 °C. Deux répétitions exactes ; hors masque inchangé après collage explicite, sortie brute non identique. Chaîne viable, correction automatique non retenue avec cette recette. Sources/masques/SHA/licence archivés, runtime inchangé, GPU libres, services actifs, machine allumée.'
row='| I03 — SDXL inpainting dédié | **Testé G357** : UNet 9 canaux, FP16 une V100 / VAE upcast FP32, 10 564 Mio | Répartition non nécessaire | Diffusers / SDXL Open RAIL++-M, révision et SHA archivés | 21 générations ; 8 retouches par passe, prompts initiaux puis ciblés : chacune 0/8 + 1 réserve, environ 11,84 s. Hors masque préservé exactement par collage, pas par la sortie brute. [Rapport](SDXL-INPAINT-G357.md), aucune promotion |'
(R/'g357-data.json').write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n');(R/'SDXL-INPAINT-G357.md').write_text(report)
names=['make_g357.py','review_g357.py','bundle_g357.py','finalize_g357.py','g357-baseline-reviews.json','g357-focused-reviews.json'];b=json.dumps({'data':d,'report':report,'summary':summary,'candidate_row':row,'sources':{n:(R/n).read_text() for n in names}},ensure_ascii=False).encode();(R/'g357-finalbundle.b64').write_bytes(base64.b64encode(zlib.compress(b)));print(json.dumps({'sha256':hashlib.sha256(b).hexdigest(),'chars':len((R/'g357-finalbundle.b64').read_bytes())}))
