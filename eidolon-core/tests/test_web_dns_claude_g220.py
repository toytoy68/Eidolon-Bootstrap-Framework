# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_web_dns_claude_g220.py
# Description : Recette Claude W1 (G220-4) : plafond des résolutions DNS, retour à la normale, charge
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Claude's W1 acceptance tests from core-patches/0004, kept after GPT integrated the fix (eb873e1) with its
own tests. Scripted resolvers and connectors only; no socket is opened."""
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


class ResolverCap(unittest.TestCase):
    def test_abandoned_resolutions_are_capped_and_fail_closed(self):
        """W1 review (G210): getaddrinfo cannot be cancelled. Hanging resolutions hold at most
        DNS_MAX_IN_FLIGHT threads; beyond that a fetch is refused at once, and slots return when they end."""
        import threading
        from eidolon_core import web_transport
        release, calls = threading.Event(), []

        def no_resolver_thread_left():
            deadline = time.monotonic() + 5
            while any(t.name == "eidolon-dns" for t in threading.enumerate()) and time.monotonic() < deadline:
                time.sleep(0.01)
            return not any(t.name == "eidolon-dns" for t in threading.enumerate())
        self.assertTrue(no_resolver_thread_left())              # earlier tests may have abandoned one

        def hanging(host, port):
            calls.append(host)
            release.wait(10)
            return [PUBLIC]
        limits = TransportLimits(total_seconds=0.05, connect_seconds=0.05, read_seconds=0.05)
        codes = []
        try:
            for _ in range(web_transport.DNS_MAX_IN_FLIGHT + 3):
                with self.assertRaises(WebTransportError) as caught:
                    fetch("https://public.example/", policy=WebPolicy(), resolver=hanging,
                          connector=Script([ok()]), limits=limits)
                codes.append(caught.exception.code)
            cap = web_transport.DNS_MAX_IN_FLIGHT
            self.assertEqual(len(calls), cap)                                 # no thread beyond the cap
            self.assertEqual(codes, ["DEADLINE_EXCEEDED"] * cap + ["DESTINATION_REFUSED"] * 3)
            start = time.monotonic()                                          # saturated: refused at once
            with self.assertRaises(WebTransportError):
                fetch("https://public.example/", policy=WebPolicy(), resolver=hanging, connector=Script([ok()]),
                      limits=TransportLimits(total_seconds=5, connect_seconds=1, read_seconds=1))
            self.assertLess(time.monotonic() - start, 0.5)
        finally:
            release.set()
        self.assertTrue(no_resolver_thread_left())              # every slot is given back
        for _ in range(web_transport.DNS_MAX_IN_FLIGHT + 2):                 # back to normal, repeatedly
            fetch("https://public.example/", policy=WebPolicy(), resolver=lambda h, p: [PUBLIC],
                  connector=Script([ok()]), limits=TransportLimits(total_seconds=2, connect_seconds=1, read_seconds=1))
        self.assertTrue(no_resolver_thread_left())

    def test_fifty_parallel_fetches_on_a_hanging_dns_stay_capped_and_bounded(self):
        """W1 load (G218-6): 50 threads fetch at once while DNS hangs. Never more than DNS_MAX_IN_FLIGHT resolver
        threads, every fetch returns within its budget (+ margin), all slots come back once DNS answers."""
        import threading
        from eidolon_core import web_transport
        release, peak, stop = threading.Event(), [0], threading.Event()

        def hanging(host, port):
            release.wait(10)
            return [PUBLIC]

        def sample():
            while not stop.is_set():
                peak[0] = max(peak[0], sum(t.name == "eidolon-dns" for t in threading.enumerate()))
                time.sleep(0.001)
        durations, codes, lock = [], [], threading.Lock()

        def one():
            start = time.monotonic()
            try:
                fetch("https://public.example/", policy=WebPolicy(), resolver=hanging, connector=Script([ok()]),
                      limits=TransportLimits(total_seconds=0.3, connect_seconds=0.1, read_seconds=0.1))
                code = "OK"
            except WebTransportError as exc:
                code = exc.code
            with lock:
                durations.append(time.monotonic() - start)
                codes.append(code)
        sampler = threading.Thread(target=sample, daemon=True)
        sampler.start()
        workers = [threading.Thread(target=one) for _ in range(50)]
        try:
            for worker in workers:
                worker.start()
            for worker in workers:
                worker.join(10)
        finally:
            release.set()
            stop.set()
            sampler.join(2)
        self.assertEqual(len(codes), 50)
        self.assertLessEqual(peak[0], web_transport.DNS_MAX_IN_FLIGHT)
        self.assertEqual(set(codes) - {"DEADLINE_EXCEEDED", "DESTINATION_REFUSED"}, set())
        self.assertLess(max(durations), 0.3 + 0.5)
        deadline = time.monotonic() + 5
        while any(t.name == "eidolon-dns" for t in threading.enumerate()) and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertFalse([t for t in threading.enumerate() if t.name == "eidolon-dns"])

    def test_one_slot_freed_lets_exactly_one_resolution_through(self):
        """W1 recovery (G214-4): with the cap reached, freeing one hanging resolution frees exactly one slot."""
        import threading
        from eidolon_core import web_transport
        gates = [threading.Event() for _ in range(web_transport.DNS_MAX_IN_FLIGHT)]
        pending = list(gates)

        def hanging(host, port):
            pending.pop(0).wait(10)
            return [PUBLIC]
        quick = TransportLimits(total_seconds=0.05, connect_seconds=0.05, read_seconds=0.05)
        try:
            for _ in gates:
                with self.assertRaises(WebTransportError):
                    fetch("https://public.example/", policy=WebPolicy(), resolver=hanging, connector=Script([ok()]),
                          limits=quick)
            gates[0].set()
            deadline = time.monotonic() + 5
            while (sum(t.name == "eidolon-dns" for t in threading.enumerate()) >= len(gates)
                   and time.monotonic() < deadline):
                time.sleep(0.01)
            normal = TransportLimits(total_seconds=2, connect_seconds=1, read_seconds=1)
            fetch("https://public.example/", policy=WebPolicy(), resolver=lambda h, p: [PUBLIC],
                  connector=Script([ok()]), limits=normal)
            fetch("https://public.example/", policy=WebPolicy(), resolver=lambda h, p: [PUBLIC],
                  connector=Script([ok()]), limits=normal)                    # sequential: the slot is reused
        finally:
            for gate in gates:
                gate.set()


if __name__ == "__main__":
    unittest.main()
