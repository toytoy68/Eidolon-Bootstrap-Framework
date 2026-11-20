# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : review_g350.py
# Description : Revue provisoire du lot Sana Sprint 0,6B
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
from pathlib import Path
import json,statistics,datetime
from zoneinfo import ZoneInfo
root=Path(__file__).parent
d=json.loads((root/'g350-data.json').read_text())
baseline=json.loads((root/'g345-data.json').read_text())
notes=[
 ('À revoir','Cinq doigts visibles, mais paume très segmentée, articulations artificielles et reflets verdâtres. Contrôle 512² hors score.','Meilleur comptage que les échecs natifs, sans valider un rendu anatomique naturel.'),
 ('Rejetée','Cinq doigts, mais extrémités et pouce déformés ; des ongles apparaissent côté paume. Anatomie incohérente malgré la texture.','La 1,6B gardait une réserve anatomique ; la 0,6B ajoute des défauts marqués. Klein a six doigts sur cette seed.'),
 ('Rejetée','Six doigts : quatre doigts centraux et deux appendices latéraux. Défaut anatomique éliminatoire.','Même échec de comptage que Sprint 1,6B ; Klein est proposé sur cette seed.'),
 ('Proposée','Exactement deux objets entiers : tasse rouge à gauche et bol bleu à droite. Ombres et reflets plausibles.','Les trois configurations respectent la composition. Quelques irrégularités de surface ne changent pas le sujet.'),
 ('Proposée','Tasse rouge et bol bleu séparés, complets et correctement placés. Céramique et lumière cohérentes.','Les trois modèles réussissent cette scène simple ; aucune supériorité visuelle générale démontrée.'),
 ('Rejetée','Lame claire détachée de la poignée ; pièce noire à droite avec poignée et garde. Aucun katana complet et fourreau distinct cohérents.','Comme Sprint 1,6B et Klein, les matières masquent une construction impossible.'),
 ('Rejetée','Trois éléments au lieu du couple demandé : fragment de lame séparé, pièce centrale hybride et fourreau à poignée.','Le tissu et le métal sont détaillés, mais la structure échoue comme chez les deux références.'),
 ('Rejetée','Deux adultes et bonnes couleurs, mais cadrage coupé aux cuisses : jambes et pieds absents. Mains également peu lisibles.','La 1,6B cadrait plus large sans tout respecter ; Klein est proposé pour son cadrage en pied.'),
 ('Rejetée','Deux adultes correctement placés devant le château ; jambes et pieds coupés par le bord inférieur.','Même limite de cadrage que la 1,6B sur cette seed ; Klein conserve les personnages entiers.'),
 ('Rejetée','Répétition exacte de G350-01 : mêmes pixels et PNG, donc mêmes défauts anatomiques. Hors score natif.','La reproductibilité est vérifiée ; elle ne constitue pas une nouvelle réussite visuelle.'),
 ('Rejetée','Format 16:9 : corps coupés vers la taille, mains et pieds hors cadre ; haut de la coiffure rogné.','Aucune des trois configurations ne respecte ici le portrait complet demandé.'),
 ('Rejetée','Format 4:3 : pieds de la femme masqués, proportions tassées, visages et mains déformés.','Le cadrage élargit la scène, mais la petite variante perd nettement en précision et en proportions.')
]
reviews={str(i):{'verdict':v,'comment':c,'comparison':cmp,'rendering':'Revue GPT provisoire ; aucune validation utilisateur attribuée.'} for i,(v,c,cmp) in enumerate(notes)}
assert len(d['results'])==12 and all(x['transformer_calls']==4 and x['steps']==4 and x['guidance']==4.5 for x in d['results'])
assert set(d['manifest']['parameter_bytes_by_device'])=={'cuda:0'}
assert d['completion']['repeat_same_pixels'] and d['results'][1]['png_sha256']==d['results'][9]['png_sha256']
assert d['health_final']['runtime_unchanged'] and all(x['match'] for x in d['health_final']['png_checks'])
for a,b in zip(d['results'],baseline['results']):
 assert all(a[k]==b[k] for k in ['index','case','width','height','seed','steps','guidance','prompt'])
