# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : bundle_g354.py
# Description : Archivage reproductible du lot Lightning
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
from pathlib import Path
import json,zlib,base64,hashlib,re
root=Path(__file__).parent;d=json.loads((root/'g354-data.json').read_text());lib=json.loads((root/'g354-library.json').read_text());d['library_file_id']=lib['library_file_id'];q=d['summary']['lightning'];clean=lambda s:re.sub(r'</?b>','',s)
report='# Juggernaut XL Lightning — G354, 14 novembre 2026\n\nEidolon Core Technologies (ECT).\n\n## Résultat\n\n'+clean(d['conclusion'])+'\n\n'+'\n\n'.join(map(clean,d['summary_paragraphs']))+'\n\n## Méthode\n\n'+'\n\n'.join(map(clean,d['method_paragraphs']))+'\n\n'
report+='''## Provenance exacte et choix de recette

Checkpoint RunDiffusion/Juggernaut-XL-Lightning, révision 9c35e7ca1112b7e567ae7b24400b83935909916d, fichier Juggernaut_RunDiffusionPhoto2_Lightning_4Steps.safetensors, 7 105 348 284 octets, SHA256 c8df560d2992ac04299412be6a36fa53a4e7a1b74f27b94867ad3f84f4b425a5. Métadonnées et blob Git de la carte vérifiés avant génération ; téléchargement de poids uniquement, aucune inférence externe. Aucune dépendance ajoutée.

L’auteur donne une plage 5–7 étapes, CFG 1,5–2,0 et DPM++ SDE ou SDE Karras. Son exemple Python emploie DPMSolverSinglestepScheduler sans forcer un algorithme SDE. Pour ce lot, choix explicite de DPMSolverSDEScheduler, Karras, epsilon, six étapes et CFG1,8. Onze évaluations UNet, donc aucun « six étapes = six évaluations » supposé. La graine du bruit brownien est explicitement fixée et le scheduler recréé pour chaque image, afin que la répétition soit indépendante du chemin de bruit précédent. Le fichier 4Steps n’est pas une preuve que cette campagne teste quatre étapes : cette variante de réglage reste à évaluer séparément.

UNet, deux encodeurs et VAE sont ceux du checkpoint complet. Runtime preference-lab identique à G353, SDPA MATH, quatre threads et fraction VRAM0,88, GPU0 identifié par UUID. VAE force_upcast, tuilage ; latents contrôlés à chaque callback, décodage contrôlé par hook. Le changement des paramètres et du sampler empêche d’attribuer une différence aux seuls poids. V9 est la référence historique G353 : ses résultats et revues sont repris, pas régénérés pour ce lot.

La licence déclarée OpenRAIL-M et la restriction de service API payant de RunDiffusion sont conservées, ainsi que les conditions des modèles de base SDXL et ByteDance Lightning OpenRAIL++-M. Usage d’évaluation locale privée. Aucun droit commercial universel déduit.

Unités isolées, verrou de campagne, pas de réseau sortant pendant l’inférence, aucune modification d’Eva, des VM ou des services. Mémoire72Go, CPU800%, durée maximale90min ; garde65°C GPU/70°C HBM. Ces plafonds sont distincts des mesures réellement observées.

## Mesures

| Recette | Images natives | Médiane (s) | Pic VRAM (Mio) | GPU/HBM max (°C) | Puissance pic (W) | Proposées / réserves / rejets |
| --- | ---: | ---: | ---: | --- | ---: | --- |
'''
for name in ['v9','lightning']:
 x=d['summary'][name];report+=f"| {name} {'G353 historique' if name=='v9' else 'G354'} | 8 | {x['median_seconds']:.6f} | {x['peak_mib']:.0f} | {x['gpu_c']:.0f}/{x['hbm_c']:.0f} | {x['power_w']:.2f} | {x['proposed']}/{x['review']}/{x['rejected']} |\n"
report+='\n'+d['execution_summary']+' Les maxima thermiques ne classent pas l’efficacité énergétique ; conditions initiales et durée différentes.\n\n## Revue Lightning\n\n| ID | Scène | Temps (s) | Avis GPT | Motif |\n| --- | --- | ---: | --- | --- |\n'
for x in sorted(d['new_results'],key=lambda x:x['index']):
 n=d['reviews']['lightning'][str(x['index'])];report+=f"| G354-{x['index']:02d} | {x['case']} / {x['condition']} | {x['seconds']:.3f} | {n['verdict']} | {n['comment']} |\n"
report+=f"\n## Conservation\n\nPDF illustré 14 pages, 12 images nouvelles face aux 12 références v9 G353 : `{d['library_file_id']}`. PNG originaux : `/srv/eidolon/workspaces/media-20261112/juggernaut-lightning-g354/`. Poids : `/srv/eidolon/data/media-models-20261113/juggernaut-lightning-g354/`. Données : `juggernaut-lightning-validation-g354.json`. Preuves : `evidence-g354/`. Les données brutes restent NOT_REVIEWED ; seule la synthèse ajoute la revue ultérieure, non attribuée à toytoy. Aucun entraînement ni promotion automatique.\n\n"
report+='[Carte auteur figée](https://huggingface.co/RunDiffusion/Juggernaut-XL-Lightning/tree/9c35e7ca1112b7e567ae7b24400b83935909916d) ; [Référence v9 G353](JUGGERNAUT-X-G353.md).\n'
summary=f"[Rapport G354](JUGGERNAUT-LIGHTNING-G354.md) : Juggernaut XL Lightning, une V100 FP16, DPM++ SDE Karras6/CFG1,8, 11 appels UNet ; 12 images et répétition exacte. {q['proposed']}/8 proposées, {q['review']} réserves, {q['rejected']} rejets ; médiane {q['median_seconds']:.3f}s, temps divisé par {d['speed_ratio_vs_v9']:.2f} face au v9 G353 historique (recettes différentes). "+d['short_decision']+' Aucun déploiement ; runtime inchangé, services actifs, GPU libres, machine allumée.'
row=f"| I06 — Juggernaut XL variantes plus récentes | V10 G353 : 11538 Mio ; **XL Lightning G354** : {q['peak_mib']:.0f} Mio, une V100 FP16 | Pas nécessaire aux recettes testées | Licences OpenRAIL-M / bases OpenRAIL++, restriction API payante ; SHA auteur vérifiés | V10 :1/8,1 réserve/17,565s. Lightning :{q['proposed']}/8,{q['review']} réserves/{q['median_seconds']:.3f}s, SDE Karras6/CFG1,8,12 images. V9 G353 historique3/8/17,600s. XI et XI Lightning restent non testés. [G353](JUGGERNAUT-X-G353.md), [G354](JUGGERNAUT-LIGHTNING-G354.md), aucune promotion |"
(root/'g354-data.json').write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n');(root/'JUGGERNAUT-LIGHTNING-G354.md').write_text(report)
sources=['make_g354.py','review_g354.py','bundle_g354.py','g354-review-notes.json'];b=json.dumps({'data':d,'report':report,'summary':summary,'candidate_row':row,'finalizer':Path('finalize_g354.py').read_text(),'report_sources':{n:Path(n).read_text() for n in sources}},ensure_ascii=False).encode();(root/'g354-finalbundle.b64').write_bytes(base64.b64encode(zlib.compress(b)));print(json.dumps({'sha256':hashlib.sha256(b).hexdigest(),'chars':len((root/'g354-finalbundle.b64').read_bytes())}))
