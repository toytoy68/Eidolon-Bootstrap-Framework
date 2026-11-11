#!/usr/bin/env python3
"""Eva — validateur de chaîne et sondes « frontière » (Claude, C-MSG-C307, 11/11/2026).

Bibliothèque standard uniquement ; ne charge aucun modèle.

1. ``invalid_claims(text)`` remplace ``eva_time_probes.step_errors`` (C303),
   dont G304 a montré qu'il laissait passer « 1466 < 1440 ». Ici, chaque
   affirmation du texte est recalculée, quel que soit le format :
   - chaînes d'égalités « 23 × 60 + 41 = 1380 + 41 = 1421 » : tous les membres
     doivent avoir la même valeur (+, −, ×, nombres négatifs admis) ; une chaîne
     qui suit ÷ ou / n'est pas évaluée (quotient entier ou fraction ambigus) ;
   - comparaisons « a < b », « a ≥ b », « a > b », « a ≤ b » : vraies, sauf si
     suivies de « ? » (question posée, pas affirmation) ;
   - « jour k » : k doit valoir 1, 2, 3… dans l'ordre d'apparition ;
   - « d jour(s) franchi(s) » / « décalage d jour(s) » : d égal au dernier k ;
   - JSON final : resultat et jours cohérents avec le dernier reste écrit.
   Il ne prouve pas que la méthode suivie est la bonne : une réponse sans
   affirmation fausse peut rester incomplète ; la justesse du JSON reste notée
   à part.

2. ``time_steps_b(start, delta)`` : variante du format où le test de boucle
   « X ≥ 1440 » / « X < 1440 » est remplacé par la soustraction toujours posée
   et le signe de son résultat (« 1466 − 1440 = 26, positif ou nul : jour 2 »,
   « 26 − 1440 = −1414, négatif : on garde 26 »). Motivation : S2 (soustraction)
   24/24 sur les deux modèles, alors que les trois échecs FS jour2-court sont des
   comparaisons fausses juste au-dessus de 1440.

3. ``build`` : questions dont le total tombe à ±60 min d'une frontière de jour
   (1440, 2880), côté au-dessus et côté au-dessous, en trois variantes
   appariées : ZS (sans aide), FA (2 exemples format C298), FB (2 exemples
   format B). Les exemples d'amorce sont eux-mêmes des cas frontière.

Usage :
  python3 -I eva_boundary_probes.py build --seed 3070 --per 8 [--exclude paires.json] > frontiere.jsonl
  python3 -I eva_boundary_probes.py grade frontiere.jsonl reponses.jsonl
  python3 -I eva_boundary_probes.py audit reponses.jsonl   # affirmations fausses, tout format
"""
import argparse
import json
import random
import re
import sys
from collections import Counter, defaultdict

JSON_TAIL = (' Termine par un objet JSON avec resultat (chaîne ou null) et unite exactement '
             '« heure ». Ajoute aussi jours, un entier.')


def hhmm(m):
    return '%02d:%02d' % divmod(m, 60)


# --------------------------------------------------------------------------
# Formats de réponse
# --------------------------------------------------------------------------
def _tail(total, days):
    hh, mm = divmod(total, 60)
    result = f'{hh:02d}:{mm:02d}'
    expected = {'resultat': result, 'unite': 'heure', 'jours': days}
    return (f'{hh} × 60 = {hh * 60} ; {total} − {hh * 60} = {mm}, et {mm} < 60. '
            f'Arrivée {result}, décalage {days} jour(s).'), expected


def time_steps_a(start, delta):
    """Format C298 (identique à eva_review_tools.time_steps)."""
    h, m = divmod(start, 60)
    parts = [f'Départ {h:02d}:{m:02d} = {h} × 60 + {m} = {h * 60} + {m} = {start} minutes.',
             f'{start} + {delta} = {start + delta} minutes.']
    total, days = start + delta, 0
    while total >= 1440:
        parts.append(f'{total} ≥ 1440 : {total} − 1440 = {total - 1440}, jour {days + 1}.')
        total -= 1440
        days += 1
    parts.append(f'{total} < 1440 : {days} jour(s) franchi(s).')
    t, expected = _tail(total, days)
    parts.append(t)
    return ' '.join(parts) + '\n' + json.dumps(expected, ensure_ascii=False), expected


