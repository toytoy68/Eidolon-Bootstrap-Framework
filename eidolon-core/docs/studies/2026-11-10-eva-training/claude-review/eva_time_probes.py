#!/usr/bin/env python3
"""Eva — sondes horaires par étape (Claude, C-MSG-C303, 10/11/2026).

Bibliothèque standard uniquement. Ce script ne charge aucun modèle : il
fabrique des questions (``build``) puis note des réponses déjà générées
(``grade``). La génération reste à faire avec le harnais existant (même
SYSTEM, même décodage glouton, ``max_new_tokens`` 384).

Objectif : départager, sur le parent et sur un candidat, les trois étapes du
calcul horaire et savoir si le format ``time_steps`` est exécutable par le
modèle avant de chercher à l'entraîner davantage.

Familles de sondes (``kind``) :
  S1  HH:MM → minutes depuis minuit                (conversion)
  S2  N − 1440, N dans [1441, 4319]                (soustraction de 1440)
  S3  N minutes → jours complets + reste           (retenue de jours)
  S4  M minutes (M < 1440) → HH:MM                 (reconversion)
  FS  question horaire complète, 2 exemples time_steps dans le message
      utilisateur (exécution en contexte, sans entraînement)
  PF  question horaire complète, réponse assistant préremplie par
      « Départ HH:MM = » (le harnais doit concaténer ``assistant_prefix``
      au prompt après le gabarit de génération, puis l'ajouter au texte)
  ZS  même question complète, sans aide (référence appariée de FS/PF)

Usage :
  python3 -I eva_time_probes.py build --seed 3030 --n 24 > probes.jsonl
  python3 -I eva_time_probes.py grade probes.jsonl reponses.jsonl
``reponses.jsonl`` : une ligne {"id": ..., "response": ...} par sonde.
Pour PF, ``response`` doit contenir le texte complet, préfixe compris.

Les questions complètes sont tirées hors des clés horaires d'E1/E2 si l'on
passe ``--exclude`` (fichier JSON contenant des listes [départ, durée]) ;
le lot final réservé n'est jamais nécessaire ici.
"""
import argparse
import json
import random
import re
import sys
from collections import Counter, defaultdict

JSON_TAIL = ' Termine par un objet JSON avec resultat (chaîne ou null) et unite exactement « {u} ».'
DAY_TAIL = ' Ajoute aussi jours, un entier.'
STRATA = [(0, False), (1, False), (1, True), (2, False), (2, True)]


def hhmm(m):
    return '%02d:%02d' % divmod(m, 60)


def time_steps(start, delta):
    """Identique à eva_review_tools.time_steps (C298)."""
    h, m = divmod(start, 60)
    lines = [f'Départ {h:02d}:{m:02d} = {h} × 60 + {m} = {h * 60} + {m} = {start} minutes.',
             f'{start} + {delta} = {start + delta} minutes.']
    total, days = start + delta, 0
    while total >= 1440:
        lines.append(f'{total} ≥ 1440 : {total} − 1440 = {total - 1440}, jour {days + 1}.')
        total -= 1440
        days += 1
    lines.append(f'{total} < 1440 : {days} jour(s) franchi(s).')
    hh, mm = divmod(total, 60)
    lines.append(f'{hh} × 60 = {hh * 60} ; {total} − {hh * 60} = {mm}, et {mm} < 60.')
    result = f'{hh:02d}:{mm:02d}'
    lines.append(f'Arrivée {result}, décalage {days} jour(s).')
    expected = {'resultat': result, 'unite': 'heure', 'jours': days}
    return ' '.join(lines) + '\n' + json.dumps(expected, ensure_ascii=False), expected


def pair(rng, day, long_, seen):
    for _ in range(100000):
        if day == 0:
            s = rng.randrange(1439); d = rng.randint(1, 1439 - s)
        elif day == 1 and not long_:
            s = rng.randrange(1440); d = rng.randint(max(1, 1440 - s), min(1500, 2879 - s))
        elif day == 1:
            s = rng.randrange(1379); d = rng.randint(1501, 2879 - s)
        elif not long_:
            s = rng.randint(1380, 1439); d = rng.randint(2880 - s, 1500)
        else:
            s = rng.randrange(1440); d = rng.randint(max(1501, 2880 - s), 4319 - s)
        if (s, d) not in seen:
            seen.add((s, d))
            return s, d
    raise RuntimeError('plus de paires disponibles')


def full_question(s, d):
    return (f'Départ à {hhmm(s)}, durée {d} minutes. Donne l’heure d’arrivée et le décalage en jours.'
            + JSON_TAIL.format(u='heure') + DAY_TAIL)


