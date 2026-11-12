# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_media_quality_probe.py
# Description : Échecs et traçabilité du protocole qualité hors GPU
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

spec = importlib.util.spec_from_file_location('quality_probe', Path(__file__).parents[1]/'docs/studies/2026-11-12-eidolon-media/quality_probe.py')
probe = importlib.util.module_from_spec(spec); spec.loader.exec_module(probe)

class QualityProtocolTests(unittest.TestCase):
    def test_pairs_keep_everything_except_size_conditioning_fixed(self):
        entries = probe.plan()
        self.assertEqual(len(entries), 12)
        for a, b in zip(entries[::2], entries[1::2]):
            left = dict(a['request']); right = dict(b['request'])
            self.assertNotEqual(left.pop('height'), right.pop('height'))
            self.assertEqual(left, right)

    def test_graph_verification_detects_sampler_and_prompt_changes(self):
        expected = probe.plan()[0]['expected_graph']
        actual = json.loads(json.dumps(expected))
        actual['7']['inputs']['filename_prefix'] = 'uniquejobid'
        self.assertTrue(probe.graph_matches(actual, expected))
        actual['5']['inputs']['steps'] = 1
        self.assertFalse(probe.graph_matches(actual, expected))

    def test_unknown_job_blocks_admission_before_engine_action(self):
        client = Mock(); client._call.return_value = [{'state': 'REVIEW_REQUIRED'}]
        opener = Mock()
        with self.assertRaisesRegex(RuntimeError, 'NONTERMINAL_JOB'):
            probe.assert_idle(client, opener)
        opener.open.assert_not_called()

    def test_submission_failure_retains_intent_and_never_retries(self):
        client = Mock(); client.submit.side_effect = TimeoutError('unknown outcome')
        with tempfile.TemporaryDirectory() as directory, patch.object(probe, 'sample_once', return_value={}):
            folder = Path(directory)/'trial'
            with self.assertRaises(TimeoutError):
                probe.run_one(client, probe.plan()[0], folder, 'stablekey')
            self.assertEqual(client.submit.call_count, 1)
            self.assertEqual(json.loads((folder/'intent.json').read_text())['idempotency_key'], 'stablekey')
            self.assertFalse(json.loads((folder/'interruption.json').read_text())['automatic_replay'])
            with self.assertRaises(FileExistsError):
                probe.run_one(client, probe.plan()[0], folder, 'newkey')
            self.assertEqual(client.submit.call_count, 1)

    def test_timeout_cancels_only_known_job_and_stops(self):
        client = Mock(); client.submit.return_value = {'id':'ownedjob','state':'RUNNING'}
        with tempfile.TemporaryDirectory() as directory, patch.object(probe, 'sample_once', return_value={}):
            with self.assertRaises(TimeoutError):
                probe.run_one(client, probe.plan()[0], Path(directory)/'trial', 'key', timeout=-1)
        client.cancel.assert_called_once_with('ownedjob')
        client.result.assert_not_called()

    def test_missing_sensor_is_not_reported_as_zero(self):
        summary = probe.summarize([{'error':'sensor failure'}])
        self.assertEqual(summary['sample_errors'],1)
        self.assertIsNone(summary['gpus']['1']['temperature.memory'])
        self.assertIsNone(summary['cpu_tdie_c'])

    def test_valid_png_does_not_imply_visual_acceptance(self):
        entry = probe.plan()[0]
        client = Mock(); client.submit.return_value = {'id':'ownedjob','state':'SUCCEEDED'}
        client.metadata.return_value = {'graph':entry['expected_graph']}
        body = io.BytesIO()
        probe.Image.new('RGB', (1024,576), 'black').save(body,format='PNG')
        client.result.return_value = (body.getvalue(), 'image/png')
        with tempfile.TemporaryDirectory() as directory, patch.object(probe, 'sample_once', return_value={}):
            result = probe.run_one(client, entry, Path(directory)/'trial', 'key')
        self.assertEqual(result['technical'], 'PASS')
        self.assertEqual(result['visual'], 'NOT_REVIEWED')

    def test_wrong_executed_workflow_stops_before_accepting_result(self):
        entry = probe.plan()[0]
        client = Mock(); client.submit.return_value = {'id':'ownedjob','state':'SUCCEEDED'}
        altered = json.loads(json.dumps(entry['expected_graph']))
        altered['2']['inputs']['text_g'] = 'different prompt'
        client.metadata.return_value = {'graph':altered}
        with tempfile.TemporaryDirectory() as directory, patch.object(probe, 'sample_once', return_value={}):
            with self.assertRaisesRegex(RuntimeError, 'EXECUTED_GRAPH_MISMATCH'):
                probe.run_one(client, entry, Path(directory)/'trial', 'key')
        client.result.assert_not_called()

if __name__ == '__main__': unittest.main()
