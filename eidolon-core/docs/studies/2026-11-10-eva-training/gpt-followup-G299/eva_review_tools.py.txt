#!/usr/bin/env python3
"""Eva — outils de contre-revue hors GPU (Claude, C-MSG-C298, 10/11/2026).

Bibliothèque standard uniquement. Aucune inférence, aucun entraînement, aucun
accès réseau. Lit des lignes JSONL déjà produites (`evaluation-*.jsonl`,
`<candidat>.jsonl` de l'audit cycle8) et les renote avec trois lectures :

- ``strict``   : réimplémentation de ``curriculum.grade`` (content_correct) ;
- ``tolerant`` : mêmes valeurs, formats normalisés (``4:59`` → ``04:59``,
  ``"1"`` → ``1`` pour jours, ``15,32`` → ``15.32``, ``euros`` → ``euro``) ;
- ``reduced``  : pour une fraction attendue, exige aussi la forme irréductible.

Classe ensuite chaque échec horaire (format, jours faux, heure fausse, écart
d'un multiple de 60 ou de 1440 minutes...) et ventile les questions horaires
par jours franchis et par durée au-delà ou en deçà de la plage d'entraînement
(1 500 minutes, maximum des cycles 3, 6 et 7).

Usage :
    python3 -I eva_review_tools.py fichier.jsonl [autre.jsonl ...]
Sortie : un objet JSON sur la sortie standard. Le script ne modifie rien.
"""
import json
import re
import sys
from collections import Counter, defaultdict
from fractions import Fraction

TRAIN_MAX_DELTA = 1500


# --------------------------------------------------------------------------
# Lecture du dernier objet JSON (même règle que curriculum.grade)
# --------------------------------------------------------------------------
def last_object(text):
    decoder = json.JSONDecoder()
    found = []
    for i, ch in enumerate(text):
        if ch == '{':
            try:
                value, _ = decoder.raw_decode(text[i:])
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict) and 'resultat' in value:
                found.append(value)
    return found[-1] if found else None


def strict_correct(value, expected):
    """Copie de la logique content_correct de curriculum.grade."""
    if value is None:
        return False
    try:
        if expected['resultat'] is None:
            ok = value.get('resultat') is None
        elif expected['unite'] == 'heure':
            ok = (value.get('resultat') == expected['resultat']
                  and value.get('jours') == expected['jours'])
        else:
            actual = value.get('resultat')
            if isinstance(actual, bool):
                return False
            ok = Fraction(str(actual)) == Fraction(expected['resultat'])
        return bool(ok and value.get('unite') == expected['unite'])
    except Exception:
        return False


# --------------------------------------------------------------------------
# Normalisations tolérantes (lecture de diagnostic, pas un nouveau barème)
# --------------------------------------------------------------------------
UNIT_ALIASES = {'euros': 'euro', '€': 'euro', 'heures': 'heure', 'h': 'heure',
                'pièces': 'pièce', 'pieces': 'pièce', 'piece': 'pièce'}


def norm_unit(u):
    if not isinstance(u, str):
        return u
    u = u.strip().lower()
    return UNIT_ALIASES.get(u, u)


def parse_clock(s):
    if not isinstance(s, str):
        return None
    m = re.fullmatch(r'\s*(\d{1,2})\s*(?:[:hH]\s*)(\d{2})\s*', s)
    if not m:
        return None
    h, mi = int(m[1]), int(m[2])
    if h > 23 or mi > 59:
        return None
    return h, mi


def parse_number(x):
    if isinstance(x, bool) or x is None:
        return None
    if isinstance(x, (int, float)):
        return Fraction(str(x))
    if not isinstance(x, str):
        return None
    s = x.strip().replace('€', '').replace(' ', '').replace(' ', '')
    s = s.replace(',', '.')
    try:
        return Fraction(s)
    except (ValueError, ZeroDivisionError):
        return None


def parse_days(x):
    if isinstance(x, bool):
        return None
    if isinstance(x, int):
        return x
    if isinstance(x, float) and x.is_integer():
        return int(x)
    if isinstance(x, str) and re.fullmatch(r'\s*-?\d+\s*', x):
        return int(x)
    return None


def tolerant_correct(value, expected):
    if value is None:
        return False
    if norm_unit(value.get('unite')) != expected['unite']:
        return False
    if expected['resultat'] is None:
        return value.get('resultat') is None
    if expected['unite'] == 'heure':
        got = parse_clock(value.get('resultat'))
        want = parse_clock(expected['resultat'])
        return got == want and parse_days(value.get('jours')) == expected['jours']
    got = parse_number(value.get('resultat'))
    return got is not None and got == Fraction(expected['resultat'])


