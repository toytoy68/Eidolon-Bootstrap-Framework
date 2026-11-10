#!/usr/bin/env python3
"""Tests des outils de contre-revue Eva (stdlib, sans GPU).

Usage : python3 -I test_eva_review_tools.py [chemin/vers/curriculum.py]
Si le chemin de curriculum.py est fourni, vérifie aussi que `strict_correct`
reproduit exactement `curriculum.grade` sur les variantes testées.
"""
import importlib.util
import json
import os
import random
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location('ert', os.path.join(HERE, 'eva_review_tools.py'))
ert = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ert)
CURRICULUM = None

H = {'resultat': '04:59', 'unite': 'heure', 'jours': 1}
E = {'resultat': '15.32', 'unite': 'euro'}
F = {'resultat': '7/3', 'unite': 'nombre'}

VARIANTS = [
    (H, '{"resultat":"04:59","unite":"heure","jours":1}'),
    (H, '{"resultat":"4:59","unite":"heure","jours":1}'),
    (H, '{"resultat":"04h59","unite":"heure","jours":1}'),
    (H, '{"resultat":"04:59","unite":"heure","jours":"1"}'),
    (H, '{"resultat":"04:59","unite":"heure","jours":true}'),
    (H, '{"resultat":"05:59","unite":"heure","jours":1}'),
    (H, '{"resultat":"04:59","unite":"heure","jours":0}'),
    (E, '{"resultat":"15,32","unite":"euro"}'),
    (E, '{"resultat":15.32,"unite":"euro"}'),
    (E, '{"resultat":"15.32","unite":"euros"}'),
    (F, '{"resultat":"14/6","unite":"nombre"}'),
    (F, '{"resultat":"7/3","unite":"nombre"}'),
    (F, 'rien'),
]


class Tests(unittest.TestCase):
    def test_tolerant_format_only(self):
        v = ert.last_object
        self.assertFalse(ert.strict_correct(v(VARIANTS[1][1]), H))
        self.assertTrue(ert.tolerant_correct(v(VARIANTS[1][1]), H))
        self.assertEqual(ert.classify_time(v(VARIANTS[1][1]), H), 'format_seul')
        self.assertTrue(ert.tolerant_correct(v(VARIANTS[7][1]), E))
        self.assertTrue(ert.tolerant_correct(v(VARIANTS[9][1]), E))

    def test_tolerant_rejects_bool_days(self):
        self.assertTrue(ert.strict_correct(ert.last_object(VARIANTS[4][1]), H))
        self.assertFalse(ert.tolerant_correct(ert.last_object(VARIANTS[4][1]), H))

    def test_time_classes(self):
        v = ert.last_object
        self.assertEqual(ert.classify_time(v(VARIANTS[5][1]), H), 'heure_decalee_+1h')
        self.assertEqual(ert.classify_time(v(VARIANTS[6][1]), H), 'jours_faux_heure_juste')
        self.assertEqual(ert.classify_time(None, H), 'json_absent')

    def test_reduced(self):
        v = ert.last_object
        self.assertTrue(ert.strict_correct(v(VARIANTS[10][1]), F))
        self.assertFalse(ert.reduced_ok(v(VARIANTS[10][1]), F))
        self.assertTrue(ert.reduced_ok(v(VARIANTS[11][1]), F))
        self.assertIsNone(ert.reduced_ok(v(VARIANTS[11][1]), E))

    def test_time_operands_all_templates(self):
        qs = ['Départ à 13:47, durée 300 minutes.',
              'Un délai de 900 minutes commence à 13:47. Quand se termine-t-il ?',
              'À 13:47, ajoute 300 minutes.',
              'Départ à 13:47. Après exactement 3000 minutes, donne l’heure.',
              'Une opération débute à 13:47 et dure 3000 minutes.']
        got = [ert.time_operands(q) for q in qs]
        self.assertEqual(got, [(827, 300), (827, 900), (827, 300), (827, 3000), (827, 3000)])

    def test_time_steps_oracle(self):
        rng = random.Random(298)
        cases = [(a, b) for a in (0, 1, 59, 60, 719, 1380, 1439) for b in (1, 59, 60, 61, 1439, 1440, 1441, 2879, 2880, 4319)]
        cases += [(rng.randrange(1440), rng.randint(1, 4320)) for _ in range(5000)]
        for a, b in cases:
            text, exp = ert.time_steps(a, b)
            d, r = divmod(a + b, 1440)
            self.assertEqual(exp, {'resultat': '%02d:%02d' % divmod(r, 60), 'unite': 'heure', 'jours': d})
            self.assertTrue(ert.strict_correct(ert.last_object(text), exp))
            self.assertLess(len(text), 600)

    def test_analyse_end_to_end(self):
        rows = [dict(skill='midnight', family=5, question='Départ à 23:00. Après exactement 2000 minutes, donne l’heure. Termine…',
                     expected={'resultat': '08:20', 'unite': 'heure', 'jours': 2},
                     response='… {"resultat":"8:20","unite":"heure","jours":2}'),
                dict(skill='fraction', family=3, question='Simplifie 14/6. Termine…', expected=F,
                     response='{"resultat":"14/6","unite":"nombre"}')]
        with tempfile.NamedTemporaryFile('w', suffix='.jsonl', delete=False, encoding='utf-8') as f:
            f.write(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows))
        try:
            rep = ert.analyse(ert.load_rows([f.name]))
        finally:
            os.unlink(f.name)
        g = rep['groupes'][f.name]
        self.assertEqual(g['midnight']['strict'], 0)
        self.assertEqual(g['midnight']['tolerant'], 1)
        self.assertEqual(g['fraction']['strict'], 1)
        self.assertEqual(g['fraction']['strict_et_irreductible'], 0)
        self.assertEqual(rep['strates_horaires'][f.name], {'jours=2|duree>1500': {'n': 1, 'strict': 0}})

    def test_strict_matches_original_grade(self):
        if CURRICULUM is None:
            self.skipTest('curriculum.py non fourni')
        for exp, text in VARIANTS:
            self.assertEqual(ert.strict_correct(ert.last_object(text), exp),
                             CURRICULUM.grade(text, exp)['content_correct'], text)


if __name__ == '__main__':
    if len(sys.argv) > 1:
        s = importlib.util.spec_from_file_location('curriculum', sys.argv.pop(1))
        CURRICULUM = importlib.util.module_from_spec(s)
        s.loader.exec_module(CURRICULUM)
    unittest.main(verbosity=1)
