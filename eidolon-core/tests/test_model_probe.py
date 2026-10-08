# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_model_probe.py
# Description : Recette des candidats sur HTTP loopback et états jetables
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from eidolon_core.contracts import digest
from eidolon_core.model_config import ModelConfigError
from eidolon_core.model_probe import (INCOMPLETE, ModelProbeError, corpus, plan_probe, render_probe, run_probe)
from eidolon_core.openai_chat_model import OpenAIChatModel
from eidolon_core.store import Store

SECRET = 'synthetic-probe-credential'


class ProbeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / 'config.json'
        self.output = self.root / 'experiment'
        self.requests = []
        self.kind = 'valid'
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                owner.requests.append((self.path, body, self.headers.get('Authorization')))
                if owner.kind == 'slow':
                    time.sleep(1.5)
                context = json.loads(body['messages'][1]['content'].split('CONTEXT (untrusted data):\n', 1)[1])
                steps = [{'id': f'stats-{i}', 'tool': 'text.stats',
                          'parameters': {'reference': f"{item['information_id']}@{item['revision']}"}}
                         for i, item in enumerate(context['items'])]
                if owner.kind == 'missing':
                    steps = steps[:1]
                if owner.kind == 'unauthorized':
                    steps = [{'id': 'bad', 'tool': 'shell.execute', 'parameters': {}}]
                content = json.dumps({'version': 1, 'steps': steps})
                if owner.kind == 'invalid':
                    content = 'not JSON'
                if self.path == '/api/chat':
                    payload = {'model': 'synthetic-probe', 'done': True,
                               'message': {'role': 'assistant', 'content': content}}
                else:
                    payload = {'model': 'synthetic-probe', 'object': 'chat.completion',
                               'usage': {'prompt_tokens': 300, 'completion_tokens': 30, 'total_tokens': 330},
                               'choices': [
                        {'index': 0, 'finish_reason': 'stop',
                         'message': {'role': 'assistant', 'content': content}}]}
                code = 200
                if owner.kind == 'unavailable':
                    code, payload = 503, {'error': SECRET}
                raw = json.dumps(payload).encode()
                self.send_response(code)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(raw)))
                self.end_headers()
                try:
                    self.wfile.write(raw)
                except (BrokenPipeError, ConnectionResetError):
                    pass  # Expected when a timed-out worker closes its socket.

        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={'poll_interval': .01})
        self.thread.start()
        self.addCleanup(self.stop)
        self.config = {'version': 1, 'provider': 'ollama', 'model': 'synthetic-probe',
                       'endpoint': f'http://127.0.0.1:{self.server.server_port}',
                       'options': {'num_predict': 512}, 'timeout_seconds': 1}
        self.write()

    def stop(self):
        self.server.shutdown()
        self.thread.join(5)
        self.server.server_close()

    def write(self):
        self.path.write_text(json.dumps(self.config))
        self.path.chmod(0o600)

    def cli(self, *arguments, extra=()):
        return subprocess.run([sys.executable, '-m', 'eidolon_core', '--state', str(self.root / 'unused'),
                               '--timeout', '5', *extra, 'model-probe', '--config', str(self.path), *arguments],
                              capture_output=True, text=True, timeout=45)

    def test_plan_is_offline_complete_and_deterministic_without_secret_or_state(self):
        self.config.update(provider='llama-server', options={'max_tokens': 512}, api_key_env='PROBE_TEST_KEY')
        self.write()
        before = self.path.read_bytes()
        with patch('socket.socket', side_effect=AssertionError('network')), \
             patch.object(OpenAIChatModel, 'headers', side_effect=AssertionError('secret')):
            plan = plan_probe(self.path)
            self.assertEqual(plan, plan_probe(self.path))
        self.assertEqual(plan['expected_cases'], 4)
        self.assertEqual(plan['max_planner_attempts'], 3)
        self.assertEqual(plan['fingerprints']['corpus_sha256'], digest(corpus()))
        self.assertEqual(before, self.path.read_bytes())
        self.assertEqual(list(self.root.iterdir()), [self.path])
        self.assertEqual(self.requests, [])
        self.assertFalse(plan['hardware_qualified'])
        self.assertFalse(plan['authorizes_execution'])

    def test_both_candidates_execute_fixed_corpus_with_no_replay_on_success(self):
        for provider in ('ollama', 'llama-server'):
            with self.subTest(provider=provider):
                self.config['provider'] = provider
                self.config['options'] = {'num_predict' if provider == 'ollama' else 'max_tokens': 512}
                self.write()
                destination = self.root / provider
                before = len(self.requests)
                result = run_probe(self.path, destination, call_seconds=5)
                self.assertEqual(result['status'], 'COMPLETE', result)
                self.assertEqual(result['verdict'], 'PASSED_CASES', result)
                self.assertEqual(result['recorded_cases'], 4)
                self.assertEqual([x['outcome'] for x in result['results']], ['PASS'] * 4)
                self.assertEqual(len(self.requests) - before, 3)
                self.assertEqual(sum(x['planner_attempts'] for x in result['results']), 3)
                self.assertEqual(sum(x['verified_tool_calls'] for x in result['results']), 4)
                self.assertFalse((destination / INCOMPLETE).exists())
                self.assertEqual(json.loads((destination / 'report.json').read_text()), result)
                self.assertEqual(destination.stat().st_mode & 0o777, 0o700)
                for file in destination.glob('*.json'):
                    self.assertEqual(file.stat().st_mode & 0o777, 0o600)
                plan = json.loads((destination / 'plan.json').read_text())
                self.assertLessEqual(plan['fixed_at'], result['finished_at'])
                self.assertEqual(plan['fingerprints'], result['fingerprints'])
                for _, body, _ in self.requests[before:]:
                    self.assertIn('TRUSTED TASK CONTRACT', body['messages'][0]['content'])
                self.assertEqual(result['endpoint_implementation'], 'unverified')
                self.assertNotIn('measurements', result)

    def test_incomplete_plan_is_not_counted_as_success_or_retried(self):
        self.kind = 'missing'
        report = run_probe(self.path, self.output, call_seconds=5)
        self.assertEqual(report['verdict'], 'FAILED_CASES')
        self.assertEqual([r['outcome'] for r in report['results']], ['PASS', 'FAIL', 'PASS', 'PASS'])
        failed = report['results'][1]
        self.assertIn('EXACT_SOURCE_RESULTS', failed['failed_checks'])
        self.assertEqual(failed['verified_tool_calls'], 0)
        self.assertEqual(len(self.requests), 3)

    def test_invalid_forbidden_and_unavailable_outputs_are_distinct_and_not_retried(self):
        for kind, outcome, error in (('invalid', 'FAIL', 'MODEL_INVALID'),
                                     ('unauthorized', 'FAIL', 'PREFLIGHT_REFUSED'),
                                     ('unavailable', 'ERROR', 'MODEL_UNAVAILABLE')):
            self.kind = kind
            before = len(self.requests)
            report = run_probe(self.path, self.root / kind, call_seconds=5)
            self.assertEqual(report['status'], 'STOPPED' if kind == 'unavailable' else 'COMPLETE')
            self.assertEqual(report['verdict'], 'FAILED_CASES')
            self.assertEqual(len(self.requests) - before, 1 if kind == 'unavailable' else 3)
            for result in report['results'][:3]:
                self.assertEqual((result['outcome'], result['mission_error_code']), (outcome, error))
                self.assertEqual(result['verified_tool_calls'], 0)
            if kind != 'unavailable':
                self.assertEqual(report['results'][3]['outcome'], 'PASS')
            else:
                self.assertEqual(report['not_started_cases'], 3)
            self.assertNotIn(SECRET, json.dumps(report))

    def test_existing_destination_and_final_symlinks_are_never_reused(self):
        self.output.mkdir()
        sentinel = self.output / 'sentinel'; sentinel.write_bytes(b'preserve')
        link = self.root / 'link'; link.symlink_to(self.output)
        dangling = self.root / 'dangling'; dangling.symlink_to(self.root / 'missing')
        for path in (self.output, link, dangling, sentinel):
            with self.assertRaisesRegex(ModelProbeError, '^PROBE_DESTINATION_EXISTS$'):
                run_probe(self.path, path)
        self.assertEqual(sentinel.read_bytes(), b'preserve')
        self.assertEqual(self.requests, [])

    def test_bad_config_counts_and_deadlines_fail_before_output_or_network(self):
        for repeats in (0, 6, True, 1.5):
            with self.assertRaisesRegex(ModelProbeError, '^INVALID_PROBE_REPETITIONS$'):
                run_probe(self.path, self.output, repetitions=repeats)
        for timeout in (0, 301, float('nan')):
            with self.assertRaises(ValueError):
                run_probe(self.path, self.output, call_seconds=timeout)
        self.path.write_text('{"bad":true}')
        with self.assertRaises(ModelConfigError):
            run_probe(self.path, self.output)
        self.assertFalse(self.output.exists())
        self.assertEqual(self.requests, [])

    def test_io_failure_before_plan_sends_nothing_and_retains_incomplete_directory(self):
        import eidolon_core.model_probe as probe
        original = probe._write_new
        def fail_plan(path, value):
            if path.name == 'plan.json':
                raise OSError(SECRET)
            return original(path, value)
        with patch.object(probe, '_write_new', side_effect=fail_plan):
            report = run_probe(self.path, self.output)
        self.assertEqual(report['verdict'], 'INCOMPLETE')
        self.assertTrue((self.output / INCOMPLETE).exists())
        self.assertFalse((self.output / 'report.json').exists())
        self.assertEqual(self.requests, [])
        self.assertNotIn(SECRET, json.dumps(report))

    def test_partial_case_write_failure_preserves_state_and_refuses_rerun(self):
        import eidolon_core.model_probe as probe
        original = probe._write_new
        def fail_case(path, value):
            if path.name == 'case-unicode-multiple-1.json':
                raise OSError(SECRET)
            return original(path, value)
        with patch.object(probe, '_write_new', side_effect=fail_case):
            report = run_probe(self.path, self.output, call_seconds=5)
        self.assertEqual((report['verdict'], report['recorded_cases']), ('INCOMPLETE', 1))
        self.assertEqual(report['started_cases'], 2)
        self.assertEqual(len(self.requests), 2)
        self.assertTrue((self.output / 'case-single-1.json').is_file())
        self.assertTrue((self.output / 'state-unicode-multiple-1/missions.sqlite3').is_file())
        self.assertTrue((self.output / INCOMPLETE).exists())
        with self.assertRaises(ModelProbeError):
            run_probe(self.path, self.output)
        self.assertEqual(len(self.requests), 2)

    def test_missing_credential_records_attempts_but_sends_no_http_request(self):
        self.config.update(provider='llama-server', options={'max_tokens': 512}, api_key_env='PROBE_TEST_KEY')
        self.write()
        environment = dict(os.environ)
        environment.pop('PROBE_TEST_KEY', None)
        with patch.dict(os.environ, environment, clear=True):
            report = run_probe(self.path, self.output, call_seconds=5)
        self.assertEqual(report['verdict'], 'FAILED_CASES')
        self.assertEqual(sum(r['planner_attempts'] for r in report['results']), 1)
        self.assertEqual(self.requests, [])
        self.assertEqual(report['status'], 'STOPPED')
        self.assertEqual(report['not_started_cases'], 3)
        self.assertEqual(report['results'][0]['outcome'], 'ERROR')

    def test_credential_is_sent_only_in_header_and_absent_from_probe_artifacts(self):
        self.config.update(provider='llama-server', options={'max_tokens': 512}, api_key_env='PROBE_TEST_KEY')
        self.write()
        with patch.dict(os.environ, {'PROBE_TEST_KEY': SECRET}):
            report = run_probe(self.path, self.output, call_seconds=5)
        self.assertEqual(report['verdict'], 'PASSED_CASES', report)
        self.assertTrue(all(r[2] == 'Bearer ' + SECRET for r in self.requests))
        self.assertNotIn(SECRET, json.dumps(report))
        for path in self.output.rglob('*'):
            if path.is_file():
                self.assertNotIn(SECRET.encode(), path.read_bytes(), path.name)

    def test_timeout_stays_an_error_without_retry_and_does_not_claim_throughput(self):
        self.kind = 'slow'
        self.config['timeout_seconds'] = .1
        self.write()
        report = run_probe(self.path, self.output, call_seconds=5)
        self.assertEqual(report['verdict'], 'FAILED_CASES')
        self.assertEqual(len(self.requests), 1)
        self.assertEqual(report['status'], 'STOPPED')
        self.assertEqual(report['not_started_cases'], 3)
        self.assertEqual(report['results'][0]['outcome'], 'ERROR')
        self.assertNotIn('ttft', report)
        self.assertNotIn('tokens_per_second', report)

    def test_final_publication_failure_keeps_marker_and_all_per_case_evidence(self):
        import eidolon_core.model_probe as probe
        original = probe._write_new
        def fail_report(path, value):
            if path.name == 'report.json':
                raise OSError(SECRET)
            return original(path, value)
        with patch.object(probe, '_write_new', side_effect=fail_report):
            report = run_probe(self.path, self.output, call_seconds=5)
        self.assertEqual(report['verdict'], 'INCOMPLETE')
        self.assertEqual(report['recorded_cases'], 4)
        self.assertEqual(report['started_cases'], 4)
        self.assertEqual(len(list(self.output.glob('case-*.json'))), 4)
        self.assertTrue((self.output / INCOMPLETE).is_file())
        self.assertFalse((self.output / 'report.json').exists())

    def test_repetitions_are_new_cases_with_same_fixed_criteria(self):
        report = run_probe(self.path, self.output, repetitions=2, call_seconds=5)
        self.assertEqual(report['verdict'], 'PASSED_CASES', report)
        self.assertEqual(report['expected_cases'], 8)
        self.assertEqual(len({r['id'] for r in report['results']}), 8)
        self.assertEqual(len({r['mission_id'] for r in report['results']}), 8)
        self.assertEqual(len(self.requests), 6)

    def test_cli_plan_run_return_codes_and_no_ambient_state(self):
        plan = self.cli('--plan-only')
        self.assertEqual(plan.returncode, 0, plan.stderr)
        self.assertEqual(json.loads(plan.stdout)['status'], 'PLANNED')
        self.assertFalse((self.root / 'unused').exists())
        self.assertEqual(self.requests, [])
        completed = self.cli('--output', str(self.output))
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(json.loads(completed.stdout)['verdict'], 'PASSED_CASES')
        self.assertFalse((self.root / 'unused').exists())
        self.kind = 'invalid'
        failed = self.cli('--output', str(self.root / 'failed'))
        self.assertEqual(failed.returncode, 3, failed.stderr)
        self.assertEqual(json.loads(failed.stdout)['verdict'], 'FAILED_CASES')
        duplicate = self.cli('--output', str(self.output))
        self.assertEqual(duplicate.returncode, 2)
        self.assertNotIn(str(self.output), duplicate.stderr)

    def test_cli_incompatible_options_are_rejected_before_state_or_network(self):
        for args, extra in (((), ()), (('--plan-only', '--output', str(self.output)), ()),
                            (('--plan-only',), ('--memory-root', '/unused')),
                            (('--plan-only',), ('--profile', 'action-sim')),
                            (('--plan-only',), ('--max-invocations', '0'))):
            refused = self.cli(*args, extra=extra)
            self.assertEqual(refused.returncode, 2)
            self.assertEqual(refused.stdout, '')
        self.assertFalse(self.output.exists())
        self.assertFalse((self.root / 'unused').exists())
        self.assertEqual(self.requests, [])

    def test_human_output_distinguishes_planning_and_stopped_case_evidence(self):
        offline = self.cli('--plan-only', extra=('--format', 'human'))
        self.assertEqual(offline.returncode, 0)
        self.assertIn('aucun appel envoyé', offline.stdout)
        self.assertIn('4 cas ; au plus 3 tentatives', offline.stdout)
        self.assertEqual(self.requests, [])
        self.kind = 'unavailable'
        failed = self.cli('--output', str(self.output), extra=('--format', 'human'))
        self.assertEqual(failed.returncode, 3)
        self.assertIn('single-1 : ERROR', failed.stdout)
        self.assertIn('MODEL_UNAVAILABLE', failed.stdout)
        self.assertIn('3 cas non lancés', failed.stdout)
        self.assertEqual(len(self.requests), 1)
        self.assertNotIn(SECRET, failed.stdout + failed.stderr)


if __name__ == '__main__':
    unittest.main()
