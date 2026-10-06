# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_research_availability.py
# Description : Capacité active, provenance distincte et diagnostic de découverte
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
from concurrent.futures import ThreadPoolExecutor
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from eidolon_core.contracts import ContractError
from eidolon_core.research import AccessFailure, Hit, ResearchCoordinator, ResearchLimits
from eidolon_core.research_pauses import ResearchPauses, PauseStorageError, origin_scope, provider_scope
from tests.test_research import Provider, Reader, dns, hit


class ActiveCapacityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'pauses.sqlite3'
        self.pauses = ResearchPauses(self.path, clock=lambda: 1000)
        self.scope = origin_scope('old.example', 443)

    def release(self, row):
        return self.pauses.release(row['id'], expected_revision=row['revision'],
                                   actor='synthetic-reviewer', reason='explicit fixture review')

    def test_release_frees_capacity_but_preserves_revision_history(self):
        with patch('eidolon_core.research_pauses.MAX_RECORDS', 1):
            first = self.pauses.pause([self.scope], reason='ACCESS_DENIED')[0]
            self.release(first)
            new_scope = origin_scope('new.example', 443)
            self.pauses.check_capacity([new_scope])
            second = self.pauses.pause([new_scope], reason='ACCESS_DENIED')[0]
            self.assertEqual(len(self.pauses.inspect()['pauses']), 2)
            self.assertEqual(self.pauses.inspect()['audit_events'], 3)
            with self.assertRaisesRegex(PauseStorageError, 'PAUSE_CAPACITY_REACHED'):
                self.pauses.pause([self.scope], reason='ACCESS_DENIED')
            self.release(second)
            again = ResearchPauses(self.path, clock=lambda: 1000).pause([self.scope], reason='ACCESS_DENIED')[0]
            self.assertEqual(again['revision'], 3)
            with self.assertRaisesRegex(ContractError, 'STALE_PAUSE'):
                self.release(first)

    def test_capacity_preflight_does_not_poison_same_coordinator(self):
        provider, reader = Provider('p1', [hit()]), Reader()
        coordinator = ResearchCoordinator([provider], reader, resolver=dns, pauses=self.pauses)
        with patch('eidolon_core.research_pauses.MAX_RECORDS', 1):
            row = self.pauses.pause([self.scope], reason='ACCESS_DENIED')[0]
            for _ in range(2):
                with self.assertRaisesRegex(PauseStorageError, '^PAUSE_CAPACITY_REACHED'):
                    coordinator.run('synthetic')
            self.assertEqual(provider.calls, 0)
            self.release(row)
            self.assertEqual(reader.calls, [])  # release alone sends nothing
            self.assertEqual(coordinator.run('synthetic')['status'], 'READ_TARGET_MET')
        self.assertEqual(provider.calls, 1)

    def test_released_scope_needs_a_slot_again(self):
        row = self.pauses.pause([self.scope], reason='ACCESS_DENIED')[0]
        self.release(row)
        other = origin_scope('other.example', 443)
        self.pauses.pause([other], reason='ACCESS_DENIED')
        before = self.pauses.inspect()
        with patch('eidolon_core.research_pauses.MAX_RECORDS', 1):
            with self.assertRaisesRegex(PauseStorageError, 'PAUSE_CAPACITY_REACHED'):
                self.pauses.check_capacity([self.scope])
            self.pauses.check_capacity([other, other])
        self.assertEqual(self.pauses.inspect(), before)

    def test_redirect_rollback_preserves_released_record(self):
        row = self.pauses.pause([self.scope], reason='ACCESS_DENIED')[0]
        self.release(row)
        before = self.pauses.inspect()
        with patch('eidolon_core.research_pauses.MAX_RECORDS', 1):
            with self.assertRaisesRegex(PauseStorageError, 'PAUSE_CAPACITY_REACHED'):
                self.pauses.pause([self.scope, origin_scope('cdn.example', 443)], reason='ACCESS_DENIED')
        self.assertEqual(self.pauses.inspect(), before)

    def test_slot_taken_after_preflight_blocks_observation_without_partial_write(self):
        with patch('eidolon_core.research_pauses.MAX_RECORDS', 1):
            self.pauses.check_capacity([self.scope])
            competing = ResearchPauses(self.path, clock=lambda: 1000)
            competing.pause([provider_scope('other')], reason='ACCESS_DENIED')
            before = self.pauses.inspect()
            with self.assertRaisesRegex(PauseStorageError, 'PAUSE_CAPACITY_REACHED'):
                self.pauses.pause([self.scope], reason='ACCESS_DENIED')
            self.assertEqual(self.pauses.inspect(), before)

    def test_actual_storage_failure_keeps_conservative_latch(self):
        provider = Provider('p1', [hit()])
        coordinator = ResearchCoordinator([provider], Reader(), resolver=dns, pauses=self.pauses)
        with patch.object(self.pauses, 'check_capacity', side_effect=PauseStorageError('PAUSE_STORAGE_UNAVAILABLE')):
            with self.assertRaises(PauseStorageError):
                coordinator.run('synthetic')
        with self.assertRaisesRegex(PauseStorageError, 'prior write uncertain'):
            coordinator.run('synthetic')
        self.assertEqual(provider.calls, 0)

    def test_two_processes_cannot_commit_into_the_same_last_slot(self):
        script = '''
import sys, time
from pathlib import Path
from eidolon_core import research_pauses as m
m.MAX_RECORDS = 1
store = m.ResearchPauses(sys.argv[1], clock=lambda: 1000)
gate = Path(sys.argv[1]).parent
(gate / sys.argv[2]).touch()
deadline = time.monotonic() + 5
while not all((gate / name).exists() for name in ('a', 'b')):
    if time.monotonic() >= deadline: raise RuntimeError('fixture barrier timeout')
    time.sleep(0.005)
try:
    store.pause([m.provider_scope(sys.argv[2])], reason='ACCESS_DENIED')
    print('COMMITTED')
except m.PauseStorageError as exc:
    print(str(exc).split(':')[0])
'''
        def run(name):
            result = subprocess.run([sys.executable, '-c', script, str(self.path), name],
                                    capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stderr)
            return result.stdout.strip()
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(run, ('a', 'b')))
        self.assertCountEqual(results, ['COMMITTED', 'PAUSE_CAPACITY_REACHED'])
        self.assertEqual(len(self.pauses.inspect()['pauses']), 1)
        self.assertEqual(self.pauses.inspect()['audit_events'], 1)

    def test_corrupt_historical_status_is_not_free_capacity(self):
        row = self.pauses.pause([self.scope], reason='ACCESS_DENIED')[0]
        self.release(row)
        with self.pauses._connection() as db:
            db.execute("UPDATE pauses SET body=replace(body, 'RELEASED', 'INVALID')")
        with self.assertRaisesRegex(PauseStorageError, 'INVALID_PAUSE_RECORD'):
            self.pauses.check_capacity([provider_scope('p')])


