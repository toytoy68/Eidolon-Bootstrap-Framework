# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_audit_regressions.py
# Description : Sondes de l'audit : annulation, refus Web et diagnostics
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
from dataclasses import replace
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from eidolon_core.actions import ActionRuntime
from eidolon_core.commands import parse_command, parse_cancel_command
from eidolon_core.contracts import ContractError
from eidolon_core.memory import DEMO_REQUEST
from eidolon_core.runtime import Runtime
from eidolon_core.store import Store
from eidolon_core.tools import Registry
from eidolon_core.worker import CallFailure
from eidolon_core.research import ResearchCoordinator
from eidolon_core.research_pauses import ResearchPauses, origin_scope
from eidolon_core.web_reader import WebReader
from eidolon_core.web_transport import RawResponse
from tests.test_actions import FaultAction, Crash
from tests.test_research import Provider, Reader, dns, hit
from tests.support import MultipleMemory


class AuditCancellationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = Store(self.temp.name)
        self.runtime = ActionRuntime(self.store)

    def approved(self, runtime):
        m = runtime.run(runtime.create_restart('nas')['id'])
        runtime.decide(m['id'], expected_sha256=m['proposal']['sha256'], decision='approve',
                       actor='audit', reason='synthetic test')
        return m['id']

    def assertVerifiedCancellation(self, result):
        self.assertEqual(result['status'], 'CANCELLED')
        self.assertEqual(result['calls'][0]['status'], 'VERIFIED')
        self.assertEqual(result['outcome']['status'], 'ACHIEVED')
        self.assertEqual(result['error']['code'], 'CANCELLED')
        self.assertIsNone(result['result'])
        self.assertEqual(self.runtime.world.observe('sim-nas')['restarts'], 1)
        self.assertEqual(sum(e['kind'] == 'CALL_STARTED' for e in self.store.events(result['id'])), 1)

    def test_cancel_at_return_or_save_still_verifies_the_effect(self):
        for point in ('TOOL_RETURNED', 'RESULT_SAVED'):
            with self.subTest(point=point), tempfile.TemporaryDirectory() as directory:
                self.store = Store(directory)
                def checkpoint(kind):
                    if kind == point: self.store.request_cancel(identity)
                self.runtime = ActionRuntime(self.store, checkpoint=checkpoint)
                identity = self.approved(self.runtime)
                self.assertVerifiedCancellation(self.runtime.run(identity))

    def test_cancel_between_processes_preserves_pending_verification(self):
        def checkpoint(kind):
            if kind == 'RESULT_SAVED': raise Crash()
        runtime = ActionRuntime(self.store, checkpoint=checkpoint)
        identity = self.approved(runtime)
        with self.assertRaises(Crash): runtime.run(identity)
        self.store.request_cancel(identity)
        self.assertVerifiedCancellation(ActionRuntime(Store(self.temp.name)).run(identity))

    def test_reconciled_receipt_can_be_verified_after_cancellation(self):
        tool = replace(self.runtime.world.tool(), execute=FaultAction(self.runtime.world, 'lost').execute)
        runtime = ActionRuntime(self.store, registry=Registry([tool]))
        identity = self.approved(runtime)
        self.assertEqual(runtime.run(identity)['status'], 'REVIEW_REQUIRED')
        self.store.request_cancel(identity)
        runtime.reconcile(identity, decision='observed-result', actor='audit', reason='recover local receipt',
                          output=runtime.world.receipt(identity)['result'])
        self.assertVerifiedCancellation(runtime.run(identity))

    def test_verification_failure_remains_resumable_with_cancellation(self):
        identity = self.approved(self.runtime)
        from eidolon_core import runtime as module
        original = module.invoke
        def unavailable(function, args, **kwargs):
            if function == self.runtime.world.verify:
                self.store.request_cancel(identity)
                raise CallFailure('TIMEOUT', 'synthetic verifier deadline')
            return original(function, args, **kwargs)
        with patch.object(module, 'invoke', side_effect=unavailable):
            blocked = self.runtime.run(identity)
        self.assertEqual(blocked['status'], 'BLOCKED')
        self.assertEqual(blocked['error']['code'], 'VERIFICATION_UNAVAILABLE')
        self.assertEqual(blocked['calls'][0]['status'], 'RETURNED')
        self.assertIsNone(blocked['result'])
        self.assertVerifiedCancellation(self.runtime.run(identity))

    def test_invalid_output_is_not_accepted_because_cancelled(self):
        def checkpoint(kind):
            if kind == 'RESULT_SAVED': self.store.request_cancel(identity)
        tool = replace(self.runtime.world.tool(), execute=FaultAction(self.runtime.world, 'wrong-output').execute)
        runtime = ActionRuntime(self.store, registry=Registry([tool]), checkpoint=checkpoint)
        identity = self.approved(runtime)
        result = runtime.run(identity)
        self.assertEqual(result['status'], 'FAILED')
        self.assertEqual(result['error']['code'], 'VERIFICATION_FAILED')
        self.assertIsNone(result['result'])
        self.assertNotEqual(result['outcome']['status'], 'ACHIEVED')

    def test_cancellation_does_not_start_next_planned_tool(self):
        def checkpoint(kind):
            if kind == 'RESULT_SAVED': self.store.request_cancel(identity)
        runtime = Runtime(self.store, memory=MultipleMemory(), checkpoint=checkpoint)
        identity = runtime.create(DEMO_REQUEST)['id']
        result = runtime.run(identity)
        self.assertEqual(result['status'], 'CANCELLED')
        self.assertEqual(len(result['calls']), 1)
        self.assertEqual(result['calls'][0]['status'], 'VERIFIED')
        self.assertEqual(result['outcome']['status'], 'PARTIAL')
        self.assertEqual(result['progress']['completed'], 1)
        self.assertIsNone(result['result'])


