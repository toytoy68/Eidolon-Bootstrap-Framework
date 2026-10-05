# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_web_transport_boundaries.py
# Description : Frontières du transport HTTP et conservation des observations
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
from dataclasses import replace
from contextlib import contextmanager
import socketserver
import ssl
import threading
import unittest
from unittest.mock import patch

from eidolon_core.contracts import ContractError
from eidolon_core.web_transport import RawResponse, StdlibConnector, WebTransportError, fetch
from eidolon_core.egress import WebPolicy
from tests.test_web_transport import DNS, PUBLIC, POLICY, FakeConnector, LoopbackConnector, ok

URL = 'https://docs.example.com/'


@contextmanager
def raw_server(reply):
    class Handler(socketserver.BaseRequestHandler):
        def handle(self):
            self.request.settimeout(2)
            request = b''
            while b'\r\n\r\n' not in request and len(request) < 4096:
                part = self.request.recv(4096)
                if not part:
                    return
                request += part
            self.request.sendall(reply)
    with socketserver.TCPServer(('127.0.0.1', 0), Handler) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield server.server_address[1]
        finally:
            server.shutdown()
            thread.join()


class TransportBoundaryTests(unittest.TestCase):
    def get(self, response, **kwargs):
        return fetch(URL, policy=POLICY, resolver=DNS,
                     connector=FakeConnector({(PUBLIC, '/'): response}), **kwargs)

    def test_ambiguous_content_length_and_transfer_are_refused(self):
        for extra in [(('Content-Length', '5'),), (('Transfer-Encoding', 'chunked'),)]:
            with self.subTest(extra=extra):
                with self.assertRaises(WebTransportError) as raised:
                    self.get(ok(extra=extra))
                self.assertEqual(raised.exception.code, 'AMBIGUOUS_HEADER')

    def test_raw_envelope_is_checked_before_its_use(self):
        for response in [replace(ok(), status=200.0), replace(ok(), status=True),
                         replace(ok(), complete=1), replace(ok(), body='hello'),
                         replace(ok(), headers=None), replace(ok(), headers=(('X', None),))]:
            with self.subTest(response=response):
                with self.assertRaises(WebTransportError) as raised:
                    self.get(response)
                self.assertEqual(raised.exception.code, 'BAD_HTTP_RESPONSE')

    def test_announced_length_and_actual_body_must_agree(self):
        with self.assertRaises(WebTransportError) as raised:
            self.get(RawResponse(200, (('Content-Length', '50'),), b'hello', True))
        self.assertEqual(raised.exception.code, 'TRUNCATED')

    def test_tls_context_cannot_be_weakened_after_construction(self):
        context = ssl.create_default_context()
        connector = StdlibConnector(context)
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        with patch('socket.create_connection', side_effect=AssertionError('socket must not open')):
            with self.assertRaises(ContractError):
                fetch(URL, policy=POLICY, resolver=DNS, connector=connector)

    def test_late_complete_response_is_marked_and_retained(self):
        ticks = iter([0., 0., 31.])
        result = self.get(ok(), clock=lambda: next(ticks))
        self.assertEqual(result.body, b'hello')
        self.assertTrue(result.deadline_exceeded)

    def test_http_refusal_keeps_status_and_retry_without_body(self):
        with self.assertRaises(WebTransportError) as raised:
            self.get(RawResponse(429, (('Retry-After', '120'),), b'SECRET', True))
        observation = raised.exception.observation
        self.assertEqual((observation['status'], observation['retry_after']), (429, 120))
        self.assertNotIn('SECRET', str(observation))
        self.assertNotIn('body_sha256', observation)

    def test_real_http_rejects_ambiguous_framing_before_reading_body(self):
        for headers, code in [
            (b'Content-Length: 5\r\nContent-Length: 5', 'AMBIGUOUS_HEADER'),
            (b'Content-Length: 5\r\nTransfer-Encoding: chunked', 'AMBIGUOUS_HEADER'),
            (b'Content-Length: -1', 'BAD_HTTP_RESPONSE'),
            (b'Content-Encoding: gzip\r\nContent-Length: 500', 'ENCODED_CONTENT')]:
            with self.subTest(headers=headers), raw_server(b'HTTP/1.1 200 OK\r\n'+headers+b'\r\n\r\n') as port:
                with self.assertRaises(WebTransportError) as raised:
                    fetch(f'http://docs.example.com:{port}/', resolver=DNS,
                          policy=WebPolicy(schemes=('http',), ports=(port,)), connector=LoopbackConnector())
                self.assertEqual(raised.exception.code, code)

    def test_real_chunked_body_with_no_content_length_is_supported(self):
        with raw_server(b'HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n5\r\nhello\r\n0\r\n\r\n') as port:
            result = fetch(f'http://docs.example.com:{port}/', resolver=DNS,
                           policy=WebPolicy(schemes=('http',), ports=(port,)), connector=LoopbackConnector())
        self.assertEqual(result.body, b'hello')


if __name__ == '__main__':
    unittest.main()
