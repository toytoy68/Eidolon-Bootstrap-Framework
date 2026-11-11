#!/usr/bin/env python3
"""Tests du validateur et des sondes frontière (stdlib).

Usage : python3 -I test_eva_boundary_probes.py [dossier probes-C303-G304]
Avec le dossier G304, vérifie aussi que le validateur retrouve sur les 312
réponses publiées au moins toutes les comparaisons fausses de l'audit GPT.
"""
import importlib.util
import json
import os
import random
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location('ebp', os.path.join(HERE, 'eva_boundary_probes.py'))
ebp = importlib.util.module_from_spec(spec); spec.loader.exec_module(ebp)
spec2 = importlib.util.spec_from_file_location('ert', os.path.join(HERE, 'eva_review_tools.py'))
ert = importlib.util.module_from_spec(spec2); spec2.loader.exec_module(ert)
G304 = None

G304_FAIL = ('Départ 23:41 = 23 × 60 + 41 = 1380 + 41 = 1421 minutes. 1421 + 1485 = 2906 minutes. '
             '2906 ≥ 1440 : 2906 − 1440 = 1466, jour 1. 1466 < 1440 : 1 jour(s) franchi(s). '
             '24 × 60 = 1440 ; 1466 − 1440 = 26, et 26 < 60. Arrivée 00:26, décalage 1 jour(s).\n'
             '{"resultat": "00:26", "unite": "heure", "jours": 1}')


def cases():
    rng = random.Random(307)
    out = [(a, b) for a in (0, 1, 59, 60, 1380, 1439) for b in (1, 59, 60, 1439, 1440, 1441, 2879, 2880, 4319)]
    out += [(rng.randrange(1440), rng.randint(1, 4319)) for _ in range(4000)]
    return out


