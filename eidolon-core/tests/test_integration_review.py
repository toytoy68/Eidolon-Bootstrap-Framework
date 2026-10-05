# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_integration_review.py
# Description : Régressions d'intégration des modules et revue C-REV-003
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
from dataclasses import replace
import os
from pathlib import Path
import pickle
import tempfile
import unittest
from unittest.mock import patch

from eidolon_core.contracts import ContractError
from eidolon_core.memory import DEMO_REQUEST
from eidolon_core.ollama_model import OllamaConfig, OllamaError, OllamaModel
from eidolon_core.runtime import Runtime
from eidolon_core.store import Busy, Store
from eidolon_core.targets import Catalog
from eidolon_core.tools import Registry, default_registry
from tests.support import effect_then_error
from tests.test_targets import config as targets_config
from tests.test_ollama_model import CannedTransport, answer, config as model_config


class IntegrationReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.store = Store(self.directory / 'state')

    def errored_call(self):
        effects = self.directory / 'effects'
        with patch.dict(os.environ, {'EIDOLON_TEST_EFFECT': str(effects)}):
            runtime = Runtime(self.store, registry=Registry([
                replace(default_registry().get('text.stats'), execute=effect_then_error)]))
            m = runtime.run(runtime.create(DEMO_REQUEST)['id'])
        self.assertEqual(m['status'], 'REVIEW_REQUIRED')
        self.assertFalse(m['calls'][0]['error_receipt']['ok'])
        return runtime, m, effects

    def test_n09_error_after_effect_requires_confirmation_and_never_retries_implicitly(self):
        runtime, m, effects = self.errored_call()
        for protocol in ('lease-v2', 'lease-v1'):
            with self.subTest(protocol=protocol):
                m = self.store.get(m['id'])
                m['calls'][0]['worker_protocol'] = protocol
                self.store.save(m, 'PROTOCOL_FIXTURE')
                with self.assertRaisesRegex(ValueError, 'confirm_no_effect'):
                    runtime.reconcile(m['id'], decision='no-effect', actor='tester', reason='error received')
                self.assertEqual(runtime.run(m['id'])['status'], 'REVIEW_REQUIRED')
        self.assertEqual(effects.read_text().splitlines(), ['synthetic effect'])
        self.assertEqual(sum(e['kind'] == 'CALL_STARTED' for e in self.store.events(m['id'])), 1)
        closed = runtime.reconcile(m['id'], decision='abandon', actor='tester', reason='effect observed')
        self.assertEqual(closed['status'], 'ABANDONED')
        self.assertTrue(closed['calls'][0]['effect_unknown'])

    def test_n10_missing_spawned_lease_cannot_be_recreated_to_enable_retry(self):
        runtime, m, _ = self.errored_call()
        call = m['calls'][0]
        lease = self.store.worker_lease_path(m['id'], call['id'], call['attempt'])
        lease.unlink()  # Simulate an unsupported cleanup after the process ended.
        with self.assertRaisesRegex(Busy, 'lease missing'):
            runtime.reconcile(m['id'], decision='no-effect', actor='tester', reason='lost trace',
                              confirm_no_effect=True)
        self.assertFalse(lease.exists())
        self.assertEqual(self.store.get(m['id'])['calls'][0]['attempt'], 1)
        self.assertEqual(runtime.reconcile(m['id'], decision='abandon', actor='tester',
                                           reason='trace missing')['status'], 'ABANDONED')

    def test_catalog_returns_detached_scopes_on_every_public_path(self):
        catalog = Catalog.from_config(targets_config())
        before = catalog.fingerprint()
        catalog.manifest()['targets'][2]['capabilities'][0]['scope']['injected'] = True
        catalog.get('nas-main').capability('files.read').scope['roots'].append('outside')
        catalog.resolve('nas-main').target.capability('files.read').scope['roots'].append('outside')
        catalog.lookup('nas-main', 'files.read').capability.scope['roots'].append('outside')
        self.assertEqual(catalog.fingerprint(), before)
        self.assertEqual(catalog.lookup('nas-main', 'files.read').capability.scope['roots'], ['archives'])

    def test_direct_catalog_constructor_copies_and_validates_targets(self):
        source = Catalog.from_config(targets_config()).get('nas-main')
        catalog = Catalog([source])
        source.capability('files.read').scope['roots'].append('outside')
        self.assertEqual(catalog.get('nas-main').capability('files.read').scope['roots'], ['archives'])
        with self.assertRaises(ContractError):
            Catalog([source, source])

    def test_catalog_scope_bound_counts_utf8_bytes(self):
        configuration = targets_config()
        configuration['targets'][0]['capabilities'][0]['scope'] = {'text': '😀' * 1100}
        with self.assertRaisesRegex(ContractError, 'scope too large'):
            Catalog.from_config(configuration)

    def test_ollama_options_are_immutable_copied_and_spawn_serializable(self):
        options = {'temperature': 0}
        config = model_config(options=options)
        model = OllamaModel(config)
        before = model.model_id
        options['temperature'] = 1
        config.manifest()['options']['temperature'] = 2
        with self.assertRaises(TypeError):
            config.options['temperature'] = 3
        self.assertEqual(model.config.options['temperature'], 0)
        self.assertEqual(pickle.loads(pickle.dumps(model)).model_id, before)
        self.assertEqual(replace(config, timeout_seconds=30).options['temperature'], 0)

    def test_replacing_model_config_blocks_resume_before_provider(self):
        model = OllamaModel(model_config())
        runtime = Runtime(self.store, model=model)
        m = runtime.create(DEMO_REQUEST)
        model.config = replace(model.config, options={'temperature': 0.5})
        with patch.object(runtime, '_invoke', side_effect=AssertionError('provider called')):
            stopped = runtime.run(m['id'])
        self.assertEqual(stopped['error']['code'], 'CONFIGURATION_CHANGED')
        self.assertNotEqual(model.model_id, m['configuration']['model'])

    def test_adapter_response_budget_also_applies_to_injected_transport(self):
        model = OllamaModel(model_config(max_response_bytes=200),
                            CannedTransport(200, 'application/json', answer('{}', extra='x' * 300)))
        with self.assertRaises(OllamaError) as raised:
            model.propose(DEMO_REQUEST, {'items': []})
        self.assertEqual(raised.exception.code, 'RESPONSE_TOO_LARGE')


if __name__ == '__main__':
    unittest.main()
