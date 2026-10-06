# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_research_pauses.py
# Description : Persistance, revue explicite et blocages Web sans réseau réel
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
from contextlib import redirect_stdout, redirect_stderr
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from eidolon_core.cli import main
from eidolon_core.contracts import ContractError
from eidolon_core.research import AccessFailure, Hit, ResearchCoordinator
from eidolon_core.research_pauses import ResearchPauses, PauseStorageError, origin_scope, provider_scope
from eidolon_core.web_reader import WebReader
from eidolon_core.web_transport import RawResponse
from tests.test_research import Clock, Provider, Reader, dns, hit
from tests.test_web_transport import DNS, PUBLIC, OTHER_PUBLIC, FakeConnector, ok, redirect


class ResearchPauseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'research-pauses.sqlite3'
        self.clock = Clock()
        self.clock.value = 1000
        self.pauses = ResearchPauses(self.path, clock=self.clock)
        self.scope = origin_scope('docs.example', 443)

    def coordinator(self, provider=None, reader=None, **kw):
        return ResearchCoordinator([provider or Provider('p1', [hit()])], reader or Reader(),
                                   resolver=dns, pauses=self.pauses, **kw)

    def release(self, record):
        return self.pauses.release(record['id'], expected_revision=record['revision'],
                                   actor='synthetic-operator', reason='reviewed fixture')

    def test_committed_pause_survives_reopen_and_does_not_expire(self):
        original = self.pauses.pause([self.scope], reason='RATE_LIMITED', retry_after=2)[0]
        self.clock.value += 1000
        reopened = ResearchPauses(self.path, clock=self.clock)
        self.assertEqual(reopened.active(self.scope), original)
        report = reopened.inspect()
        self.assertFalse(report['automatic_release'])
        self.assertFalse(report['authorizes_execution'])
        self.assertEqual(report['audit_events'], 1)

    def test_release_checks_wait_revision_and_records_actor_without_request(self):
        original = self.pauses.pause([self.scope], reason='RATE_LIMITED', retry_after=30)[0]
        with self.assertRaisesRegex(ContractError, 'RETRY_DELAY_PENDING'):
            self.release(original)
        newer = self.pauses.pause([self.scope], reason='ACCESS_DENIED')[0]
        self.clock.value += 30
        with self.assertRaisesRegex(ContractError, 'STALE_PAUSE'):
            self.release(original)
        result = self.release(newer)
        self.assertFalse(result['request_sent'])
        self.assertFalse(result['authorizes_execution'])
        self.assertIsNone(self.pauses.active(self.scope))
        with self.pauses._connection() as db:
            event = json.loads(db.execute("SELECT body FROM pause_events WHERE kind='RELEASED'").fetchone()[0])
        self.assertEqual(event['actor'], 'synthetic-operator')
        self.assertEqual(self.pauses.inspect()['audit_events'], 3)

    def test_new_observation_after_release_is_active_with_new_revision(self):
        first = self.pauses.pause([self.scope], reason='ACCESS_DENIED')[0]
        self.release(first)
        again = self.pauses.pause([self.scope], reason='CHALLENGE', review=True)[0]
        self.assertGreater(again['revision'], first['revision'])
        self.assertTrue(self.pauses.active(self.scope)['review_required'])
        with self.assertRaisesRegex(ContractError, 'STALE_PAUSE'): self.release(first)

    def test_merge_keeps_longest_delay_and_ambiguous_review(self):
        first = self.pauses.pause([self.scope], reason='RETRY_WAIT', retry_after=100, review=True)[0]
        self.clock.value += 1
        second = self.pauses.pause([self.scope], reason='RATE_LIMITED', retry_after=1)[0]
        self.assertEqual(first['not_before_ms'], second['not_before_ms'])
        self.assertTrue(second['review_required'])
        self.clock.value += 99
        self.release(second)

    def test_capacity_failure_rolls_back_redirect_scopes_without_eviction(self):
        with patch('eidolon_core.research_pauses.MAX_RECORDS', 1):
            with self.assertRaisesRegex(PauseStorageError, 'PAUSE_CAPACITY'):
                self.pauses.pause([self.scope, origin_scope('cdn.example', 443)], reason='ACCESS_DENIED')
        self.assertEqual(self.pauses.inspect()['pauses'], [])
        self.assertEqual(self.pauses.inspect()['audit_events'], 0)

    def test_sql_fault_rolls_back_pause_and_release_with_their_audits(self):
        with self.pauses._connection() as db:
            db.execute("CREATE TRIGGER fail_audit BEFORE INSERT ON pause_events BEGIN SELECT RAISE(ABORT,'SECRET-SQL'); END")
        with self.assertRaisesRegex(PauseStorageError, '^PAUSE_STORAGE_UNAVAILABLE$'):
            self.pauses.pause([self.scope], reason='ACCESS_DENIED')
        self.assertIsNone(self.pauses.active(self.scope))
        with self.pauses._connection() as db: db.execute('DROP TRIGGER fail_audit')
        record = self.pauses.pause([self.scope], reason='ACCESS_DENIED')[0]
        with self.pauses._connection() as db:
            db.execute("CREATE TRIGGER fail_audit BEFORE INSERT ON pause_events BEGIN SELECT RAISE(ABORT,'SECRET-SQL'); END")
        with self.assertRaises(PauseStorageError): self.release(record)
        self.assertEqual(self.pauses.active(self.scope), record)

    def test_ambiguous_429_stays_blocked_after_restart_and_later_clock(self):
        reader = Reader({'https://docs.example/a': dict(status=429, retry_review_required=True)})
        self.assertEqual(self.coordinator(reader=reader).run('synthetic')['sources'][0]['state'], 'RATE_LIMITED')
        self.clock.value += 10000
        self.pauses = ResearchPauses(self.path, clock=self.clock)
        second = self.coordinator(reader=reader).run('synthetic')
        self.assertEqual(second['sources'][0]['state'], 'RETRY_WAIT')
        self.assertEqual(second['read_calls'], 0)
        self.assertEqual(len(reader.calls), 1)
        self.release(self.pauses.active(self.scope))
        reader.replies = {}
        self.assertEqual(self.coordinator(reader=reader).run('synthetic')['status'], 'READ_TARGET_MET')
        self.assertEqual(len(reader.calls), 2)

    def test_release_reenables_same_coordinator_without_stale_ram_hold(self):
        reader = Reader({'https://docs.example/a': dict(status=429, retry_after=1)})
        coordinator = self.coordinator(reader=reader)
        coordinator.run('synthetic')
        self.clock.value += 1
        self.release(self.pauses.active(self.scope))
        reader.replies = {}
        self.assertEqual(coordinator.run('synthetic')['status'], 'READ_TARGET_MET')

    def test_provider_pause_skips_search_but_allows_distinct_provider(self):
        provider = Provider('p1', AccessFailure('RATE_LIMITED', 1))
        self.coordinator(provider=provider).run('synthetic')
        fallback = Provider('p2', [hit()])
        report = ResearchCoordinator([provider, fallback], Reader(), resolver=dns,
                                     pauses=ResearchPauses(self.path)).run('synthetic')
        self.assertEqual(provider.calls, 1)
        self.assertEqual(report['providers'][0]['status'], 'RETRY_WAIT')
        self.assertEqual(report['status'], 'READ_TARGET_MET')
        self.assertIsNotNone(self.pauses.active(provider_scope('p1')))

    def test_denial_and_login_do_not_turn_into_repeated_http_calls(self):
        for reply in [dict(status=403), dict(status=200, media_type='text/html', body=b'<form><input type="password"></form>')]:
            with self.subTest(reply=reply):
                reader = Reader({'https://docs.example/a': reply})
                self.coordinator(reader=reader).run('synthetic')
                self.coordinator(reader=reader).run('synthetic')
                self.assertEqual(len(reader.calls), 1)
                self.release(self.pauses.active(self.scope))

    def test_redirect_to_paused_origin_is_blocked_before_target_connection(self):
        self.pauses.pause([origin_scope('cdn.example.com', 443)], reason='ACCESS_DENIED')
        connector = FakeConnector({(PUBLIC, '/'): redirect('https://cdn.example.com/'), (OTHER_PUBLIC, '/'): ok()})
        coordinator = ResearchCoordinator([Provider('p', [Hit('https://docs.example.com/', 'fixture')])],
                                         WebReader(DNS, connector), resolver=DNS, pauses=self.pauses)
        report = coordinator.run('synthetic')
        self.assertEqual(report['sources'][0]['state'], 'RETRY_WAIT')
        self.assertEqual(len(connector.calls), 1)

    def test_429_after_redirect_commits_initial_and_final_origin_pauses(self):
        connector = FakeConnector({(PUBLIC, '/'): redirect('https://cdn.example.com/'),
            (OTHER_PUBLIC, '/'): RawResponse(429, (('Retry-After', 'invalid'),), b'', True)})
        c = ResearchCoordinator([Provider('p', [Hit('https://docs.example.com/', 'fixture')])],
                               WebReader(DNS, connector), resolver=DNS, pauses=self.pauses)
        c.run('synthetic')
        for host in ('docs.example.com', 'cdn.example.com'):
            self.assertTrue(self.pauses.active(origin_scope(host, 443))['review_required'])
        self.assertEqual(self.pauses.inspect()['audit_events'], 2)

    def test_storage_failure_aborts_before_any_provider(self):
        provider = Provider('p', [hit()])
        coordinator = self.coordinator(provider=provider)
        with patch.object(self.pauses, 'active', side_effect=PauseStorageError('PAUSE_STORAGE_UNAVAILABLE')):
            with self.assertRaises(PauseStorageError): coordinator.run('synthetic')
        self.assertEqual(provider.calls, 0)
        with self.assertRaises(PauseStorageError): coordinator.run('synthetic')
        self.assertEqual(provider.calls, 0)

    def test_failed_pause_write_stops_fallback_and_latches_fault(self):
        provider = Provider('p1', AccessFailure('RATE_LIMITED'))
        fallback = Provider('p2', [hit()])
        c = ResearchCoordinator([provider, fallback], Reader(), resolver=dns, pauses=self.pauses)
        with patch.object(self.pauses, 'pause', side_effect=PauseStorageError('PAUSE_STORAGE_UNAVAILABLE')):
            with self.assertRaises(PauseStorageError): c.run('synthetic')
        self.assertEqual(fallback.calls, 0)
        with self.assertRaises(PauseStorageError): c.run('synthetic')
        self.assertEqual(provider.calls, 1)

    def test_corrupt_record_is_fatal_not_an_empty_gate(self):
        record = self.pauses.pause([self.scope], reason='ACCESS_DENIED')[0]
        with self.pauses._connection() as db:
            db.execute('UPDATE pauses SET body=? WHERE id=?', ('{"scope":{}}', record['id']))
        with self.assertRaises(PauseStorageError): self.pauses.active(self.scope)

    def test_backward_or_nonfinite_clock_cannot_release_early(self):
        record = self.pauses.pause([self.scope], reason='ACCESS_DENIED')[0]
        self.clock.value -= 1
        with self.assertRaisesRegex(ContractError, 'PAUSE_CLOCK_REGRESSION'): self.release(record)
        self.clock.value = float('nan')
        with self.assertRaisesRegex(PauseStorageError, 'INVALID_PAUSE_CLOCK'): self.release(record)

    def test_strict_scope_delay_and_operator_validation(self):
        for scope in ({'kind':'unknown'}, {'kind':'provider','provider_id':'with space'}, {'kind':'origin','host':'UPPER','port':443}):
            with self.assertRaises(ContractError): self.pauses.pause([scope], reason='ACCESS_DENIED')
        for delay in (True, -1, 86401, 1.2):
            with self.assertRaises(ContractError): self.pauses.pause([self.scope], reason='RATE_LIMITED', retry_after=delay)
        record = self.pauses.pause([self.scope], reason='ACCESS_DENIED')[0]
        for actor in ('', '\ud800', 'a'*201):
            with self.assertRaises(ContractError):
                self.pauses.release(record['id'], expected_revision=record['revision'], actor=actor, reason='test')
        self.assertIsNotNone(self.pauses.active(self.scope))

    def test_process_exit_after_commit_keeps_pause_and_release_audit(self):
        code = '''import os,sys
from eidolon_core.research_pauses import ResearchPauses,provider_scope
p=ResearchPauses(sys.argv[1])
r=p.pause([provider_scope('child')],reason='ACCESS_DENIED')[0]
if sys.argv[2]=='release': p.release(r['id'],expected_revision=r['revision'],actor='child',reason='test')
os._exit(71)
'''
        for operation in ('pause', 'release'):
            path = Path(self.temp.name) / (operation+'.sqlite3')
            result = subprocess.run([sys.executable, '-c', code, str(path), operation], capture_output=True, text=True)
            self.assertEqual(result.returncode, 71, result.stderr)
            report = ResearchPauses(path).inspect()
            self.assertEqual(report['pauses'][0]['status'], 'ACTIVE' if operation=='pause' else 'RELEASED')
            self.assertEqual(report['audit_events'], 1 if operation=='pause' else 2)

    def test_cli_inspects_and_releases_without_constructing_runtime(self):
        record = self.pauses.pause([self.scope], reason='ACCESS_DENIED')[0]
        with patch('eidolon_core.cli.Runtime', side_effect=AssertionError('no runtime')):
            for args in (['research-pauses'], ['research-release', record['id'], '--revision','1','--actor','test','--reason','reviewed']):
                out, err = io.StringIO(), io.StringIO()
                with redirect_stdout(out), redirect_stderr(err):
                    code = main(['--state', self.temp.name, *args])
                self.assertEqual((code, err.getvalue()), (0, ''))
                self.assertFalse(json.loads(out.getvalue())['authorizes_execution'])
        self.assertFalse((Path(self.temp.name) / 'missions.sqlite3').exists())

    def test_missing_pause_cli_does_not_create_empty_database(self):
        path = Path(self.temp.name) / 'absent'
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertEqual(main(['--state', str(path), 'research-pauses']), 2)
        self.assertFalse(path.exists())

    def test_provider_unavailable_with_delay_also_persists_the_wait(self):
        provider = Provider('p1', AccessFailure('UNAVAILABLE', 30))
        c = self.coordinator(provider=provider)
        c.run('synthetic')
        self.assertEqual(self.pauses.active(provider_scope('p1'))['reason'], 'RETRY_WAIT')
        c.run('synthetic')
        self.assertEqual(provider.calls, 1)

    def test_failed_origin_pause_write_does_not_continue_reading(self):
        reader = Reader({'https://docs.example/a': dict(status=429)})
        provider = Provider('p1', [hit(), hit('b')])
        c = self.coordinator(provider=provider, reader=reader)
        with patch.object(self.pauses, 'pause', side_effect=PauseStorageError('PAUSE_STORAGE_UNAVAILABLE')):
            with self.assertRaises(PauseStorageError): c.run('synthetic')
        self.assertEqual(len(reader.calls), 1)
        with self.assertRaises(PauseStorageError): c.run('synthetic')
        self.assertEqual(len(reader.calls), 1)

    def test_slow_gate_lookup_cannot_start_a_provider_after_deadline(self):
        provider = Provider('p1', [hit()])
        c = self.coordinator(provider=provider, clock=self.clock)
        def slow_lookup(scope):
            self.clock.value += 31
            return None
        with patch.object(self.pauses, 'active', side_effect=slow_lookup):
            report = c.run('synthetic')
        self.assertEqual(report['status'], 'DEADLINE')
        self.assertEqual(provider.calls, 0)
