# Eidolon Core Technologies (ECT) — readable study generated from saved results
from pathlib import Path
import json
P=Path(__file__).resolve().parent;D=P/'core/eidolon-core/docs/studies/2026-11-20-roles-eva';E=Path('/srv/eidolon/work/eva-learning-cycle13-lowdose-20261120')
def read(p):return json.loads(p.read_text())
raw={x['model']:x for n in ['benchmark-summary.json','extended-summary.json'] for x in read(P/n) if 'roles' in x}
structured={x['model']:x for n in ['structured-summary.json','extended-structured-summary.json'] for x in read(P/n) if 'roles'in x}
L=['# Modèles par rôle et Eva E5 — 20 novembre 2026','Eidolon Core Technologies (ECT).', '',
'Cette étude remplace une qualification par simple chargement ou débit par des contrats de rôle. Les décisions de contrôle et de sécurité restent hors LLM. Aucun modèle de production n’est remplacé.',
'', '[Protocole et amendements](PROTOCOL.md) · [Catalogue par utilité](ROLE-CATALOG.md) · [Apprentissage Eva](EVA-E5.md)', '',
'## Contrats texte',
'Cellules : strict libre / JSON contraint, sur 12. Les réponses ouvertes sont relues séparément dans chat-review.json. La seconde passe est exploratoire.',
'','| Modèle | Robot | Darme | Système | Calcul/dates |','| --- | --- | --- | --- | --- |']
for name,x in raw.items():
 if name not in structured:continue
 L.append('| '+name+' | '+' | '.join(str(x['roles'][r]['strict'])+' / '+str(structured[name]['roles'][r]['strict']) for r in ['robot','darme','systeme','raisonnement'])+' |')
L+=['','Le tag qwen3:30b contient Thinking 2507. Le test adapté à 8192 tokens donne 12/12 robot, 10/12 Darme, 12/12 système et 6/12 calcul/dates stricts. La relecture confirme 12/12 valeurs correctes, avec six clés JSON incorrectes. Deux injections Darme restent mal traitées. Les passages à 512 tokens sont des diagnostics de budget inadapté, pas une qualification complète.',
'','## Compression et perception',
'Prism PTQ1_0, PQ2_0 et Q2_0 exécutés sur le fork cec7baeffba70dcf52890069aa8588d4a71006dd, compilé sm70 avec CUDA12.9 isolé. Mêmes scores fermés ; PQ2 reproduit 52/52 textes Q2, PTQ1 48/52. Les fichiers prism-perf-clean donnent la répétition après libération des GPU et arrêt du lecteur de métadonnées CPU. Le premier passage reste conservé.',
'WeVisOne : comptage, localisation, absence et OCR réussis sur une scène synthétique. Segmentation FP16 : NaN ; décodeur seul FP32 : encore NaN. Chaîne entière FP32 : masques finis, IoU1 sur forme initiale, déplacée et répétée. Prototype uniquement ; dépendances différentes des pins auteur.',
'','## Reproduction et preuve',
'Code de banc dans code/, cas et oracles dans cases.json, identités GGUF, révisions et SHA des téléchargements conservés. Runtime texte : llama.cpp b1b770d90d94cad9e9ea5b993bdbc383a522fb28, CUDA12.9 privé avec correction noexcept glibc2.41 décrite dans le lot backlog précédent. Source et poids complets restent sur X399.',
'Les JSONL publics conservent la réponse finale, les scores et durées ; seul le nombre de caractères du raisonnement est exporté. Adresses LAN et UUID GPU sont masqués. SOURCE-INDEX.json identifie les fichiers publiés ; les manifestes sources identifient les originaux avant assainissement. Les fichiers de configuration exportés sont documentaires, à adapter avant exécution.',
'Le code Eva exporté conserve sa logique complète ; corpus, pack-plan, checkpoints, RNG et optimiseur sont dans le dossier local de campagne. Les données historiques E4b restent référencées par source-manifest.json et lineage.json.',
'','## Conservation et suites',
'Dossiers locaux : /srv/eidolon/ssd/work/roles-eva-20261120 et /srv/eidolon/work/eva-learning-cycle13-lowdose-20261120.',
'P0 : chaîne Darme indépendante de bout en bout. P1 : confirmation Eva inédite, corpus de rôles élargi, N6000 réel et hors réseau. P2 : vision terrain et mémoire avec dates/ACL. Projecteur Prism, autres tailles, code et voix restent non qualifiés dans ce lot.']
(D/'README.md').write_text('\n'.join(L)+'\n')
r=read(E/'resultat-final.json');dec=r['decision'];L=['# Eva E5 — réduction de dose', '', 'Parent : cycle5 accepté, inchangé. Max learning rate 1e-6 au lieu de 3e-6, autres paramètres conservés. Critères figés avant lancement. Aucun test final réservé évalué.', '', 'X1 : HH:MM vers minutes ; X2 : minutes vers jours entiers et reste ; X3 : minutes vers HH:MM. Objectif : améliorer les composants horaires sans dégrader la composition et les acquis.', '', '## Résultats']
for step,a in r['assessments'].items():
 L+=['', '### Pas '+step, '', '| Mesure | Parent recalculé | Candidat |','| --- | --- | --- |']
 for k in ['X1','X2','X3']:L.append('| '+k+' /96 | '+str(a['parent']['components'][k]['correct'])+' | '+str(a['after']['components'][k]['correct'])+' |')
 for k in ['report','day0','anchors']:L.append('| '+k+' | '+str(a['parent'][k]['correct'])+' | '+str(a['after'][k]['correct'])+' |')
 L+=['','Gardes : '+json.dumps(a['guards'],ensure_ascii=False)+'.']
L+=['','Décision enregistrée : '+json.dumps(dec,ensure_ascii=False)+'.','Qualification expérimentale : '+str(dec['qualified'])+'. Aucun remplacement automatique. Diagnostic de transfert hors sélection dans role-transfer-summary.json, canaris relus dans canary-review.json.',
'','Les scores horaires historiques ne sont pas une validation aveugle. Les gains appariés sont exploratoires. La perte de train ne suffit pas à établir une amélioration générale. Les gardes arrêtent la continuation si nécessaire.','',
'Précontrôles : memtester4G sur le même démarrage, SHA doubles, rechargements, qualification DDP quatre updates, contrôle des gradients/masques et sauvegardes vérifiées. Cela ne certifie pas les128G de RAM.',
'','Énergie secteur des seuls intervalles instrumentés : '+str(round(sum(x['energy_wh'] for x in r['telemetry'].values()),3))+' Wh. Voir energy-summary.json pour durée et limites.']
(D/'EVA-E5.md').write_text('\n'.join(L)+'\n')
print('study written')
