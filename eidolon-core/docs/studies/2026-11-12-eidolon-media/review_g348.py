# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : review_g348.py
# Description : Revue provisoire du lot SD3.5 Large Turbo
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
from pathlib import Path
import json,statistics
root=Path(__file__).parent;d=json.loads((root/'g348-data.json').read_text());klein=json.loads((root/'g340-data.json').read_text())
notes=[
('Rejetée','Quatre doigts apparents seulement, deux extrémités coupées par le cadre. Texture floue ; contrôle 512² hors score.','Ce petit format échoue alors que les deux mains natives réussissent le comptage.'),
('Proposée','Cinq doigts séparés, paume et poignet visibles. Doigts fins et peau lissée, sans anomalie de comptage.','La première seed réussit là où Medium SLG G347-01 et Klein G340-01 ont six doigts.'),
('Proposée','Cinq doigts distincts et cadrage complet. Paume cohérente, détail de peau assez lissé.','Comptage également réussi par Medium SLG G347-02 et Klein G340-02.'),
('Proposée','Une tasse rouge orangé à gauche, un bol bleu à droite, entièrement visibles sur fond gris. Anse ouverte et céramique cohérente.','Même conformité globale que les deux références ; rouge plus orangé et rendu plus doux.'),
('Proposée','Tasse rouge à gauche, bol bleu à droite, complets. Anse lisible et proportions crédibles.','Scène également proposée avec Medium SLG et Klein.'),
('Rejetée','Deux poignées et deux lames croisées ; un élément partiellement gainé. Ne représente pas un katana unique avec son fourreau séparé.','Structure différente des références, mais duplication persistante et composition non conforme.'),
('Rejetée','Lame détachée, poignée sans liaison cohérente et élément supplémentaire ; assemblage impossible.','Échec structurel également présent avec Medium SLG et Klein.'),
('Proposée','Deux adultes en pied, homme en armure noire à gauche et femme en kimono rouge à droite. Mains visibles, détails fins assez doux.','Cadrage et visibilité meilleurs que G347-07 ; Klein G340-07 était aussi proposé. Anatomie fine à apprécier par l’utilisateur.'),
('Rejetée','Duo principal en pied, mais passants supplémentaires au fond et mains féminines cachées.','Le cadrage progresse par rapport à G347-08, mais le comptage échoue ; Klein G340-08 était proposé.'),
('Proposée','Répétition exacte de 01 : mêmes pixels, même PNG et cinq doigts.','Contrôle de reproductibilité hors score natif et hors médiane.'),
('Rejetée','Format 16:9 : pieds des deux personnages coupés par le bord inférieur.','G347-10 gardait les pieds mais masquait les mains ; aucune des deux recettes ne satisfait toutes les contraintes.'),
('Rejetée','Format 4:3 : jambes et pieds coupés. Femme de dos, ses deux mains ne sont pas clairement visibles.','Régression de cadrage face à G347-11, qui était seulement à revoir ; hors score natif.')]
reviews={str(i):{'verdict':v,'comment':c,'comparison':k,'rendering':'Revue GPT provisoire ; aucune validation utilisateur attribuée.'} for i,(v,c,k) in enumerate(notes)}
assert len(d['results'])==12 and all(x['block_calls']=={'0':76,'1':76} and x['steps']==4 and x['guidance']==0 for x in d['results'])
assert set(d['manifest']['parameter_bytes_by_device'])=={'cuda:0','cuda:1'}
assert d['completion']['repeat_same_pixels'] and d['results'][1]['png_sha256']==d['results'][9]['png_sha256']
assert d['health_final']['runtime_unchanged'] and all(x['match'] for x in d['health_final']['png_checks'])
native=[x for x in d['results'] if x['condition']=='quality'];median=statistics.median(x['seconds'] for x in native);km=statistics.median(x['seconds'] for x in klein['results'] if x['condition']=='quality')
d['reviews']=reviews
for row in d['results']:row['visual']=reviews[str(row['index'])]['verdict']
d['native_summary']={'proposed':5,'review':0,'rejected':3,'total':8,'median_seconds':median,'klein_seconds':km,'relative_time_vs_klein_percent':(median/km-1)*100}
d['completion']['visual_acceptance']='REVIEWED_NOT_PROMOTED';d['promotion_allowed']=False
d['conclusion']='<b>Large Turbo : 5/8 images proposées à 3,13 s médianes.</b> Les deux mains natives réussissent le comptage. Les katanas et le second duo restent rejetés. Candidat rapide à comparer visuellement à Klein, qui obtient aussi 5/8 avec une seule V100.'
d['summary_paragraphs']=[
'<b>Résultats :</b> mains 01/02, objets 03/04 et duo 07 proposés. Katanas 05/06 et duo 08 rejetés. Contrôle 512² et deux formats écran rejetés ; répétition 09 identique et proposée hors score.',
f'<b>Temps :</b> {median:.2f} s contre {km:.2f} s pour Klein, environ 7,8 % de moins sur ce lot. Turbo utilise deux V100 ; ce petit écart ne suffit pas à conclure sur l’efficacité énergétique.',
'<b>Matériel :</b> pics VRAM GPU0/GPU1 : 13 692 / 8 550 Mio. Maxima GPU : 40/37 °C ; HBM : 41/36 °C. Générateur réellement réparti, 19 blocs sur chaque carte.',
'<b>Décision :</b> conserver comme candidat rapide, sans remplacement automatique de Klein. Rendu doux et lissé ; Z-Image reste réservé aux demandes détaillées suivant ta préférence. Avis provisoires sur une petite grille.'
]
d['method_paragraphs']=[
'<b>Recette :</b> SD3.5 Large Turbo, quatre étapes, guidage 0, sans SLG, FlowMatchEuler shift 3. Même grille de quatre scènes, deux seeds 20261113/20261114, répétition, contrôle 512² et deux formats écran. Aucun prompt ou seed sélectionné après observation.',
'<b>Adaptation V100 :</b> générateur FP16, blocs 0-18 GPU0 et 19-37 GPU1 ; entrées et sortie GPU0. Placement effectif : 8,17 et 7,94 Go de paramètres. Chaque image exécute 76 appels de blocs par carte (19 x 4), vérifiés par compteur non modifiant. VAE GPU0 FP32 tuilé.',
'<b>Encodage :</b> CLIP-L, CLIP-G, T5-XXL CPU FP32, cache G346 réutilisé après comparaison SHA des poids, configurations et tokenizers. Les 42,89 s indiquent le coût initial des cinq textes ; aucun nouvel encodage G348.',
'<b>Chronométrage :</b> génération/décodage, contrôles numériques et sauvegarde du latent inclus. Chargement (9,09 s), encodage et écriture PNG finale exclus. Médiane sur les huit natives ; aucune mesure depuis clic ni énergie totale.',
'<b>Intégrité :</b> 12 PNG vérifiés, répétition identique en pixels et PNG. Aucun incident de génération ni erreur de télémétrie ; runtime inchangé. Limites 300 W par V100 ; pics ponctuels 314,44 / 304,18 W. GPU libres, services actifs, VM Memory-engine en marche.',
'<b>Provenance :</b> auteur Stability AI, révision ec07796 ; copie publique adamo1139, révision 9ad870a. Sept fichiers de poids aux SHA identiques auteur ; licence Stability AI Community archivée. Pas de code du miroir exécuté, génération locale sans réseau sortant.',
'<b>Limites :</b> recette auteur en BF16 adaptée en FP16, sans prétendre à une équivalence de qualité BF16. PyTorch 2.6.0+cu124 / Diffusers 0.37.0 / Transformers 4.56.1 inchangés. Comparaison de recettes et matériels différents, quatre scènes seulement. Large non Turbo reste non testé. Machine laissée allumée.'
]
d['run_paths']=['/srv/eidolon/workspaces/media-20261112/sd35-large-turbo-g348/run01','/srv/eidolon/workspaces/media-20261112/sd35-large-turbo-g348/run02'];d['historical_references']=['G347','G340 corrected','G344']
(root/'g348-data.json').write_text(json.dumps(d,ensure_ascii=False,indent=2));(root/'g348-reviews.json').write_text(json.dumps(reviews,ensure_ascii=False,indent=2))
print(json.dumps(d['native_summary']))
