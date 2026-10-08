# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_model_probe_inspect.py
# Description : Consultation hors ligne des documents de recette synthétiques
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from eidolon_core.contracts import digest
from eidolon_core.model_probe import INCOMPLETE, plan_probe
from eidolon_core.model_probe_inspect import ProbeInspectionError, inspect_probe


class ProbeInspectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'probe'
        self.root.mkdir()
        config = self.root.parent / 'model.json'
        config.write_text(json.dumps({'version': 1, 'provider': 'ollama', 'model': 'synthetic',
                                     'endpoint': 'http://127.0.0.1:11434', 'options': {'num_predict': 512}}))
        config.chmod(0o600)
        self.plan = plan_probe(config)
        self.plan['fixed_at'] = '2026-10-08T07:00:00+00:00'
        self.results = []
        for i, case in enumerate(self.plan['cases'], 1):
            empty = case['id'] == 'empty'
            identity = case['id'] + '-1'
            self.results.append({'id': identity, 'state_directory': 'state-' + identity,
                                 'mission_id': f'm-{i:032x}', 'outcome': 'PASS', 'failed_checks': [],
                                 'mission_status': 'BLOCKED' if empty else 'SUCCEEDED',
                                 'mission_error_code': 'MEMORY_EMPTY' if empty else None,
                                 'planner_attempts': 0 if empty else 1,
                                 'verified_tool_calls': len(case['context']['items']), 'elapsed_ms': 12.3})
        self.report = {k: v for k, v in self.plan.items() if k not in {'status', 'cases', 'fixed_at'}}
        self.report.update(status='COMPLETE', verdict='PASSED_CASES', results=self.results,
                           started_at=self.plan['fixed_at'], finished_at='2026-10-08T07:01:00+00:00',
                           recorded_cases=4, started_cases=4, not_started_cases=0,
                           elapsed_ms=1000, error_code=None)
        self.write_all()

    def write(self, name, value):
        (self.root / name).write_text(json.dumps(value))

    def write_all(self):
        self.write('plan.json', self.plan)
        for result in self.results:
            self.write('case-' + result['id'] + '.json', result)
        self.write('report.json', self.report)

    def inspect(self):
        with patch('socket.socket', side_effect=AssertionError('network')), \
             patch('eidolon_core.store.Store', side_effect=AssertionError('store')), \
             patch('eidolon_core.runtime.Runtime', side_effect=AssertionError('runtime')):
            return inspect_probe(self.root)

    def test_consistent_documents_are_read_only_not_hardware_or_sqlite_validation(self):
        before = {p.name: p.read_bytes() for p in self.root.iterdir()}
        result = self.inspect()
        self.assertEqual(result['status'], 'CONSISTENT')
        self.assertEqual(result['reported_verdict'], 'PASSED_CASES')
        self.assertEqual(result['recorded_cases'], 4)
        self.assertFalse(result['server_contacted'])
        self.assertFalse(result['mission_evidence_rechecked'])
        self.assertFalse(result['hardware_qualified'])
        self.assertFalse(result['authorizes_execution'])
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.root.iterdir()})

    def test_incomplete_marker_overrides_even_a_consistent_success_report(self):
        self.write(INCOMPLETE, {'status': 'INCOMPLETE', 'resume_allowed': False})
        result = self.inspect()
        self.assertEqual(result['status'], 'INCOMPLETE')
        self.assertEqual(result['reported_verdict'], 'PASSED_CASES')
        self.assertTrue(result['unrecorded_cases_may_have_started'])

    def test_missing_report_preserves_recorded_results_and_unknown_started_count(self):
        (self.root / 'report.json').unlink()
        for result in self.results[1:]:
            (self.root / ('case-' + result['id'] + '.json')).unlink()
        self.write(INCOMPLETE, {'status': 'INCOMPLETE', 'resume_allowed': False})
        result = self.inspect()
        self.assertEqual(result['status'], 'INCOMPLETE')
        self.assertEqual(result['recorded_cases'], 1)
        self.assertIsNone(result['started_cases'])
        self.assertTrue(result['unrecorded_cases_may_have_started'])
        self.assertIsNone(result['reported_verdict'])

    def test_missing_plan_returns_incomplete_only_when_marker_identifies_experiment(self):
        (self.root / 'plan.json').unlink()
        with self.assertRaisesRegex(ProbeInspectionError, '^NOT_A_PROBE_DIRECTORY$'):
            self.inspect()
        self.write(INCOMPLETE, {'status': 'INCOMPLETE', 'resume_allowed': False})
        result = self.inspect()
        self.assertEqual(result['code'], 'PROBE_PLAN_MISSING')
        self.assertIsNone(result['expected_cases'])
        self.assertIsNone(result['started_cases'])

    def test_case_gap_duplicate_mission_and_report_disagreement_are_refused(self):
        (self.root / 'case-single-1.json').unlink()
        with self.assertRaises(ProbeInspectionError):
            self.inspect()
        self.write_all()
        changed = deepcopy(self.results[1]); changed['mission_id'] = self.results[0]['mission_id']
        self.write('case-unicode-multiple-1.json', changed)
        with self.assertRaises(ProbeInspectionError):
            self.inspect()
        self.write_all()
        self.report['results'] = self.results[:-1]
        self.write('report.json', self.report)
        with self.assertRaises(ProbeInspectionError):
            self.inspect()

    def test_modified_corpus_recomputed_hash_does_not_replace_the_fixed_suite(self):
        self.plan['cases'][0]['context']['items'][0]['needs_review'] = 1
        self.plan['fingerprints']['corpus_sha256'] = digest(self.plan['cases'])
        self.write('plan.json', self.plan)
        with self.assertRaises(ProbeInspectionError):
            self.inspect()

    def test_json_boolean_and_integer_are_not_interchangeable_between_documents(self):
        original = deepcopy(self.report)
        self.report['results'] = deepcopy(self.results)
        self.report['results'][0]['planner_attempts'] = True
        self.write('report.json', self.report)
        with self.assertRaises(ProbeInspectionError):
            self.inspect()
        self.report = deepcopy(original)
        self.report['repetitions'] = True
        self.write('report.json', self.report)
        with self.assertRaises(ProbeInspectionError):
            self.inspect()
        self.report = original
        self.write_all()
        self.write(INCOMPLETE, {'status': 'INCOMPLETE', 'resume_allowed': 0})
        with self.assertRaises(ProbeInspectionError):
            self.inspect()

    def test_malformed_unknown_and_impossible_case_claims_are_refused(self):
        for change in ({'outcome': 'QUALIFIED'}, {'outcome': {}}, {'planner_attempts': True},
                       {'verified_tool_calls': 0}, {'mission_status': 'RUNNING'},
                       {'elapsed_ms': 10**400}, {'state_directory': '../foreign'},
                       {'mission_id': 'private-canary'}, {'failed_checks': ['UNKNOWN_PRIVATE']},
                       {'authorizes_execution': True}):
            with self.subTest(change=list(change)):
                self.write('case-single-1.json', {**self.results[0], **change})
                with self.assertRaisesRegex(ProbeInspectionError, '^PROBE_DOCUMENT_INCONSISTENT$'):
                    self.inspect()
        self.write_all()
        self.report['verdict'] = 'QUALIFIED'
        self.write('report.json', self.report)
        with self.assertRaises(ProbeInspectionError):
            self.inspect()

    def test_fifo_symlink_directory_and_oversized_documents_refused_without_following(self):
        target = self.root / 'plan.json'
        for kind in ('fifo', 'link', 'directory', 'big'):
            target.unlink()
            if kind == 'fifo':
                os.mkfifo(target)
            elif kind == 'link':
                target.symlink_to(self.root.parent / 'does-not-exist')
            elif kind == 'directory':
                target.mkdir()
            else:
                target.write_bytes(b' ' * 1_000_001)
            with self.subTest(kind=kind), self.assertRaisesRegex(ProbeInspectionError, '^PROBE_DOCUMENT_UNREADABLE$'):
                self.inspect()
            if kind == 'directory':
                target.rmdir()
            else:
                target.unlink()
            self.write('plan.json', self.plan)

    def test_stopped_error_is_consistent_but_never_promoted_to_pass(self):
        result = self.results[0]
        result.update(outcome='ERROR', mission_status='BLOCKED', mission_error_code='MODEL_UNAVAILABLE',
                      verified_tool_calls=0, failed_checks=['MISSION_ACHIEVED', 'SOURCE_COUNT', 'EXACT_SOURCE_RESULTS'])
        for omitted in self.results[1:]:
            (self.root / ('case-' + omitted['id'] + '.json')).unlink()
        self.write('case-single-1.json', result)
        self.report.update(status='STOPPED', verdict='FAILED_CASES', results=[result], recorded_cases=1,
                           started_cases=1, not_started_cases=3, error_code='PROBE_CASE_ERROR')
        self.write('report.json', self.report)
        actual = self.inspect()
        self.assertEqual(actual['status'], 'CONSISTENT')
        self.assertEqual(actual['reported_verdict'], 'FAILED_CASES')
        self.assertEqual(actual['run_status'], 'STOPPED')

    def test_directory_symlink_and_non_probe_folder_are_refused(self):
        link = self.root.parent / 'link'; link.symlink_to(self.root)
        with self.assertRaisesRegex(ProbeInspectionError, '^PROBE_DIRECTORY_REQUIRED$'):
            inspect_probe(link)
        unrelated = self.root.parent / 'unrelated'; unrelated.mkdir()
        with self.assertRaisesRegex(ProbeInspectionError, '^NOT_A_PROBE_DIRECTORY$'):
            inspect_probe(unrelated)

    def test_cli_is_offline_has_explicit_inspection_status_and_preserves_corrupt_details(self):
        args = [sys.executable, '-m', 'eidolon_core', '--state', str(self.root.parent / 'unused'),
                'model-probe-inspect', '--directory', str(self.root)]
        inspected = subprocess.run(args, capture_output=True, text=True, timeout=5)
        self.assertEqual(inspected.returncode, 0, inspected.stderr)
        self.assertEqual(json.loads(inspected.stdout)['status'], 'CONSISTENT')
        self.assertFalse((self.root.parent / 'unused').exists())
        self.write(INCOMPLETE, {'status': 'INCOMPLETE', 'resume_allowed': False})
        partial = subprocess.run(args, capture_output=True, text=True, timeout=5)
        self.assertEqual(partial.returncode, 2)
        (self.root / 'plan.json').write_text('{"private-canary": invalid}')
        invalid = subprocess.run(args, capture_output=True, text=True, timeout=5)
        self.assertEqual(invalid.returncode, 2)
        self.assertEqual(invalid.stdout, '')
        self.assertNotIn('private-canary', invalid.stderr)
        self.assertNotIn(str(self.root), invalid.stderr)


if __name__ == '__main__':
    unittest.main()