class Tests(unittest.TestCase):
    def test_format_a_identical_to_c298(self):
        for s, d in cases()[:300]:
            self.assertEqual(ebp.time_steps_a(s, d), ert.time_steps(s, d))

    def test_oracles_have_no_false_claim(self):
        for s, d in cases():
            for fn in (ebp.time_steps_a, ebp.time_steps_b):
                text, exp = fn(s, d)
                self.assertEqual(ebp.invalid_claims(text), [], (fn.__name__, s, d, text))
                self.assertTrue(ebp._correct(ebp._last_object(text), exp))
                self.assertEqual(exp, ert.time_steps(s, d)[1])

    def test_g304_false_comparison_caught(self):
        bad = ebp.invalid_claims(G304_FAIL)
        self.assertIn(('comparaison', '1466 < 1440'), bad)

    def test_arithmetic_and_chain_errors(self):
        t = ebp.time_steps_b(1421, 1485)[0]
        self.assertEqual(ebp.invalid_claims(t), [])
        self.assertIn('calcul', {c for c, _ in ebp.invalid_claims(t.replace('= 1466,', '= 1476,'))})
        self.assertIn('calcul', {c for c, _ in ebp.invalid_claims(t.replace('1380 + 41 = 1421', '1380 + 41 = 1431'))})
        self.assertIn('calcul', {c for c, _ in ebp.invalid_claims(t.replace('26 − 1440 = −1414', '26 − 1440 = −1404'))})
        self.assertIn('suite_jours', {c for c, _ in ebp.invalid_claims(t.replace('jour 2', 'jour 3'))})
        self.assertIn('json_incoherent', {c for c, _ in ebp.invalid_claims(t.replace('"jours": 2', '"jours": 1'))})

    def test_eval_signs(self):
        self.assertEqual(ebp._eval('26 − 1440'), -1414)
        self.assertEqual(ebp._eval('−1414'), -1414)
        self.assertEqual(ebp._eval('23 × 60 + 41'), 1421)
        self.assertEqual(ebp._eval('1380 + 41'), 1421)

    def test_format_detection(self):
        self.assertEqual(ebp.format_of(ebp.time_steps_a(5, 3000)[0]), 'A')
        self.assertEqual(ebp.format_of(ebp.time_steps_b(5, 3000)[0]), 'B')
        self.assertEqual(ebp.format_of('1148 + 2612 = 3760 minutes depuis minuit.'), 'court')

    def test_build_boundaries(self):
        rows = ebp.build(3070, 8, [], exact=2)
        timed = [r for r in rows if r['kind'] != 'SG']
        sg = [r for r in rows if r['kind'] == 'SG']
        self.assertEqual(len(timed), (4 * 8 + 6 * 2) * 3)
        self.assertEqual(len(sg), 8 + 2 * 8)
        self.assertEqual(len({r['id'] for r in rows}), len(rows))
        totals = set()
        for r in timed:
            s, d = r['time_key']
            t = s + d
            totals.add(t)
            f, side = r['stratum'].split('-', 1)
            if side.startswith('exact'):
                self.assertEqual(t, int(f) + int(side[5:]))
            elif side == 'dessus':
                self.assertTrue(int(f) <= t <= int(f) + 59)
            else:
                self.assertTrue(int(f) - 60 <= t < int(f))
            self.assertEqual(r['expected'], ert.time_steps(s, d)[1])
        for t in (1439, 1440, 1441, 2879, 2880, 2881):
            self.assertIn(t, totals)
        self.assertEqual({r['stratum'] for r in sg}, {'negatif', 'nul', 'positif'})
        self.assertIn(-1, {r['expected']['resultat'] for r in sg})
        self.assertIn(0, {r['expected']['resultat'] for r in sg})
        shots = timed[1]['question'].split('Résous maintenant')[0]
        for r in timed:
            self.assertNotIn(ebp.question(*r['time_key']), shots)

    def test_grade_oracle(self):
        rows = ebp.build(3070, 4, [])
        resp = []
        for r in rows:
            if r['kind'] == 'SG':
                resp.append(dict(id=r['id'], response=json.dumps(r['expected'], ensure_ascii=False)))
            else:
                fn = ebp.time_steps_b if r['kind'] == 'FB' else ebp.time_steps_a
                resp.append(dict(id=r['id'], response=fn(*r['time_key'])[0]))
        g = ebp.grade(rows, resp)
        for k, v in g['sondes'].items():
            self.assertEqual(v['correct'], v['n'], k)
            if not k.startswith('SG'):
                self.assertEqual(v['sans_affirmation_fausse'], v['n'], k)
        self.assertEqual(g['sans_reponse'], 0)

    def test_g308_mutations_caught(self):
        t = ebp.time_steps_b(1421, 1485)[0]
        cats = lambda x: {c for c, _ in ebp.invalid_claims(x)}
        self.assertIn('signe', cats(t.replace('1466, positif ou nul', '1466, négatif')))
        self.assertIn('signe', cats(t.replace('−1414, négatif', '−1414, positif ou nul')))
        m3 = t.replace('Arrivée 00:26', 'Arrivée 00:27').replace('"resultat": "00:26"', '"resultat": "00:27"')
        self.assertIn('heure_vs_reste', cats(m3))
        a = ebp.time_steps_a(1421, 1485)[0]
        m4 = a.replace('Arrivée 00:26', 'Arrivée 00:27').replace('"resultat": "00:26"', '"resultat": "00:27"')
        self.assertIn('heure_vs_reste', cats(m4))

    def test_format_c(self):
        for s0, d0 in cases():
            text, exp = ebp.time_steps_c(s0, d0)
            self.assertEqual(exp, ert.time_steps(s0, d0)[1])
            self.assertEqual(ebp.invalid_claims(text), [], text)
            self.assertTrue(ebp._correct(ebp._last_object(text), exp))
            self.assertEqual(ebp.format_of(text), 'C')
            self.assertTrue(text.startswith(f'{s0} + {d0} = {s0 + d0} minutes depuis minuit.'))
        t = ebp.time_steps_c(1355, 297)[0]
        self.assertIn('1652 ≥ 1440 : 1652 − 1440 = 212, jour 1. 212 < 1440. Cela donne 03:32, avec 1 jour(s).', t)
        cats = lambda x: {c for c, _ in ebp.invalid_claims(x)}
        self.assertIn('json_incoherent', cats(t.replace('"jours": 1', '"jours": 0')))
        self.assertIn('heure_vs_reste', cats(t.replace('"resultat": "03:32"', '"resultat": "03:42"')))
        self.assertIn('compte_jours', cats(t.replace('avec 1 jour(s)', 'avec 0 jour(s)')))

    def test_build_with_fc(self):
        rows = ebp.build(3070, 8, [], formats=('FA', 'FB', 'FC'))
        self.assertEqual(sum(r['kind'] == 'FC' for r in rows), 4 * 8 + 6 * 2)
        self.assertEqual(rows, rows)
        base = ebp.build(3070, 8, [])
        self.assertEqual([r for r in rows if r['kind'] != 'FC'], base)

    def test_against_g304(self):
        if G304 is None:
            self.skipTest('dossier G304 non fourni')
        audit = json.load(open(os.path.join(G304, 'invariant-audit.json'), encoding='utf-8'))
        for name in ('parent-cycle5', 'E2-step102'):
            rows = [json.loads(l) for l in open(os.path.join(G304, 'run', f'responses-{name}.jsonl'), encoding='utf-8')]
            mine = {r['id']: ebp.invalid_claims(r['response']) for r in rows}
            for item in audit[name]['false_comparison_claims']:
                got = {x for c, x in mine[item['id']] if c == 'comparaison'}
                for claim in item['claims']:
                    self.assertIn(claim, got, (name, item['id']))


if __name__ == '__main__':
    if len(sys.argv) > 1:
        G304 = sys.argv.pop(1)
    unittest.main(verbosity=1)
