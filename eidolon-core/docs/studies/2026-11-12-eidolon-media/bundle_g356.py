# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : bundle_g356.py
# Description : Archivage de la campagne XI Lightning G356
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
from pathlib import Path
import json,zlib,base64,hashlib,re
r=Path(__file__).parent;d=json.loads((r/'g356-data.json').read_text());lib=json.loads((r/'g356-library.json').read_text());d['library_file_id']=lib['library_file_id'];q=d['summary']['xi_lightning'];clean=lambda s:re.sub(r'</?b>','',s)
report='# Juggernaut XI Lightning — G356, 14 novembre 2026\n\nEidolon Core Technologies (ECT).\n\n## Résultat\n\n'+clean(d['conclusion'])+'\n\n'+'\n\n'.join(map(clean,d['summary_paragraphs']))+'\n\n## Méthode\n\n'+'\n\n'.join(map(clean,d['method_paragraphs']))+'\n\n'
report+='''## Variante exacte et provenance

RunDiffusion/Juggernaut-XI-Lightning, révision dbb242e5b54f33ce3bde22464f8813c1427bf1d4. Fichier Juggernaut-XI-byRunDiffusion-Lightning-Civitai-Version.safetensors, 7 105 348 616 octets, SHA256 609fde646e7fc60a259ad67351e02258ac7929a0a1f5040049dfec6a15f37b1a. Checkpoint complet, UNet/encodeurs FP16 et VAE stocké FP32. Métadonnées, taille et SHA vérifiés, carte auteur vérifiée par blob Git. Aucun poids redistribué dans le dépôt.

L’autre fichier auteur Juggernaut-XI-byRunDiffusion-Lightning.safetensors pèse 6 938 040 706 octets, SHA7782222e931a52aaded32647553ee4162c455046fa6a64ab6176cc1d2bae9da1. Inspection limitée à son en-tête public : VAE stocké FP16. Il n’a pas été téléchargé intégralement ni exécuté ; aucune équivalence numérique des deux fichiers n’est affirmée. La variante Civitai-Version choisie provient directement du dépôt officiel RunDiffusion.

Attribution : RunDiffusion / KandooAI, Juggernaut XI Lightning. CC BY-NC-ND4.0 et conditions auteur additionnelles, licences des bases SDXL et ByteDance Lightning archivées. Usage privé non commercial. Aucune création de compte, aucun formulaire, token ou renseignement personnel transmis ; métadonnées officielles gated=false et URL publique auteur. Aucune API de génération extérieure.

[Carte auteur figée](https://huggingface.co/RunDiffusion/Juggernaut-XI-Lightning/tree/dbb242e5b54f33ce3bde22464f8813c1427bf1d4) ; [licence](https://creativecommons.org/licenses/by-nc-nd/4.0/).

## Comparabilité et limites techniques

Même grille et seeds que G354/G355. Deux références historiques, non régénérées : XI standard G355 (DPM++2M Karras30/CFG5) et XL Lightning G354 (DPM++SDE Karras6/CFG1,8). XI Lightning G356 emploie cette dernière recette avec la même graine du bruit brownien ; onze évaluations UNet pour six étapes nominales. Ces références ne constituent pas un ordre de passage randomisé. Le rapport illustré juxtapose XI standard et XI Lightning ; le tableau inclut aussi XL Lightning.

Chaque checkpoint fournit tous ses poids de pipeline. VAE activé en tuiles et upcast FP32, encodeurs/UNet GPU0 FP16. SDPA MATH, quatre threads, fraction VRAM0,88 ; aucun remplacement de paquet ou pilote. Encodage, débruitage, contrôles et décodage inclus dans le temps ; chargement et sauvegarde PNG exclus. Valeurs latentes et décodage finis contrôlés, appels UNet comptés, répétition vérifiée par pixels et SHA PNG. Les avertissements restent dans les journaux ; inspection CPU dédiée des indices CLIP et des dtypes conservée. Le buffer CLIP position_ids est fractionnaire et ignoré par Transformers, dont le buffer non persistant est la séquence entière0–76 ; équivalence avec un autre lecteur de checkpoint non démontrée. Aucun patch des poids ou du scheduler.

Unités transitoires limitées à72Go/800%CPU/90min, GPU0 V100 précisément identifié,300W ; garde65°C GPU/70°C HBM, verrou de campagne, réseau sortant interdit pendant l’inférence. GPU1 et GTX1060 au repos. Aucun entraînement, intégration ou promotion, aucune modification des VM ou services.

## Mesures

| Recette | N natives | Médiane (s) | Pic VRAM (Mio) | GPU/HBM max (°C) | Pic puissance (W) | Proposées / réserves / rejets |
| --- | ---: | ---: | ---: | --- | ---: | --- |
'''
for name in ['v11','xi_lightning','xl_lightning']:
 x=d['summary'][name];report+=f"| {name} | 8 | {x['median_seconds']:.6f} | {x['peak_mib']:.0f} | {x['gpu_c']:.0f}/{x['hbm_c']:.0f} | {x['power_w']:.2f} | {x['proposed']}/{x['review']}/{x['rejected']} |\n"
