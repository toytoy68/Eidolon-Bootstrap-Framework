# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_web_reader.py
# Description : Raccordement HTTP à la recherche, délais et quotas sans Internet
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
import unittest
from unittest.mock import patch

from eidolon_core.contracts import ContractError, encode
from eidolon_core.research import Hit, ResearchCoordinator
from eidolon_core.web_reader import WebReader
from eidolon_core.web_transport import RawResponse, TransportLimits, WebTransportError, _retry_after
from tests.test_research import Clock, Provider
from tests.test_web_transport import DNS, POLICY, PUBLIC, OTHER_PUBLIC, FakeConnector, ok, redirect

URL = 'https://docs.example.com/'


class WebReaderTests(unittest.TestCase):
    def setup_reader(self, reply, **kwargs):
        connector = FakeConnector({(PUBLIC, '/'): reply})
        reader = WebReader(DNS, connector, transport_id='fixture/1', **kwargs)
        coordinator = ResearchCoordinator([Provider('fixture', [Hit(URL, 'fixture')])],
                                          reader, resolver=DNS)
        return coordinator, connector

    def test_receipt_is_preserved_and_cached_without_relabeling_observation_time(self):
        c, connector = self.setup_reader(ok())
        first = c.run('reference')['sources'][0]
        second = c.run('reference')['sources'][0]
        self.assertTrue(second['cache_hit'])
        self.assertEqual(first['retrieval'], second['retrieval'])
        self.assertEqual(first['body_sha256'], first['retrieval']['sha256'])
        self.assertEqual(first['observed_at'], first['retrieval']['observed_at'])
        self.assertEqual(len(connector.calls), 1)

    def test_http_status_and_retry_after_are_not_discarded(self):
        for status, state in [(403, 'ACCESS_DENIED'), (429, 'RATE_LIMITED'), (503, 'HTTP_ERROR')]:
            c, connector = self.setup_reader(RawResponse(status, (('Retry-After', '120'),), b'SECRET', True))
            clock = Clock(); c.clock = clock
            source = c.run('reference')['sources'][0]
            self.assertEqual((source['state'], source['http_status'], source['retry_after']), (state, status, 120))
            self.assertEqual(source['retrieval']['kind'], 'http_headers')
            self.assertNotIn('SECRET', encode(source))
            self.assertIsNone(source['text'])
            clock.value = 119; c.run('reference')
            self.assertEqual(len(connector.calls), 1)
            clock.value = 120; c.run('reference')
            self.assertEqual(len(connector.calls), 2)

    def test_retry_http_date_and_unbounded_or_malformed_values(self):
        now = datetime(2026, 10, 5, 16, tzinfo=timezone.utc)
        self.assertEqual(_retry_after(format_datetime(now + timedelta(seconds=120), usegmt=True), now), (120, False))
        self.assertEqual(_retry_after(format_datetime(now - timedelta(seconds=5), usegmt=True), now), (0, False))
        for text in ['999999999999999999999999', '86401', '-1', 'not a date']:
            self.assertEqual(_retry_after(text, now), (None, True))
            c, connector = self.setup_reader(RawResponse(429, (('Retry-After', text),), b'', True))
            clock = Clock(); c.clock = clock
            source = c.run('reference')['sources'][0]
            self.assertTrue(source['retry_review_required'])
            clock.value = 1_000_000; c.run('reference')
            self.assertEqual(len(connector.calls), 1)

    def test_redirect_with_retry_after_does_not_reach_location(self):
        response = RawResponse(302, (('Location', '/later'), ('Retry-After', '60')), b'', True)
        c, connector = self.setup_reader(response)
        source = c.run('reference')['sources'][0]
        self.assertEqual((source['state'], source['http_status']), ('HTTP_ERROR', 302))
        self.assertEqual(len(connector.calls), 1)

    def test_quota_on_redirected_domain_is_respected_for_later_direct_url(self):
        connector = FakeConnector({(PUBLIC, '/'): redirect('/quota'),
                                   (PUBLIC, '/quota'): RawResponse(429, (('Retry-After', '60'),), b'', True)})
        provider = Provider('fixture', [Hit(URL, 'redirect'), Hit(URL + 'quota', 'direct')])
        c = ResearchCoordinator([provider], WebReader(DNS, connector), resolver=DNS)
        r = c.run('reference')
        self.assertEqual(len(connector.calls), 2)
        self.assertEqual([s['state'] for s in r['sources']], ['RATE_LIMITED', 'RATE_LIMITED'])

    def test_transport_failures_keep_distinct_non_successful_states(self):
        for code, state in [('TLS_CERTIFICATE', 'TLS_ERROR'), ('TIMEOUT', 'TIMEOUT'),
                            ('TRUNCATED', 'TRUNCATED'), ('DESTINATION_REFUSED', 'POLICY_REFUSED'),
                            ('AMBIGUOUS_HEADER', 'INVALID_RESPONSE'), ('BODY_TOO_LARGE', 'TOO_LARGE')]:
            c, _ = self.setup_reader(WebTransportError(code))
            r = c.run('reference')
            self.assertEqual((r['status'], r['sources'][0]['state']), ('NO_READABLE_SOURCE', state))

    def test_alternate_redirect_cannot_recontact_a_rate_limited_host(self):
        connector = FakeConnector({(OTHER_PUBLIC, '/'): RawResponse(429, (('Retry-After', '120'),), b'', True),
                                   (PUBLIC, '/'): redirect('https://cdn.example.com/')})
        provider = Provider('fixture', [Hit('https://cdn.example.com/', 'quota'), Hit(URL, 'redirect')])
        c = ResearchCoordinator([provider], WebReader(DNS, connector), resolver=DNS)
        r = c.run('reference')
        self.assertEqual(len(connector.calls), 2)  # no third call to cdn
        self.assertEqual([s['state'] for s in r['sources']], ['RATE_LIMITED', 'RETRY_WAIT'])

    def test_late_receipt_is_kept_but_not_cached_or_reported_as_target_met(self):
        clock = Clock()
        c, connector = self.setup_reader(ok(), clock=clock, limits=TransportLimits(total_seconds=1, max_body_bytes=128_000))
        exchange = connector.exchange
        def late(**kwargs):
            result = exchange(**kwargs); clock.value += 2; return result
        connector.exchange = late
        r = c.run('reference')  # coordinator's own clock has NOT reached its 30s limit
        self.assertEqual((r['status'], r['readable_pages']), ('DEADLINE', 1))
        self.assertEqual(r['sources'][0]['text'], 'hello')
        c.run('reference')
        self.assertEqual(len(connector.calls), 2)

    def test_cancel_after_receipt_keeps_transport_provenance(self):
        c, connector = self.setup_reader(ok())
        r = c.run('reference', cancelled=lambda: bool(connector.calls))
        self.assertEqual((r['status'], r['readable_pages']), ('CANCELLED', 1))
        self.assertEqual(r['sources'][0]['retrieval']['status'], 200)

    def test_tampered_receipt_is_refused_without_read_success(self):
        c, _ = self.setup_reader(ok())
        good = c.reader.read(URL, POLICY)
        with patch.object(WebReader, 'read_guarded', return_value=replace(good, retrieval={**good.retrieval, 'sha256': 'wrong'})):
            r = c.run('reference')
        self.assertEqual((r['readable_pages'], r['sources'][0]['state']), (0, 'READER_ERROR'))

    def test_configuration_has_bounded_body_and_stable_identity(self):
        r = WebReader(DNS)
        with self.assertRaises(FrozenInstanceError): r.transport_id = 'other'
        self.assertNotEqual(r.reader_id, replace(r, transport_id='other/1').reader_id)
        with self.assertRaises(ContractError): WebReader(DNS, limits=TransportLimits())

    def test_complete_local_http_demo_without_dns_or_external_connection(self):
        from examples.research_http_demo import run_demo
        import socket
        original = socket.create_connection
        def local_only(address, *args, **kwargs):
            self.assertEqual(address[0], '127.0.0.1')
            return original(address, *args, **kwargs)
        with patch.object(socket, 'create_connection', side_effect=local_only):
            r = run_demo()
        self.assertEqual((r['http_requests'], r['report']['status']), (5, 'PARTIAL'))


if __name__ == '__main__':
    unittest.main()
