# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_archive_page.py
# Description : Catalogue HTTP privé, pagination et refus sans mutation
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
from contextlib import redirect_stdout, closing
from copy import deepcopy
from http.client import HTTPConnection
import io
import json
import os
from pathlib import Path
import threading
import unittest
from unittest.mock import patch

from eidolon_core import http_api, preflight, research_archive
from eidolon_core.archive_page import ArchivePages, ArchivePageError
from eidolon_core.contracts import digest, encode
from eidolon_core.store import Store
from tests import test_research_archive as fixtures

TOKEN = 'synthetic_archive_token_' + 'x' * 32


class ArchivePageTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.ArchiveTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root = self.fixture.root
        self.directory = self.fixture.directory
        # Three real exports, chained from real guard records with private query canaries.
        (self.directory / self.fixture.name).unlink()
        previous = '0' * 64
        for index, record in enumerate(self.fixture.records, 1):
            meta = self.fixture.export([record], index=index, previous=previous)
            name = f'research-archive-{index:06d}.json'
            self.fixture.save(meta, name)
            verified = research_archive.validate_export(encode(meta).encode(), name)
            previous = digest(verified['entry'])
        self.store = Store(self.root / 'state')
        self.server = http_api.ReadServer(self.store.directory, TOKEN, port=0,
                                          research_archives=self.directory)
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={'poll_interval': .01})
        self.thread.start()
        self.addCleanup(self.stop)

    def stop(self):
        self.server.shutdown()
        self.thread.join(5)
        self.server.server_close()

    def request(self, data=None, *, path='/v1/research-archives', method='POST', auth=True, headers=None, body=None):
        fields = {'Content-Type': 'application/json'}
        if auth:
            fields['Authorization'] = 'Bearer ' + TOKEN
        fields.update(headers or {})
        if body is None and method == 'POST':
            body = json.dumps({} if data is None else data)
        with closing(HTTPConnection('127.0.0.1', self.server.server_port, timeout=3)) as conn:
            conn.request(method, path, body=body, headers=fields)
            response = conn.getresponse()
            return response.status, dict(response.getheaders()), json.loads(response.read())

    def test_complete_pagination_preserves_files_and_excludes_private_data(self):
        before = self.fixture.files()
        seen, cursor = [], None
        for index in range(3):
            status, headers, page = self.request({'limit': 1, 'cursor': cursor})
            self.assertEqual(status, 200)
            self.assertEqual(page['status'], 'PAGE')
            self.assertEqual(page['archive_count'], 3)
            self.assertEqual(page['run_count'], 3)
            self.assertEqual(page['items'][0]['index'], index + 1)
            self.assertEqual(page['has_more'], index < 2)
            self.assertEqual(headers['Cache-Control'], 'no-store')
            self.assertIn('Content-Security-Policy', headers)
            for flag in ('authenticity_verified', 'live_journal_checked', 'committed_status_known',
                         'authorizes_execution', 'request_sent'):
                self.assertIs(page[flag], False)
            for canary in ('PRIVATE_QUERY_CANARY', 'jean@example.invalid', 'query_sha256',
                           self.fixture.guard.guard_id, str(self.root), 'operation_id', 'm-' + 'b' * 32):
                self.assertNotIn(canary, encode(page))
            seen.extend(x['file'] for x in page['items'])
            cursor = page['next_cursor']
        self.assertIsNone(cursor)
        self.assertEqual(len(set(seen)), 3)
        self.assertEqual(self.fixture.files(), before)
        self.assertFalse((self.directory / 'liste.md').exists())

    def test_authentication_and_origin_precede_archive_read(self):
        with patch.object(self.server.archive_pages, 'page', side_effect=AssertionError('must not read')):
            self.assertEqual(self.request(auth=False)[0], 401)
            self.assertEqual(self.request(headers={'Authorization': 'Bearer wrong'})[0], 401)
            self.assertEqual(self.request(headers={'Origin': 'https://evil.invalid'})[0], 403)
            self.assertEqual(self.request(headers={'Host': 'evil.invalid'})[0], 403)

    def test_only_fixed_post_route_no_raw_export_or_index(self):
        for path in ('/v1/research-archives', '/v1/research-archives/research-archive-000001.json',
                     '/liste.md', '/research-archive-000001.json', '/v1/research-archives?directory=/tmp'):
            self.assertEqual(self.request(path=path, method='GET')[0], 404)
        self.assertEqual(self.request(method='DELETE')[0], 405)
        self.assertEqual(self.request({'directory': str(self.root)})[2]['error'], 'UNKNOWN_FIELD')

    def test_strict_body_and_cursor_validation(self):
        for body in ('{"limit":1,"limit":2}', '{"limit":NaN}', '[]'):
            self.assertEqual(self.request(body=body)[2]['error'], 'INVALID_JSON')
        for limit in (True, 0, 101, '1', 1.5):
            self.assertEqual(self.request({'limit': limit})[2]['error'], 'INVALID_PAGE_LIMIT')
        _, _, page = self.request({'limit': 1})
        for field, value in (('version', True), ('store_id', '../private'), ('catalog_sha256', 'bad'),
                             ('after_index', True), ('after_index', 0), ('after_index', 1001)):
            cursor = deepcopy(page['next_cursor']); cursor[field] = value
            self.assertEqual(self.request({'cursor': cursor})[2]['error'], 'INVALID_ARCHIVE_CURSOR')
        cursor = deepcopy(page['next_cursor']); cursor['after_index'] = 3
        self.assertEqual(self.request({'cursor': cursor})[2]['error'], 'INVALID_ARCHIVE_CURSOR')

    def test_changed_catalog_requires_reset_with_no_mixed_items(self):
        _, _, first = self.request({'limit': 1})
        # Missing tail is not authenticated by this standalone reader, but changes its generation.
        (self.directory / 'research-archive-000003.json').unlink()
        status, _, result = self.request({'cursor': first['next_cursor']})
        self.assertEqual(status, 200)
        self.assertEqual(result['status'], 'RESET_REQUIRED')
        self.assertEqual(result['reason'], 'CATALOG_CHANGED')
        self.assertEqual(result['items'], [])
        self.assertFalse(result['has_more'])
        self.assertIsNone(result['next_cursor'])
        self.assertEqual(self.request()[2]['archive_count'], 2)

    def test_other_store_cursor_resets(self):
        _, _, first = self.request({'limit': 1})
        cursor = first['next_cursor']; cursor['store_id'] = 's-' + 'f' * 32
        self.assertEqual(self.request({'cursor': cursor})[2]['reason'], 'STORE_CHANGED')

    def test_corrupt_later_archive_refuses_even_first_page(self):
        path = self.directory / 'research-archive-000003.json'
        path.write_text('{"private":"hidden-canary"}')
        before = self.fixture.files()
        status, _, result = self.request({'limit': 1})
        self.assertEqual(status, 503)
        self.assertEqual(result['error'], 'ARCHIVES_UNAVAILABLE')
        self.assertNotIn('items', result)
        self.assertNotIn('hidden-canary', encode(result))
        self.assertEqual(self.fixture.files(), before)

    def test_missing_unconfigured_and_empty_are_distinct(self):
        for path in self.directory.iterdir():
            path.unlink()
        self.assertEqual(self.request()[2]['archive_count'], 0)
        self.directory.rmdir()
        self.assertEqual(self.request()[2]['error'], 'ARCHIVES_UNAVAILABLE')
        self.assertFalse(self.directory.exists())
        self.server.archive_pages = None
        self.assertEqual(self.request()[0], 404)
        self.assertEqual(self.request()[2]['error'], 'ARCHIVES_NOT_CONFIGURED')

    def test_fifo_and_symlink_refused_without_content_read(self):
        path = self.directory / 'research-archive-000001.json'
        original = path.read_bytes(); path.unlink()
        os.mkfifo(path, 0o600)
        self.assertEqual(self.request()[2]['error'], 'ARCHIVES_UNAVAILABLE')
        path.unlink()
        target = self.root / 'private-target'; target.write_bytes(original); target.chmod(0o600)
        path.symlink_to(target)
        self.assertEqual(self.request()[2]['error'], 'ARCHIVES_UNAVAILABLE')
        self.assertEqual(target.read_bytes(), original)

    def test_busy_archive_reader_keeps_health_available(self):
        with self.server.archive_pages.lock:
            self.assertEqual(self.request()[2]['error'], 'ARCHIVES_BUSY')
            self.assertEqual(self.request(method='GET', path='/v1/health')[0], 200)
        self.assertEqual(self.request()[0], 200)

    def test_cooperative_deadline_refuses_instead_of_partial_page_and_unlocks(self):
        before = self.fixture.files()
        with patch('eidolon_core.research_archive.time') as clock:
            clock.monotonic.side_effect = [10, 10, 10, 13]
            self.assertEqual(self.request()[2]['error'], 'ARCHIVES_UNAVAILABLE')
        self.assertEqual(self.request()[0], 200)
        self.assertEqual(self.fixture.files(), before)

    def test_review_guard_and_store_identity_are_rechecked_after_catalog_read(self):
        original = research_archive.read_catalog
        marker = self.store.directory / 'RECOVERY-REVIEW-ONLY'
        def changed(*args, **kwargs):
            result = original(*args, **kwargs)
            marker.write_text('synthetic')
            return result
        with patch('eidolon_core.archive_page.read_catalog', side_effect=changed):
            status, _, result = self.request()
        self.assertEqual(status, 503)
        self.assertNotIn('items', result)
        marker.unlink()
        self.assertEqual(self.request()[0], 200)

    def test_preflight_and_cli_check_validate_archives_without_binding_or_writes(self):
        token = self.root / 'token'; token.write_text(TOKEN); token.chmod(0o600)
        before = self.fixture.files()
        output = io.StringIO()
        with patch('socket.socket', side_effect=AssertionError('no bind')), redirect_stdout(output):
            result = http_api.main(['--state', str(self.store.directory), '--token-file', str(token),
                                    '--research-archives', str(self.directory), '--check'])
        self.assertEqual(result, 0)
        report = json.loads(output.getvalue())
        self.assertIn({'name': 'archives', 'status': 'PASS', 'code': 'ARCHIVES_READABLE'}, report['checks'])
        self.assertEqual(self.fixture.files(), before)
        report = preflight.inspect(self.store.directory, token, research_archives=self.root / 'missing')
        self.assertEqual(report['status'], 'FAIL')
        self.assertNotIn(str(self.root), preflight.render(report, 'human'))
        self.assertFalse((self.root / 'missing').exists())

    def test_startup_refuses_missing_or_symlinked_archive_directory(self):
        target = self.root / 'archive-link'; target.symlink_to(self.directory, target_is_directory=True)
        for path in (target, self.root / 'missing'):
            with self.assertRaises(research_archive.ArchiveError):
                http_api.ReadServer(self.store.directory, TOKEN, port=0, research_archives=path)
        self.assertFalse((self.root / 'missing').exists())

    def test_invalid_read_budgets_refused_before_disk_access(self):
        for value in (True, 0, -1, 61, float('nan'), float('inf'), '1'):
            with self.assertRaisesRegex(research_archive.ArchiveError, 'INVALID_ARCHIVE_READ_BUDGET'):
                research_archive.read_catalog(self.root / 'missing', time_budget_seconds=value)
