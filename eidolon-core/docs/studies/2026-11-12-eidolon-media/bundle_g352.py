# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : bundle_g352.py
# Description : Archivage du comparatif FLUX Schnell Q4
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
from pathlib import Path
import json,zlib,base64,hashlib,re
d=json.loads(Path('g352-data.json').read_text());lib=json.loads(Path('g352-library.json').read_text())
d['library_file_id']=lib['library_file_id'];Path('g352-data.json').write_text(json.dumps(d,ensure_ascii=False,indent=2))
n=d['native_summary'];m=d['manifest'];g=d['telemetry']['gpus']['0'];clean=lambda t:re.sub(r'</?b>','',t)
native=[r for r in d['results'] if r['condition']=='quality']
report='# FLUX.1 Schnell GGUF Q4_0 — G352, 14 novembre 2026\n\nEidolon Core Technologies (ECT).\n\n## Résultat et décision\n\n'+clean(d['conclusion'])+'\n\n'+'\n\n'.join(map(clean,d['summary_paragraphs']))+'\n\n'
report+=f"Huit natives 1024² : **{n['proposed']} proposées, {n['review']} à revoir, {n['rejected']} rejetées**. Médiane {n['median_seconds']:.9f} s, plage {min(x['seconds'] for x in native):.9f}–{max(x['seconds'] for x in native):.9f} s. Toutes les revues sont provisoires, par GPT ; aucune validation toytoy attribuée.\n\n"
report+='## Recette et méthode\n\n'+'\n\n'.join(map(clean,d['method_paragraphs']))+'\n\n'
report+='''Même grille que Q8 G351 et complet G339 : main ouverte, tasse/bol, katana/fourreau, duo en pied ; seeds 20261113 et 20261114. Huit natives 1024², contrôle 512², répétition, 1024×576 et 768×576. Prompts et seeds figés avant observation, sans retouche ni sélection a posteriori.

Fichier Q4_0, 776 tenseurs (304 Q4_0, 472 F16). Après conversion des noms et séparation des projections : 494 modules GGUFLinear, 1 156 paramètres sur GPU0 ; 6 770 653 312 octets de paramètres dont 6 656 753 664 quantifiés. Déquantification dynamique PyTorch vers FP16, pas de calcul natif INT4 ni de kernel CUDA distant. Tous les paramètres du générateur résident sur GPU0, sans offload CPU. Quatre appels du générateur et 228 appels de blocs vérifiés par image.

Attention MATH par morceaux de 256 requêtes, VAE Flux FP32 sur GPU0 avec tuiles de 512 pixels. Scheduler FlowMatchEuler shift 1, décalage dynamique désactivé, 4 étapes, guidage 0. CLIP-L et T5-XXL via Comfy CPU FP32, 256 tokens, embeddings enregistrés FP16. Quatre nouveaux encodages G352, puis cache vérifié par SHA réutilisé. L’avertissement CLIP text_projection.weight absent existait déjà dans G339/G351 ; encodeurs inchangés.

## Provenance et environnement

Conversion publique city96/FLUX.1-schnell-gguf, révision f495746ed9c5efcf4661f53ef05401dceadc17d2. Variante exacte flux1-schnell-Q4_0.gguf (pas Q4_K_S). Fichier de 6 770 707 360 octets, SHA256 90a393d3a44bec691c707003f434fdde06064b870bb3c206eb7a4f109b25ff4e. Provenance directe BFL déclarée par le convertisseur, sans audit intégral de conversion. Carte auteur et licence Apache 2.0 de Schnell archivées. Encodeurs et VAE G339 réutilisés après vérification de chaque SHA.

PyTorch 2.6.0+cu124, Diffusers 0.32.2, Transformers 4.49.0 ; même environnement preference-lab et mêmes sources de pipeline/attention que Q8. Paquet gguf 0.17.1 installé dans flux-q4-g352/vendor, roue SHA vérifiée, sans dépendances réinstallées. Licence MIT archivées. Test de déquantification de 16 blocs Q4 sur V100 contre NumPy : écart maximal nul sur cet échantillon seulement. Sources et résultat conservés.

## Incident et exécution

Après téléchargement et vérification réussis, la préparation a échoué uniquement à la copie de la licence gguf : le script cherchait dist-info/licenses/LICENSE, alors que la roue fournit dist-info/LICENSE. Chemin corrigé dans la source, licence copiée depuis la roue et comparée à celle de G351 avant tout lancement. Ancienne source, journal et réparation archivés. Ce défaut ne concernait ni les poids ni le runtime d’inférence.

Le transfert explicite transformer.to('cuda:0'), introduit en G351 pour le chargeur single-file Diffusers 0.32.2, est conservé dès le départ. Contrôles de placement effectués avant génération. Contrôle 512² puis grille terminés sans échec de génération.

Générations locales, réseau sortant bloqué dans les unités transitoires, verrou de campagne, UUID exact GPU0. Limites 72 Go RAM, 800 % CPU, 90 minutes ; allocation PyTorch limitée à 0,94 de GPU0 et garde 65 °C GPU / 70 °C HBM. GPU1 et GTX1060 ne participent pas au calcul. Aucun pilote, service de production, entraînement ou modèle favori modifié.

'''
report+=f"Pic VRAM GPU0 {g['memory.used']['max']:.0f} Mio, réduction {n['vram_saved_vs_q8_pct']:.2f} % face à Q8. GPU/HBM {g['temperature.gpu']['max']:.0f}/{g['temperature.memory']['max']:.0f} °C. Consigne 300 W, pic échantillonné {g['power.draw']['max']:.2f} W ; pas de mesure d’énergie totale. CPU Tdie {d['telemetry']['cpu_tdie_c']['max']:.3f} °C sur la grille à cache chaud. Erreurs de télémétrie : {d['telemetry']['sample_errors']}. Encodages : {m['encode_seconds']:.9f} s ; chargement grille : {m['load_seconds']:.9f} s.\n\n"
report+=d['execution_summary']+'\n\n## Images\n\n| Image | Cas / condition | Temps (s) | Avis GPT | Commentaire |\n| --- | --- | ---: | --- | --- |\n'
for x in d['results']:
 r=d['reviews'][str(x['index'])];report+=f"| G352-{x['index']:02d} | {x['case']} / {x['condition']} | {x['seconds']:.3f} | {r['verdict']} | {r['comment']} |\n"
