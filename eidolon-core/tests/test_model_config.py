# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_model_config.py
# Description : Configuration privée et parcours CLI vers un faux Ollama local
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
import unittest
from unittest.mock import patch

from eidolon_core.memory import DEMO_REQUEST
from eidolon_core.model_config import load_model, ModelConfigError
from eidolon_core.ollama_model import OllamaModel
from tests.test_ollama_model import MODEL, answer, plan_for


class ModelConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config_path = self.root / 'model.json'
        self.config = {'version': 1, 'provider': 'ollama', 'endpoint': 'http://127.0.0.1:11434',
                       'model': MODEL, 'options': {'temperature': 0, 'num_predict': 512}}
        self.write()

    def write(self, value=None):
        self.config_path.write_text(json.dumps(self.config if value is None else value))
        self.config_path.chmod(0o600)

    def test_loading_is_network_free_and_canonical(self):
        before = self.config_path.read_bytes()
        with patch('socket.socket', side_effect=AssertionError('no network')):
            first = load_model(self.config_path)
            self.assertIsInstance(first, OllamaModel)
            self.config_path.write_text(json.dumps(self.config, indent=4, sort_keys=True))
            second = load_model(self.config_path)
        self.assertEqual(first.model_id, second.model_id)
        self.assertEqual(first.config.manifest()['budgets']['output_tokens'], 512)
        self.assertFalse(first.config.allow_non_loopback)

    def test_ambiguous_json_unknown_keys_and_non_finite_values_refused(self):
        for raw in ('{"version":1,"version":1}', '[1]', '{"x":NaN}', '[' * 2000):
            self.config_path.write_text(raw)
            with self.assertRaisesRegex(ModelConfigError, 'INVALID_MODEL_CONFIG'):
                load_model(self.config_path)
        for change in ({'version': True}, {'provider': 'other'}, {'allow_non_loopback': True},
                       {'token': 'private-canary'}, {'options': {}}, {'options': {'num_predict': -1}},
                       {'options': {'num_predict': True}}, {'options': {'num_predict': 8193}},
                       {'options': {'num_predict': 64, 'num_ctx': 0}}, {'options': {'num_predict': 64, 'seed': 1.5}},
                       {'timeout_seconds': 0}, {'max_response_bytes': 0}):
            self.write({**self.config, **change})
            with self.assertRaisesRegex(ModelConfigError, 'INVALID_MODEL_CONFIG'):
                load_model(self.config_path)

    def test_only_literal_loopback_endpoint_without_credentials_or_redirect_path(self):
        for endpoint in ('http://localhost:11434', 'http://192.0.2.1:11434', 'http://ollama.example.invalid',
                         'http://127.0.0.1:0', 'http://127.0.0.1:99999', 'http://127.0.0.1:bad',
                         'http://user:secret@127.0.0.1:11434', 'http://127.0.0.1:11434/?token=private',
                         'http://127.0.0.1:11434/api/chat', 'http://127.0.0.1:\n11434'):
            self.write({**self.config, 'endpoint': endpoint})
            with self.assertRaisesRegex(ModelConfigError, 'INVALID_MODEL_CONFIG'):
                load_model(self.config_path)
        self.write({**self.config, 'endpoint': 'http://[::1]:11434'})
        self.assertEqual(load_model(self.config_path).config.endpoint, 'http://[::1]:11434')

    def test_private_regular_bounded_file_and_symlink_fifo_refusal(self):
        self.config_path.chmod(0o644)
        with self.assertRaisesRegex(ModelConfigError, 'MODEL_CONFIG_NOT_PRIVATE_OR_TOO_LARGE'):
            load_model(self.config_path)
        self.config_path.chmod(0o600)
        self.config_path.write_bytes(b' ' * 16385)
        with self.assertRaises(ModelConfigError):
            load_model(self.config_path)
        self.config_path.unlink()
        os.mkfifo(self.config_path, 0o600)
        with self.assertRaises(ModelConfigError):
            load_model(self.config_path)
        self.config_path.unlink()
        target = self.root / 'target'; target.write_text('private-canary'); target.chmod(0o600)
        self.config_path.symlink_to(target)
        with self.assertRaisesRegex(ModelConfigError, 'MODEL_CONFIG_UNAVAILABLE'):
            load_model(self.config_path)
        self.assertEqual(target.read_text(), 'private-canary')


class ModelCLITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.requests = []
        self.response_kind = 'valid'
        owner = self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass
            def do_POST(self):
                raw = self.rfile.read(int(self.headers['Content-Length']))
                owner.requests.append((self.path, raw))
                content = plan_for(raw)
                code = 200
                if owner.response_kind == 'invalid':
                    content = 'not a plan'
                if owner.response_kind == 'unauthorized':
                    content = json.dumps({'version': 1, 'steps': [{'id': 'danger', 'tool': 'service.restart', 'parameters': {}}]})
                payload = answer(content)
                if owner.response_kind == 'unavailable':
                    code, payload = 503, {'error': 'synthetic unavailable'}
                data = json.dumps(payload).encode()
                self.send_response(code)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(data)))
                self.end_headers()
                self.wfile.write(data)
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={'poll_interval': .01})
        self.thread.start()
        self.addCleanup(self.stop)
        self.config_path = self.root / 'model.json'
        self.config = {'version': 1, 'provider': 'ollama',
                       'endpoint': f'http://127.0.0.1:{self.server.server_port}', 'model': MODEL,
                       'options': {'num_predict': 512}, 'timeout_seconds': 2}
        self.write()
        self.state = self.root / 'state'

    def stop(self):
        self.server.shutdown(); self.thread.join(5); self.server.server_close()

    def write(self):
        self.config_path.write_text(json.dumps(self.config)); self.config_path.chmod(0o600)

    def cli(self, *args, model=True, extra=()):
        command = [sys.executable, '-m', 'eidolon_core', '--state', str(self.state), '--timeout', '5']
        if model:
            command += ['--model-config', str(self.config_path)]
        return subprocess.run([*command, *extra, *args], capture_output=True, text=True, timeout=15)

    def test_real_cli_worker_calls_fake_ollama_then_verifies_and_never_replays_completed(self):
        done = self.cli('demo')
        self.assertEqual(done.returncode, 0, done.stderr)
        mission = json.loads(done.stdout)
        self.assertEqual(mission['status'], 'SUCCEEDED')
        self.assertTrue(mission['configuration']['model'].startswith('ollama/'))
        self.assertEqual(len(self.requests), 1)
        self.assertEqual(self.requests[0][0], '/api/chat')
        body = json.loads(self.requests[0][1])
        self.assertFalse(body['stream'])
        self.assertNotIn('tools', body)
        self.assertEqual(self.cli('run', mission['id']).returncode, 0)
        self.assertEqual(len(self.requests), 1)

    def test_create_sends_nothing_and_changed_config_cannot_resume(self):
        created = self.cli('create', DEMO_REQUEST)
        self.assertEqual(created.returncode, 0, created.stderr)
        identity = json.loads(created.stdout)['id']
        self.assertEqual(self.requests, [])
        self.config['options']['num_predict'] = 256; self.write()
        changed = self.cli('run', identity)
        self.assertEqual(changed.returncode, 2)
        self.assertIn('CONFIGURATION_CHANGED', changed.stdout + changed.stderr)
        self.assertEqual(self.requests, [])
        self.config['options']['num_predict'] = 512; self.write()
        self.assertEqual(self.cli('run', identity).returncode, 0)
        self.assertEqual(len(self.requests), 1)

    def test_unavailable_and_invalid_model_remain_explicit(self):
        for kind, status, code, exit_code in (('unavailable', 'BLOCKED', 'MODEL_UNAVAILABLE', 2),
                                             ('invalid', 'FAILED', 'MODEL_INVALID', 3),
                                             ('unauthorized', 'BLOCKED', 'PREFLIGHT_REFUSED', 2)):
            with self.subTest(kind=kind):
                self.response_kind = kind
                done = self.cli('demo')
                self.assertEqual(done.returncode, exit_code, done.stderr)
                mission = json.loads(done.stdout)
                self.assertEqual(mission['status'], status)
                self.assertEqual(mission['error']['code'], code)
                self.assertEqual(mission['calls'], [])

    def test_default_demo_remains_deterministic_without_network(self):
        done = self.cli('demo', model=False)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(self.requests, [])
        self.assertNotIn('ollama/', done.stdout)

    def test_invalid_or_incompatible_config_does_not_create_state_or_contact_server(self):
        refused = self.cli('demo', extra=['--profile', 'research-sim'])
        self.assertEqual(refused.returncode, 2)
        self.assertIn('MODEL_CONFIG_COMMAND_NOT_SUPPORTED', refused.stderr)
        self.assertFalse(self.state.exists())
        self.config_path.write_text('{"private-canary":true}')
        refused = self.cli('demo')
        self.assertEqual(refused.returncode, 2)
        self.assertIn('INVALID_MODEL_CONFIG', refused.stderr)
        self.assertNotIn('private-canary', refused.stderr)
        self.assertNotIn(str(self.config_path), refused.stderr)
        self.assertFalse(self.state.exists())
        refused = self.cli('client-missions')
        self.assertEqual(refused.returncode, 2)
        self.assertIn('MODEL_CONFIG_COMMAND_NOT_SUPPORTED', refused.stderr)
        self.assertEqual(self.requests, [])
