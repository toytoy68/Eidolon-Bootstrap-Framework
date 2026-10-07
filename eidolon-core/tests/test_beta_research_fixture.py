# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_beta_research_fixture.py
# Description : Recette recherches, copies d'archives et consultation réelle
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
from contextlib import closing
from http.client import HTTPConnection
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

from eidolon_core import beta_fixture, beta_research_fixture, preflight
from eidolon_core.archive_page import ArchivePages
from eidolon_core.client_sync import ClientSync
from eidolon_core.contracts import ContractError
from eidolon_core.http_api import ReadOnlyStore, ReadServer, read_token
from eidolon_core.research_archive import read_catalog
from eidolon_core.research_guard import ResearchGuard
from eidolon_core.research_runtime import ResearchRuntime
from eidolon_core.store import Store


class BetaResearchFixtureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'research-demo'

    def prepare(self):
        report = beta_fixture.create(self.root, profile='research-archives')
        self.assertEqual(report['status'], 'READY', report)
        self.manifest = json.loads((self.root / 'manifest.json').read_text())
        return report

    def test_real_missions_copied_evidence_and_read_only_pages(self):
        report = self.prepare()
        self.assertEqual(report['mission_count'], 3)
        self.assertEqual(report['receipt_count'], 0)
        self.assertEqual(self.manifest['active_runs_removed'], 0)
        self.assertTrue(self.manifest['exports_are_copies'])
        self.assertFalse(self.manifest['rotation_enabled'])
        store = ReadOnlyStore(self.root / 'state')
        token = read_token(self.root / 'read-token')
        self.assertNotIn(token, json.dumps(report) + json.dumps(self.manifest))
        for row in self.manifest['scenarios']:
            mission = ClientSync(store).snapshot(row['mission_id'])['snapshot']['mission']
            self.assertEqual(mission['status'], row['expected_status'])
            self.assertEqual(mission['outcome_status'], row['expected_outcome'])
        guard = ResearchGuard(self.root / 'state/research-fixture/guard', create=False)
        active_before = guard.path.read_bytes()
        catalog = read_catalog(self.root / 'archives')
        self.assertEqual((catalog['archive_count'], catalog['run_count']), (3, 3))
        pages = ArchivePages(store, self.root / 'archives')
        cursor, indices = None, []
        while True:
            page = pages.page(limit=1, cursor=cursor)
            indices.extend(i['index'] for i in page['items'])
            self.assertFalse(page['committed_status_known'])
            cursor = page['next_cursor']
            if cursor is None:
                break
        self.assertEqual(indices, [1, 2, 3])
        self.assertEqual(guard.path.read_bytes(), active_before)
        self.assertEqual(len(guard.inspect()['runs']), 3)
        self.assertEqual((self.root / 'archives').stat().st_mode & 0o777, 0o700)
        for file in (self.root / 'archives').glob('*'):
            self.assertEqual(file.stat().st_mode & 0o777, 0o600)
        succeeded = next(r for r in self.manifest['scenarios'] if r['expected_status'] == 'SUCCEEDED')
        runtime = ResearchRuntime(Store(self.root / 'state'))
        self.assertEqual(runtime.run(succeeded['mission_id'])['status'], 'SUCCEEDED')
        self.assertEqual(guard.path.read_bytes(), active_before)

    def test_loopback_server_serves_fixture_missions_and_archive_metadata(self):
        self.prepare()
        token = read_token(self.root / 'read-token')
        report = preflight.inspect(self.root / 'state', self.root / 'read-token',
                                   research_archives=self.root / 'archives')
        self.assertEqual(report['status'], 'PASS')
        server = ReadServer(self.root / 'state', token, port=0, research_archives=self.root / 'archives')
        thread = threading.Thread(target=server.serve_forever, kwargs={'poll_interval': .01})
        thread.start()
        try:
            for route, field in (('/v1/missions', 'items'), ('/v1/research-archives', 'items')):
                with closing(HTTPConnection('127.0.0.1', server.server_port, timeout=3)) as conn:
                    conn.request('POST', route, body='{}', headers={
                        'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'})
                    response = conn.getresponse()
                    result = json.loads(response.read())
                    self.assertEqual(response.status, 200)
                    self.assertEqual(len(result[field]), 3)
                    self.assertFalse(result['authorizes_execution'])
        finally:
            server.shutdown(); thread.join(5); server.server_close()

    def test_partial_export_failure_keeps_marker_and_original_evidence(self):
        original = beta_research_fixture.validate_export
        count = 0
        def fail_second(*args):
            nonlocal count
            count += 1
            if count == 2:
                raise OSError('PRIVATE-error-canary')
            return original(*args)
        with patch.object(beta_research_fixture, 'validate_export', side_effect=fail_second):
            report = beta_fixture.create(self.root, profile='research-archives')
        self.assertEqual(report['status'], 'INCOMPLETE')
        self.assertNotIn('PRIVATE-error-canary', json.dumps(report))
        self.assertTrue((self.root / 'state/BETA-PREPARATION-INCOMPLETE').exists())
        self.assertEqual(len(list((self.root / 'archives').glob('*.json'))), 1)
        with self.assertRaisesRegex(ContractError, 'BETA_PREPARATION_INCOMPLETE'):
            ReadOnlyStore(self.root / 'state')
        guard = ResearchGuard(self.root / 'state/research-fixture/guard', create=False)
        self.assertEqual(len(guard.inspect()['runs']), 3)
        self.assertFalse((self.root / 'read-token').exists())
        self.assertEqual(beta_fixture.create(self.root, profile='research-archives')['code'], 'DESTINATION_EXISTS')

    def test_existing_destination_and_unknown_profile_never_modify_data(self):
        self.root.mkdir()
        sentinel = self.root / 'keep'; sentinel.write_bytes(b'unchanged')
        self.assertEqual(beta_fixture.create(self.root, profile='research-archives')['code'], 'DESTINATION_EXISTS')
        for profile in ('not-a-profile', None, [], True):
            self.assertEqual(beta_fixture.create(self.root / 'new', profile=profile)['code'], 'INVALID_PROFILE')
        self.assertEqual(list(self.root.iterdir()), [sentinel])
        self.assertEqual(sentinel.read_bytes(), b'unchanged')

    def test_index_failure_cannot_publish_ready_state(self):
        with patch.object(beta_research_fixture, 'write_index', side_effect=OSError('private')):
            report = beta_fixture.create(self.root, profile='research-archives')
        self.assertEqual(report['status'], 'INCOMPLETE')
        self.assertTrue((self.root / 'state/BETA-PREPARATION-INCOMPLETE').exists())
        self.assertFalse((self.root / 'manifest.json').exists())

    def test_actual_cli_json_then_human_refusal(self):
        args = [sys.executable, '-m', 'eidolon_core.beta_fixture', '--output', str(self.root),
                '--profile', 'research-archives']
        done = subprocess.run(args, capture_output=True, text=True, timeout=20)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(json.loads(done.stdout)['code'], 'RESEARCH_FIXTURE_READY')
        refused = subprocess.run([*args, '--format', 'human'], capture_output=True, text=True, timeout=10)
        self.assertEqual(refused.returncode, 2)
        self.assertIn('DESTINATION_EXISTS', refused.stdout)
        self.assertNotIn(str(self.root), refused.stdout + refused.stderr)
