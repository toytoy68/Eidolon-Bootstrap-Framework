# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : bundle_g353.py
# Description : Assemblage du rapport Juggernaut G353
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
from pathlib import Path
import json,zlib,base64,hashlib,re
d=json.loads(Path('g353-data.json').read_text());lib=json.loads(Path('g353-library.json').read_text());d['library_file_id']=lib['library_file_id'];Path('g353-data.json').write_text(json.dumps(d,ensure_ascii=False,indent=2))
a=d['summary']['v10'];b=d['summary']['v9'];clean=lambda t:re.sub(r'</?b>','',t)
report='# Juggernaut X v10 face à v9 — G353, 14 novembre 2026\n\nEidolon Core Technologies (ECT).\n\n## Résultat et décision\n\n'+clean(d['conclusion'])+'\n\n'+'\n\n'.join(map(clean,d['summary_paragraphs']))+'\n\n'
report+='## Méthode\n\n'+'\n\n'.join(map(clean,d['method_paragraphs']))+'\n\n'
report+='''Chaque variante a douze sorties : contrôle main 512², quatre scènes × deux seeds à 1024², répétition de la première main, duo 1024×576 et 768×576. Seeds 20261113/20261114, prompts identiques au lot FLUX pour faciliter la revue de contenu. Comparatif v9/v10 strictement apparié : même DPM++2M Karras, 30 étapes, CFG5, négatif vide, dimensions originales/cibles égales à la sortie, crop0. Aucun upscaling ni refiner ou LoRA. Le carré 1024² sert de géométrie commune, tandis que la carte auteur v10 recommande 832×1216/1216×832 : ces deux géométries restent non testées.

V9 est régénéré pour étendre le témoin G333 au duo et aux formats écran. Les sept comparaisons de pixels avec G333 (six natives communes et répétition) sont toutes identiques. G333 utilisait six natives ; G353 en utilise huit. Ne pas comparer directement les fractions 2/6 et n/8 comme une évolution du modèle. Pas de conclusions de généralisation sur deux seeds.

## Poids et licences

- V10 standard RunDiffusion/Juggernaut-X-v10, révision 35e4f3ccbe745c3e1221715d04a452aaa1ee5761. Fichier Juggernaut-X-RunDiffusion-NSFW.safetensors, 7 105 348 672 octets, SHA256 d91d35736d8f2be038f760a9b0009a771ecf0a417e9b38c244a84ea4cb9c0c45. Le nom du checkpoint ne décrit pas le contenu du benchmark, constitué de quatre scènes publiques non explicites.
- V9 RunDiffusion/Juggernaut-XL-v9, révision cf419233522daa0b9ea36c3aff98fa2cab1fb0fb. Fichier déjà local, 7 105 348 188 octets, SHA256 c9e3e68f89b8e38689e1097d4be4573cf308de4e3fd044c64ca697bdb4aa8bca. Empreinte revérifiée, aucun nouveau téléchargement v9.
- CreativeML OpenRAIL-M déclaré par les cartes auteur, restriction de déploiement derrière une API payante conservée. Carte v10 figée et vérifiée par blob Git, carte v9 G333 et textes OpenRAIL-M/SDXL OpenRAIL++-M archivés. Ce lot est une évaluation privée locale ; aucune affirmation de liberté commerciale universelle.

Chaque checkpoint fournit son UNet, ses encodeurs et son VAE : la comparaison porte sur l’ensemble du checkpoint et pas uniquement les poids du débruiteur. Pas de partage silencieux d’encodeur/VAE entre variantes.

## Exécution et instrumentation

Même runtime preference-lab que G333 : PyTorch2.6.0+cu124, Diffusers0.32.2, Transformers4.49.0 ; aucun paquet installé. Configs SDXL locales et sources du runtime empreintées avant/après. UNet et encodeurs FP16 sur GPU0 ; force_upcast du VAE pour le décodage, tuilage activé. Paramètres de pipeline et scheduler archivés par modèle. Attention PyTorch MATH, Flash/Memory Efficient désactivées, cudnn benchmark désactivé. 4 threads PyTorch, fraction mémoire 0,88 sur une V100 Volta précisément identifiée par UUID.

Instrumentation non modificatrice : 30 appels UNet par image, latents contrôlés après chaque étape et valeurs décodées finies. Les temps incluent encodage texte, débruitage, décodage, contrôles et synchronisation ; ils excluent chargement et sauvegarde du PNG. Les rapports FLUX précédents excluent l’encodage : leurs médianes ne sont pas un chronomètre équivalent. Pics GPU/VRAM/HBM/puissance échantillonnés, pas de Wh secteur attribués aux GPU. Ordre fixe v10 puis v9 : les températures ne classent pas l’efficacité thermique des modèles.

Premier contrôle interrompu avant toute image : l’export JSON strict refusait lambda_min_clipped=-inf du scheduler. Seul l’exporteur transforme maintenant les valeurs non finies en chaînes ; aucune modification du calcul du scheduler. Source initiale et run00-config-json-failed conservés. Contrôle 512² puis campagne complète achevés après correction.

Unités transitoires utilisateur toytoy, réseau sortant interdit, verrou de campagne, 72Go RAM/800%CPU/90min au maximum. GPU0 V100 à 300 W, garde65°C GPU/70°C HBM ; GPU1 et GTX1060 au repos. Aucun arrêt d’Eva ni changement de pilote/service/production. Aucun entraînement, LoRA, déploiement ou promotion.

'''
report+='## Mesures\n\n| Modèle | N natives | Médiane / min / max (s) | Pic VRAM (Mio) | GPU / HBM (°C) | Puissance pic (W) | Proposées / réserves / rejets |\n| --- | ---: | --- | ---: | --- | ---: | --- |\n'
for name in ['v9','v10']:
 q=d['summary'][name];report+=f"| {name} | 8 | {q['median_seconds']:.6f} / {q['min_seconds']:.6f} / {q['max_seconds']:.6f} | {q['peak_mib']:.0f} | {q['gpu_c']:.0f} / {q['hbm_c']:.0f} | {q['power_w']:.2f} | {q['proposed']} / {q['review']} / {q['rejected']} |\n"