class ResearchContentTests(unittest.TestCase):
    def coordinator(self, hits, reader=None, **kwargs):
        return ResearchCoordinator([Provider('p1', hits)], reader or Reader(), resolver=dns, **kwargs)

    def test_identical_bodies_keep_receipts_without_meeting_two_page_target(self):
        urls = ['https://docs.example/a', 'https://docs.example/a?utm_source=x',
                'https://other.example/item?id=2']
        reader = Reader()
        report = self.coordinator([Hit(url, 'fixture') for url in urls], reader).run('synthetic', required_pages=3)
        self.assertEqual((report['status'], report['readable_pages']), ('PARTIAL', 1))
        self.assertEqual(reader.calls, urls)
        self.assertEqual([s['state'] for s in report['sources']], ['READ', 'DUPLICATE_CONTENT', 'DUPLICATE_CONTENT'])
        for source in report['sources'][1:]:
            self.assertEqual(source['duplicate_of'], report['sources'][0]['id'])
            self.assertIsNotNone(source['text'])
            self.assertIn('body_sha256', source)
            self.assertEqual(len(source['found_by']), 1)

    def test_functional_parameters_and_different_contents_are_preserved(self):
        urls = ['https://docs.example/item?id=1', 'https://docs.example/item?id=2']
        reader = Reader({url: {'body': f'document {i}'.encode()} for i, url in enumerate(urls)})
        report = self.coordinator([Hit(url, 'fixture') for url in urls], reader).run('synthetic', required_pages=2)
        self.assertEqual(report['status'], 'READ_TARGET_MET')
        self.assertEqual(reader.calls, urls)
        self.assertEqual(len({s['url_sha256'] for s in report['sources']}), 2)
        self.assertEqual(report['sources'][0]['url'], report['sources'][1]['url'])

    def test_cached_duplicates_are_recomputed_for_each_report(self):
        provider, reader = Provider('p1', [hit('a'), hit('b')]), Reader()
        coordinator = ResearchCoordinator([provider], reader, resolver=dns)
        for _ in range(2):
            report = coordinator.run('synthetic', required_pages=2)
            self.assertEqual(report['readable_pages'], 1)
            self.assertEqual(report['sources'][1]['state'], 'DUPLICATE_CONTENT')
        self.assertTrue(all(s['cache_hit'] for s in report['sources']))
        self.assertEqual(len(reader.calls), 2)
        provider.hits = [hit('b')]
        report = coordinator.run('synthetic')
        self.assertEqual(report['sources'][0]['state'], 'READ')
        self.assertNotIn('duplicate_of', report['sources'][0])
        self.assertEqual(len(reader.calls), 2)

    def test_same_final_url_remains_duplicate_even_with_changed_body(self):
        reader = Reader({hit('b').url: {'url': hit('a').url, 'body': b'changed'}})
        report = self.coordinator([hit('a'), hit('b')], reader).run('synthetic', required_pages=2)
        self.assertEqual(report['readable_pages'], 1)
        self.assertEqual(report['sources'][1]['state'], 'DUPLICATE_FINAL')

    def test_near_duplicates_are_not_claimed_detected(self):
        reader = Reader({hit('b').url: {'body': b'Ne pas confirmer sans preuve. '}})
        report = self.coordinator([hit('a'), hit('b')], reader).run('synthetic', required_pages=2)
        self.assertEqual(report['readable_pages'], 2)