report+=f"\n## Livrable et limites\n\nRapport illustré Eidolon-comparatif-FLUXSchnellQ4-G352.pdf, 14 pages, identité `{d['library_file_id']}`. Synthèse flux-q4-validation-g352.json et preuves evidence-g352/.\n\n"
report+='''PNG, latents, embeddings et journaux conservés sous /srv/eidolon/workspaces/media-20261112/flux-q4-g352/. Poids sous /srv/eidolon/data/media-models-20261113/flux-schnell-q4/. Les résultats bruts gardent leur statut initial NOT_REVIEWED/PENDING_REVIEW ; la synthèse ajoute la revue ultérieure.

Revue subjective sur aperçus réduits ; PNG natifs conservés. Quatre scènes et deux seeds ne permettent pas de généraliser la fiabilité. Même recette et matériel pour Q8/Q4 ; temps observés sur une exécution, sans intervalle statistique. Comparaison FP16 sur deux cartes : quantification et répartition changent ensemble. Les chronomètres incluent calcul, décodage, contrôles et sauvegarde du latent, mais excluent encodage, chargement et écriture PNG finale. Aucune promesse de latence depuis clic, de performance INT4 native ou de supériorité générale.

[Conversion city96](https://huggingface.co/city96/FLUX.1-schnell-gguf/tree/f495746ed9c5efcf4661f53ef05401dceadc17d2) ; [Q8 G351](FLUX-Q8-G351.md) ; [complet G339](FLUX-COMPARISON-G339.md).
'''
Path('FLUX-Q4-G352.md').write_text(report)
summary=f"[Rapport G352](FLUX-Q4-G352.md) : FLUX Schnell GGUF Q4_0, calcul FP16 sur une V100 ; 4 étapes, guidage 0, 12 images, répétition exacte. Natives : {n['proposed']}/8 proposées, {n['review']} réserves, {n['rejected']} rejets ; {n['median_seconds']:.3f} s médianes contre {n['q8_seconds']:.3f} s Q8. Pic {g['memory.used']['max']:.0f} Mio (-{n['vram_saved_vs_q8_pct']:.1f} % vs Q8), GPU/HBM {g['temperature.gpu']['max']:.0f}/{g['temperature.memory']['max']:.0f} °C. "+d['short_decision']+' Copie de licence corrigée avant génération, trace conservée. Runtime inchangé, GPU libres, services actifs, machine allumée.'
row=f"| I09 — FLUX.1 Schnell GGUF Q4 | **Testé G352** : Q4_0, calcul FP16 une V100, pic {g['memory.used']['max']:.0f} Mio | Aucun besoin de répartition dans cette recette | Apache 2.0 ; city96 figé, SHA vérifié, gguf MIT isolé | 12 images ; {n['proposed']}/8 proposées, {n['review']} réserves, {n['rejected']} rejets ; {n['median_seconds']:.3f} s à 4 étapes, -{n['vram_saved_vs_q8_pct']:.1f} % VRAM vs Q8. [Rapport](FLUX-Q4-G352.md), aucune promotion |"
b=json.dumps({'data':d,'report':report,'summary':summary,'candidate_row':row,'finalizer':Path('finalize_g352.py').read_text(),'report_sources':{f:Path(f).read_text() for f in ['make_g352.py','review_g352.py','bundle_g352.py','g352-review-notes.json']}},ensure_ascii=False).encode()
Path('g352-finalbundle.b64').write_bytes(base64.b64encode(zlib.compress(b)))
print(json.dumps({'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest(),'base64_chars':len(Path('g352-finalbundle.b64').read_bytes())}))