class AuditResearchTests(unittest.TestCase):
    def test_http_refusal_survives_truncated_or_oversized_body(self):
        for status in (401, 403, 429):
            for body in (dict(complete=False), dict(body=b'x' * 128001)):
                with self.subTest(status=status, issue=list(body)), tempfile.TemporaryDirectory() as directory:
                    pauses = ResearchPauses(Path(directory) / 'pauses.sqlite3')
                    reader = Reader({hit().url: dict(status=status, **body)})
                    for _ in range(2):
                        ResearchCoordinator([Provider('p', [hit()])], reader, resolver=dns, pauses=pauses).run('fixture')
                    self.assertEqual(len(reader.calls), 1)
                    self.assertIsNotNone(pauses.active(origin_scope('docs.example', 443)))

    def test_refusal_persists_even_if_post_response_dns_fails(self):
        for status in (403, 429, 503):
            with self.subTest(status=status), tempfile.TemporaryDirectory() as directory:
                pauses = ResearchPauses(Path(directory) / 'pauses.sqlite3')
                class Connector:
                    calls = 0
                    def exchange(self, **kwargs):
                        self.calls += 1
                        return RawResponse(status, (('Retry-After', '30'),), b'', True)
                connector = Connector()
                queries = []
                def resolver(host, port):
                    queries.append(host)
                    if len(queries) == 3:  # preflight and fetch pass, post-response DNS fails
                        raise OSError('synthetic temporary DNS outage')
                    return dns(host, port)
                for _ in range(2):
                    ResearchCoordinator([Provider('p', [hit()])], WebReader(resolver, connector),
                                        resolver=resolver, pauses=pauses).run('fixture')
                self.assertEqual(connector.calls, 1)
                self.assertIsNotNone(pauses.active(origin_scope('docs.example', 443)))


class AuditCommandTests(unittest.TestCase):
    def test_command_parse_keeps_specific_contract_diagnostic(self):
        for parser in (parse_command, parse_cancel_command):
            with self.subTest(parser=parser.__name__):
                with self.assertRaisesRegex(ContractError, 'exact versioned'): parser('{}')
                with self.assertRaisesRegex(ContractError, 'duplicate JSON key'):
                    parser('{"protocol":1,"protocol":2}')

    def test_command_parse_rejects_non_text_inputs_with_contract_error(self):
        for parser in (parse_command, parse_cancel_command):
            for value in (None, 42, {}, b'\xff', '\ud800'):
                with self.subTest(parser=parser.__name__, value=repr(value)):
                    with self.assertRaises(ContractError): parser(value)


if __name__ == '__main__':
    unittest.main()
