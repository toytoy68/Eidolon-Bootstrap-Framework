# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_egress.py
# Description : Tests de la politique de destination Web, résolveur simulé
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

"""Synthetic resolver only; a patched socket proves no network access."""
import socket
import unittest
from unittest.mock import patch

from eidolon_core.contracts import ContractError
from eidolon_core.egress import WebPolicy, classify, decide, follow

PUBLIC_V4 = "93.184.215.14"
PUBLIC_V6 = "2606:2800:21f:cb07:6820:80da:af6b:8b2c"


def resolver(table):
    def resolve(host, port):
        answer = table[host]
        if isinstance(answer, Exception):
            raise answer
        return answer
    return resolve


DNS = resolver({"docs.example.com": [PUBLIC_V4], "v6.example.com": [PUBLIC_V6],
                "xn--bcher-kva.example": [PUBLIC_V4],
                "mixed.example.com": [PUBLIC_V4, "10.0.0.5"],
                "metadata.example.com": ["169.254.169.254"],
                "empty.example.com": [], "broken.example.com": OSError("no route"),
                "garbage.example.com": ["not-an-ip"],
                "nas.attacker.example": ["192.168.1.10"]})


class ClassifyTests(unittest.TestCase):
    def test_public_unicast_passes(self):
        for address in (PUBLIC_V4, "8.8.8.8", PUBLIC_V6, "2001:4860:4860::8888", "::ffff:8.8.8.8",
                        "64:ff9b::808:808"):
            self.assertIsNone(classify(address), address)

    def test_non_public_addresses_are_refused(self):
        cases = {
            "10.0.0.1": "NOT_GLOBAL", "172.16.0.1": "NOT_GLOBAL", "192.168.1.135": "NOT_GLOBAL",
            "100.64.0.1": "NOT_GLOBAL", "192.0.2.1": "NOT_GLOBAL", "198.18.0.1": "NOT_GLOBAL",
            "127.0.0.1": "LOOPBACK", "169.254.169.254": "LINK_LOCAL", "0.0.0.0": "UNSPECIFIED",
            "224.0.0.1": "MULTICAST", "255.255.255.255": "NOT_GLOBAL",
            "::1": "LOOPBACK", "fe80::1": "LINK_LOCAL", "fc00::1": "NOT_GLOBAL", "::": "UNSPECIFIED",
            "ff02::1": "MULTICAST", "2001:db8::1": "NOT_GLOBAL",
            # Python's is_global says True for the next three; they still embed local IPv4.
            "64:ff9b::7f00:1": "LOOPBACK", "64:ff9b:1::a00:1": "NAT64_LOCAL", "::127.0.0.1": "IPV4_COMPATIBLE",
            "::ffff:127.0.0.1": "LOOPBACK", "::ffff:169.254.169.254": "LINK_LOCAL",
            "2002:7f00:1::1": "LOOPBACK", "2002:c0a8:101::1": "NOT_GLOBAL",
            "2001:0:4136:e378:8000:63bf:80ff:fffe": "TEREDO",
        }
        for address, reason in cases.items():
            self.assertEqual(classify(address), reason, address)


