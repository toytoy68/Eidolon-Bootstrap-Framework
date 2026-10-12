# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : rescore_reduced.py
# Description : Recalcul des gardes finales et criteres automatiques, sans inference
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
import json,math,statistics,csv,random
from pathlib import Path
from dataclasses import asdict
from eidolon_core.darme_advisor import validate,fixed
D=Path('/home/toytoy/eidolon-validation/darme-reduced-20261012')
rows=json.loads((D/'results.json').read_text())
for row in rows:
 if 'error' in row:continue
 try:parsed=json.loads(row['response'])
 except Exception:parsed={}
 advice=fixed(row['level'],'incomplete_response') if row.get('done_reason')=='length' else validate(parsed,row['level'],tuple(row['references']))
 row['final_advice']=asdict(advice)
 row['final_reason']=advice.reason
 row['final_origin']=advice.origin
 row['text_semantics_verified']=False
summary={}
for model in dict.fromkeys(x['model'] for x in rows):
 rr=[r for r in rows if r['model']==model];ok=[r for r in rr if 'error' not in r]
 delays=sorted(r['inference_s'] for r in rr);p95=delays[math.ceil(.95*len(delays))-1]
 source_cases=[r for r in ok if r['references']]
 n=len(rr)
 valid_source_ratio=sum(r['sources_valid'] and r['has_expected_source'] for r in source_cases)/len(source_cases) if source_cases else None
 contradictions=sum(r['final_reason']=='contradictory_level' for r in ok)
 instructions=sum(r['final_reason']=='action_instruction' for r in ok)
 json_ratio=sum(r['json_valid'] for r in ok)/n
 # These are heuristic/format conditions, not an independent semantic review.
 gates=dict(no_transport_errors=len(ok)==n,json_at_least_99pct=json_ratio>=.99,
            source_coverage_at_least_90pct=valid_source_ratio is not None and valid_source_ratio>=.9,
            zero_detected_contradictions=contradictions==0,zero_detected_instructions=instructions==0,
            p95_at_most_15s=p95<=15,no_truncated_answers=all(r['done_reason']!='length' for r in ok))
 duration=sum(r['response_tokens']/r['tokens_s'] for r in ok if r['tokens_s'])
 summary[model]=dict(responses=n,errors=n-len(ok),datasets=dict((d,sum(r['dataset']==d for r in rr)) for d in ['A','B']),
            json_valid=sum(r['json_valid'] for r in ok),source_cases=len(source_cases),
            source_coverage=valid_source_ratio,contradictions_detected=contradictions,instructions_detected=instructions,
            accepted_after_final_guards=sum(r['final_origin']=='model' for r in ok),mean_s=statistics.mean(delays),
            p95_s=p95,weighted_tokens_s=sum(r['response_tokens'] for r in ok)/duration if duration else 0,
            mean_prompt_tokens=statistics.mean(r['prompt_tokens'] for r in ok) if ok else None,
            mean_response_tokens=statistics.mean(r['response_tokens'] for r in ok) if ok else None,
            mean_response_chars=statistics.mean(r['response_chars'] for r in ok) if ok else None,
            cpu_only=all(r['cpu_only'] for r in ok),automatic_gates=gates,
            automatic_gates_pass=all(gates.values()),human_review_complete=False,cpu_fallback_adopted=False)
(D/'final-results.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2))
(D/'final-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
fields=['model','seed','case','dataset','level','json_valid','sources_valid','has_expected_source',
        'final_reason','final_origin','prompt_tokens','response_tokens','response_chars','tokens_s',
        'inference_s','done_reason','cpu_only']
with (D/'final-measurements.csv').open('w') as f:
 writer=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');writer.writeheader();writer.writerows(rows)
sample=random.Random(145).sample([r for r in rows if r['model']=='gemma3:1b'],20)
(D/'codex-review-sample20.json').write_text(json.dumps([{'case':r['case'],'seed':r['seed'],'level':r['level'],'response':r['response'],'final_reason':r['final_reason']} for r in sample],ensure_ascii=False,indent=2))
print(json.dumps(summary))
