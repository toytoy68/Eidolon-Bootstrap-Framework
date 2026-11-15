# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : review_g355.py
# Description : Revue du lot XI v11 et référence historique v9
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
from pathlib import Path
import json,statistics,hashlib
root=Path(__file__).parent;d=json.loads((root/'g355-raw.json').read_text());ref=json.loads((root/'juggernaut-x-validation-g353.json').read_text());notes=json.loads((root/'g355-review-notes.json').read_text())
assert len(d['results'])==12 and all(x['unet_calls']==30 and x['decoder_calls']>=1 and x['steps']==30 for x in d['results'])
assert d['completion']['repeat_same_pixels']=={'v11':True}
assert d['health_final']['runtime_unchanged'] and all(x['match'] for x in d['health_final']['png_checks']) and all(x['match'] for x in d['health_final']['source_checks'])
d['reference']={'campaign':'G353','commit':'e72dd12369cbd2e0d2ee4e5d8c9420b0f75c705b','source_sha256':hashlib.sha256((root/'juggernaut-x-validation-g353.json').read_bytes()).hexdigest(),'source_path':'juggernaut-x-validation-g353.json','regenerated_in_G355':False,'summary':ref['summary']['v9'],'reviews':ref['reviews']['v9']}
d['new_results']=d['results'].copy();d['results']+= [x for x in ref['results'] if x['model']=='v9'];d['reviews']={'v11':notes['reviews'],'v9':ref['reviews']['v9']};d['comparisons']=notes['comparisons']
assert set(notes['reviews'])==set(map(str,range(12))) and len(notes['comparisons'])==12
rows=sorted(d['new_results'],key=lambda x:x['index']);assert rows[1]['sha256']==rows[9]['sha256']
native=[x for x in rows if x['condition']=='quality'];g=d['telemetry_by_model']['v11']['gpus']['0'];q={k:sum(notes['reviews'][str(i)]['verdict']==v for i in range(1,9)) for k,v in [('proposed','Proposée'),('review','À revoir'),('rejected','Rejetée')]};q.update(median_seconds=statistics.median(x['seconds'] for x in native),min_seconds=min(x['seconds'] for x in native),max_seconds=max(x['seconds'] for x in native),peak_mib=g['memory.used']['max'],gpu_c=g['temperature.gpu']['max'],hbm_c=g['temperature.memory']['max'],power_w=g['power.draw']['max']);d['summary']={'v11':q,'v9':ref['summary']['v9']}
for x in rows:
 other=next(y for y in d['results'] if y['model']=='v9' and y['index']==x['index']);assert all(x[k]==other[k] for k in ['case','prompt','seed','negative_prompt','width','height','condition','steps','cfg']);x['visual']=notes['reviews'][str(x['index'])]['verdict']
factor=ref['summary']['v9']['median_seconds']/q['median_seconds'];d['speed_ratio_vs_v9']=factor
d['conclusion']=f'<b>XI v11 : {q["proposed"]}/8 images proposées, contre 3/8 pour v9.</b> Médiane {q["median_seconds"]:.2f} s contre 17,60 s pour v9 G353. Recette commune : 30 étapes, CFG5.'
d['summary_paragraphs']=['<b>Constat visuel :</b> '+notes['visual_summary'],'<b>Comparaison :</b> 12 nouvelles images v11 face aux 12 références v9 du lot G353. Scènes, seeds, DPM++2M Karras, 30 étapes, CFG5 et matériel identiques ; v9 non régénéré dans ce lot.',f'<b>Matériel :</b> une V100 ; maxima GPU/HBM {q["gpu_c"]:.0f}/{q["hbm_c"]:.0f} °C. Répétition pixel-identique. Temps incluant encodage texte, génération et décodage, hors chargement et sauvegarde.','<b>Décision :</b> '+notes['decision']+' Avis GPT provisoires, aucune validation utilisateur attribuée.']
d['method_paragraphs']=[
'<b>Plan :</b> douze images XI v11 : contrôle 512², huit natives 1024², répétition, duo 1024 × 576 et 768 × 576. Seeds 20261113/20261114, prompts figés et négatif vide. Aucun refiner, LoRA, retouche ni sélection des seeds.',
'<b>Recette :</b> DPMSolverMultistepScheduler, DPM++2M Karras, 30 étapes, CFG5 ; trente appels UNet mesurés. Dimensions originales/cibles égales à la sortie, crop0. Même recette que v9 G353, dont les résultats sont repris sans nouvelle exécution.',
'<b>Précision :</b> UNet et deux encodeurs FP16 GPU0, VAE upcast FP32 et tuilage. PyTorch2.6.0+cu124, Diffusers0.32.2, Transformers4.49.0 ; aucun paquet ni pilote modifié. Sources et configurations vérifiées avant/après.',
'<b>Provenance :</b> RunDiffusion/Juggernaut-XI-v11, révision f836518c, fichier 7,105 Go, SHA256 33e58e86…5b42719e. Checkpoint complet : UNet, encodeurs et VAE propres au modèle. Carte auteur et licences archivées.',
'<b>Licence et attribution :</b> modèle RunDiffusion / KandooAI, CC BY-NC-ND4.0, conditions auteur additionnelles et licence du SDXL de base. Essai privé non commercial, poids non redistribués. Attribution conservée sur les images du rapport.',
'<b>Compatibilité :</b> le buffer CLIP position_ids stocké en FP16 contient des valeurs non entières. Transformers l’ignore et recrée la séquence standard0–76. Aucun poids modifié ; équivalence avec d’autres interfaces non vérifiée.',
'<b>Accès :</b> carte mentionnant un accès soumis à acceptation, mais API officielle gated=false et URL auteur accessible publiquement sans authentification (HTTP200). Aucun formulaire, compte ou renseignement personnel transmis.',
'<b>Isolation et mesure :</b> une V100 à300W, garde GPU/HBM65/70°C ; inférence sans réseau sortant, verrou et limites de ressources. Latents et décodage finis contrôlés. Temps encodage + débruitage + décodage + contrôles ; pics échantillonnés.',
'<b>Limites :</b> huit natives, revue GPT non aveugle sur aperçus réduits. Carré1024² commun au comparatif ; formats auteur832×1216/1216×832 non testés. V9 historique, pas de classement universel. Machine allumée, GPU libres et services actifs.'
]
d['short_decision']=notes['decision'];d['promotion_allowed']=False;d['completion']['visual_acceptance']='REVIEWED_NOT_PROMOTED';d['execution_summary']='12 nouvelles générations achevées, 30 appels UNet chacune, répétition exacte. 12 PNG vérifiés, sources/configs/runtime inchangés. GPU libres, cinq services actifs et Memory-engine en marche. Machine allumée.'
(root/'g355-data.json').write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n');print(json.dumps(q));print('Speed ratio',factor)
