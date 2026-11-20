# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : bundle_g351.py
# Description : Archivage du comparatif FLUX Schnell Q8
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
from pathlib import Path
import json,zlib,base64,hashlib,re
p=Path('g351-data.json');d=json.loads(p.read_text());lib=json.loads(Path('g351-library.json').read_text())
d['library_file_id']=lib['library_file_id'];p.write_text(json.dumps(d,ensure_ascii=False,indent=2))
n=d['native_summary'];native=[r for r in d['results'] if r['condition']=='quality'];m=d['manifest'];g=d['telemetry']['gpus']['0'];clean=lambda t:re.sub(r'</?b>','',t)
report='# FLUX.1 Schnell GGUF Q8 — G351, 14 novembre 2026\n\nEidolon Core Technologies (ECT).\n\n## Résultat et décision\n\n'+clean(d['conclusion'])+'\n\n'+'\n\n'.join(map(clean,d['summary_paragraphs']))+'\n\n'
report+=f"Douze images examinées. Huit natives 1024² : **{n['proposed']} proposées, {n['review']} à revoir et {n['rejected']} rejetées**. Médiane **{n['median_seconds']:.9f} s**, plage {min(r['seconds'] for r in native):.9f}–{max(r['seconds'] for r in native):.9f} s. Chargement : {m['load_seconds']:.9f} s. Avis GPT provisoires ; aucune validation utilisateur attribuée et aucune promotion.\n\n"
report+='## Recette et méthode\n\n'+'\n\n'.join(map(clean,d['method_paragraphs']))+'\n\n'
report+='''Même grille et mêmes prompts que G339 : main ouverte, tasse/bol, katana/fourreau, duo en pied ; seeds 20261113 et 20261114. Huit natives 1024², contrôle 512², répétition, 1024×576 et 768×576. Aucun prompt retouché ni sélection de seed après observation.

Poids du générateur stockés en Q8_0 pour les grandes matrices et F16 pour les autres tenseurs ; déquantification dynamique, calcul FP16. Les 776 tenseurs du fichier comprennent 304 Q8_0 et 472 F16. Après conversion de noms et séparation des projections, 494 modules GGUFLinear et 1 156 paramètres sont placés sur GPU0. Stockage de paramètres : 12 687 767 680 octets, dont 12 573 868 032 quantifiés. Tous les paramètres sont effectivement résidents sur GPU0 ; aucun offload du générateur vers CPU. Quatre appels du générateur et 228 appels de blocs par image, contrôlés sans modifier les tenseurs.

Attention par morceaux de 256 requêtes identique à G339, backend MATH. VAE Flux FP32 GPU0 tuilé à 512 pixels, recouvrement standard. Scheduler FlowMatchEuler : shift 1, décalage dynamique désactivé. Quatre étapes, guidage 0, texte T5 de 256 tokens. Encodeurs CLIP-L et T5-XXL via le même moteur Comfy en CPU FP32, embeddings stockés FP16. Nouvel encodage des quatre prompts lors du premier essai G351, puis cache SHA vérifié pour les essais suivants. L’avertissement CLIP `text_projection.weight` absent était déjà présent dans le témoin G339 ; pas de modification des encodeurs.

## Provenance et environnement

Conversion publique `city96/FLUX.1-schnell-gguf`, révision `f495746ed9c5efcf4661f53ef05401dceadc17d2`. Fichier `flux1-schnell-Q8_0.gguf`, 12 687 821 728 octets, SHA256 `f6694941193b10148dbf1f0f498d4ccd3e9875c127fc53946213b68580c66f10`. Conversion directe de BFL Schnell déclarée par city96 ; cela ne signifie pas identité des poids avec le checkpoint FP16. Carte de conversion et licence Apache 2.0 du Schnell d’origine archivées. Encodeurs et VAE G339 réutilisés après vérification SHA.

Même environnement `preference-lab` que G339 : PyTorch 2.6.0+cu124, Diffusers 0.32.2, Transformers 4.49.0. Paquet gguf 0.17.1 ajouté seulement dans `flux-q8-g351/vendor`, roue vérifiée SHA, sans dépendance réinstallée et sans modification du runtime partagé. Licence MIT du paquet archivée. Déquantification PyTorch native, aucun kernel CUDA distant ou compilation supplémentaire. Un contrôle sur 16 blocs Q8 compare les résultats GPU à NumPy (tolérance 0,1 %, écart absolu maximal 0,00003004) : compatibilité limitée, pas audit intégral de la conversion.

Empreintes du moteur, de la pipeline, des fonctions GGUF et de l’attention consignées dans `runtime-provenance.json`. Les empreintes runtime avant/après sont identiques. Aucune fusion mémoire des cartes ni mesure NVLink revendiquée : seule GPU0 calcule.

## Incident conservé et exécution

Premier chargement interrompu avant toute image : le chargeur single-file Diffusers 0.32.2 conserve les paramètres sur CPU et ignore le placement passé au chargement. Le contrôle de placement a refusé cet état. Correction dans le seul runner : transfert explicite `transformer.to('cuda:0')`, puis contrôle des 1 156 paramètres et des matrices quantifiées. Essai échoué conservé dans `run00-placement-failed`, ancienne source archivée. Le contrôle 512² et la grille suivants ont terminé sans incident.

Génération locale, accès réseau sortant interdit dans les unités, verrou de campagne et UUID exact de GPU0. Limites 72 Go RAM, 800 % CPU, 90 minutes ; garde 65 °C GPU / 70 °C HBM. Fraction d’allocation PyTorch bornée à 0,94 sur GPU0. Aucun entraînement ou déploiement. GPU1 et GTX 1060 ne participent pas au calcul.

'''
report+=f"Pic VRAM GPU0 : {g['memory.used']['max']:.0f} Mio. Maxima GPU {g['temperature.gpu']['max']:.0f} °C et HBM {g['temperature.memory']['max']:.0f} °C. Consigne 300 W, pic ponctuel {g['power.draw']['max']:.2f} W ; aucune mesure d’énergie totale. CPU Tdie {d['telemetry']['cpu_tdie_c']['max']:.3f} °C sur la grille à cache chaud. Coût initial des quatre encodages : {m['encode_seconds']:.9f} s. Erreurs de télémétrie sur la grille : {d['telemetry']['sample_errors']}.\n\n"
report+=d['execution_summary']+'\n\n## Images\n\n| Image | Cas / condition | Temps (s) | Avis GPT | Commentaire |\n| --- | --- | ---: | --- | --- |\n'
for x in d['results']:
 r=d['reviews'][str(x['index'])];report+=f"| G351-{x['index']:02d} | {x['case']} / {x['condition']} | {x['seconds']:.3f} | {r['verdict']} | {r['comment']} |\n"
