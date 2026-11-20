# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : review_g352.py
# Description : Revue provisoire du lot FLUX Schnell Q4
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
from pathlib import Path
import json,statistics,datetime
from zoneinfo import ZoneInfo
root=Path(__file__).parent;d=json.loads((root/'g352-data.json').read_text());baseline=json.loads((root/'g351-data.json').read_text());full=json.loads((root/'g339-data.json').read_text());reviews=json.loads((root/'g352-review-notes.json').read_text())
assert set(reviews)=={str(i) for i in range(12)}
for r in reviews.values():r['rendering']='Revue GPT provisoire ; aucune validation utilisateur attribuée.'
assert len(d['results'])==12 and all(x['transformer_calls']==4 and x['block_calls']==228 and x['steps']==4 and x['guidance']==0 for x in d['results'])
assert set(d['manifest']['parameter_bytes_by_device'])=={'cuda:0'} and d['manifest']['gguf_linear_modules']==494
assert d['completion']['repeat_same_pixels'] and d['results'][1]['png_sha256']==d['results'][9]['png_sha256']
assert d['health_final']['runtime_unchanged'] and all(x['match'] for x in d['health_final']['png_checks'])
for a,b in zip(d['results'],baseline['results']):
 assert all(a[k]==b[k] for k in ['index','case','width','height','seed','steps','guidance','prompt'])
native=[x for x in d['results'] if x['condition']=='quality'];median=statistics.median(x['seconds'] for x in native);bm=statistics.median(x['seconds'] for x in baseline['results'] if x['condition']=='quality')
counts={k:sum(reviews[str(i)]['verdict']==v for i in range(1,9)) for k,v in [('proposed','Proposée'),('review','À revoir'),('rejected','Rejetée')]};assert sum(counts.values())==8
d['reviews']=reviews
for row in d['results']:row['visual']=reviews[str(row['index'])]['verdict']
d['native_summary']={**counts,'total':8,'median_seconds':median,'q8_seconds':bm,'time_ratio_vs_q8':median/bm}
d['completion']['visual_acceptance']='REVIEWED_NOT_PROMOTED';d['promotion_allowed']=False
g=d['telemetry']['gpus']['0'];memory=g['memory.used']['max']
fm=statistics.median(x['seconds'] for x in full['results'] if x['condition']=='quality')
q8_memory=baseline['telemetry']['gpus']['0']['memory.used']['max'];saving=(1-memory/q8_memory)*100
for a,b in zip(d['results'],full['results']):
 assert all(a[k]==b[k] for k in ['index','case','width','height','seed','steps','guidance','prompt'])
d['native_summary'].update(full_fp16_seconds=fm,vram_saved_vs_q8_pct=saving,q8_peak_mib=q8_memory)
d['conclusion']=f'<b>Schnell Q4 : {saving:.1f} % de VRAM en moins que Q8.</b> {counts["proposed"]}/8 images proposées ; {median:.2f} s médianes contre {bm:.2f} s pour Q8, sur la même V100.'
d['summary_paragraphs']=[
 f'<b>Conformité :</b> {counts["proposed"]} proposées, {counts["review"]} à revoir, {counts["rejected"]} rejetées sur huit natives. Q8 et FP16 : 4/8 chacun. La main 01 devient plus floue ; le katana 06 gagne une poignée détachée. Avis GPT provisoires.',
 f'<b>Temps :</b> {median:.2f} s contre {bm:.2f} s en Q8 ({(median/bm-1)*100:+.1f} %). Le complet FP16 réparti sur deux cartes faisait {fm:.2f} s. Temps hors encodage des textes et chargement du modèle.',
 f'<b>Mémoire et chauffe :</b> pic {memory:.0f} Mio ({memory/1024:.2f} Gio), contre {q8_memory:.0f} Mio en Q8. GPU1 au repos. Maxima GPU {g["temperature.gpu"]["max"]:.0f} °C / HBM {g["temperature.memory"]["max"]:.0f} °C.',
 '<b>Décision :</b> à réserver aux contraintes de VRAM. Sur ce lot, moins de mémoire mais une finition moins bonne et aucun gain de vitesse. Aucun remplacement des favoris et aucune promotion.'
]
d['method_paragraphs']=[
 '<b>Comparaison :</b> mêmes prompts, seeds, quatre étapes et guidage 0 que G351/G339. Q8 et Q4 utilisent GPU0 seulement, même runtime et même attention. FP16 complet utilise deux cartes : son temps ne permet pas d’isoler le coût de la quantification.',
 '<b>Précision :</b> fichier Q4_0 avec tenseurs auxiliaires F16 ; déquantification dynamique, calcul FP16, 494 modules GGUFLinear. Tous les paramètres du générateur sur GPU0, sans offload CPU. Quatre appels du modèle et 228 appels de blocs contrôlés par image.',
 '<b>Recette :</b> FlowMatchEuler shift 1, pas de décalage dynamique ; attention découpée en 256 requêtes. VAE Flux FP32 sur GPU0, tuiles de 512 pixels. CLIP-L/T5 CPU FP32, 256 tokens, embeddings FP16.',
 f'<b>Chronométrage :</b> quatre nouveaux encodages CPU en {d["manifest"]["encode_seconds"]:.2f} s, puis cache pour la grille. Chargement grille : {d["manifest"]["load_seconds"]:.2f} s. Temps image : génération, décodage, contrôles et sauvegarde du latent ; écriture PNG finale exclue.',
 '<b>Traçabilité :</b> conversion city96 f495746, SHA vérifié ; Apache 2.0 et licence MIT gguf archivées. PyTorch 2.6.0+cu124, Diffusers 0.32.2 et Transformers 4.49.0 inchangés. gguf 0.17.1 isolé ; aucun kernel distant.',
 '<b>Exécution :</b> douze images terminées ; répétition à pixels et PNG identiques. Correction d’un chemin de copie de licence pendant la préparation, conservée dans les preuves. Aucun échec de génération.',
 f'<b>Matériel :</b> consigne 300 W, pic ponctuel {g["power.draw"]["max"]:.2f} W, sans mesure d’énergie totale. Garde 65 °C GPU / 70 °C HBM. Services actifs et GPU libres après les tests ; machine laissée allumée.',
 '<b>Limites :</b> huit images natives, appréciation subjective sur aperçus réduits ; PNG originaux conservés. Deux seeds ne mesurent pas la fiabilité générale. « Proposée » ne signifie pas approuvée par toytoy.'
]
d['execution_summary']='Douze images terminées, latents et pixels finis, répétition pixel et PNG identiques. Incident de préparation limité à la copie de licence, corrigé avant génération et archivé. Contrôle final '+datetime.datetime.fromisoformat(d['health_final']['time']).astimezone(ZoneInfo('Europe/Paris')).isoformat()+' : runtime partagé inchangé, douze SHA PNG vérifiés, aucun client GPU, cinq services actifs et Memory-engine en marche. Machine laissée allumée.'
d['short_decision']='Moins de VRAM, mais main 01 plus floue et poignée surnuméraire en 06 ; aucun gain de vitesse, aucune promotion.'
d['run_paths']=['/srv/eidolon/workspaces/media-20261112/flux-q8-g352/run01','/srv/eidolon/workspaces/media-20261112/flux-q8-g352/run02'];d['historical_references']=['G339','G351']
(root/'g352-data.json').write_text(json.dumps(d,ensure_ascii=False,indent=2));(root/'g352-reviews.json').write_text(json.dumps(reviews,ensure_ascii=False,indent=2))
print(json.dumps(d['native_summary']))