class DiscoveryStatusTests(unittest.TestCase):
    def report(self, providers, reader=None, **kwargs):
        return ResearchCoordinator(providers, reader or Reader(), resolver=dns, **kwargs).run('synthetic')

    def test_empty_and_unavailable_are_distinct_without_changing_read_status(self):
        for replies, expected in [([[], []], 'EMPTY'),
                                  ([AccessFailure('UNAVAILABLE'), RuntimeError('private')], 'UNAVAILABLE'),
                                  ([[], AccessFailure('UNAVAILABLE')], 'INCOMPLETE')]:
            with self.subTest(expected=expected):
                report = self.report([Provider(f'p{i}', reply) for i, reply in enumerate(replies)])
                self.assertEqual(report['status'], 'NO_READABLE_SOURCE')
                self.assertEqual(report['discovery_status'], expected)
                self.assertNotIn('private', str(report))

    def test_hits_remain_discovered_when_policy_or_reader_refuses(self):
        for found, reader in [([hit()], Reader({hit().url: AccessFailure('UNAVAILABLE')})),
                              ([Hit('http://127.0.0.1/', 'local')], Reader())]:
            report = self.report([Provider('p', found)], reader)
            self.assertEqual(report['status'], 'NO_READABLE_SOURCE')
            self.assertEqual(report['discovery_status'], 'HITS_FOUND')

    def test_unvisited_providers_and_cancellation_never_claim_empty_or_unavailable(self):
        for reply in [[], AccessFailure('UNAVAILABLE')]:
            report = self.report([Provider('p1', reply), Provider('p2', [hit()])],
                                 limits=ResearchLimits(providers=1))
            self.assertEqual(report['discovery_status'], 'INCOMPLETE')
        coordinator = ResearchCoordinator([Provider('p', [])], Reader(), resolver=dns)
        report = coordinator.run('synthetic', cancelled=lambda: True)
        self.assertEqual((report['status'], report['discovery_status']), ('CANCELLED', 'INCOMPLETE'))

    def test_invalid_search_batch_is_unavailable_not_empty(self):
        for replies in [[object()], [hit()] * 11]:
            report = self.report([Provider('p', replies)])
            self.assertEqual(report['discovery_status'], 'UNAVAILABLE')
            self.assertEqual(report['sources'], [])

    def test_persistent_provider_pause_reports_unavailable_without_sending(self):
        with tempfile.TemporaryDirectory() as root:
            pauses = ResearchPauses(Path(root) / 'pauses.sqlite3')
            pauses.pause([provider_scope('p')], reason='ACCESS_DENIED')
            provider = Provider('p', [])
            report = self.report([provider], pauses=pauses)
            self.assertEqual(report['discovery_status'], 'UNAVAILABLE')
            self.assertEqual(provider.calls, 0)


if __name__ == '__main__':
    unittest.main()
