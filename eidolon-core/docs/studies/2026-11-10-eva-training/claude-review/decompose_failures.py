#!/usr/bin/env python3
"""Décompose les échecs horaires au format court « a + b = c minutes … Cela donne HH:MM ».

Pour chaque réponse horaire fausse, vérifie séparément :
  conversion  a == minutes de l'heure de départ
  addition    a + b == c
  modulo      HH:MM rendu == c mod 1440
  jours       jours rendu == c // 1440
Usage : python3 -I decompose_failures.py audit-parent-failures.jsonl
"""
import json
import re
import sys
from collections import Counter


def analyse(rows):
    out = Counter()
    for r in rows:
        if r['expected'].get('unite') != 'heure' or r['evaluation']['content_correct']:
            continue
        q = r['question']
        t = re.search(r'(\d{2}):(\d{2})', q)
        s = int(t[1]) * 60 + int(t[2])
        resp = r['response']
        m = re.match(r'\s*(\d+)\s*\+\s*(\d+)\s*=\s*(\d+)', resp)
        if not m:
            out[(r.get('skill', '?'), 'format_inconnu')] += 1
            continue
        a, b, c = int(m[1]), int(m[2]), int(m[3])
        got = re.search(r'"resultat":\s*"(\d{2}):(\d{2})"', resp)
        gj = re.search(r'"jours":\s*(\d+)', resp)
        key = (r.get('skill', '?'),
               'conversion_ok' if a == s else 'conversion_FAUSSE',
               'addition_ok' if a + b == c else 'addition_FAUSSE',
               'modulo_ok' if got and int(got[1]) * 60 + int(got[2]) == c % 1440 else 'modulo_FAUX',
               'jours_ok' if gj and int(gj[1]) == c // 1440 else 'jours_FAUX')
        out[key] += 1
    return out


if __name__ == '__main__':
    rows = [json.loads(l) for l in open(sys.argv[1], encoding='utf-8') if l.strip()]
    for k, v in sorted(analyse(rows).items()):
        print(v, ' | '.join(k))
