"""W1: bounded DNS resolution without contacting the Internet."""
import threading
import time
import unittest

from eidolon_core.egress import WebPolicy
from eidolon_core.web_transport import (DNS_MAX_IN_FLIGHT, TransportLimits,
                                        WebTransportError, fetch)
from tests.test_web_transport import FakeConnector, PUBLIC, ok


class ResolverDeadlineTests(unittest.TestCase):
    def test_hung_resolver_returns_within_budget_and_recovers(self):
        release = threading.Event()
        def hanging(host, port):
            release.wait(5)
            return [PUBLIC]
        limits = TransportLimits(total_seconds=0.05, connect_seconds=0.05, read_seconds=0.05)
        start = time.monotonic()
        try:
            with self.assertRaises(WebTransportError) as error:
                fetch("https://docs.example.com/", policy=WebPolicy(), resolver=hanging,
                      connector=FakeConnector({(PUBLIC, "/"): ok()}), limits=limits)
            self.assertEqual(error.exception.code, "DEADLINE_EXCEEDED")
            self.assertLess(time.monotonic() - start, 0.6)
        finally:
            release.set()

    def test_resolver_thread_count_never_exceeds_cap(self):
        release = threading.Event()
        entered = []
        def hanging(host, port):
            entered.append(host)
            release.wait(5)
            return [PUBLIC]
        limits = TransportLimits(total_seconds=0.03, connect_seconds=0.03, read_seconds=0.03)
        try:
            for _ in range(DNS_MAX_IN_FLIGHT + 2):
                with self.assertRaises(WebTransportError):
                    fetch("https://docs.example.com/", policy=WebPolicy(), resolver=hanging,
                          connector=FakeConnector({(PUBLIC, "/"): ok()}), limits=limits)
            self.assertLessEqual(len(entered), DNS_MAX_IN_FLIGHT)
        finally:
            release.set()
