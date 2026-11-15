# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : bundle_g350.py
# Description : Synthèse et archivage du lot Sana Sprint 0,6B
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
from pathlib import Path
import json,zlib,base64,hashlib,re
p=Path('g350-data.json');d=json.loads(p.read_text());lib=json.loads(Path('g350-library.json').read_text())
d['library_file_id']=lib['library_file_id'];p.write_text(json.dumps(d,ensure_ascii=False,indent=2))
n=d['native_summary'];native=[r for r in d['results'] if r['condition']=='quality'];m=d['manifest'];g=d['telemetry']['gpus']['0'];clean=lambda t:re.sub(r'</?b>','',t)
report='# Sana Sprint 0,6B — G350, 14 novembre 2026\n\nEidolon Core Technologies (ECT).\n\n## Résultat et décision\n\n'+clean(d['conclusion'])+'\n\n'+'\n\n'.join(map(clean,d['summary_paragraphs']))+'\n\n'
report+=f"Douze images examinées. Sur les huit natives 1024² : **{n['proposed']} proposées, {n['review']} à revoir et {n['rejected']} rejetées**. Médiane **{n['median_seconds']:.9f} s**, plage {min(r['seconds'] for r in native):.9f}–{max(r['seconds'] for r in native):.9f} s. Chargement : {m['load_seconds']:.9f} s. Avis GPT provisoires ; aucune validation utilisateur attribuée, aucune promotion.\n\n"
report+='## Recette et méthode\n\n'+'\n\n'.join(map(clean,d['method_paragraphs']))+'\n\n'
report+='''Même grille que G345 et G340 : main ouverte, tasse/bol, katana/fourreau, duo en pied ; seeds 20261113 et 20261114. Huit natives 1024², contrôle 512², répétition, 1024×576 et 768×576. Aucun prompt ajusté ni seed sélectionnée après observation. Identité des prompts, seeds, dimensions et réglages vérifiée avec G345.

Générateur FP32 : 2 374 004 864 octets de paramètres sur GPU0. Attention linéaire Sana native, backend PyTorch MATH pour les autres attentions. Guidage intégré au générateur, pas de CFG doublant le batch. Résolution exacte, sans resolution binning. L’exemple auteur utilise deux étapes ; quatre étapes sont conservées pour comparer directement les deux variantes Sprint. Les poids diffèrent, ce n’est pas un test du seul effet du nombre de paramètres. Le format écran 4:3 dégrade particulièrement les proportions et les visages.

## Provenance et droits

Dépôt auteur `Efficient-Large-Model/Sana_Sprint_0.6B_1024px_diffusers`, révision `aa76e7f4f4928f378716b6716a2130fba3caf5b1`. Générateur téléchargé : 1 187 078 584 octets, SHA256 `9069dd697395b96a59d1f74837461f7aeb3d95e55b67fa85c9f31c9106b65e87`.

Deux shards Gemma2 et DC-AE réutilisés depuis G345 après vérification des empreintes avec les métadonnées auteur. Configurations, tokenizers et cache des embeddings identiques : `encoder-reuse-proof.json`. Les 26,757161908 s sont le coût historique des quatre encodages CPU G345 ; aucune nouvelle dépense d’encodage mesurée ici. Les instructions textuelles standard de Sana sont consignées dans le manifeste, sans réécriture externe des prompts.

Licence du dépôt Apache 2.0 archivée et identique à G345. Les conditions Gemma et sa politique d’usage restent applicables ; leur présence empêche de qualifier l’ensemble de libre de toute restriction. Licence DC-AE conservée séparément. Aucun code distant exécuté. Fiche auteur et configurations archivées, poids identifiés par SHA.

## Exécution et clôture

Préparation, contrôle 512² puis lot qualité. Génération locale sans réseau sortant, UUID exact de la première V100, verrou de campagne ; limites 72 Go RAM, 800 % CPU, 90 minutes et garde 65 °C GPU / 70 °C HBM. Seule GPU0 calcule ; GPU1 et GTX 1060 restent disponibles. Aucun entraînement, déploiement ou modification sur l’autre plateforme.

'''
report+=f"Pic VRAM GPU0 : {g['memory.used']['max']:.0f} Mio. Maxima GPU {g['temperature.gpu']['max']:.0f} °C, HBM {g['temperature.memory']['max']:.0f} °C. Consigne 300 W, pic ponctuel mesuré {g['power.draw']['max']:.2f} W ; ce n’est pas une puissance moyenne ni une énergie. CPU Tdie {d['telemetry']['cpu_tdie_c']['max']:.3f} °C. Erreurs de télémétrie : {d['telemetry']['sample_errors']}.\n\n"
report+=d['execution_summary']+'\n\nUn premier appel de lancement a visé par erreur un chemin tools absent ; il a échoué avant toute exécution. Le chemin du lanceur a été corrigé, sans changer la recette ni relancer une génération existante. Aucun incident dans les deux lots exécutés.\n\n## Images\n\n| Image | Cas / condition | Temps (s) | Avis GPT | Commentaire |\n| --- | --- | ---: | --- | --- |\n'
for x in d['results']:
 r=d['reviews'][str(x['index'])];report+=f"| G350-{x['index']:02d} | {x['case']} / {x['condition']} | {x['seconds']:.3f} | {r['verdict']} | {r['comment']} |\n"
