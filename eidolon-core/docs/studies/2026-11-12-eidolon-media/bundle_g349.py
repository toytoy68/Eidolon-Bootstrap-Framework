# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : bundle_g349.py
# Description : Synthèse et archivage du lot SD3.5 Large
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
from pathlib import Path
import json,zlib,base64,hashlib,re,statistics
p=Path('g349-data.json');d=json.loads(p.read_text());lib=json.loads(Path('g349-library.json').read_text());d['library_file_id']=lib['library_file_id'];p.write_text(json.dumps(d,ensure_ascii=False,indent=2))
n=d['native_summary'];native=[r for r in d['results'] if r['condition']=='quality'];m=d['manifest'];g=d['telemetry']['gpus'];clean=lambda t:re.sub(r'</?b>','',t)
report='# SD3.5 Large - G349, 14 novembre 2026\n\nEidolon Core Technologies (ECT). Powered by Stability AI.\n\n## Résultat et décision\n\n'+clean(d['conclusion'])+'\n\n'+'\n\n'.join(map(clean,d['summary_paragraphs']))+'\n\n'
report+=f"Douze images examinées. Natives1024² : **{n['proposed']} proposées, {n['review']} à revoir, {n['rejected']} rejetées**. Médiane{n['median_seconds']:.9f}s, plage{min(r['seconds'] for r in native):.9f}-{max(r['seconds'] for r in native):.9f}s. Chargement{m['load_seconds']:.9f}s. Avis GPT provisoires ; aucune validation utilisateur attribuée, aucune promotion.\n\n"
report+='''## Recette, provenance et adaptation

Recette de la fiche auteur : **28 étapes, guidance3,5, sans SLG**, FlowMatchEuler shift3. Même grille, prompts et seeds20261113/20261114 que G348 : huit natives1024², contrôle512², répétition,1024x576 et768x576. Aucun prompt retouché ni seed sélectionnée après observation. Les poids et la recette diffèrent de Turbo : ce lot n’isole pas le seul effet du nombre d’étapes.

Générateur FP16 réparti : blocs0-18 GPU0,19-37 GPU1, entrées et sortie GPU0. Placement réel8 173 096 064 /7 940 158 976octets de paramètres. Compteurs532appels de blocs par GPU et par image (19x28), contrôlés sans modifier les tenseurs. CFG groupé natif de Diffusers. VAE GPU0 FP32 tuilé. La fiche auteur utilise BF16 ; ce lot ne démontre pas une équivalence de qualité FP16/BF16. Pas de mémoire déclarée unifiée ni mesure de débit NVLink revendiquée.

CLIP-L,CLIP-G,T5-XXL CPU FP32,256tokensT5 ; cache G346 réutilisé après vérification SHA des poids, configurations, tokenizers et embeddings. Les42,891310s indiquent le coût historique des cinq textes, sans nouvel encodage G349. PyTorch2.6.0+cu124, Diffusers0.37.0, Transformers4.56.1 inchangés. SDPA EFFICIENT_ATTENTION transformer, MATH VAE. Chronomètre génération/décodage incluant contrôles numériques et sauvegarde du latent, excluant chargement, encodage et sauvegarde PNG finale. Aucune latence depuis clic ni énergie totale.

Auteur `stabilityai/stable-diffusion-3.5-large`, révision `ceddf0a7fdf2064ea28e2213e3b84e4afa170a0f`. Copie publique `adamo1139/stable-diffusion-3.5-large-ungated`, révision `5d868ffde1c2396697cc1ab7555dc5f64e056a63`. Sept fichiers de poids SHA identiques aux métadonnées auteur. Deux nouveaux shards de générateur totalisant16 292 705 296octets téléchargés ; encodeurs et VAE réutilisés par liens physiques après vérification. Configurations/tokenizers/index/licence vérifiés aux blobs/SHA auteur.

Licence Stability AI Community5juillet2024 identique à celle lue pour G348, conservée. Fiche auteur publique consultée sur le Web ; fiche du miroir conservée sous son propre nom, identité de blob consignée. Dépôt auteur gated auto, aucune inscription ou transmission au formulaire. Aucun code du miroir exécuté.

## Exécution et clôture

Préparation puis contrôle512² avant grille native. Génération locale sans réseau sortant, UUID exacts des deux V100, verrou de campagne, limites72GoRAM/800%CPU/90minutes et garde65°C GPU/70°C HBM. Aucun entraînement, déploiement ou changement sur l’autre plateforme.

'''
report+=f"Pics VRAM GPU0/GPU1 : {g['0']['memory.used']['max']:.0f}/{g['1']['memory.used']['max']:.0f}Mio. Maxima GPU : {g['0']['temperature.gpu']['max']:.0f}/{g['1']['temperature.gpu']['max']:.0f}°C ; HBM : {g['0']['temperature.memory']['max']:.0f}/{g['1']['temperature.memory']['max']:.0f}°C. Consignes300W par V100, pics ponctuels{g['0']['power.draw']['max']:.2f}/{g['1']['power.draw']['max']:.2f}W. CPU Tdie{d['telemetry']['cpu_tdie_c']['max']:.3f}°C. Erreurs télémétrie :{d['telemetry']['sample_errors']}.\n\n"
report+=d['execution_summary']+'\n\n## Images\n\n| Image | Cas / condition | Temps (s) | Avis GPT | Commentaire |\n| --- | --- | ---: | --- | --- |\n'
for x in d['results']:
 r=d['reviews'][str(x['index'])];report+=f"| G349-{x['index']:02d} | {x['case']} / {x['condition']} | {x['seconds']:.3f} | {r['verdict']} | {r['comment']} |\n"