def reduced_ok(value, expected):
    """Fraction attendue : la chaîne rendue doit être irréductible (p/q, q>1)."""
    if '/' not in str(expected['resultat']):
        return None
    actual = value.get('resultat') if value else None
    if not isinstance(actual, str):
        return False
    m = re.fullmatch(r'\s*(-?\d+)\s*/\s*(\d+)\s*', actual)
    if not m:
        return False
    p, q = int(m[1]), int(m[2])
    f = Fraction(p, q)
    return f.numerator == p and f.denominator == q


# --------------------------------------------------------------------------
# Questions horaires : extraction et classification des erreurs
# --------------------------------------------------------------------------
def time_operands(question):
    """Renvoie (départ en minutes, durée) ou None."""
    q = question.split(' Termine')[0]
    t = re.search(r'(\d{2}):(\d{2})', q)
    if not t:
        return None
    rest = q[:t.start()] + q[t.end():]
    nums = re.findall(r'\d+', rest)
    if not nums:
        return None
    return int(t[1]) * 60 + int(t[2]), int(nums[0])


def classify_time(value, expected):
    if value is None:
        return 'json_absent'
    if strict_correct(value, expected):
        return 'correct'
    if tolerant_correct(value, expected):
        return 'format_seul'
    want = parse_clock(expected['resultat'])
    got = parse_clock(value.get('resultat'))
    days_ok = parse_days(value.get('jours')) == expected['jours']
    if norm_unit(value.get('unite')) != 'heure':
        return 'unite'
    if got is None:
        return 'heure_illisible'
    if got == want:
        return 'jours_faux_heure_juste'
    exp_total = expected['jours'] * 1440 + want[0] * 60 + want[1]
    gd = parse_days(value.get('jours'))
    got_total = (gd if gd is not None else 0) * 1440 + got[0] * 60 + got[1]
    diff = got_total - exp_total
    if days_ok and got[1] == want[1]:
        return 'heure_decalee_%+dh' % ((got[0] - want[0]))
    if diff % 60 == 0:
        return 'ecart_multiple_60'
    if abs(diff) <= 5:
        return 'ecart_minutes_<=5'
    return 'jours_justes_heure_fausse' if days_ok else 'heure_et_jours_faux'


# --------------------------------------------------------------------------
# Format d'explication horaire « soustractions vérifiables » (proposition)
# --------------------------------------------------------------------------
def time_steps(start, delta):
    """Explication où chaque étape est une opération courte et vérifiable."""
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


# --------------------------------------------------------------------------
# Rapport
# --------------------------------------------------------------------------
def load_rows(paths):
    rows = []
    for p in paths:
        with open(p, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    r = json.loads(line)
                    r['_source'] = p
                    rows.append(r)
    return rows


def group_name(r):
    return r.get('skill') or 'famille-%s' % r.get('family')


def analyse(rows):
    out = defaultdict(lambda: Counter())
    time_classes = defaultdict(Counter)
    strata = defaultdict(Counter)
    for r in rows:
        key = (r['_source'], group_name(r))
        exp = r['expected']
        val = last_object(r.get('response', ''))
        c = out[key]
        c['n'] += 1
        c['strict'] += strict_correct(val, exp)
        c['tolerant'] += tolerant_correct(val, exp)
        c['tronque'] += bool(r.get('token_limit_reached'))
        red = reduced_ok(val, exp)
        if red is not None:
            c['fraction_attendue'] += 1
            c['strict_et_irreductible'] += bool(strict_correct(val, exp) and red)
        if exp.get('unite') == 'heure':
            time_classes[key][classify_time(val, exp)] += 1
            ops = time_operands(r['question'])
            if ops:
                start, delta = ops
                s = 'jours=%d|duree%s%d' % (exp['jours'], '<=' if delta <= TRAIN_MAX_DELTA else '>',
                                            TRAIN_MAX_DELTA)
                strata[(r['_source'], s)]['n'] += 1
                strata[(r['_source'], s)]['strict'] += strict_correct(val, exp)
    rep = {'groupes': {}, 'erreurs_horaires': {}, 'strates_horaires': {}}
    for (src, g), c in sorted(out.items()):
        rep['groupes'].setdefault(src, {})[g] = dict(c)
    for (src, g), c in sorted(time_classes.items()):
        rep['erreurs_horaires'].setdefault(src, {})[g] = dict(c)
    for (src, s), c in sorted(strata.items()):
        rep['strates_horaires'].setdefault(src, {})[s] = dict(c)
    return rep


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    print(json.dumps(analyse(load_rows(argv[1:])), ensure_ascii=False, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
