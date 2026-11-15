# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : review_g357.py
# Description : Bilan apparié des retouches G357
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
from pathlib import Path
import json,statistics,hashlib
R=Path(__file__).parent;d=json.loads((R/'g357-final-raw.json').read_text());base=json.loads((R/'g357-baseline-reviews.json').read_text());focus=json.loads((R/'g357-focused-reviews.json').read_text());d['reviews']={'baseline':base,'focused':focus}
assert len(d['results'])==21 and set(focus)==set(map(str,range(1,10)))
assert all(x['unet_calls']==19 for x in d['results']) and d['telemetry']['sample_errors']==0
for c in d['completion'].values():assert c['repeat_same_pixels']=={'sdxl_inpaint':True} and c['raw_repeat_same_pixels']
for x in d['results']:
 if x['phase']=='focused':
  y=next(y for y in d['results'] if y['index']==x['index'] and y['phase']=='baseline')
  assert all(x[k]==y[k] for k in ['source_sha256','mask_sha256','seed','steps','cfg','strength','width','height','negative_prompt']) and x['prompt']!=y['prompt']
 x['visual']=d['reviews'][x['phase']][str(x['index'])]['verdict']
d['summary_by_phase']={}
for phase in ['baseline','focused']:
 rows=[x for x in d['results'] if x['phase']==phase and x['condition']=='quality'];assert len(rows)==8
 q={key:sum(d['reviews'][phase][str(x['index'])]['verdict']==val for x in rows) for key,val in [('proposed','Proposée'),('review','À revoir'),('rejected','Rejetée')]}
 q.update(median_seconds=statistics.median(x['seconds'] for x in rows),raw_outside_mae_min=min(x['preservation']['raw_outside_mae'] for x in rows),raw_outside_mae_max=max(x['preservation']['raw_outside_mae'] for x in rows),raw_outside_max=max(x['preservation']['raw_outside_max'] for x in rows));d['summary_by_phase'][phase]=q
q=d['summary_by_phase']['focused'].copy();g=d['telemetry']['gpus']['0'];q.update(peak_mib=g['memory.used']['max'],gpu_c=g['temperature.gpu']['max'],hbm_c=g['temperature.memory']['max'],power_w=g['power.draw']['max']);d['summary']=q
f=d['summary_by_phase']['focused'];b=d['summary_by_phase']['baseline']
d['summary_paragraphs']=[f'<b>Effet du prompt :</b> première passe {b["proposed"]}/8 proposées, {b["review"]} réserve ; passe ciblée {f["proposed"]}/8 proposées, {f["review"]} réserve. Même source, masque, seed et recette dans chaque paire.','<b>Préservation :</b> la sortie brute modifie aussi des pixels hors masque. Le collage binaire avec la source assure leur conservation exacte, mais peut rendre les raccords visibles. Ce résultat vient du traitement, pas du modèle seul.','<b>Décision :</b> '+'Chaîne techniquement viable, correction automatique non retenue avec ces masques et réglages. Le prompt ciblé ne change aucun verdict ; la main conserve une amélioration partielle.','Avis GPT sur une petite grille de retouches ; ce score ne se compare pas directement aux campagnes texte-vers-image.']
d['method_paragraphs']=[
'<b>Modèle :</b> diffusers/stable-diffusion-xl-1.0-inpainting-0.1, révision 115134f3. Pipeline complet FP16 auteur, UNet dédié à neuf canaux. Licence CreativeML Open RAIL++-M et carte auteur archivées ; recherche privée locale, aucun poids redistribué.',
'<b>Sources :</b> quatre PNG G356 (01 main, 03 objets, 06 sabre, 07 duo), empreintes vérifiées. Quatre masques polygonaux binaires figés avant tout essai ; mêmes masques dans les deux passes, aucun ajustement après résultat.',
'<b>Plan :</b> 21 générations : contrôle 512² ; huit retouches natives 1024² avec prompts d’origine ; répétition et masques vide/plein ; huit retouches avec prompts ciblés et une seconde répétition. Deux seeds : 20261113 et 20261114. Aucune sélection de seed.',
'<b>Recette :</b> Euler auteur, CFG 8, 20 étapes demandées, force 0,99. Diffusers exécute 19 étapes et 19 appels UNet, mesurés. Négatif vide, pas de LoRA, refiner, super-résolution ou adoucissement du masque.',
'<b>Précision :</b> une V100 GPU0, UNet/CLIP FP16 ; VAE avec force_upcast FP32 dans la pipeline, tuilage. PyTorch 2.6.0+cu124 / Diffusers 0.32.2. Encodage VAE, latents et décodage finis contrôlés ; runtime inchangé.',
'<b>Mesures :</b> encodage texte/image + débruitage + décodage et contrôles numériques inclus ; chargement, sauvegarde et collage exclus. Écart hors masque calculé sur les PNG RGB, moyenne absolue par canal sur 255. Contrôle séparé de la sortie brute et du composite.',
'<b>Limites :</b> seconde passe choisie après observation de la première ; revue GPT non aveugle sur aperçus réduits. Masques manuels grossiers, seulement deux graines, force et guidage non balayés. Échec de cette recette ne prouve pas une incapacité générale du modèle.',
'<b>Exploitation :</b> inférence sans réseau, plafond 300 W et garde GPU/HBM 65/70 °C. Deux répétitions exactes, 84 PNG vérifiés (21 sources, masques, sorties brutes et composites). Aucun entraînement ni promotion ; services actifs, GPU libres, machine allumée.'
]
d['promotion_allowed']=False;d['review_status']='GPT_PROVISIONAL_NOT_PROMOTED'
(R/'g357-data.json').write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n');print(json.dumps(d['summary_by_phase'],ensure_ascii=False))
