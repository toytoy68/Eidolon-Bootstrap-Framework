#!/usr/bin/env python3
"""Tests des sondes horaires (stdlib). python3 -I test_eva_time_probes.py"""
import importlib.util
import json
import os
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location('etp', os.path.join(HERE, 'eva_time_probes.py'))
etp = importlib.util.module_from_spec(spec); spec.loader.exec_module(etp)
spec2 = importlib.util.spec_from_file_location('ert', os.path.join(HERE, 'eva_review_tools.py'))
ert = importlib.util.module_from_spec(spec2); spec2.loader.exec_module(ert)


class Tests(unittest.TestCase):
    def setUp(self):
        self.rows = etp.build(3030, 24, [])

    def test_counts_and_unique(self):
        kinds = {}
        for r in self.rows:
            kinds[r['kind']] = kinds.get(r['kind'], 0) + 1
        self.assertEqual(kinds, {'S1': 24, 'S2': 24, 'S3': 24, 'S4': 24, 'ZS': 20, 'FS': 20, 'PF': 20})
        self.assertEqual(len({r['id'] for r in self.rows}), len(self.rows))

    def test_same_time_steps_as_c298(self):
        for s, d in [(0, 1), (827, 1739), (1439, 2880), (500, 3819)]:
            self.assertEqual(etp.time_steps(s, d), ert.time_steps(s, d))

    def test_strata_are_correct(self):
        for r in self.rows:
            if r['kind'] == 'ZS':
                day, length = r['stratum'].split('-')
                self.assertEqual(r['expected']['jours'], int(day[4:]))
                q = r['question']
                d = int(q.split('durée ')[1].split(' ')[0])
                self.assertEqual(d > 1500, length == 'long')

    def test_exclude_respected(self):
        keys = set()
        for r in self.rows:
            if r['kind'] == 'ZS':
                q = r['question']; s = q.split('Départ à ')[1][:5]
                keys.add((int(s[:2]) * 60 + int(s[3:]), int(q.split('durée ')[1].split(' ')[0])))
        again = etp.build(3030, 24, list(keys))
        for r in again:
            if r['kind'] == 'ZS':
                q = r['question']; s = q.split('Départ à ')[1][:5]
                self.assertNotIn((int(s[:2]) * 60 + int(s[3:]), int(q.split('durée ')[1].split(' ')[0])), keys)

    def test_oracle_answers_score_full(self):
        resp = []
        for r in self.rows:
            if r['kind'] in ('ZS', 'FS', 'PF'):
                q = r['question'].split('Départ à ')[-1]
                s = int(q[:2]) * 60 + int(q[3:5]); d = int(q.split('durée ')[1].split(' ')[0])
                resp.append(dict(id=r['id'], response=etp.time_steps(s, d)[0]))
            else:
                resp.append(dict(id=r['id'], response=json.dumps(r['expected'], ensure_ascii=False)))
        g = etp.grade(self.rows, resp)
        for k, v in g['sondes'].items():
            self.assertEqual(v['correct'], v['n'], k)
            if k.split('|')[0] in ('ZS', 'FS', 'PF'):
                self.assertEqual(v['format_time_steps'], v['n'])
                self.assertFalse([x for x in v if x.startswith('etape_')], k)
        self.assertEqual(g['sondes_sans_reponse'], 0)

    def test_step_errors_located(self):
        good = etp.time_steps(1148, 2612)[0]
        self.assertEqual(etp.step_errors(good), [])
        bad = good.replace('2320 − 1440 = 880', '2320 − 1440 = 890')
        self.assertIn('soustraction_1440', etp.step_errors(bad))
        bad2 = good.replace('= 1148 minutes', '= 1158 minutes')
        self.assertIn('conversion', etp.step_errors(bad2))

    def test_old_format_not_counted(self):
        old = '1148 + 2612 = 3760 minutes depuis minuit. Cela donne 10:20, après 0 jour(s).'
        self.assertFalse(etp.follows_time_steps(old))

    def test_paired(self):
        zs = next(r for r in self.rows if r['kind'] == 'ZS')
        fs = next(r for r in self.rows if r['kind'] == 'FS' and r['pair'] == zs['pair'])
        resp = [dict(id=zs['id'], response='{}'),
                dict(id=fs['id'], response=json.dumps(fs['expected'], ensure_ascii=False))]
        g = etp.grade(self.rows, resp)
        self.assertEqual(g['appariement_vs_ZS']['FS_gagne'], 1)


if __name__ == '__main__':
    unittest.main(verbosity=1)
