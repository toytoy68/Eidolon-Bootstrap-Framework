# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : review_g353.py
# Description : Synthèse et contrôles du comparatif Juggernaut
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
from pathlib import Path
import json,statistics,datetime
from zoneinfo import ZoneInfo
root=Path(__file__).parent;d=json.loads((root/'g353-data.json').read_text());notes=json.loads((root/'g353-review-notes.json').read_text())
assert len(d['results'])==24 and all(x['unet_calls']==30 and x['decoder_calls']>=1 for x in d['results'])
assert d['completion']['repeat_same_pixels']=={'v10':True,'v9':True}
assert d['health_final']['runtime_unchanged'] and all(x['match'] for x in d['health_final']['png_checks']) and all(x['match'] for x in d['health_final']['source_checks'])
summaries={}
for name in ['v10','v9']:
 assert set(notes['reviews'][name])=={str(i) for i in range(12)}
 rows=sorted([x for x in d['results'] if x['model']==name],key=lambda x:x['index']);assert [x['index'] for x in rows]==list(range(12))
 assert rows[1]['sha256']==rows[9]['sha256']
 native=[x for x in rows if x['condition']=='quality'];assert len(native)==8
 c={k:sum(notes['reviews'][name][str(i)]['verdict']==v for i in range(1,9)) for k,v in [('proposed','Proposée'),('review','À revoir'),('rejected','Rejetée')]};assert sum(c.values())==8
 g=d['telemetry_by_model'][name]['gpus']['0'];summaries[name]={**c,'median_seconds':statistics.median(x['seconds'] for x in native),'min_seconds':min(x['seconds'] for x in native),'max_seconds':max(x['seconds'] for x in native),'peak_mib':g['memory.used']['max'],'gpu_c':g['temperature.gpu']['max'],'hbm_c':g['temperature.memory']['max'],'power_w':g['power.draw']['max']}
 for x in rows:
  other=next(y for y in d['results'] if y['model']!=name and y['index']==x['index'])
  assert all(x[k]==other[k] for k in ['case','prompt','seed','steps','cfg','negative_prompt','width','height','condition'])
  x['visual']=notes['reviews'][name][str(x['index'])]['verdict']
d['summary']=summaries;d['reviews']=notes['reviews'];d['comparisons']=notes['comparisons'];a=summaries['v10'];b=summaries['v9']
d['conclusion']=f'<b>Juggernaut v10 : {a["proposed"]}/8 images proposées, contre {b["proposed"]}/8 en v9.</b> Même recette sur une V100 ; {a["median_seconds"]:.2f} s médianes pour v10 et {b["median_seconds"]:.2f} s pour v9.'
d['summary_paragraphs']=[
 '<b>Constat visuel :</b> '+notes['visual_summary'],
 '<b>Temps :</b> encodage des textes, génération et décodage compris ; chargement et écriture PNG exclus. Les temps FLUX des rapports précédents excluaient l’encodage : comparaison directe de vitesse à éviter.',
 f'<b>Matériel :</b> GPU0 seul ; maxima GPU/HBM v10 {a["gpu_c"]:.0f}/{a["hbm_c"]:.0f} °C, v9 {b["gpu_c"]:.0f}/{b["hbm_c"]:.0f} °C. Répétitions pixel-identiques pour les deux modèles.',
 '<b>Décision :</b> '+notes['decision']+' Les propositions sont des avis GPT provisoires, aucune validation utilisateur attribuée.'
]
d['method_paragraphs']=[
 '<b>Plan :</b> douze images par modèle : contrôle 512², huit natives 1024², répétition, 1024 × 576 et 768 × 576. Quatre scènes, seeds 20261113/20261114. Prompts figés et négatif vide, aucun refiner, LoRA, retouche ou tri des seeds.',
 '<b>Recette commune :</b> DPM++ 2M Karras, 30 étapes, CFG 5 ; dimensions originales/cibles égales à la sortie, crop 0. Trente appels UNet mesurés, latents et décodage finis. V9 régénéré dans le même lot. Poids complets de chaque checkpoint, y compris encodeurs et VAE.',
 '<b>Précision :</b> UNet et encodeurs GPU0 FP16, VAE avec upcast FP32 au décodage ; tuilage activé. Même Diffusers 0.32.2 / PyTorch 2.6.0+cu124 / Transformers 4.49.0 que G333. Aucun paquet installé ni runtime modifié.',
 '<b>Provenance :</b> v10 RunDiffusion 35e4f3cc, v9 cf419233 ; fichiers safetensors SHA vérifiés. CreativeML OpenRAIL-M déclaré, restriction de service API payant et conditions du SDXL de base archivées. Essai privé local.',
 '<b>Incident corrigé :</b> premier essai arrêté avant image lors de l’écriture du réglage -inf en JSON. Exporteur corrigé pour représenter cette valeur en texte ; calcul du scheduler inchangé. Essai et source initiaux conservés.',
 '<b>Mesure :</b> temps encodage + débruitage + décodage + contrôles, hors chargement et sauvegarde PNG. Sonde GPU/HBM/VRAM/puissance ; ordre fixe v10 puis v9. Pics thermiques échantillonnés, pas comparaison d’efficacité énergétique.',
 '<b>Isolation :</b> une V100 à 300 W, garde 65 °C GPU / 70 °C HBM. Inférence sans accès réseau sortant, verrou de campagne, limites de ressources. GPU libres et services actifs après les tests ; machine allumée.',
 '<b>Limites :</b> revue GPT non aveugle sur aperçus réduits, huit natives seulement. 1024² sert au comparatif ; les formats auteur 832 × 1216 / 1216 × 832 restent non testés. Aucun score universel ni promotion automatique.'
]
d['promotion_allowed']=False;d['completion']['visual_acceptance']='REVIEWED_NOT_PROMOTED';d['short_decision']=notes['decision']
d['execution_summary']='24 images terminées après correction de l’export JSON ; 30 appels UNet par image et deux répétitions exactes. Contrôle final '+datetime.datetime.fromisoformat(d['health_final']['time']).astimezone(ZoneInfo('Europe/Paris')).isoformat()+' : sources et runtime inchangés, empreintes de 24 PNG vérifiées, GPU libres, services actifs et Memory-engine en fonctionnement. Machine laissée allumée.'
(root/'g353-data.json').write_text(json.dumps(d,ensure_ascii=False,indent=2));print(json.dumps(summaries))
