# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : review_g354.py
# Description : Revue du lot Lightning et référence historique v9
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
from pathlib import Path
import json,statistics,hashlib
root=Path(__file__).parent;d=json.loads((root/'g354-raw.json').read_text());ref=json.loads((root/'juggernaut-x-validation-g353.json').read_text());notes=json.loads((root/'g354-review-notes.json').read_text())
assert len(d['results'])==12 and all(x['unet_calls']==11 and x['decoder_calls']>=1 and x['steps']==6 for x in d['results'])
assert d['completion']['repeat_same_pixels']=={'lightning':True}
assert d['health_final']['runtime_unchanged'] and all(x['match'] for x in d['health_final']['png_checks']) and all(x['match'] for x in d['health_final']['source_checks'])
d['reference']={'campaign':'G353','commit':'e72dd12369cbd2e0d2ee4e5d8c9420b0f75c705b','source_sha256':hashlib.sha256((root/'juggernaut-x-validation-g353.json').read_bytes()).hexdigest(),'source_path':'juggernaut-x-validation-g353.json','regenerated_in_G354':False,'summary':ref['summary']['v9'],'reviews':ref['reviews']['v9']}
d['new_results']=d['results'].copy();d['results']+= [x for x in ref['results'] if x['model']=='v9'];d['reviews']={'lightning':notes['reviews'],'v9':ref['reviews']['v9']};d['comparisons']=notes['comparisons']
assert set(notes['reviews'])==set(map(str,range(12))) and len(notes['comparisons'])==12
rows=sorted(d['new_results'],key=lambda x:x['index']);assert rows[1]['sha256']==rows[9]['sha256']
native=[x for x in rows if x['condition']=='quality'];g=d['telemetry_by_model']['lightning']['gpus']['0'];q={k:sum(notes['reviews'][str(i)]['verdict']==v for i in range(1,9)) for k,v in [('proposed','Proposée'),('review','À revoir'),('rejected','Rejetée')]};q.update(median_seconds=statistics.median(x['seconds'] for x in native),min_seconds=min(x['seconds'] for x in native),max_seconds=max(x['seconds'] for x in native),peak_mib=g['memory.used']['max'],gpu_c=g['temperature.gpu']['max'],hbm_c=g['temperature.memory']['max'],power_w=g['power.draw']['max']);d['summary']={'lightning':q,'v9':ref['summary']['v9']}
for x in rows:
 other=next(y for y in d['results'] if y['model']=='v9' and y['index']==x['index']);assert all(x[k]==other[k] for k in ['case','prompt','seed','negative_prompt','width','height','condition']);x['visual']=notes['reviews'][str(x['index'])]['verdict']
factor=ref['summary']['v9']['median_seconds']/q['median_seconds'];d['speed_ratio_vs_v9']=factor
d['conclusion']=f'<b>Lightning : {q["proposed"]}/8 images proposées, contre 3/8 pour v9.</b> Médiane {q["median_seconds"]:.2f} s contre 17,60 s pour v9 G353, soit un temps divisé par {factor:.2f} dans ces recettes.'
d['summary_paragraphs']=['<b>Constat visuel :</b> '+notes['visual_summary'],'<b>Comparaison :</b> 12 nouvelles images Lightning ; les 12 images v9 proviennent du lot G353. Scènes, seeds et matériel identiques, mais sampler, étapes et guidage différents. Le gain porte sur la recette complète.',f'<b>Matériel :</b> une V100 ; maxima GPU/HBM {q["gpu_c"]:.0f}/{q["hbm_c"]:.0f} °C. Répétition pixel-identique. Temps incluant encodage texte, génération et décodage, hors chargement et sauvegarde.','<b>Décision :</b> '+notes['decision']+' Avis GPT provisoires, aucune validation utilisateur attribuée.']
d['method_paragraphs']=[
'<b>Plan :</b> douze images Lightning : contrôle 512², huit natives 1024², répétition, duo 1024 × 576 et 768 × 576. Seeds 20261113/20261114, prompts figés, négatif vide. Aucun refiner, LoRA, retouche ni tri des seeds.',
'<b>Recette :</b> DPM++ SDE Karras via DPMSolverSDEScheduler Diffusers ; 6 étapes nominales et 11 appels UNet mesurés, CFG 1,8. Bruit brownien réinitialisé avec la seed de chaque image. Les deux sorties répétées ont les mêmes pixels et le même SHA PNG.',
'<b>Choix des réglages :</b> le fichier porte 4Steps ; la carte auteur recommande 5–7 étapes et CFG 1,5–2,0. Ce lot teste 6/1,8, pas une campagne 4 étapes. Son exemple Python utilise un autre scheduler : la recette exacte employée ici est archivée.',
'<b>Précision et runtime :</b> UNet et encodeurs FP16 GPU0, VAE upcast FP32 et tuilage. PyTorch 2.6.0+cu124, Diffusers 0.32.2, Transformers 4.49.0 et torchsde déjà présents. Aucun paquet ni pilote modifié ; sources et configurations vérifiées avant/après.',
'<b>Provenance :</b> RunDiffusion/Juggernaut-XL-Lightning, révision 9c35e7ca, fichier 7,105 Go, SHA256 c8df560d…f4b425a5. Carte auteur, OpenRAIL-M et licences OpenRAIL++ SDXL/ByteDance archivées, restriction API payante conservée.',
'<b>Observation numérique :</b> avertissement torchsde sur une borne brownienne (écart d’arrondi environ 2,3 × 10^-7). Aucun avertissement masqué ; latents et décodage finis vérifiés. Aucun correctif numérique appliqué.',
'<b>Isolation et mesure :</b> GPU0 V100 à 300 W, garde GPU/HBM 65/70 °C ; réseau sortant interdit pendant la génération, verrou de campagne et limites de ressources. Durée encodage + débruitage + décodage + contrôles ; pics échantillonnés.',
'<b>Limites :</b> huit images natives, revue GPT non aveugle sur aperçus réduits. V9 G353 historique, recettes distinctes ; aucun classement universel ni effet causal des seuls poids. Machine laissée allumée, GPU libres et services actifs.'
]
d['short_decision']=notes['decision'];d['promotion_allowed']=False;d['completion']['visual_acceptance']='REVIEWED_NOT_PROMOTED';d['execution_summary']='12 nouvelles générations achevées, 11 appels UNet chacune, répétition exacte. 12 PNG vérifiés, sources/configs/runtime inchangés. GPU libres, cinq services actifs et Memory-engine en marche. Machine allumée.'
(root/'g354-data.json').write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n');print(json.dumps(q));print('Speed ratio',factor)
