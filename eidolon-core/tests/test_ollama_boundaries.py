# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_ollama_boundaries.py
# Description : Frontières strictes et confidentialité des erreurs Ollama
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Synthetic protocol and real local workers only; no model qualification."""
from dataclasses import dataclass
import json
from socketserver import BaseRequestHandler, ThreadingTCPServer
import tempfile
import threading
import unittest

from eidolon_core.contracts import ContractError
from eidolon_core.memory import DEMO_REQUEST
from eidolon_core.ollama_model import OllamaError, OllamaModel
from eidolon_core.runtime import Runtime
from eidolon_core.store import Store
from tests.test_ollama_model import answer, config

CANARY = 'synthetic-private-error-content'


@dataclass(frozen=True)
class ErrorTransport:
    mode: str

    def post(self, url, body, *, timeout, max_bytes):
        if self.mode == 'http':
            return 500, 'application/json', json.dumps({'error': CANARY}).encode()
        if self.mode == 'model':
            return 200, 'application/json', json.dumps({'error': CANARY}).encode()
        return 200, 'application/json', json.dumps(answer('{}', done_reason=CANARY)).encode()


class BrokenStatusHandler(BaseRequestHandler):
    def handle(self):
        self.request.recv(65536)
        self.request.sendall(CANARY.encode() + b'\r\n\r\n')


class OllamaBoundaryTests(unittest.TestCase):
    def test_duplicate_control_keys_refused_at_every_object_level(self):
        raw = json.dumps(answer('{}'))
        documents = [raw.replace('"done": true', '"done":false,"done":true'),
                     raw.replace('"content": "{}"', '"content":"discarded","content":"{}"'),
                     raw.replace('"role": "assistant"', '"role":"user","role":"assistant"')]
        model = OllamaModel(config())
        for document in documents:
            with self.subTest(document=document), self.assertRaises(OllamaError) as raised:
                model.read_response(200, 'application/json', document.encode())
            self.assertEqual(raised.exception.code, 'BAD_RESPONSE')

    def test_overflow_numbers_and_unpaired_surrogates_refused(self):
        raw = json.dumps(answer('{}'))
        documents = [raw.replace('"eval_count": 12', '"eval_count":1e999'),
                     json.dumps(answer('\ud800')), json.dumps(answer('{}', other='\udfff'))]
        model = OllamaModel(config())
        for document in documents:
            with self.assertRaises(OllamaError) as raised:
                model.read_response(200, 'application/json', document.encode())
            self.assertEqual(raised.exception.code, 'BAD_RESPONSE')

    def test_invalid_control_field_types_refused(self):
        model = OllamaModel(config())
        for calls in (False, {}, '', 0):
            payload = answer('{}', message={'role': 'assistant', 'content': '{}', 'tool_calls': calls})
            with self.subTest(calls=calls), self.assertRaises(OllamaError) as raised:
                model.read_response(200, 'application/json', json.dumps(payload).encode())
            self.assertEqual(raised.exception.code, 'BAD_RESPONSE')
        for calls in (None, []):
            payload = answer('{}', message={'role': 'assistant', 'content': '{}', 'tool_calls': calls})
            self.assertEqual(model.read_response(200, 'application/json', json.dumps(payload).encode()), '{}')

    def test_invalid_transport_status_refused_without_echo(self):
        model = OllamaModel(config())
        for status in (200.0, True, '200', CANARY, 0, 600):
            with self.assertRaises(OllamaError) as raised:
                model.read_response(status, 'application/json', json.dumps(answer('{}')).encode())
            self.assertEqual(raised.exception.code, 'BAD_RESPONSE')
            self.assertNotIn(CANARY, str(raised.exception))

    def test_invalid_endpoints_fail_before_transport(self):
        for endpoint in ('http://127.0.0.1:99999', 'http://127.0.0.1:bad',
                         'http://127.0.0.1:\n11434', 'http://[::1',
                         'http://@127.0.0.1:11434', 'http://127.0.0.1:11434?',
                         'http://127.0.0.1:11434#', 'http://127.0.0.1:\x7f',
                         'http://127.0.0.1/' + 'x' * 2000):
            with self.subTest(endpoint=endpoint), self.assertRaises(ContractError):
                config(endpoint=endpoint)

    def test_invalid_scalar_options_have_consistent_contract_errors(self):
        cases = [{'options': {'temperature': 10**400}}, {'options': {'temperature': -1}},
                 {'options': {'temperature': True}}, {'options': {'num_predict': -1}},
                 {'options': {'num_predict': 0}}, {'options': {'num_predict': 8193}},
                 {'options': {'num_predict': 1.5}}, {'options': {'num_ctx': 1}},
                 {'options': {'num_ctx': 262145}}, {'options': {'top_k': 1.5}},
                 {'options': {'seed': -1}}, {'options': {'top_p': 0}},
                 {'options': {'top_p': 1.1}}, {'timeout_seconds': 10**400},
                 {'model': 'bad\ud800'}, {'model': 'bad\x7f'}]
        for values in cases:
            with self.subTest(fields=list(values)), self.assertRaises(ContractError):
                config(**values)

    def test_valid_scalar_boundaries_remain_usable(self):
        for options in ({}, {'num_predict': 1, 'num_ctx': 256, 'seed': 0, 'top_k': 0,
                            'top_p': .01, 'temperature': 0},
                        {'num_predict': 8192, 'num_ctx': 262144, 'seed': 2**31 - 1,
                         'top_k': 2**31 - 1, 'top_p': 1, 'temperature': 2}):
            self.assertEqual(dict(config(options=options).options), options)

    def test_server_error_text_never_reaches_mission_events_or_storage(self):
        for mode, code in (('http', 'HTTP_STATUS'), ('model', 'MODEL_ERROR'), ('finish', 'INCOMPLETE')):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as state:
                store = Store(state)
                runtime = Runtime(store, model=OllamaModel(config(), ErrorTransport(mode)))
                mission = runtime.run(runtime.create(DEMO_REQUEST)['id'])
                self.assertEqual(mission['status'], 'BLOCKED')
                self.assertEqual(mission['error']['code'], 'MODEL_UNAVAILABLE')
                self.assertIn(code, mission['error']['message'])
                self.assertIsNone(mission['model_output'])
                self.assertEqual(mission['calls'], [])
                self.assertNotIn(CANARY, json.dumps(mission) + json.dumps(store.events(mission['id'])))
                self.assertNotIn(CANARY.encode(), store.path.read_bytes())

    def test_malformed_http_status_is_a_sanitized_transport_error(self):
        with ThreadingTCPServer(('127.0.0.1', 0), BrokenStatusHandler) as server:
            server.daemon_threads = True
            thread = threading.Thread(target=server.serve_forever, kwargs={'poll_interval': .01})
            thread.start()
            try:
                model = OllamaModel(config(endpoint=f'http://127.0.0.1:{server.server_address[1]}'))
                with self.assertRaises(OllamaError) as raised:
                    model.propose(DEMO_REQUEST, {'items': []})
                self.assertEqual(raised.exception.code, 'TRANSPORT')
                self.assertNotIn(CANARY, str(raised.exception))
                self.assertTrue(raised.exception.__suppress_context__)
            finally:
                server.shutdown()
                thread.join(3)

    def test_changed_adapter_contract_blocks_preexisting_mission(self):
        from eidolon_core.contracts import digest
        with tempfile.TemporaryDirectory() as state:
            model = OllamaModel(config())
            runtime = Runtime(Store(state), model=model)
            previous = model.config.manifest()
            previous['adapter'] = 'ollama-chat/1'
            old = {**runtime.configuration(), 'model': f'ollama/{model.config.model}@{digest(previous)[:16]}'}
            mission = runtime.store.create(DEMO_REQUEST, old)
            result = runtime.run(mission['id'])
            self.assertEqual(result['error']['code'], 'CONFIGURATION_CHANGED')
            self.assertEqual(result['calls'], [])
