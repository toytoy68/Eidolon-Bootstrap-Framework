#!/usr/bin/env python3
"""Eva — analyse étape par étape parent / candidat (Claude, C-MSG-C313, 11/11/2026).

Bibliothèque standard. Lit `report-responses.json` (G312 : {"parent": [...],
"step204": [...]}) et compare, sur les questions horaires hors acquis :
- présence de la conversion juste (minutes du départ écrites) et du total juste ;
- forme de la réponse (début « Départ », format court « a + b = c … Cela donne »,
  autre) et justesse par forme ;
- nouvelles opérations après le total (− 1440, ÷ 60, heures ≥ 24, reconversion
  « h × 60 = … ; ») et leur justesse ;
- répartition des pertes (juste → faux) selon que conversion et total sont restés justes.

« Conversion juste » = l'entier du départ en minutes figure dans le raisonnement :
indicateur de présence, pas preuve que l'étape a été faite au bon endroit.

Usage : python3 -I eva_hybrid_analysis.py report-responses.json [parent] [step204]
"""
import json
import re
import sys
from collections import Counter, defaultdict

OPS = {'soustraction_1440': r'[−-] ?1440 ?=', 'division_60': r'÷ ?60|/ ?60',
       'heure_sup_24': r'\b(2[4-9]|[3-9]\d) ?(h|:)\d\d', 'reconversion_x60': r'\d+ × 60 = \d+ ;',
       'cela_donne': r'Cela donne'}


def body(t):
    j = t.rfind('{')
    return t[:j] if j >= 0 else t


def form(t):
    if t.lstrip().startswith('Départ'):
        return 'Départ'
    if re.match(r'\s*\d+ \+ \d+ = \d+ minutes depuis minuit\. Cela donne', t):
        return 'court'
    return 'autre'


def rows_of(data, cand):
    return [r for r in data[cand] if r['expected'].get('unite') == 'heure' and r.get('group') != 'anchor']


def features(r):
    s, d = r['time_key']
    b = body(r['response'])
    nums = {int(x) for x in re.findall(r'(?<![\d:])\d+(?![\d:])', b)}
    return dict(ok=bool(r['evaluation']['content_correct']), conv=s in nums, total=s + d in nums,
                form=form(r['response']), stratum=r['stratum'], jours=r['expected']['jours'],
                ops={k for k, p in OPS.items() if re.search(p, b)}, tokens=r.get('generated_tokens'))


def analyse(data, a='parent', b='step204'):
    out = {}
    F = {}
    for cand in (a, b):
        F[cand] = {r['id']: features(r) for r in rows_of(data, cand)}
        c = Counter(); byform = defaultdict(Counter); ops = defaultdict(Counter)
        for f in F[cand].values():
            c['n'] += 1; c['justes'] += f['ok']; c['conversion_presente'] += f['conv']
            c['total_present'] += f['total']; c['total_present_mais_faux'] += f['total'] and not f['ok']
            byform[f['form']]['n'] += 1; byform[f['form']]['justes'] += f['ok']
            for o in f['ops']:
                ops[o]['n'] += 1; ops[o]['justes'] += f['ok']
        toks = [f['tokens'] for f in F[cand].values() if isinstance(f['tokens'], int)]
        out[cand] = dict(totaux=dict(c), par_forme={k: dict(v) for k, v in byform.items()},
                         operations={k: dict(v) for k, v in ops.items()},
                         tokens_moyens=round(sum(toks) / len(toks), 1) if toks else None)
    P, S = F[a], F[b]
    common = P.keys() & S.keys()
    losses = [i for i in common if P[i]['ok'] and not S[i]['ok']]
    gains = [i for i in common if S[i]['ok'] and not P[i]['ok']]
    lc = Counter()
    for i in losses:
        f = S[i]
        lc[' | '.join(('conversion ok' if f['conv'] else 'conversion perdue',
                        'total ok' if f['total'] else 'total perdu', f['form']))] += 1
    out['pertes'] = dict(n=len(losses), detail=dict(lc.most_common()),
                         par_strate=dict(Counter(P[i]['stratum'] for i in losses)))
    out['gains'] = dict(n=len(gains), par_strate=dict(Counter(P[i]['stratum'] for i in gains)))
    return out


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(2)
    data = json.load(open(sys.argv[1], encoding='utf-8'))
    print(json.dumps(analyse(data, *sys.argv[2:4]), ensure_ascii=False, indent=1))
