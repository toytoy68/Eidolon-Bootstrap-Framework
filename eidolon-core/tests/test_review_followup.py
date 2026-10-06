# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_review_followup.py
# Description : Régressions G019/G020, budgets et capacité avant appel
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from eidolon_core.commands import (PROTOCOL, CANCEL_PROTOCOL, parse_command,
                                   parse_cancel_command, validate_command, validate_cancel_command)
from eidolon_core.contracts import ContractError
from eidolon_core.research import Hit, ResearchCoordinator, ResearchLimits
from eidolon_core.research_pauses import ResearchPauses, PauseStorageError, origin_scope, provider_scope
from eidolon_core.web_reader import WebReader
from eidolon_core.web_transport import RawResponse
from tests.test_research import Clock, Provider, Reader, dns, hit
from tests.test_web_transport import DNS, PUBLIC, OTHER_PUBLIC, FakeConnector, ok, redirect


class FollowupTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / 'pauses.sqlite3'
        self.clock = Clock()
        self.pauses = ResearchPauses(self.path, clock=self.clock)

    def released(self, scope):
        row = self.pauses.pause([scope], reason='ACCESS_DENIED')[0]
        self.pauses.release(row['id'], expected_revision=row['revision'], actor='test', reason='fixture')

    def web(self, connector, *, seconds=13):
        provider = Provider('p1', [Hit('https://docs.example.com/a', 'synthetic')])
        return ResearchCoordinator([provider], WebReader(DNS, connector, clock=self.clock),
            resolver=DNS, pauses=self.pauses, clock=self.clock, limits=ResearchLimits(seconds=seconds))

    def test_slow_hop_lookup_does_not_start_exchange_after_budget(self):
        connector = FakeConnector({(PUBLIC, '/a'): ok()})
        active = self.pauses.active
        def slow(scope):
            result = active(scope)
            self.clock.value += 6
            return result
        with patch.object(self.pauses, 'active', side_effect=slow):
            report = self.web(connector).run('synthetic')
        self.assertEqual(connector.calls, [])
        self.assertEqual(report['status'], 'DEADLINE')
        self.assertEqual(report['readable_pages'], 0)

    def test_cancel_during_redirect_gate_stops_second_exchange(self):
        connector = FakeConnector({(PUBLIC, '/a'): redirect('https://cdn.example.com/b'),
                                   (OTHER_PUBLIC, '/b'): ok()})
        active = self.pauses.active
        cancelled = False
        def gate(scope):
            nonlocal cancelled
            if scope == origin_scope('cdn.example.com', 443): cancelled = True
            return active(scope)
        with patch.object(self.pauses, 'active', side_effect=gate):
            report = self.web(connector).run('synthetic', cancelled=lambda: cancelled)
        self.assertEqual(len(connector.calls), 1)
        self.assertEqual(report['status'], 'CANCELLED')
        self.assertEqual(report['readable_pages'], 0)

    def test_deadline_during_redirect_gate_stops_second_exchange(self):
        connector = FakeConnector({(PUBLIC, '/a'): redirect('https://cdn.example.com/b'),
                                   (OTHER_PUBLIC, '/b'): ok()})
        active = self.pauses.active
        def gate(scope):
            if scope == origin_scope('cdn.example.com', 443): self.clock.value = 13
            return active(scope)
        with patch.object(self.pauses, 'active', side_effect=gate):
            report = self.web(connector).run('synthetic')
        self.assertEqual(len(connector.calls), 1)
        self.assertEqual(report['status'], 'DEADLINE')

    def test_capacity_check_is_read_only_deduplicates_and_keeps_released_rows(self):
        scope = provider_scope('p1')
        self.released(scope)
        before = self.pauses.inspect()
        with patch('eidolon_core.research_pauses.MAX_RECORDS', 1):
            self.pauses.check_capacity([scope, scope])
            with self.assertRaisesRegex(PauseStorageError, 'PAUSE_CAPACITY_REACHED'):
                self.pauses.check_capacity([origin_scope('new.example', 443)])
            self.pauses.pause([scope], reason='ACCESS_DENIED')
        self.assertEqual(len(self.pauses.inspect()['pauses']), 1)
        self.assertEqual(self.pauses.inspect()['audit_events'], before['audit_events'] + 1)

    def test_full_store_blocks_new_provider_after_reconstruction(self):
        self.released(provider_scope('old'))
        provider, reader = Provider('p1', [hit()]), Reader()
        before = self.pauses.inspect()
        with patch('eidolon_core.research_pauses.MAX_RECORDS', 1):
            for _ in range(2):
                coordinator = ResearchCoordinator([provider], reader, resolver=dns,
                    pauses=ResearchPauses(self.path, clock=self.clock))
                with self.assertRaisesRegex(PauseStorageError, 'PAUSE_CAPACITY_REACHED'):
                    coordinator.run('synthetic')
        self.assertEqual(provider.calls, 0)
        self.assertEqual(reader.calls, [])
        self.assertEqual(self.pauses.inspect(), before)

    def test_full_store_blocks_new_origin_after_reconstruction(self):
        self.released(provider_scope('p1'))
        provider, reader = Provider('p1', [hit()]), Reader({hit().url: dict(status=429)})
        before = self.pauses.inspect()
        with patch('eidolon_core.research_pauses.MAX_RECORDS', 1):
            for _ in range(2):
                coordinator = ResearchCoordinator([provider], reader, resolver=dns,
                    pauses=ResearchPauses(self.path, clock=self.clock))
                with self.assertRaisesRegex(PauseStorageError, 'PAUSE_CAPACITY_REACHED'):
                    coordinator.run('synthetic')
        self.assertEqual(provider.calls, 2)  # existing provider remains eligible
        self.assertEqual(reader.calls, [])
        self.assertEqual(self.pauses.inspect(), before)

    def test_redirect_needs_capacity_for_initial_and_final_origins_together(self):
        self.released(provider_scope('p1'))
        connector = FakeConnector({(PUBLIC, '/a'): redirect('https://cdn.example.com/b'),
                                   (OTHER_PUBLIC, '/b'): ok()})
        before = self.pauses.inspect()
        with patch('eidolon_core.research_pauses.MAX_RECORDS', 2):
            with self.assertRaisesRegex(PauseStorageError, 'PAUSE_CAPACITY_REACHED'):
                self.web(connector).run('synthetic')
        self.assertEqual(len(connector.calls), 1)
        self.assertEqual(self.pauses.inspect(), before)

    def test_same_origin_redirect_fits_one_remaining_slot(self):
        self.released(provider_scope('p1'))
        connector = FakeConnector({(PUBLIC, '/a'): redirect('/b'),
                                   (PUBLIC, '/b'): RawResponse(429, (('Retry-After', '1'),), b'', True)})
        with patch('eidolon_core.research_pauses.MAX_RECORDS', 2):
            report = self.web(connector).run('synthetic')
        self.assertEqual(len(connector.calls), 2)
        self.assertEqual(report['sources'][0]['state'], 'RATE_LIMITED')
        self.assertIsNotNone(self.pauses.active(origin_scope('docs.example.com', 443)))

    def test_capacity_gate_cannot_hide_timeout_or_cancel(self):
        for cancelled in (False, True):
            with self.subTest(cancelled=cancelled):
                self.clock.value = 0
                provider = Provider('p1', [hit()])
                coordinator = ResearchCoordinator([provider], Reader(), resolver=dns,
                    pauses=self.pauses, clock=self.clock, limits=ResearchLimits(seconds=1))
                stop = False
                check = self.pauses.check_capacity
                def slow(scopes):
                    nonlocal stop
                    check(scopes)
                    self.clock.value = 2
                    stop = cancelled
                with patch.object(self.pauses, 'check_capacity', side_effect=slow):
                    report = coordinator.run('synthetic', cancelled=lambda: stop)
                self.assertEqual(provider.calls, 0)
                self.assertEqual(report['status'], 'CANCELLED' if cancelled else 'DEADLINE')

    def test_capacity_failure_is_sticky_and_does_not_fallback(self):
        providers = [Provider('p1', []), Provider('p2', [])]
        coordinator = ResearchCoordinator(providers, Reader(), resolver=dns, pauses=self.pauses)
        with patch.object(self.pauses, 'check_capacity', side_effect=PauseStorageError('PAUSE_STORAGE_UNAVAILABLE')):
            with self.assertRaises(PauseStorageError): coordinator.run('synthetic')
        with self.assertRaises(PauseStorageError): coordinator.run('synthetic')
        self.assertEqual([p.calls for p in providers], [0, 0])

    def test_capacity_validates_scopes_and_does_not_recreate_deleted_storage(self):
        for value in (None, [], [{}], [provider_scope('p1')] * 3):
            with self.subTest(value=value), self.assertRaisesRegex(ContractError, 'INVALID_PAUSE_SCOPE'):
                self.pauses.check_capacity(value)
        self.path.unlink()
        with self.assertRaises(PauseStorageError): self.pauses.check_capacity([provider_scope('p1')])
        self.assertFalse(self.path.exists())

    def test_late_receipt_is_preserved_and_normal_read_works(self):
        for late in (False, True):
            with self.subTest(late=late):
                self.clock.value = 0
                connector = FakeConnector({(PUBLIC, '/a'): ok(b'evidence')})
                exchange = connector.exchange
                def response(**kwargs):
                    result = exchange(**kwargs)
                    if late: self.clock.value = 20
                    return result
                with patch.object(connector, 'exchange', side_effect=response):
                    report = self.web(connector).run('synthetic')
                self.assertEqual(report['status'], 'DEADLINE' if late else 'READ_TARGET_MET')
                self.assertEqual(report['sources'][0]['text'], 'evidence')
                self.assertEqual(len(connector.calls), 1)


class CommandDiagnosticTests(unittest.TestCase):
    def test_invalid_mission_id_has_precise_diagnostic_for_both_protocols(self):
        for protocol, parser, validator in [(PROTOCOL, parse_command, validate_command),
                (CANCEL_PROTOCOL, parse_cancel_command, validate_cancel_command)]:
            command = dict(protocol=protocol, store_id='s-'+'0'*32, client_id='test', command_key='test',
                           mission_id='invalid', actor='test', reason='synthetic')
            if protocol == PROTOCOL:
                command.update(expected_revision=0, proposal_sha256='0'*64, decision='approve')
            for identity in ('../bad', None, 12, [], {}, 'm-'+'f'*31):
                command['mission_id'] = identity
                for mode in ('dict', 'str', 'bytes'):
                    with self.subTest(protocol=protocol, identity=identity, mode=mode):
                        with self.assertRaisesRegex(ContractError, '^INVALID_COMMAND: invalid mission_id$'):
                            if mode == 'dict': validator(command)
                            else:
                                raw = json.dumps(command)
                                parser(raw.encode() if mode == 'bytes' else raw)
