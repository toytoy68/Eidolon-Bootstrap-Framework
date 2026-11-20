# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : review_g349.py
# Description : Revue provisoire du lot SD3.5 Large
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
from pathlib import Path
import json,statistics,datetime
from zoneinfo import ZoneInfo
root=Path(__file__).parent;d=json.loads((root/'g349-data.json').read_text());turbo=json.loads((root/'g348-data.json').read_text());klein=json.loads((root/'g340-data.json').read_text());reviews=json.loads((root/'g349-review-notes.json').read_text())
assert set(reviews)=={str(i) for i in range(12)}
for r in reviews.values():r['rendering']='Revue GPT provisoire ; aucune validation utilisateur attribuée.'
assert len(d['results'])==12 and all(x['block_calls']=={'0':532,'1':532} and x['steps']==28 and x['guidance']==3.5 for x in d['results'])
assert set(d['manifest']['parameter_bytes_by_device'])=={'cuda:0','cuda:1'}
assert d['completion']['repeat_same_pixels'] and d['results'][1]['png_sha256']==d['results'][9]['png_sha256']
assert d['health_final']['runtime_unchanged'] and all(x['match'] for x in d['health_final']['png_checks'])
native=[x for x in d['results'] if x['condition']=='quality'];median=statistics.median(x['seconds'] for x in native);tm=statistics.median(x['seconds'] for x in turbo['results'] if x['condition']=='quality')
counts={k:sum(reviews[str(i)]['verdict']==v for i in range(1,9)) for k,v in [('proposed','Proposée'),('review','À revoir'),('rejected','Rejetée')]};assert sum(counts.values())==8
d['reviews']=reviews
for row in d['results']:row['visual']=reviews[str(row['index'])]['verdict']
d['native_summary']={**counts,'total':8,'median_seconds':median,'turbo_seconds':tm,'time_ratio_vs_turbo':median/tm}
d['completion']['visual_acceptance']='REVIEWED_NOT_PROMOTED';d['promotion_allowed']=False
g=d['telemetry']['gpus'];temp=f"{g['0']['temperature.gpu']['max']:.0f}/{g['1']['temperature.gpu']['max']:.0f}";hbm=f"{g['0']['temperature.memory']['max']:.0f}/{g['1']['temperature.memory']['max']:.0f}";mem=f"{g['0']['memory.used']['max']:,.0f} / {g['1']['memory.used']['max']:,.0f}".replace(',',' ')
d['conclusion']=f"<b>SD3.5 Large : {counts['proposed']}/8 images proposées, à {median:.2f} s médianes.</b> La peau et les matières gagnent en détail, mais les deux mains ont six doigts et les katanas restent incohérents. Aucun avantage global établi face à Turbo."
d['summary_paragraphs']=[
f"<b>Conformité :</b> {counts['proposed']} proposées, {counts['review']} à revoir, {counts['rejected']} rejetées sur huit natives. Objets 03/04 conformes ; mains 01/02 et katanas 05/06 rejetés. Duo 07 : {reviews['7']['verdict'].lower()} ; duo 08 : {reviews['8']['verdict'].lower()}.",
f"<b>Coût :</b> environ {median/tm:.1f} fois le temps de Turbo ({tm:.2f} s), avec les mêmes deux V100. Poids et recette diffèrent : ce n’est pas un test du seul nombre d’étapes. Encodages identiques réutilisés.",
f"<b>Matériel :</b> pics VRAM GPU0/GPU1 : {mem} Mio. Maxima GPU {temp} °C, HBM {hbm} °C. Répartition réelle des blocs, aucune erreur de génération et runtime inchangé.",
'<b>Décision :</b> ne pas remplacer les candidats rapides. Un rendu plus détaillé ne suffit pas à compenser les défauts et le délai sur cette grille. Z-Image G344 conserve son rôle détaillé à la demande selon ta préférence ; aucune promotion.'
]
d['method_paragraphs']=[
'<b>Recette :</b> SD3.5 Large, 28 étapes, guidage 3,5, sans SLG ; FlowMatchEuler shift 3. Même grille de quatre scènes et deux seeds 20261113/20261114, contrôle 512², répétition et deux formats écran. Aucun prompt ajusté après observation.',
'<b>Deux V100 :</b> générateur FP16, blocs 0-18 GPU0 et 19-37 GPU1, entrées et sortie GPU0. 8,17/7,94 Go de paramètres ; 532 appels de blocs par carte et par image (19 x 28), contrôlés sans modifier les tenseurs. CFG groupé natif. VAE GPU0 FP32 tuilé.',
'<b>Encodages :</b> CLIP-L, CLIP-G et T5-XXL CPU FP32, cache G346 réutilisé après comparaison SHA des poids, configurations et tokenizers. 42,89 s est le coût historique des cinq textes, sans nouvel encodage G349.',
f"<b>Temps :</b> génération/décodage, contrôles numériques et sauvegarde du latent inclus ; chargement ({d['manifest']['load_seconds']:.2f} s), encodage et écriture PNG finale exclus. Médiane sur huit natives, aucune mesure depuis clic ni énergie totale.",
f"<b>Intégrité :</b> 12 PNG vérifiés ; répétition pixel et PNG identiques. Aucun incident de génération. Consignes 300 W par V100 ; pics ponctuels {g['0']['power.draw']['max']:.2f}/{g['1']['power.draw']['max']:.2f} W. GPU libres, cinq services actifs et VM Memory-engine en marche.",
'<b>Provenance :</b> auteur Stability AI, révision ceddf0a ; copie publique adamo1139, révision 5d868ff. Sept fichiers de poids aux SHA identiques auteur, licence Stability AI Community identique G348 archivée. Génération locale sans réseau sortant ; aucun code du miroir exécuté.',
'<b>Limites :</b> recette auteur BF16 adaptée en FP16, sans validation d’une équivalence visuelle. PyTorch 2.6.0+cu124 / Diffusers 0.37.0 / Transformers 4.56.1 inchangés. Petite grille et avis subjectifs ; proposée ne vaut pas approbation utilisateur. Machine laissée allumée.'
]
d['execution_summary']='Douze images terminées, latents/pixels finis, répétition pixel et PNG identiques. Aucun incident de génération ni erreur télémétrie. Contrôle final horodaté '+datetime.datetime.fromisoformat(d['health_final']['time']).astimezone(ZoneInfo('Europe/Paris')).isoformat()+' (Europe/Paris) : runtime inchangé, douze SHA PNG vérifiés, aucun client GPU, cinq services actifs et Memory-engine en marche. Machine laissée allumée.'
d['short_decision']='Deux mains à six doigts, katanas incohérents ; aucun avantage global établi face à Turbo malgré les détails supplémentaires.'
d['run_paths']=['/srv/eidolon/workspaces/media-20261112/sd35-large-g349/run01','/srv/eidolon/workspaces/media-20261112/sd35-large-g349/run02'];d['historical_references']=['G348','G340 corrected','G344']
(root/'g349-data.json').write_text(json.dumps(d,ensure_ascii=False,indent=2));(root/'g349-reviews.json').write_text(json.dumps(reviews,ensure_ascii=False,indent=2))
print(json.dumps(d['native_summary']))
