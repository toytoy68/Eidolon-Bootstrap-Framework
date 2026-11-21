# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_media_prompt_probe.py
# Description : Comparabilite des essais de formulation G331
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
from collections import Counter
import importlib
from pathlib import Path
import sys
import unittest

STUDY = Path(__file__).resolve().parents[1]/'docs/studies/2026-11-12-eidolon-media'
sys.path.insert(0, str(STUDY))
probe = importlib.import_module('prompt_probe')

class PromptProbeTests(unittest.TestCase):
    def test_all_conditions_and_seeds_are_retained(self):
        entries = probe.plan()
        self.assertEqual(len(entries),12)
        self.assertEqual(Counter(e['case'] for e in entries),
            Counter({c+'_'+v:2 for c in probe.DETAILED for v in ('original','detailed')}))
        for case in probe.DETAILED:
            rows=[e for e in entries if e['case'].startswith(case+'_')]
            self.assertEqual([e['case'].removeprefix(case+'_') for e in rows],
                ['original','detailed','detailed','original'])

    def test_only_prompt_changes_within_each_matched_pair(self):
        entries=probe.plan()
        for i in range(0,len(entries),2):
            a=dict(entries[i]['request']);b=dict(entries[i+1]['request'])
            self.assertNotEqual(a.pop('prompt'),b.pop('prompt'))
            self.assertEqual(a,b)

    def test_no_lora_or_confirmation_seed(self):
        for entry in probe.plan():
            self.assertNotEqual(entry['request']['seed'],155921)
            classes=[n['class_type'] for n in entry['expected_graph'].values()]
            self.assertFalse(any('lora' in c.lower() for c in classes))

if __name__=='__main__': unittest.main()