report+=f"\n## Livrable, preuves et limites\n\nRapport illustré `Eidolon-comparatif-SD35Large-G349.pdf`,14pages, identité `{d['library_file_id']}`,version0. Preuves `evidence-g349/`, synthèse `sd35-large-validation-g349.json`, sources de préparation/génération/rapport conservées.\n\n"
report+='''PNG/latents/caches sous `/srv/eidolon/workspaces/media-20261112/sd35-large-g349/`,run01(smoke),run02(qualité). Poids sous `/srv/eidolon/data/media-models-20261113/sd35-large`. Preuves brutes conservées en PENDING_REVIEW/NOT_REVIEWED ; revue postérieure dans la synthèse et `visual-reviews.json`.

Quatre scènes, deux seeds et revue subjective ; proposée ne vaut pas approuvée par toytoy. Comparaison de recettes différentes et non étude statistique robuste. [Turbo G348](SD35-LARGE-TURBO-G348.md), [Klein G340](KLEIN-G340.md). Aucune validation générale de toutes les tâches SD3.5 ni intégration en production.

[Fiche auteur](https://huggingface.co/stabilityai/stable-diffusion-3.5-large/blob/ceddf0a7fdf2064ea28e2213e3b84e4afa170a0f/README.md) ; [copie publique vérifiée](https://huggingface.co/adamo1139/stable-diffusion-3.5-large-ungated/tree/5d868ffde1c2396697cc1ab7555dc5f64e056a63).
'''
Path('SD35-LARGE-G349.md').write_text(report)
summary=f"[Rapport G349](SD35-LARGE-G349.md) : SD3.5 Large FP16 sur deux V100,28étapes/CFG3,5 ;12images, répétition exacte. Natives :{n['proposed']}/8 proposées,{n['review']}réserves,{n['rejected']}rejets ;{n['median_seconds']:.3f}s médianes. "+d['short_decision']+f" Pics{g['0']['memory.used']['max']:.0f}/{g['1']['memory.used']['max']:.0f}Mio, GPU{g['0']['temperature.gpu']['max']:.0f}/{g['1']['temperature.gpu']['max']:.0f}°C.532appels de blocs/carte/image vérifiés. Runtime inchangé, GPU libres, services actifs, machine allumée. Aucune promotion."
row=f"| I25 — Stable Diffusion 3.5 Large / Large Turbo 8B | Une carte non testée ; générateur seul16,3Go de fichiers | **Large/Turbo FP16 répartis testés**,19blocs par V100 ; encodeurs CPU, VAE GPU0 | Stability Community archivée ; sept fichiers de poids SHA identiques auteur par variante | **G348 Turbo** :5/8 proposées,3rejets/3,130s,4étapes/guidage0. **G349 Large** :{n['proposed']}/8 proposées,{n['review']}réserves,{n['rejected']}rejets/{n['median_seconds']:.3f}s,28étapes/CFG3,5.12images/lot. [Turbo](SD35-LARGE-TURBO-G348.md), [Large](SD35-LARGE-G349.md). Aucune promotion |"
b=json.dumps({'data':d,'report':report,'summary':summary,'candidate_row':row,'finalizer':Path('finalize_g349.py').read_text(),'report_sources':{f:Path(f).read_text() for f in ['make_g349.py','review_g349.py','bundle_g349.py','g349-review-notes.json']}},ensure_ascii=False).encode();Path('g349-finalbundle.b64').write_bytes(base64.b64encode(zlib.compress(b)));print(len(b),hashlib.sha256(b).hexdigest())
