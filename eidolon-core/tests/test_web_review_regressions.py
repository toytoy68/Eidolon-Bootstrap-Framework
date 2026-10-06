# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_web_review_regressions.py
# Description : Régressions D1/D2 de la contre-revue HTTP Claude G008
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
from unittest import TestCase
from unittest.mock import MagicMock, patch
from eidolon_core.contracts import ContractError
from eidolon_core.egress import WebPolicy
from eidolon_core.research import AccessFailure, Hit, ResearchCoordinator
from eidolon_core.web_reader import WebReader
from eidolon_core.web_transport import RawResponse, StdlibConnector, TransportLimits, WebTransportError, fetch
from tests.test_research import Clock, Provider
from tests.test_web_transport import DNS, POLICY, PUBLIC, FakeConnector, LoopbackConnector, ok, redirect
from tests.test_web_transport_boundaries import raw_server

URL = 'https://docs.example.com/'
BAD_HEADERS = (
    (('Retry-After', '600'), ('Retry-After', '600')),
    (('Retry-After', '600'), ('Content-Type', 'text/plain'), ('Content-Type', 'text/plain')),
    (('Retry-After', '600'), ('Content-Length', '0'), ('Transfer-Encoding', 'chunked')),
    (('Retry-After', '600'), ('Content-Length', 'invalid-secret-value')),
    (('Retry-After', '١٢٠'),),
)