class DecisionTests(unittest.TestCase):
    def test_public_https_url_is_allowed_with_a_pinned_address(self):
        d = decide("https://docs.example.com/guide?q=1", DNS)
        self.assertEqual((d.allowed, d.code, d.host, d.port, d.address), (True, "ALLOWED", "docs.example.com",
                                                                            443, PUBLIC_V4))
        self.assertEqual(decide("https://v6.example.com/", DNS).address, PUBLIC_V6)
        self.assertEqual(decide("https://DOCS.Example.COM./", DNS).host, "docs.example.com")
        self.assertEqual(decide("https://bücher.example/", DNS).host, "xn--bcher-kva.example")

    def test_url_shape_refusals(self):
        cases = {
            "http://docs.example.com/": "SCHEME_REFUSED", "ftp://docs.example.com/": "SCHEME_REFUSED",
            "file:///etc/passwd": "SCHEME_REFUSED", "gopher://x.example/": "SCHEME_REFUSED",
            "https://user:pw@docs.example.com/": "CREDENTIALS_IN_URL",
            "https://docs.example.com@10.0.0.1/": "CREDENTIALS_IN_URL",
            "https://docs.example.com:8443/": "PORT_REFUSED", "https://docs.example.com:99999/": "BAD_PORT",
            "https:///path": "BAD_HOST", "https://intranet/": "BAD_HOST",
            "https://router.lan/": "LOCAL_NAME", "https://printer.local/": "LOCAL_NAME",
            "https://localhost/": "BAD_HOST", "https://a.localhost/": "LOCAL_NAME",
            "https://2130706433/": "AMBIGUOUS_NUMERIC_HOST", "https://0x7f000001/": "AMBIGUOUS_NUMERIC_HOST",
            "https://127.1/": "AMBIGUOUS_NUMERIC_HOST", "https://017700000001/": "AMBIGUOUS_NUMERIC_HOST",
            "https://0x7f.0.0.1/": "AMBIGUOUS_NUMERIC_HOST",
            "https://[fe80::1%25eth0]/": "BAD_HOST",
            "https://docs.example.com/a b": "BAD_URL", "https://docs.example.com/\n": "BAD_URL",
            "": "BAD_URL", "https://" + "a" * 2050 + ".com/": "BAD_URL",
        }
        for url, code in cases.items():
            d = decide(url, DNS)
            self.assertEqual((d.allowed, d.code), (False, code), url)
            self.assertIsNone(d.address, url)

    def test_ip_literals_are_classified_without_dns(self):
        def no_dns(host, port):
            raise AssertionError("resolver must not be called for a literal")
        self.assertTrue(decide(f"https://{PUBLIC_V4}/", no_dns).allowed)
        for url, code in {"https://127.0.0.1/": "DESTINATION_LOOPBACK",
                          "https://169.254.169.254/latest/meta-data/": "DESTINATION_LINK_LOCAL",
                          "https://192.168.1.135/": "DESTINATION_NOT_GLOBAL",
                          "https://[::1]/": "DESTINATION_LOOPBACK",
                          "https://[::ffff:10.0.0.1]/": "DESTINATION_NOT_GLOBAL",
                          "https://[64:ff9b::7f00:1]/": "DESTINATION_LOOPBACK"}.items():
            self.assertEqual(decide(url, no_dns).code, code, url)

    def test_resolution_rules(self):
        cases = {"https://mixed.example.com/": "DESTINATION_NOT_GLOBAL",
                 "https://metadata.example.com/": "DESTINATION_LINK_LOCAL",
                 "https://nas.attacker.example/": "DESTINATION_NOT_GLOBAL",
                 "https://empty.example.com/": "RESOLUTION_EMPTY",
                 "https://broken.example.com/": "RESOLUTION_FAILED",
                 "https://garbage.example.com/": "RESOLUTION_INVALID",
                 "https://unknown.example.com/": "RESOLUTION_FAILED"}
        for url, code in cases.items():
            self.assertEqual(decide(url, DNS).code, code, url)
        many = resolver({"many.example.com": [PUBLIC_V4] * 33})
        self.assertEqual(decide("https://many.example.com/", many).code, "RESOLUTION_TOO_LARGE")

    def test_rebinding_needs_no_second_lookup(self):
        answers = iter([[PUBLIC_V4], ["127.0.0.1"]])

        def rebinding(host, port):
            return next(answers)
        d = decide("https://docs.example.com/", rebinding)
        self.assertEqual((d.allowed, d.address), (True, PUBLIC_V4))
        # The connector must connect to d.address; a later lookup would return 127.0.0.1.

    def test_http_and_ports_only_by_explicit_policy(self):
        policy = WebPolicy(schemes=("http", "https"), ports=(80, 443))
        self.assertTrue(decide("http://docs.example.com/", DNS, policy).allowed)
        for kwargs in ({"schemes": ("ftp",)}, {"schemes": ()}, {"ports": (0,)}, {"ports": ("443",)},
                       {"max_redirects": 11}, {"max_redirects": -1}):
            with self.assertRaises(ContractError, msg=kwargs):
                WebPolicy(**kwargs)


class RedirectTests(unittest.TestCase):
    def setUp(self):
        self.start = decide("https://docs.example.com/a/b", DNS)

    def test_each_hop_is_checked_again(self):
        hop = follow(self.start, "/c", DNS)
        self.assertEqual((hop.allowed, hop.url, hop.hop), (True, "https://docs.example.com/c", 1))
        for location, code in {"https://169.254.169.254/": "DESTINATION_LINK_LOCAL",
                               "https://nas.attacker.example/": "DESTINATION_NOT_GLOBAL",
                               "http://docs.example.com/": "DOWNGRADE_REFUSED",
                               "//127.0.0.1/x": "DESTINATION_LOOPBACK",
                               "https://user@docs.example.com/": "CREDENTIALS_IN_URL"}.items():
            self.assertEqual(follow(self.start, location, DNS).code, code, location)

    def test_redirect_count_is_bounded(self):
        d = self.start
        for _ in range(5):
            d = follow(d, "/next", DNS)
            self.assertTrue(d.allowed)
        self.assertEqual(follow(d, "/next", DNS).code, "TOO_MANY_REDIRECTS")
        policy = WebPolicy(max_redirects=0)
        start = decide("https://docs.example.com/", DNS, policy)
        self.assertEqual(follow(start, "/x", DNS, policy).code, "TOO_MANY_REDIRECTS")

    def test_cannot_follow_a_refusal(self):
        with self.assertRaises(ContractError):
            follow(decide("https://127.0.0.1/", DNS), "/x", DNS)


class NoNetworkTests(unittest.TestCase):
    def test_module_opens_no_socket(self):
        def forbidden(*args, **kwargs):
            raise AssertionError("network access attempted")
        with patch.object(socket, "socket", forbidden), patch.object(socket, "getaddrinfo", forbidden), \
                patch.object(socket, "create_connection", forbidden):
            decide("https://docs.example.com/", DNS)
            follow(decide("https://docs.example.com/", DNS), "/x", DNS)
            decide("https://192.168.1.135/", DNS)


if __name__ == "__main__":
    unittest.main()