native=[x for x in d['results'] if x['condition']=='quality']
median=statistics.median(x['seconds'] for x in native)
bm=statistics.median(x['seconds'] for x in baseline['results'] if x['condition']=='quality')
counts={k:sum(reviews[str(i)]['verdict']==v for i in range(1,9)) for k,v in [('proposed','Proposée'),('review','À revoir'),('rejected','Rejetée')]}
assert counts=={'proposed':2,'review':0,'rejected':6}
d['reviews']=reviews
for row in d['results']:row['visual']=reviews[str(row['index'])]['verdict']
d['native_summary']={**counts,'total':8,'median_seconds':median,'sprint_1600m_seconds':bm,'time_reduction_vs_1600m':1-median/bm}
d['completion']['visual_acceptance']='REVIEWED_NOT_PROMOTED';d['promotion_allowed']=False
g=d['telemetry']['gpus']['0'];memory=g['memory.used']['max'];old_memory=baseline['telemetry']['gpus']['0']['memory.used']['max']
d['conclusion']=f'<b>Sana Sprint 0,6B : 2/8 images proposées, à {median:.2f} s médianes.</b> Rapide et peu gourmand en VRAM, mais aucune amélioration de conformité face à la 1,6B. Les objets réussissent ; mains, katanas et duos échouent.'
d['summary_paragraphs']=[
 '<b>Conformité :</b> 2 proposées, aucune réserve et 6 rejets sur huit natives. La main 02 a six doigts ; la 01 conserve cinq doigts avec une anatomie incohérente. Duos trop serrés, katanas mal assemblés.',
 f'<b>Coût :</b> temps réduit de {(1-median/bm)*100:.1f} % face à la 1,6B ({bm:.2f} s). Même recette, mêmes encodages réutilisés et une seule V100. L’exemple auteur à deux étapes n’est pas testé ici.',
 f'<b>Matériel :</b> pic {memory:.0f} Mio ({memory/1024:.2f} Gio), contre {old_memory:.0f} Mio pour la 1,6B. Maxima GPU {g["temperature.gpu"]["max"]:.0f} °C et HBM {g["temperature.memory"]["max"]:.0f} °C. Aucun incident de génération.',
 '<b>Décision :</b> candidat aux aperçus simples sous contrainte mémoire ; aucun remplacement de Klein ou des favoris qualitatifs. Z-Image G344 reste réservé au détail à la demande selon ta préférence. Aucune promotion.'
]
d['method_paragraphs']=[
 '<b>Recette :</b> Sana Sprint 0,6B, quatre étapes SCM, guidage intégré 4,5, max_timesteps 1,57080, intermediate_timesteps=None. Même grille et réglages que Sprint 1,6B G345. Exemple auteur à deux étapes ; ce lot teste quatre étapes, pas la vitesse minimale.',
 '<b>Calcul :</b> générateur et DC-AE FP32 sur GPU0, décodage tuilé 512. Quatre appels du générateur comptés par image, sans modifier les tenseurs. FP32 conserve la plage numérique nécessaire sur V100 ; aucune équivalence visuelle BF16 revendiquée.',
 '<b>Textes :</b> quatre encodages Gemma2 CPU FP32 réutilisés depuis G345 après contrôle SHA des poids, configurations, tokenizers et cache. 26,76 s est leur coût historique ; aucun nouvel encodage dans ce lot.',
 f'<b>Temps :</b> génération, décodage, contrôles et sauvegarde du latent inclus ; chargement ({d["manifest"]["load_seconds"]:.2f} s), encodage et écriture PNG finale exclus. Médiane de huit natives 1024². Aucune mesure depuis clic ni énergie totale.',
 f'<b>Intégrité :</b> 12 PNG vérifiés, répétition pixel et PNG identiques. Consigne 300 W ; pic ponctuel observé {g["power.draw"]["max"]:.2f} W. GPU libres, cinq services actifs, VM Memory-engine en marche. Runtime inchangé.',
 '<b>Provenance :</b> dépôt auteur Efficient-Large-Model, révision aa76e7f. Poids et fichiers identifiés par SHA ; licence Apache 2.0 archivée, conditions Gemma et DC-AE conservées séparément. Génération locale sans réseau sortant.',
 '<b>Limites :</b> quatre scènes, deux seeds et revue subjective. PyTorch 2.6.0+cu124, Diffusers 0.37.0, Transformers 4.56.1. Aperçus réduits pour la revue, PNG natifs conservés. Proposée ne vaut pas approbation de toytoy ; machine laissée allumée.'
]
d['execution_summary']='Douze images terminées, latents/pixels finis, répétition pixel et PNG identiques. Aucun incident de génération ni erreur télémétrie. Contrôle final '+datetime.datetime.fromisoformat(d['health_final']['time']).astimezone(ZoneInfo('Europe/Paris')).isoformat()+' : runtime inchangé, douze SHA PNG vérifiés, aucun client GPU, cinq services actifs et Memory-engine en marche. Machine laissée allumée.'
d['short_decision']='Gain de temps et de VRAM, sans progrès de conformité ; candidat limité aux aperçus simples, aucune promotion.'
d['run_paths']=['/srv/eidolon/workspaces/media-20261112/sana-sprint-600m-g350/run01','/srv/eidolon/workspaces/media-20261112/sana-sprint-600m-g350/run02']
d['historical_references']=['G345','G340 corrected','G344']
(root/'g350-data.json').write_text(json.dumps(d,ensure_ascii=False,indent=2))
(root/'g350-reviews.json').write_text(json.dumps(reviews,ensure_ascii=False,indent=2))
print(json.dumps(d['native_summary']))