def time_steps_b(start, delta):
    """Format B : soustraction toujours posée, décision sur le signe."""
    h, m = divmod(start, 60)
    parts = [f'Départ {h:02d}:{m:02d} = {h} × 60 + {m} = {h * 60} + {m} = {start} minutes.',
             f'{start} + {delta} = {start + delta} minutes.']
    total, days = start + delta, 0
    while True:
        diff = total - 1440
        if diff >= 0:
            days += 1
            parts.append(f'{total} − 1440 = {diff}, positif ou nul : jour {days}.')
            total = diff
        else:
            parts.append(f'{total} − 1440 = −{-diff}, négatif : on garde {total}, {days} jour(s) franchi(s).')
            break
    t, expected = _tail(total, days)
    parts.append(t)
    return ' '.join(parts) + '\n' + json.dumps(expected, ensure_ascii=False), expected


# --------------------------------------------------------------------------
# Validateur d'affirmations
# --------------------------------------------------------------------------
NUM = r'[−-]?\d+'
EXPR = rf'{NUM}(?:\s*[+−×*-]\s*\d+)*'
CHAIN_RE = re.compile(rf'(?<![\d:])({EXPR}(?:\s*=\s*{EXPR})+)')
CMP_RE = re.compile(rf'(?<![\d:])(?=({NUM})\s*(<|≥|>|≤)\s*({NUM})(?![\d:]))')
DAY_RE = re.compile(r'\bjour (\d+)\b')
FINAL_DAYS_RE = re.compile(r'(\d+) jour\(s\) franchi\(s\)|décalage (?:de )?(\d+) jour\(s\)')


def _int(s):
    return int(s.replace('−', '-'))


def _eval(expr):
    """Évalue +, −, × sur des entiers (× prioritaire), signe initial admis. Pas d'eval()."""
    e = expr.replace(' ', '').replace('−', '-').replace('*', '×')
    m = re.match(r'-?\d+', e)
    vals, ops, pos = [int(m[0])], [], m.end()
    for op, n in re.findall(r'([+×-])(-?\d+)', e[pos:]):
        n = int(n)
        if op == '×':
            vals[-1] *= n
        else:
            ops.append(op)
            vals.append(n)
    total = vals[0]
    for op, v in zip(ops, vals[1:]):
        total = total + v if op == '+' else total - v
    return total


def invalid_claims(text):
    """Liste des affirmations fausses : (catégorie, extrait)."""
    body = text
    j = body.rfind('{')
    if j >= 0:
        body = body[:j]
    out = []
    for m in CHAIN_RE.finditer(body):
        if body[:m.start()].rstrip()[-1:] in ('÷', '/'):
            continue                      # division non évaluée ici (quotient entier ou fraction)
        members = [s for s in re.split(r'\s*=\s*', m[1])]
        try:
            vals = [_eval(s) for s in members]
        except (ValueError, IndexError):
            continue
        if len(set(vals)) > 1:
            out.append(('calcul', m[1]))
    for m in CMP_RE.finditer(body):
        if re.match(r'\s*\?', body[m.end(3):]):
            continue                      # « 780 < 60 ? Non » : question, pas affirmation
        a, op, b = _int(m[1]), m[2], _int(m[3])
        ok = {'<': a < b, '≥': a >= b, '>': a > b, '≤': a <= b}[op]
        if not ok:
            out.append(('comparaison', f'{m[1]} {op} {m[3]}'))
    days = [int(k) for k in DAY_RE.findall(body)]
    if days and days != list(range(1, len(days) + 1)):
        out.append(('suite_jours', str(days)))
    finals = [int(a or b) for a, b in FINAL_DAYS_RE.findall(body)]
    if days and finals and any(f != days[-1] for f in finals):
        out.append(('compte_jours', f'{days[-1]} vs {finals}'))
    obj = _last_object(text)
    if obj and finals and isinstance(obj.get('jours'), int) and obj['jours'] != finals[-1]:
        out.append(('json_incoherent', f"jours {obj['jours']} vs {finals[-1]}"))
    arr = re.findall(r'Arrivée (\d{2}:\d{2})', body)
    if obj and arr and obj.get('resultat') != arr[-1]:
        out.append(('json_incoherent', f"{obj.get('resultat')} vs {arr[-1]}"))
    return out


def _last_object(text):
    dec = json.JSONDecoder(); out = None
    for i, ch in enumerate(text):
        if ch == '{':
            try:
                v, _ = dec.raw_decode(text[i:])
            except json.JSONDecodeError:
                continue
            if isinstance(v, dict) and 'resultat' in v:
                out = v
    return out


def _correct(obj, exp):
    return bool(obj) and obj.get('unite') == 'heure' and obj.get('resultat') == exp['resultat'] \
        and isinstance(obj.get('jours'), int) and not isinstance(obj.get('jours'), bool) \
        and obj['jours'] == exp['jours']