report+='\n'+d['execution_summary']+' Les maxima échantillonnés ne permettent pas de classer l’efficacité énergétique.\n\n## Revue des nouvelles images\n\n| Image | Condition | Temps (s) | Avis GPT | Motif |\n| --- | --- | ---: | --- | --- |\n'
for x in sorted(d['new_results'],key=lambda x:x['index']):
 n=d['reviews']['xi_lightning'][str(x['index'])];report+=f"| G356-{x['index']:02d} | {x['case']} / {x['condition']} | {x['seconds']:.3f} | {n['verdict']} | {n['comment']} |\n"
report+=f"\n## Conservation\n\nPDF illustré de14pages : `{d['library_file_id']}`. PNG originaux `/srv/eidolon/workspaces/media-20261112/juggernaut-xi-lightning-g356/`, poids `/srv/eidolon/data/media-models-20261113/juggernaut-xi-lightning-g356/`. Synthèse `juggernaut-xi-lightning-validation-g356.json`, preuves `evidence-g356/`. Les données brutes restent NOT_REVIEWED, la revue ultérieure GPT figure dans la synthèse ; aucun avis utilisateur attribué. Aucune sélection automatique ni promotion.\n\n"
report+='[XI standard G355](JUGGERNAUT-XI-G355.md) ; [XL Lightning G354](JUGGERNAUT-LIGHTNING-G354.md).\n'
summary=f"[Rapport G356](JUGGERNAUT-XI-LIGHTNING-G356.md) : XI Lightning Civitai-Version, une V100 FP16/VAE upcast FP32, SDE Karras6/CFG1,8,11 appels UNet ;12 nouvelles images, répétition exacte. {q['proposed']}/8 proposées,{q['review']} réserves,{q['rejected']} rejets ;{q['median_seconds']:.3f}s. Références historiques XI standard2/8+1réserve/17,562s et XL Lightning1/8/6,843s. "+d['short_decision']+' Licences/attribution conservées, runtime inchangé, GPU libres, services actifs, machine allumée.'
row=f"| I06 — Juggernaut XL variantes récentes | V10 G353, XL Lightning G354, XI standard G355, **XI Lightning G356** : {q['peak_mib']:.0f} Mio, une V100 | Pas nécessaire aux recettes testées | V10/XL Lightning OpenRAIL ; XI CC BY-NC-ND4.0+conditions auteur et licences de base conservées ; SHA vérifiés | V10:1/8/17,565s ; XL Lightning:1/8/6,843s ; XI standard:2/8+1réserve/17,562s ; XI Lightning:{q['proposed']}/8+{q['review']}réserves/{q['median_seconds']:.3f}s. Fichier Civitai-Version testé ; fichier alternatif VAE FP16 non testé. [G355](JUGGERNAUT-XI-G355.md), [G356](JUGGERNAUT-XI-LIGHTNING-G356.md), aucune promotion |"
(r/'g356-data.json').write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n');(r/'JUGGERNAUT-XI-LIGHTNING-G356.md').write_text(report)
sources=['make_g356.py','review_g356.py','bundle_g356.py','g356-review-notes.json'];b=json.dumps({'data':d,'report':report,'summary':summary,'candidate_row':row,'finalizer':(r/'finalize_g356.py').read_text(),'report_sources':{n:(r/n).read_text() for n in sources}},ensure_ascii=False).encode();(r/'g356-finalbundle.b64').write_bytes(base64.b64encode(zlib.compress(b)));print(json.dumps({'sha256':hashlib.sha256(b).hexdigest(),'chars':len((r/'g356-finalbundle.b64').read_bytes())}))