report+=f"\n## Livrable, preuves et limites\n\nRapport illustré `Eidolon-comparatif-SanaSprint600M-G350.pdf`, 14 pages, identité `{d['library_file_id']}`. Preuves `evidence-g350/`, synthèse `sana-sprint-600m-validation-g350.json`, sources de préparation, génération et rapport conservées.\n\n"
report+='''PNG, latents et cache sous `/srv/eidolon/workspaces/media-20261112/sana-sprint-600m-g350/`, run01 (contrôle) et run02 (qualité). Poids sous `/srv/eidolon/data/media-models-20261113/sana-sprint-600m`. Les preuves brutes gardent PENDING_REVIEW/NOT_REVIEWED ; la revue postérieure est portée par la synthèse et `visual-reviews.json`.

Quatre scènes, deux seeds et avis subjectifs sur aperçus réduits : ce résultat ne valide ni toutes les tâches Sana ni une intégration en production. Le score compte le respect de la consigne, pas seulement la beauté du rendu. Une proposition n’est pas une approbation de toytoy. La comparaison avec Klein concerne des recettes différentes ; la comparaison Sprint garde les mêmes réglages et composants texte/décodage.

[Fiche auteur](https://huggingface.co/Efficient-Large-Model/Sana_Sprint_0.6B_1024px_diffusers/blob/aa76e7f4f4928f378716b6716a2130fba3caf5b1/README.md) ; [Sana Sprint dans Diffusers](https://huggingface.co/docs/diffusers/api/pipelines/sana_sprint).
'''
Path('SANA-SPRINT-600M-G350.md').write_text(report)
summary=f"[Rapport G350](SANA-SPRINT-600M-G350.md) : Sana Sprint 0,6B FP32 sur une V100, 4 étapes / guidage intégré 4,5 ; 12 images, répétition exacte. Natives : {n['proposed']}/8 proposées, {n['review']} réserve, {n['rejected']} rejets ; {n['median_seconds']:.3f} s médianes contre {n['sprint_1600m_seconds']:.3f} s en 1,6B. "+d['short_decision']+f" Pic {g['memory.used']['max']:.0f} Mio, GPU {g['temperature.gpu']['max']:.0f} °C, HBM {g['temperature.memory']['max']:.0f} °C. Quatre appels du générateur vérifiés par image. Runtime inchangé, GPU libres, services actifs, machine allumée."
row=f"| I27 — Sana Sprint 0,6B / 1,6B | **Deux variantes testées** sur une V100 FP32 ; pics 5 336 / 9 184 Mio | Quatre étapes SCM, guidage intégré 4,5 ; Gemma2 CPU, DC-AE GPU0 | Apache 2.0 ; conditions Gemma et DC-AE conservées, pas de promesse d’absence de restrictions | **G345 1,6B** : 2/8 proposées, 1 réserve, 5 rejets / 1,833 s. **G350 0,6B** : 2/8 proposées, 6 rejets / 1,279 s. Douze images par lot. Gain temps/VRAM sans progrès de conformité ; [G350](SANA-SPRINT-600M-G350.md), aucune promotion |"
b=json.dumps({'data':d,'report':report,'summary':summary,'candidate_row':row,'finalizer':Path('finalize_g350.py').read_text(),'report_sources':{f:Path(f).read_text() for f in ['make_g350.py','review_g350.py','bundle_g350.py']}},ensure_ascii=False).encode()
Path('g350-finalbundle.b64').write_bytes(base64.b64encode(zlib.compress(b)))
print(json.dumps({'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest(),'base64_chars':len(Path('g350-finalbundle.b64').read_bytes())}))
