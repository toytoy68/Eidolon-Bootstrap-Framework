# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_media_checkpoint_probe.py
# Description : Contrôle de comparabilité et conflit GPU pour la campagne G333
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
import importlib.util
from pathlib import Path
import unittest

FILE = Path(__file__).resolve().parents[1]/'docs/studies/2026-11-12-eidolon-media/checkpoint_probe.py'
spec = importlib.util.spec_from_file_location('checkpoint_probe', FILE)
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


class CheckpointTests(unittest.TestCase):
    def test_matched_common_conditions(self):
        base = probe.plan('sdxl')
        for model in ('realvis', 'juggernaut'):
            self.assertEqual(base, probe.plan(model)[:7])
        self.assertEqual(len({(r['case'], r['seed']) for r in base[:6]}), 6)

    def test_author_condition_changes_steps_only(self):
        rows = probe.plan('realvis')
        self.assertEqual(len(rows), 13)
        for a, b in zip(rows[:6], rows[7:]):
            self.assertEqual({**a, 'condition': 'author50', 'steps': 50}, b)
        self.assertEqual({**rows[0], 'condition': 'repeat30'}, rows[6])

    def test_foreign_gpu_client_stops_campaign(self):
        probe.check_processes('', 123)
        probe.check_processes('123\n', 123)
        with self.assertRaisesRegex(RuntimeError, 'OTHER_GPU_CLIENT'):
            probe.check_processes('123\n456\n', 123)
