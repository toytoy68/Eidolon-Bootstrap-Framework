# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_web_g187_probes.py
# Description : Audit Claude G187 du transport Web existant : budget global, DNS, redirections, sans réseau
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Independent probes of web_transport/egress against the G187 contract (Claude). No socket is opened:
resolvers and connectors are scripted. W1 is integrated; its probe is a normal regression test."""
import time
import unittest

from eidolon_core.egress import WebPolicy
from eidolon_core.web_transport import RawResponse, TransportLimits, WebTransportError, fetch

PUBLIC = "93.184.215.14"     # classification only, never contacted (scripted connector)


class Script:
    def __init__(self, responses):
        self.responses, self.calls = list(responses), []

    def exchange(self, *, scheme, host, port, address, target, headers, limits, remaining_seconds):
        self.calls.append((host, address, target))
        return self.responses.pop(0)


def ok(body=b"bonjour"):
    return RawResponse(200, (("Content-Type", "text/plain"), ("Content-Length", str(len(body)))), body, True)


class TransportAgainstG187(unittest.TestCase):
    def test_non_http_schemes_are_refused_before_any_resolution(self):
        asked = []
        for url in ("file:///etc/passwd", "ftp://example.org/x", "data:text/plain,x", "javascript:alert(1)",
                    "http://example.org/"):                       # plain http too, by default policy
            with self.assertRaises(WebTransportError) as caught:
                fetch(url, policy=WebPolicy(), resolver=lambda h, p: asked.append(h) or [PUBLIC], connector=Script([]))
            self.assertEqual(caught.exception.code, "DESTINATION_REFUSED")
        self.assertEqual(asked, [])

    def test_redirect_to_metadata_or_loopback_is_refused_and_never_contacted(self):
        for target in ("http://169.254.169.254/latest/meta-data/", "https://127.0.0.1/", "https://[::1]/",
                       "https://internal.example/"):
            table = {"public.example": [PUBLIC], "internal.example": ["10.0.0.5"]}
            connector = Script([RawResponse(302, (("Location", target),), b"", True)])
            with self.assertRaises(WebTransportError):
                fetch("https://public.example/", policy=WebPolicy(), resolver=lambda h, p: table[h], connector=connector)
            self.assertEqual(len(connector.calls), 1, target)       # only the public first hop

    def test_rebinding_after_the_check_cannot_change_the_contacted_address(self):
        answers = iter([[PUBLIC], ["127.0.0.1"]])
        connector = Script([ok()])
        fetch("https://public.example/", policy=WebPolicy(), resolver=lambda h, p: next(answers), connector=connector)
        self.assertEqual(connector.calls[0][1], PUBLIC)

    def test_a_slow_resolver_cannot_exceed_the_total_budget(self):
        """Claude finding W1: name resolution runs before and outside the deadline. system_resolver calls
        getaddrinfo, which has no timeout (resolv.conf retries can last tens of seconds), so total_seconds
        does not bound a fetch. Expected: resolution inside the budget (worker with timeout, or a resolver
        that receives the remaining time)."""
        def slow(host, port):
            time.sleep(1.0)
            return [PUBLIC]
        start = time.monotonic()
        try:
            fetch("https://public.example/", policy=WebPolicy(), resolver=slow, connector=Script([ok()]),
                  limits=TransportLimits(total_seconds=0.2, connect_seconds=0.1, read_seconds=0.1))
        except WebTransportError:
            pass
        self.assertLess(time.monotonic() - start, 0.6)


if __name__ == "__main__":
    unittest.main()