report+='\nChargements grille : '+', '.join(f"{x['model']} {x['load_seconds']:.6f}s" for x in d['loads'])+'.\n\n'+d['execution_summary']+'\n\n## Revue de chaque image\n\n| Image | Condition | Temps (s) | Avis GPT | Commentaire |\n| --- | --- | ---: | --- | --- |\n'
for name in ['v10','v9']:
 for x in sorted([x for x in d['results'] if x['model']==name],key=lambda x:x['index']):
  note=d['reviews'][name][str(x['index'])];report+=f"| G353-{name}-{x['index']:02d} | {x['case']} / {x['condition']} | {x['seconds']:.3f} | {note['verdict']} | {note['comment']} |\n"
report+=f"\n## Conservation\n\nRapport illustré Eidolon-comparatif-JuggernautX-G353.pdf, 14 pages, identité `{d['library_file_id']}`. Synthèse juggernaut-x-validation-g353.json, preuves evidence-g353/. PNG originaux sous /srv/eidolon/workspaces/media-20261112/juggernaut-x-g353/, poids v10 sous /srv/eidolon/data/media-models-20261113/juggernaut-x-g353/.\n\n"
report+='''Avis GPT non aveugles sur aperçus réduits, à distinguer de l’avis de toytoy. Aucune validation anatomique professionnelle. Les résultats bruts gardent NOT_REVIEWED/PENDING_REVIEW ; la synthèse ajoute la revue ultérieure. Erreurs, configurations et sources conservées, aucun échec effacé.

[Auteur v10](https://huggingface.co/RunDiffusion/Juggernaut-X-v10/tree/35e4f3ccbe745c3e1221715d04a452aaa1ee5761) ; [témoin G333](CHECKPOINTS-G333.md) ; [file de candidats](CANDIDATE-QUEUE-G332.md).
'''
Path('JUGGERNAUT-X-G353.md').write_text(report)
summary=f"[Rapport G353](JUGGERNAUT-X-G353.md) : Juggernaut v10/v9, même DPM++2M Karras30/CFG5 sur une V100 ; 24 images et deux répétitions exactes. V10 {a['proposed']}/8 proposées, {a['review']} réserves, {a['rejected']} rejets / {a['median_seconds']:.3f}s ; v9 {b['proposed']}/8 proposées, {b['review']} réserves, {b['rejected']} rejets / {b['median_seconds']:.3f}s. "+d['short_decision']+' Export JSON du scheduler corrigé avant génération, trace conservée. Runtime inchangé, GPU libres, services actifs, machine allumée.'
row=f"| I06 — Juggernaut XL variantes plus récentes | **V10 testé G353** FP16 une V100, pic {a['peak_mib']:.0f} Mio | Pas nécessaire à cette recette | V10 OpenRAIL-M déclaré + restriction API payante, auteur figé/SHA vérifié ; autres versions à auditer séparément | V10 {a['proposed']}/8 proposées, {a['review']} réserves, {a['rejected']} rejets, {a['median_seconds']:.3f}s ; témoin v9 régénéré {b['proposed']}/8, {b['median_seconds']:.3f}s. 24 images. XI/Lightning restent non testés. [Rapport](JUGGERNAUT-X-G353.md), aucune promotion |"
sources=['make_g353.py','review_g353.py','bundle_g353.py','g353-review-notes.json']
payload=json.dumps({'data':d,'report':report,'summary':summary,'candidate_row':row,'finalizer':Path('finalize_g353.py').read_text(),'report_sources':{n:Path(n).read_text() for n in sources}},ensure_ascii=False).encode();Path('g353-finalbundle.b64').write_bytes(base64.b64encode(zlib.compress(payload)))
print(json.dumps({'bytes':len(payload),'sha256':hashlib.sha256(payload).hexdigest(),'chars':len(Path('g353-finalbundle.b64').read_bytes())}))
