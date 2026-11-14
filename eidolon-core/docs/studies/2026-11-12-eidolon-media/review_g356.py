# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : review_g356.py
# Description : Comparaison XI Lightning, XI standard et XL Lightning
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
from pathlib import Path
import json,statistics,hashlib
root=Path(__file__).parent;d=json.loads((root/'g356-raw.json').read_text());notes=json.loads((root/'g356-review-notes.json').read_text())
ref=json.loads((root/'juggernaut-xi-validation-g355.json').read_text());xl=json.loads((root/'juggernaut-lightning-validation-g354.json').read_text())
assert len(d['results'])==12 and all(x['unet_calls']==11 and len(x['timesteps'])==11 and x['decoder_calls']>=1 and x['steps']==6 and x['cfg']==1.8 for x in d['results'])
assert d['completion']['repeat_same_pixels']=={'xi_lightning':True}
assert d['health_final']['runtime_unchanged'] and all(x['match'] for x in d['health_final']['png_checks']) and all(x['match'] for x in d['health_final']['source_checks'])
d['references']={}
for key,name,commit in [('xi_standard','juggernaut-xi-validation-g355.json','b7f297f4f0ae45d21fc290634db0ac8a80439930'),('xl_lightning','juggernaut-lightning-validation-g354.json','8ec671e0bcbf92d792e0ea28072d47d2538cef23')]:
 d['references'][key]={'source_path':name,'commit':commit,'sha256':hashlib.sha256((root/name).read_bytes()).hexdigest(),'regenerated_in_G356':False}
d['new_results']=d['results'].copy();d['results']+=[x for x in ref['new_results'] if x['model']=='v11'];d['xl_reference_results']=xl['new_results'];d['reviews']={'xi_lightning':notes['reviews'],'v11':ref['reviews']['v11'],'xl_lightning':xl['reviews']['lightning']};d['comparisons']=notes['comparisons']
assert set(notes['reviews'])==set(map(str,range(12))) and len(notes['comparisons'])==12
rows=sorted(d['new_results'],key=lambda x:x['index']);assert rows[1]['sha256']==rows[9]['sha256']
native=[x for x in rows if x['condition']=='quality'];g=d['telemetry_by_model']['xi_lightning']['gpus']['0'];q={k:sum(notes['reviews'][str(i)]['verdict']==v for i in range(1,9)) for k,v in [('proposed','Proposée'),('review','À revoir'),('rejected','Rejetée')]};q.update(median_seconds=statistics.median(x['seconds'] for x in native),min_seconds=min(x['seconds'] for x in native),max_seconds=max(x['seconds'] for x in native),peak_mib=g['memory.used']['max'],gpu_c=g['temperature.gpu']['max'],hbm_c=g['temperature.memory']['max'],power_w=g['power.draw']['max']);d['summary']={'xi_lightning':q,'v11':ref['summary']['v11'],'xl_lightning':xl['summary']['lightning']}
for x in rows:
 y=next(y for y in ref['new_results'] if y['index']==x['index']);z=next(z for z in xl['new_results'] if z['index']==x['index']);keys=['case','prompt','seed','negative_prompt','width','height','condition'];assert all(x[k]==y[k] for k in keys);assert all(x[k]==z[k] for k in keys+['steps','cfg']);x['visual']=notes['reviews'][str(x['index'])]['verdict']
factor=ref['summary']['v11']['median_seconds']/q['median_seconds'];d['speed_ratio_vs_standard']=factor
d['conclusion']=f'<b>XI Lightning : {q["proposed"]}/8 images proposées.</b> XI standard : 2/8 et 1 réserve ; XL Lightning : 1/8. Médiane {q["median_seconds"]:.2f} s, contre 17,56 s pour XI standard.'
d['summary_paragraphs']=['<b>Constat visuel :</b> '+notes['visual_summary'],'<b>Comparaison :</b> 12 nouvelles images XI Lightning. Références historiques XI standard G355 et XL Lightning G354 ; mêmes scènes, seeds et matériel. Les deux Lightning emploient la même recette 6/CFG 1,8 ; XI standard utilise 30/CFG5.',f'<b>Matériel :</b> une V100 ; maxima GPU/HBM {q["gpu_c"]:.0f}/{q["hbm_c"]:.0f} °C. Répétition pixel-identique. Temps encodage texte + génération + décodage, hors chargement et sauvegarde.','<b>Décision :</b> '+notes['decision']+' Avis GPT provisoires, aucune validation utilisateur attribuée.']
d['method_paragraphs']=[
'<b>Plan :</b> douze nouvelles images : contrôle 512², huit natives 1024², répétition, duo 1024×576 et 768×576. Seeds 20261113/20261114, prompts figés, négatif vide, aucun refiner, LoRA, retouche ou sélection de seeds.',
'<b>Recette :</b> DPMSolverSDEScheduler, DPM++ SDE Karras, 6 étapes nominales / 11 appels UNet mesurés, CFG 1,8. Scheduler recréé et graine brownienne fixée pour chaque image. Même recette que XL Lightning G354.',
'<b>Précision :</b> UNet et encodeurs FP16 GPU 0, VAE upcast FP32/tuilage. PyTorch 2.6.0+cu124, Diffusers 0.32.2 et Transformers 4.49.0 ; aucun paquet ni pilote modifié. Sources et configurations vérifiées avant/après.',
'<b>Poids exacts :</b> RunDiffusion/Juggernaut-XI-Lightning, révision dbb242e5 ; fichier Civitai-Version, SHA256 609fde64…15f37b1a, 7,105 Go, VAE stocké FP32. L’autre fichier du dépôt, VAE stocké FP16, n’est pas testé.',
'<b>Licence :</b> RunDiffusion / KandooAI, CC BY-NC-ND 4.0 et conditions auteur ; licences de base SDXL/ByteDance conservées. Évaluation locale privée non commerciale, aucune redistribution de poids. Accès public auteur, aucun formulaire transmis.',
'<b>Compatibilité :</b> buffer CLIP position_ids non entier ignoré par Transformers, qui reconstruit 0–76 ; comportement et source archivés. Avertissements torchsde de borne brownienne conservés ; valeurs finies contrôlées, aucun correctif numérique.',
'<b>Isolation :</b> GPU 0 seul, 300 W, garde GPU/HBM 65/70 °C, réseau sortant interdit pour l’inférence, verrou et limites de ressources. Temps incluant encodage et contrôles ; pics mémoire/puissance/température échantillonnés.',
'<b>Limites :</b> huit natives, revue GPT non aveugle sur aperçus réduits. XI standard et XL Lightning repris de G355/G354, pas régénérés. Recette distincte du standard ; aucune attribution du gain aux seuls poids. Machine allumée, GPU libres et services actifs.'
]
d['short_decision']=notes['decision'];d['promotion_allowed']=False;d['completion']['visual_acceptance']='REVIEWED_NOT_PROMOTED';d['execution_summary']='12 nouvelles générations achevées, 11 appels UNet chacune, répétition exacte. 12 PNG vérifiés, sources/configs/runtime inchangés. GPU libres, cinq services actifs et Memory-engine en marche. Machine allumée.'
(root/'g356-data.json').write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n');print(json.dumps(q));print('Speed ratio vs XI standard',factor)