class WebReviewRegressionTests(TestCase):
    def test_ambiguous_429_and_503_suspend_same_domain_without_retry_or_error_body(self):
        for status in (429, 503):
            for headers in BAD_HEADERS:
                with self.subTest(status=status, headers=headers):
                    connector = FakeConnector({(PUBLIC, '/'): RawResponse(status, headers, b'SECRET', True),
                                               (PUBLIC, '/next'): ok()})
                    clock = Clock()
                    c = ResearchCoordinator([Provider('fixture', [Hit(URL, 'one'), Hit(URL+'next', 'two')])],
                                            WebReader(DNS, connector), resolver=DNS, clock=clock)
                    r = c.run('reference', required_pages=2)
                    self.assertEqual(len(connector.calls), 1)
                    self.assertEqual(r['readable_pages'], 0)
                    receipt = r['sources'][0]['retrieval']
                    self.assertEqual(receipt['status'], status)
                    self.assertFalse(receipt['headers_validated'])
                    self.assertTrue(receipt['retry_review_required'])
                    self.assertIsNone(receipt['retry_after'])
                    self.assertNotIn('SECRET', str(r))
                    self.assertNotIn('invalid-secret-value', str(r))
                    clock.value += 1_000_000
                    c.run('reference', required_pages=2)
                    self.assertEqual(len(connector.calls), 1)

    def test_real_429_and_503_keep_status_when_header_validation_fails(self):
        for status in (429, 503):
            with self.subTest(status=status), raw_server(
                f'HTTP/1.1 {status} Wait\r\n'.encode() +
                b'Retry-After: 600\r\nContent-Length: 4\r\nContent-Length: 4\r\n\r\nLEAK'
            ) as port:
                page = WebReader(DNS, LoopbackConnector()).read(
                    f'http://docs.example.com:{port}/', WebPolicy(schemes=('http',), ports=(port,)))
                self.assertEqual(page.status, status)
                self.assertEqual(page.body, b'')
                self.assertTrue(page.retry_review_required)
                self.assertEqual(page.retrieval['header_error'], 'AMBIGUOUS_HEADER')

    def test_invalid_success_headers_still_fail_closed(self):
        connector = FakeConnector({(PUBLIC, '/'): RawResponse(200, BAD_HEADERS[0], b'SECRET', True)})
        with self.assertRaises(WebTransportError) as raised:
            fetch(URL, policy=POLICY, resolver=DNS, connector=connector)
        self.assertEqual(raised.exception.code, 'AMBIGUOUS_HEADER')
        self.assertIsNone(raised.exception.observation)

    def test_invalid_status_is_never_promoted_to_rate_limit(self):
        for status in (429.0, '429', True):
            with self.subTest(status=status), self.assertRaises(WebTransportError) as raised:
                fetch(URL, policy=POLICY, resolver=DNS,
                      connector=FakeConnector({(PUBLIC, '/'): RawResponse(status, (), b'', True)}))
            self.assertEqual(raised.exception.code, 'BAD_HTTP_RESPONSE')
            self.assertIsNone(raised.exception.observation)

    def test_real_connector_accepts_offset_reader_clocks(self):
        # 237.965 previously produced 30.00000000000003 seconds, rejected
        # before connecting. Exercise the real connector with that clock too.
        for offset in (0., 1e9, 237.965):
            with self.subTest(offset=offset), raw_server(
                b'HTTP/1.1 200 OK\r\nContent-Length: 5\r\n\r\nhello'
            ) as port:
                result = fetch(f'http://docs.example.com:{port}/', resolver=DNS,
                               policy=WebPolicy(schemes=('http',), ports=(port,)),
                               connector=LoopbackConnector(), clock=lambda: offset)
                self.assertEqual(result.body, b'hello')
                self.assertFalse(result.deadline_exceeded)

    def test_real_connector_checks_own_elapsed_time_even_with_frozen_reader_clock(self):
        conn = MagicMock()
        response = conn.getresponse.return_value
        response.status = 200
        response.getheaders.return_value = [('Content-Length', '10')]
        response.read.return_value = b'x'
        response.isclosed.return_value = False
        for offset in (0., 1e9):
            with self.subTest(offset=offset), patch(
                'eidolon_core.web_transport._PinnedHTTPConnection', return_value=conn
            ), patch('eidolon_core.web_transport.time.monotonic', side_effect=[100., 100., 102.]):
                with self.assertRaises(WebTransportError) as raised:
                    fetch('http://docs.example.com/', resolver=DNS,
                          policy=WebPolicy(schemes=('http',), ports=(80,)),
                          clock=lambda: offset, limits=TransportLimits(total_seconds=1))
                self.assertEqual(raised.exception.code, 'DEADLINE_EXCEEDED')
                conn.close.assert_called()

    def test_remaining_budget_decreases_across_redirects(self):
        connector = FakeConnector({(PUBLIC, '/'): redirect('/next'), (PUBLIC, '/next'): ok()})
        budgets = []
        exchange = connector.exchange
        def recording(**kwargs):
            budgets.append(kwargs['remaining_seconds'])
            return exchange(**kwargs)
        connector.exchange = recording
        ticks = iter([1000., 1002., 1007., 1008.])
        fetch(URL, policy=POLICY, resolver=DNS, connector=connector,
              clock=lambda: next(ticks), limits=TransportLimits(total_seconds=10))
        self.assertEqual(budgets, [8., 3.])

    def test_guard_time_is_charged_before_connection(self):
        clock = Clock()
        connector = FakeConnector({(PUBLIC, '/'): ok()})
        def slow_guard(decision):
            clock.value += 31
        with self.assertRaises(WebTransportError) as raised:
            fetch(URL, policy=POLICY, resolver=DNS, connector=connector,
                  clock=clock, before_hop=slow_guard)
        self.assertEqual(raised.exception.code, 'DEADLINE_EXCEEDED')
        self.assertEqual(connector.calls, [])

    def test_redirect_without_location_is_invalid_response(self):
        reader = WebReader(DNS, FakeConnector({(PUBLIC, '/'): RawResponse(302, (), b'', True)}))
        with self.assertRaises(AccessFailure) as raised:
            reader.read(URL, POLICY)
        self.assertEqual(raised.exception.code, 'INVALID_RESPONSE')

    def test_invalid_remaining_budget_never_opens_a_socket(self):
        connector = StdlibConnector()
        for budget in (0, -1, True, float('nan'), float('inf'), 31):
            with self.subTest(budget=budget), patch('socket.create_connection') as connect:
                with self.assertRaises(ContractError):
                    connector.exchange(scheme='https', host='docs.example.com', port=443,
                                       address=PUBLIC, target='/', headers=(), limits=TransportLimits(),
                                       remaining_seconds=budget)
                connect.assert_not_called()
