from pathlib import Path
import json,statistics
root=Path(__file__).parent
d=json.loads((root/'g347-data.json').read_text());base=json.loads((root/'g346-data.json').read_text())
notes=[
('Proposée','Cinq doigts séparés, paume et poignet visibles. Texture un peu lissée ; contrôle 512² hors score.','Même réussite du petit format que G346, sans prédire la conformité à 1024².'),
('Rejetée','Six doigts : quatre doigts centraux et deux appendices latéraux.','SLG ne corrige pas cette seed ; même défaut que G346-01 et Klein G340-01.'),
('Proposée','Cinq doigts distincts : quatre dressés et un pouce à droite. Paume et poignet cohérents, légère texture lissée.','Gain sur G346-02 qui avait six doigts ; rejoint la proposition Klein G340-02.'),
('Proposée','Une tasse rouge à gauche et un bol bleu à droite, complets sur fond gris. Anse ouverte et céramique crédible.','Conformité maintenue par rapport à G346-03 et Klein G340-03.'),
('Proposée','Deux objets complets, couleurs et positions conformes. Anse de la tasse ouverte et lisible.','Amélioration sur G346-04 : la réserve sur l’anse est levée dans cette revue.'),
('Rejetée','Poignée et pièce ressemblant à une lame séparées ; aucun katana assemblé avec son fourreau cohérent.','Changement de composition, mais le défaut structurel de G346-05 persiste.'),
('Rejetée','Plusieurs pièces supplémentaires et dissociées, lame et poignées incompatibles ; katana non cohérent.','Même famille d’échec que G346-06 ; les matières ne compensent pas la structure.'),
('Rejetée','Deux adultes en pied, mais une main de la femme reste cachée ; pieds et chaussures déformés.','Une main féminine apparaît avec SLG, sans satisfaire complètement la visibilité demandée.'),
('Rejetée','Couleurs et duo respectés, mains visibles, mais jambes et pieds coupés par le cadre.','Cadrage toujours non conforme comme G346-08 ; Klein G340-08 était proposé.'),
('Rejetée','Répétition exacte de 01 : mêmes pixels, même PNG et six doigts.','Hors score natif ; la répétition confirme le défaut de la première seed.'),
('Rejetée','Format 16:9 : deux adultes en pied, mais mains de la femme cachées dans les manches.','SLG ne corrige pas la contrainte manquante de G346-10 ; hors score natif.'),
('À revoir','Format 4:3 : deux adultes en pied, mains visibles, mais mains/gants peu lisibles et pieds féminins disproportionnés.','Comme G346-11, cadrage satisfaisant mais réserves anatomiques ; hors score natif.')]
reviews={str(i):{'verdict':v,'comment':c,'comparison':k,'rendering':'Revue GPT provisoire ; aucune validation utilisateur attribuée.'} for i,(v,c,k) in enumerate(notes)}
assert len(d['results'])==12 and all(x['transformer_calls']==47 and x['slg_calls']==7 for x in d['results'])
assert d['completion']['repeat_same_pixels'] and d['results'][1]['png_sha256']==d['results'][9]['png_sha256']
assert d['health_final']['runtime_unchanged'] and all(x['match'] for x in d['health_final']['png_checks'])
native=[x for x in d['results'] if x['condition']=='quality'];median=statistics.median(x['seconds'] for x in native);baseline=base['native_summary']['median_seconds'];pct=(median/baseline-1)*100
d['reviews']=reviews
for row in d['results']:row['visual']=reviews[str(row['index'])]['verdict']
d['native_summary']={'proposed':3,'review':0,'rejected':5,'total':8,'median_seconds':median,'baseline_seconds':baseline,'overhead_percent':pct}
d['completion']['visual_acceptance']='REVIEWED_NOT_PROMOTED';d['promotion_allowed']=False
d['conclusion']='<b>SLG apporte un gain limité : 3/8 proposées contre 1/8 sans SLG.</b> Une main et l’anse de la tasse sont corrigées. Les katanas et les duos restent non conformes. Aucun remplacement de Klein proposé.'
d['summary_paragraphs']=[
f'<b>Coût mesuré :</b> {median:.2f} s par image 1024² contre {baseline:.2f} s, soit +{pct:.1f} %. Même modèle, mêmes prompts et seeds ; 47 passages du transformer dont 7 avec couches sautées.',
'<b>Sur huit images :</b> main 02 et objets 03/04 proposés ; main 01, katanas 05/06 et duos 07/08 rejetés. Le contrôle 512² est proposé ; répétition et formats écran sont hors score.',
'<b>Matériel :</b> une V100, pic 10 556 Mio, GPU 47 °C / HBM 52 °C. Deuxième V100 au repos ; runtime inchangé, services actifs, GPU libérés.',
'<b>Décision :</b> gain insuffisant sur cette petite grille. Klein conserve 5/8 à environ 3,40 s ; Z-Image G344, apprécié pour son rendu, reste réservé aux demandes détaillées. Ces avis restent à valider par toytoy.'
]
d['method_paragraphs']=[
'<b>Comparaison contrôlée :</b> témoin G346 et variante G347 : mêmes poids, cache d’encodages, prompts, seeds, résolutions, FP16, 40 étapes, CFG 4,5, FlowMatchEuler shift 3, négatif vide. Seul réglage génératif ajouté : Skip Layer Guidance.',
'<b>SLG :</b> couches [7,8,9], force 2,8, début 0,01, fin 0,2. Dans Diffusers 0.37.0 : 40 passages complets et 7 passages supplémentaires avec couches sautées. Compteur non modifiant vérifié sur les 12 images. Ce n’est pas une reproduction du workflow ComfyUI auteur, qui utilise d’autres réglages.',
'<b>Exécution :</b> GPU0 V100 16 Go, transformer FP16 ; VAE FP32 tuilé. CLIP-L, CLIP-G et T5-XXL encodés sur CPU FP32 lors de G346 ; cache réutilisé et SHA vérifié. PyTorch 2.6.0+cu124, Transformers 4.56.1. Aucun téléchargement pendant la génération.',
'<b>Temps :</b> génération et décodage, contrôles numériques et sauvegarde du latent inclus ; chargement, encodage initial et écriture PNG finale exclus. Médiane sur les huit natives seulement. Les 42,89 s d’encodage sont le coût initial G346, pas un nouvel encodage G347.',
'<b>Intégrité :</b> 12 PNG vérifiés, répétition pixel et PNG identiques. Aucun incident de génération. Consigne GPU 300 W ; pic ponctuel 309,09 W. Aucun total d’énergie mesuré. GPU/HBM au maximum 47/52 °C ; services actifs, Memory-engine en marche.',
'<b>Provenance :</b> poids G346 réutilisés, auteur Stability AI et copie publique adamo1139 aux SHA identiques auteur. Licence Stability AI Community archivée. Sources et révisions exactes dans le rapport du dépôt ; aucune promotion en production.',
'<b>Limites :</b> quatre scènes et deux seeds, revue visuelle subjective. Comparaison Klein/Z-Image de recettes différentes ; le score ne mesure pas une supériorité générale. Proposée ne signifie pas approuvée par l’utilisateur. Machine laissée allumée.'
]
d['run_paths']=['/srv/eidolon/workspaces/media-20261112/sd35-slg-g347/run01','/srv/eidolon/workspaces/media-20261112/sd35-slg-g347/run02'];d['historical_references']=['G346','G340 corrected','G344']
(root/'g347-data.json').write_text(json.dumps(d,ensure_ascii=False,indent=2));(root/'g347-reviews.json').write_text(json.dumps(reviews,ensure_ascii=False,indent=2))
print(json.dumps(d['native_summary']))