def build(seed, n, exclude):
    rng = random.Random(seed)
    seen = set(exclude)
    rows = []
    for i in range(n):
        m = rng.randrange(1440)
        rows.append(dict(id=f'S1-{i}', kind='S1', stratum='conversion',
                         question=f'Convertis l’heure {hhmm(m)} en minutes écoulées depuis minuit.' + JSON_TAIL.format(u='minute'),
                         expected={'resultat': str(m), 'unite': 'minute'}))
        x = rng.randint(1441, 4319)
        rows.append(dict(id=f'S2-{i}', kind='S2', stratum='1441-2879' if x < 2880 else '2880-4319',
                         question=f'Calcule {x} − 1440.' + JSON_TAIL.format(u='nombre'),
                         expected={'resultat': str(x - 1440), 'unite': 'nombre'}))
        y = rng.randint(1, 4319)
        q, r = divmod(y, 1440)
        rows.append(dict(id=f'S3-{i}', kind='S3', stratum=f'jours{q}',
                         question=(f'{y} minutes : combien de jours complets de 1440 minutes contiennent-elles, '
                                   f'et combien de minutes restent ? Donne le reste dans resultat.')
                         + JSON_TAIL.format(u='minute') + DAY_TAIL,
                         expected={'resultat': str(r), 'unite': 'minute', 'jours': q}))
        z = rng.randrange(1440)
        rows.append(dict(id=f'S4-{i}', kind='S4', stratum='reconversion',
                         question=f'Convertis {z} minutes depuis minuit en heure HH:MM.' + JSON_TAIL.format(u='heure'),
                         expected={'resultat': hhmm(z), 'unite': 'heure'}))
    shots = []
    for day, long_ in [(1, False), (2, True)]:
        s, d = pair(rng, day, long_, seen)
        shots.append((full_question(s, d), time_steps(s, d)[0]))
    preamble = 'Voici deux exemples résolus.\n\n' + '\n\n'.join(
        f'Question : {q}\nRéponse : {a}' for q, a in shots) + '\n\nRésous maintenant de la même manière.\n'
    per = max(1, n // len(STRATA))
    for day, long_ in STRATA:
        for i in range(per):
            s, d = pair(rng, day, long_, seen)
            q = full_question(s, d)
            exp = time_steps(s, d)[1]
            st = f'jour{day}-{"long" if long_ else "court"}'
            key = f'{st}-{i}'
            rows.append(dict(id=f'ZS-{key}', kind='ZS', stratum=st, pair=key, question=q, expected=exp))
            rows.append(dict(id=f'FS-{key}', kind='FS', stratum=st, pair=key, question=preamble + q, expected=exp))
            rows.append(dict(id=f'PF-{key}', kind='PF', stratum=st, pair=key, question=q, expected=exp,
                             assistant_prefix=f'Départ {hhmm(s)} = '))
    return rows


def last_object(text):
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


def correct(value, exp):
    if not value or value.get('unite') != exp['unite']:
        return False
    if str(value.get('resultat')).strip() != exp['resultat']:
        return False
    if 'jours' in exp:
        j = value.get('jours')
        return isinstance(j, int) and not isinstance(j, bool) and j == exp['jours']
    return True


STEP_RE = re.compile(r'(\d+) ≥ 1440 : \1 − 1440 = (\d+)')


def follows_time_steps(text):
    return bool(re.search(r'Départ \d{2}:\d{2} = \d+ × 60 \+ \d+', text))


def step_errors(text):
    """Pour un texte au format time_steps : étapes fausses relevées."""
    errs = []
    m = re.search(r'Départ (\d{2}):(\d{2}) = (\d+) × 60 \+ (\d+) = (\d+) \+ (\d+) = (\d+) minutes', text)
    if m:
        h, mi = int(m[1]), int(m[2])
        if int(m[7]) != h * 60 + mi:
            errs.append('conversion')
    m2 = re.search(r'(\d+) \+ (\d+) = (\d+) minutes\.', text)
    if m2 and int(m2[1]) + int(m2[2]) != int(m2[3]):
        errs.append('addition')
    for a, b in STEP_RE.findall(text):
        if int(a) - 1440 != int(b):
            errs.append('soustraction_1440')
    m3 = re.search(r'(\d+) < 1440 : (\d+) jour', text)
    if m3:
        n_sub = len(STEP_RE.findall(text))
        if int(m3[2]) != n_sub:
            errs.append('compte_jours')
    m4 = re.search(r'(\d+) × 60 = (\d+) ; (\d+) − (\d+) = (\d+), et', text)
    if m4 and (int(m4[1]) * 60 != int(m4[2]) or int(m4[3]) - int(m4[4]) != int(m4[5]) or int(m4[5]) >= 60):
        errs.append('reconversion')
    return errs


def grade(probes, responses):
    by_id = {p['id']: p for p in probes}
    stats = defaultdict(Counter)
    pairs = defaultdict(dict)
    missing = 0
    for r in responses:
        p = by_id.get(r['id'])
        if p is None:
            continue
        text = r.get('response', '')
        ok = correct(last_object(text), p['expected'])
        k = (p['kind'], p['stratum'])
        stats[k]['n'] += 1
        stats[k]['correct'] += ok
        if p['kind'] in ('ZS', 'FS', 'PF'):
            fmt = follows_time_steps(text)
            stats[k]['format_time_steps'] += fmt
            if fmt:
                for e in step_errors(text):
                    stats[k]['etape_' + e] += 1
            pairs[p['pair']][p['kind']] = ok
    missing = len(set(by_id) - {r['id'] for r in responses})
    paired = Counter()
    for v in pairs.values():
        for alt in ('FS', 'PF'):
            if 'ZS' in v and alt in v:
                paired[f'{alt}_gagne'] += (v[alt] and not v['ZS'])
                paired[f'{alt}_perd'] += (v['ZS'] and not v[alt])
    return dict(sondes={f'{k}|{s}': dict(c) for (k, s), c in sorted(stats.items())},
                appariement_vs_ZS=dict(paired), sondes_sans_reponse=missing)


def main(argv):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    b = sub.add_parser('build')
    b.add_argument('--seed', type=int, default=3030)
    b.add_argument('--n', type=int, default=24)
    b.add_argument('--exclude', help='JSON : liste de [départ, durée] à éviter')
    g = sub.add_parser('grade')
    g.add_argument('probes'); g.add_argument('responses')
    a = ap.parse_args(argv)
    if a.cmd == 'build':
        ex = [tuple(x) for x in json.load(open(a.exclude, encoding='utf-8'))] if a.exclude else []
        for row in build(a.seed, a.n, ex):
            print(json.dumps(row, ensure_ascii=False))
    else:
        load = lambda f: [json.loads(l) for l in open(f, encoding='utf-8') if l.strip()]
        print(json.dumps(grade(load(a.probes), load(a.responses)), ensure_ascii=False, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
