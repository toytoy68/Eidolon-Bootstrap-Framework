# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : review_g351.py
# Description : Revue provisoire du lot FLUX Schnell Q8
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
from pathlib import Path
import json,statistics,datetime
from zoneinfo import ZoneInfo
root=Path(__file__).parent;d=json.loads((root/'g351-data.json').read_text());baseline=json.loads((root/'g339-data.json').read_text());reviews=json.loads((root/'g351-review-notes.json').read_text())
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
d['native_summary']={**counts,'total':8,'median_seconds':median,'full_fp16_seconds':bm,'time_ratio_vs_full':median/bm}
d['completion']['visual_acceptance']='REVIEWED_NOT_PROMOTED';d['promotion_allowed']=False
g=d['telemetry']['gpus']['0'];memory=g['memory.used']['max']
d['conclusion']=f'<b>FLUX Schnell Q8 : une V100 suffit, mais le calcul prend {median/bm:.2f} fois plus de temps.</b> {counts["proposed"]}/8 images proposées à {median:.2f} s médianes. Le gain est matériel ; les défauts de conformité restent à examiner scène par scène.'
d['summary_paragraphs']=[
 f'<b>Conformité :</b> {counts["proposed"]} proposées, {counts["review"]} à revoir, {counts["rejected"]} rejetées sur huit natives. Le détail des mains, des katanas et du cadrage figure dans les pages suivantes. Score du complet G339 : 4/8 ; Klein : 5/8.',
 f'<b>Temps :</b> {median:.2f} s contre {bm:.2f} s pour le complet réparti sur deux V100. Même recette Schnell ; quantification et nombre de cartes changent ensemble. Le Q8 n’apporte pas de gain de vitesse dans cette configuration.',
 f'<b>Mémoire :</b> pic {memory:.0f} Mio ({memory/1024:.2f} Gio) sur GPU0 ; GPU1 au repos. Le complet utilisait 13 346 / 13 082 Mio sur deux cartes. Maxima GPU {g["temperature.gpu"]["max"]:.0f} °C et HBM {g["temperature.memory"]["max"]:.0f} °C.',
 '<b>Décision :</b> conserver comme option Schnell sur une carte, quand libérer la seconde est prioritaire. Aucun remplacement automatique des favoris ; Klein reste plus rapide avec une seule carte dans notre recette. Aucune promotion.'
]
d['method_paragraphs']=[
 '<b>Recette :</b> même grille, prompts, seeds et moteur que Schnell G339. Quatre étapes, guidage 0, scheduler FlowMatchEuler shift 1 sans décalage dynamique. Attention découpée en 256 requêtes, VAE FP32 tuilé à 512 pixels.',
 '<b>Q8 sur GPU0 :</b> poids Q8_0 et F16, déquantification dynamique et calcul FP16. 494 modules quantifiés, tous les paramètres sur GPU0 ; aucun offload CPU du générateur. Quatre appels du modèle et 228 appels de blocs contrôlés par image.',
 f'<b>Textes et temps :</b> CLIP-L/T5 CPU FP32, 256 tokens. Quatre nouveaux encodages : {d["manifest"]["encode_seconds"]:.2f} s, puis cache réutilisé. Temps affichés hors chargement ({d["manifest"]["load_seconds"]:.2f} s), encodage et écriture PNG ; contrôles et sauvegarde du latent inclus.',
 '<b>Incident corrigé :</b> premier chargement resté sur CPU, détecté avant génération. Transfert GPU explicite ajouté au runner ; essai échoué conservé. Les douze images suivantes sont terminées, répétition pixel et PNG identiques.',
 '<b>Environnement :</b> PyTorch 2.6.0+cu124 / Diffusers 0.32.2 / Transformers 4.49.0 inchangés. gguf 0.17.1 ajouté dans un dossier isolé. Aucun kernel distant. Conversion city96 f495746, empreinte du fichier vérifiée ; Apache 2.0 et licence gguf MIT archivées.',
 f'<b>Matériel :</b> consigne 300 W ; pic ponctuel {g["power.draw"]["max"]:.2f} W, sans mesure d’énergie totale. Garde 65 °C GPU / 70 °C HBM. Après le lot : GPU libres, cinq services actifs et Memory-engine en marche, machine allumée.',
 '<b>Limites :</b> huit natives, revue subjective sur aperçus réduits. Les PNG natifs sont conservés. Quantification et répartition matérielle varient ensemble ; ce comparatif n’isole pas leur coût respectif. Proposée ne signifie pas approuvée par toytoy.'
]
d['execution_summary']='Douze images terminées après correction du placement initial, latents et pixels finis, répétition pixel et PNG identiques. Aucun incident dans les deux lots achevés. Contrôle final '+datetime.datetime.fromisoformat(d['health_final']['time']).astimezone(ZoneInfo('Europe/Paris')).isoformat()+' : runtime partagé inchangé, douze SHA PNG vérifiés, aucun client GPU, cinq services actifs et Memory-engine en marche. Machine laissée allumée.'
d['short_decision']='Schnell tient sur une seule carte, mais le Q8 ne gagne pas en vitesse ; option pour libérer GPU1, aucune promotion.'
d['run_paths']=['/srv/eidolon/workspaces/media-20261112/flux-q8-g351/run01','/srv/eidolon/workspaces/media-20261112/flux-q8-g351/run02'];d['historical_references']=['G339','G340 corrected']
(root/'g351-data.json').write_text(json.dumps(d,ensure_ascii=False,indent=2));(root/'g351-reviews.json').write_text(json.dumps(reviews,ensure_ascii=False,indent=2))
print(json.dumps(d['native_summary']))