report+=f"\n## Livrable et limites\n\nRapport illustré `Eidolon-comparatif-FLUXSchnellQ8-G351.pdf`, 14 pages, identité `{d['library_file_id']}`. Synthèse `flux-q8-validation-g351.json`, preuves `evidence-g351/`, sources du runner et du rapport conservées.\n\n"
report+='''PNG, latents, encodages et incident conservés sous `/srv/eidolon/workspaces/media-20261112/flux-q8-g351/`. Poids sous `/srv/eidolon/data/media-models-20261113/flux-schnell-q8/`. Les résultats bruts restent NOT_REVIEWED/PENDING_REVIEW ; la synthèse porte la revue ultérieure. Les aperçus sont réduits pour la revue ; les PNG natifs restent disponibles.

Quatre scènes, deux seeds et appréciation subjective. Même recette Schnell, mais quantification et nombre de GPU changent ensemble : ne pas attribuer la totalité du delta de temps à la seule déquantification. Les chronomètres incluent génération, décodage, contrôles et sauvegarde du latent, pas chargement, encodage ou écriture PNG finale. Pas de latence depuis clic, ni de conclusion statistique générale ou d’approbation utilisateur inventée.

[Conversion city96](https://huggingface.co/city96/FLUX.1-schnell-gguf/tree/f495746ed9c5efcf4661f53ef05401dceadc17d2) ; [support GGUF Diffusers](https://huggingface.co/docs/diffusers/quantization/gguf) ; [témoin complet G339](FLUX-COMPARISON-G339.md) ; [Klein G340](KLEIN-G340.md).
'''
Path('FLUX-Q8-G351.md').write_text(report)
summary=f"[Rapport G351](FLUX-Q8-G351.md) : FLUX Schnell GGUF Q8_0, calcul FP16 sur une V100 ; 4 étapes, guidage 0, 12 images, répétition exacte. Natives : {n['proposed']}/8 proposées, {n['review']} réserves et {n['rejected']} rejets ; {n['median_seconds']:.3f} s médianes contre {n['full_fp16_seconds']:.3f} s pour le complet réparti G339. "+d['short_decision']+f" Pic {g['memory.used']['max']:.0f} Mio, GPU {g['temperature.gpu']['max']:.0f} °C, HBM {g['temperature.memory']['max']:.0f} °C. Incident de placement CPU détecté puis corrigé, trace conservée. Runtime partagé inchangé, GPU libres, services actifs, machine allumée."
row=f"| I08 — FLUX.1 Schnell GGUF Q8 | **Testé G351** sur une V100 : GGUF Q8_0, calcul FP16, pic {g['memory.used']['max']:.0f} Mio ; encodeurs CPU | Une seule carte nécessaire dans la recette testée | Apache 2.0 ; conversion city96 figée et SHA vérifié, gguf MIT isolé | 12 images ; {n['proposed']}/8 proposées, {n['review']} réserves, {n['rejected']} rejets ; {n['median_seconds']:.3f} s médianes à 4 étapes. Déquantification Volta prouvée dans ce périmètre ; [rapport](FLUX-Q8-G351.md), aucune promotion |"
b=json.dumps({'data':d,'report':report,'summary':summary,'candidate_row':row,'finalizer':Path('finalize_g351.py').read_text(),'report_sources':{f:Path(f).read_text() for f in ['make_g351.py','review_g351.py','bundle_g351.py','quantization_probe_g351.py','g351-review-notes.json']}},ensure_ascii=False).encode()
Path('g351-finalbundle.b64').write_bytes(base64.b64encode(zlib.compress(b)))
print(json.dumps({'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest(),'base64_chars':len(Path('g351-finalbundle.b64').read_bytes())}))