def format_of(text):
    if re.search(r'− 1440 = [−-]?\d+, (positif ou nul|négatif)', text):
        return 'B'
    if re.search(r'Départ \d{2}:\d{2} = \d+ × 60', text):
        return 'A'
    if re.match(r'\s*\d+ \+ \d+ = \d+ minutes', text):
        return 'court'
    return 'autre'


# --------------------------------------------------------------------------
# Construction des sondes frontière
# --------------------------------------------------------------------------
def boundary_pair(rng, frontier, side, seen):
    """Total dans [F, F+59] (side='dessus') ou [F−60, F−1] (side='dessous')."""
    for _ in range(100000):
        total = rng.randint(frontier, frontier + 59) if side == 'dessus' else rng.randint(frontier - 60, frontier - 1)
        s = rng.randrange(1440)
        d = total - s
        if d >= 1 and (s, d) not in seen:
            seen.add((s, d))
            return s, d
    raise RuntimeError('plus de paires')


def question(s, d):
    return f'Départ à {hhmm(s)}, durée {d} minutes. Donne l’heure d’arrivée et le décalage en jours.' + JSON_TAIL


def build(seed, per, exclude):
    rng = random.Random(seed)
    seen = set(exclude)
    shot_pairs = [boundary_pair(rng, 1440, 'dessus', seen), boundary_pair(rng, 2880, 'dessus', seen)]
    pre = {}
    for name, fn in (('FA', time_steps_a), ('FB', time_steps_b)):
        pre[name] = 'Voici deux exemples résolus.\n\n' + '\n\n'.join(
            f'Question : {question(s, d)}\nRéponse : {fn(s, d)[0]}' for s, d in shot_pairs) \
            + '\n\nRésous maintenant de la même manière.\n'
    rows = []
    for frontier in (1440, 2880):
        for side in ('dessous', 'dessus'):
            st = f'{frontier}-{side}'
            for i in range(per):
                s, d = boundary_pair(rng, frontier, side, seen)
                exp = time_steps_a(s, d)[1]
                key = f'{st}-{i}'
                q = question(s, d)
                rows.append(dict(id=f'ZS-{key}', kind='ZS', stratum=st, pair=key, question=q, expected=exp, time_key=[s, d]))
                for name in ('FA', 'FB'):
                    rows.append(dict(id=f'{name}-{key}', kind=name, stratum=st, pair=key,
                                     question=pre[name] + q, expected=exp, time_key=[s, d]))
    return rows


def grade(probes, responses):
    by_id = {p['id']: p for p in probes}
    stats = defaultdict(Counter)
    pairs = defaultdict(dict)
    for r in responses:
        p = by_id.get(r['id'])
        if p is None:
            continue
        text = r.get('response', '')
        ok = _correct(_last_object(text), p['expected'])
        k = f"{p['kind']}|{p['stratum']}"
        c = stats[k]
        c['n'] += 1
        c['correct'] += ok
        c['format_' + format_of(text)] += 1
        bad = invalid_claims(text)
        c['sans_affirmation_fausse'] += not bad
        for cat in {b[0] for b in bad}:
            c['faux_' + cat] += 1
        pairs[p['pair']][p['kind']] = ok
    paired = Counter()
    for v in pairs.values():
        for a, b in (('FA', 'ZS'), ('FB', 'ZS'), ('FB', 'FA')):
            if a in v and b in v:
                paired[f'{a}>{b}'] += v[a] and not v[b]
                paired[f'{b}>{a}'] += v[b] and not v[a]
    return dict(sondes=dict(sorted((k, dict(v)) for k, v in stats.items())),
                apparie=dict(paired), sans_reponse=len(set(by_id) - {r['id'] for r in responses}))


def main(argv):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    b = sub.add_parser('build')
    b.add_argument('--seed', type=int, default=3070)
    b.add_argument('--per', type=int, default=8)
    b.add_argument('--exclude')
    g = sub.add_parser('grade'); g.add_argument('probes'); g.add_argument('responses')
    au = sub.add_parser('audit'); au.add_argument('responses')
    a = ap.parse_args(argv)
    load = lambda f: [json.loads(l) for l in open(f, encoding='utf-8') if l.strip()]
    if a.cmd == 'build':
        ex = [tuple(x) for x in json.load(open(a.exclude, encoding='utf-8'))] if a.exclude else []
        for row in build(a.seed, a.per, ex):
            print(json.dumps(row, ensure_ascii=False))
    elif a.cmd == 'grade':
        print(json.dumps(grade(load(a.probes), load(a.responses)), ensure_ascii=False, indent=1))
    else:
        out = {}
        for r in load(a.responses):
            bad = invalid_claims(r.get('response', ''))
            if bad:
                out[r['id']] = bad
        print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
