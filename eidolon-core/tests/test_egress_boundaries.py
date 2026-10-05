# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_egress_boundaries.py
# Description : Frontières URL, DNS et exclusions de réseaux synthétiques
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

"""No real DNS or socket: the public IPs below are classification fixtures."""
from dataclasses import asdict, replace, FrozenInstanceError
import ipaddress
import itertools
import pickle
import socket
import unittest
from unittest.mock import patch

from eidolon_core.contracts import ContractError, encode
from eidolon_core.egress import WebPolicy, classify, decide, follow


def public_dns(*args):
    return ["8.8.8.8"]


class EgressBoundaryTests(unittest.TestCase):
    def test_bad_urls_refuse_without_exception_or_dns(self):
        bad = [None, 42, {}, b"https://public.example/", "https://[broken/",
               "https://[8.8.8.8]/", "https://public.example：443/",
               "https://public.example:0/", "https://public.example:/",
               "https://public.example/\ud800", "https://public.example/\x85",
               "https://public.example/\u202e", "https://public.example/a b",
               "https://public.example/\\evil", "https://public.example/%zz",
               "https://public.example..", "https://[2001:4860::1]suffix/",
               "https://[2001:4860::1]:443suffix/"]
        with patch("socket.getaddrinfo", side_effect=AssertionError("no DNS")):
            for url in bad:
                with self.subTest(url=repr(url)):
                    d = decide(url, socket.getaddrinfo)
                    self.assertFalse(d.allowed)
                    self.assertEqual(d.url, "")
                    encode(asdict(d))

    def test_refusals_do_not_echo_credentials_or_queries(self):
        d = decide("https://user:synthetic-secret@public.example/?private=value", public_dns)
        self.assertEqual(d.code, "CREDENTIALS_IN_URL")
        self.assertNotIn("synthetic-secret", encode(asdict(d)))
        self.assertNotIn("private=value", encode(asdict(d)))

    def test_canonical_url_matches_checked_idna_host_and_port(self):
        d = decide("HTTPS://BÜCHER.Example.:443/été?q=é#fragment", public_dns)
        self.assertTrue(d.allowed)
        self.assertEqual(d.url, "https://xn--bcher-kva.example/%C3%A9t%C3%A9?q=%C3%A9")
        self.assertEqual((d.host, d.port, d.address), ("xn--bcher-kva.example", 443, "8.8.8.8"))
        d2 = decide(d.url, public_dns)
        self.assertEqual(d, d2)
        with patch("socket.getaddrinfo", side_effect=AssertionError("literal must bypass DNS")):
            self.assertEqual(decide("https://１２７.０.０.１/", socket.getaddrinfo).code, "DESTINATION_LOOPBACK")

    def test_normalization_expansion_is_bounded(self):
        self.assertEqual(decide("https://public.example/" + "é" * 1000, public_dns).code, "BAD_URL")

    def test_redirect_controls_are_refused_before_join(self):
        start = decide("https://public.example/a", public_dns)
        for location in ["/a\nb", " /page", "\t/page", "https://[broken/", "/\ud800", "/\\local", None]:
            with self.subTest(location=repr(location)):
                d = follow(start, location, public_dns)
                self.assertFalse(d.allowed)
                self.assertEqual(d.code, "BAD_URL")
                self.assertEqual(d.url, "")

    def test_policy_inputs_are_copied_and_spawn_serializable(self):
        schemes, ports, networks = ["https"], [443], ["8.8.8.8"]
        policy = WebPolicy(schemes, ports, blocked_networks=networks)
        original = policy.policy_id
        schemes.append("http"); ports.append(80); networks.clear()
        copy = pickle.loads(pickle.dumps(policy))
        self.assertEqual(copy.policy_id, original)
        self.assertEqual(decide("https://8.8.8.8/", public_dns, copy).code, "DESTINATION_BLOCKED_NETWORK")
        self.assertFalse(decide("http://public.example/", public_dns, copy).allowed)
        with self.assertRaises(FrozenInstanceError):
            copy.ports = (80,)
        manifest = copy.manifest(); manifest["blocked_networks"].clear()
        self.assertEqual(copy.policy_id, original)

    def test_policy_invalid_types_and_cidr_host_bits(self):
        for kw in [dict(schemes="https"), dict(schemes=[[]]), dict(ports=None), dict(ports=[True]),
                   dict(ports=range(1, 100)), dict(max_redirects=True), dict(blocked_networks="8.8.8.8"),
                   dict(blocked_networks=[None]), dict(blocked_networks=[134744072]),
                   dict(blocked_networks=["8.8.8.8/24"]), dict(blocked_networks=["::1%lo/128"]),
                   dict(blocked_networks=["8.8.8.8"] * 257)]:
            with self.subTest(kw=kw), self.assertRaises(ContractError):
                WebPolicy(**kw)
        for policy in [False, {}, "default"]:
            with self.assertRaises(ContractError):
                decide("https://public.example", public_dns, policy)

    def test_manifest_canonical_and_binding_changes(self):
        a = WebPolicy(blocked_networks=["8.8.8.8", "2001:4860::/32"])
        b = WebPolicy(blocked_networks=["2001:4860::/32", "8.8.8.8/32", "8.8.8.8"])
        self.assertEqual(a.policy_id, b.policy_id)
        self.assertNotEqual(a.policy_id, WebPolicy().policy_id)
        self.assertNotEqual(a.policy_id, replace(a, max_redirects=2).policy_id)

    def test_public_household_addresses_refused_for_literals_and_dns(self):
        # Arbitrary global addresses stand in for a household IPv4 and prefix;
        # they are never queried and are not the user's network configuration.
        policy = WebPolicy(blocked_networks=("8.8.8.8", "2001:4860::/32"))
        for address in ["8.8.8.8", "2001:4860:4860::8888"]:
            netloc = f"[{address}]" if ":" in address else address
            literal = decide(f"https://{netloc}/", public_dns, policy)
            named = decide("https://household.example/", lambda *a: [address], policy)
            self.assertEqual(literal.code, "DESTINATION_BLOCKED_NETWORK")
            self.assertEqual(named.code, "DESTINATION_BLOCKED_NETWORK")
        self.assertTrue(decide("https://9.9.9.9/", public_dns, policy).allowed)
        mixed = decide("https://mixed.example/", lambda *a: ["9.9.9.9", "8.8.8.8"], policy)
        self.assertEqual(mixed.code, "DESTINATION_BLOCKED_NETWORK")

    def test_deny_network_applies_to_embedded_ipv4_and_outer_ipv6(self):
        policy = WebPolicy(blocked_networks=("8.8.8.0/24",))
        for address in ["::ffff:8.8.8.8", "64:ff9b::808:808", "2002:808:808::1"]:
            self.assertEqual(decide(f"https://[{address}]/", public_dns, policy).code,
                             "DESTINATION_BLOCKED_NETWORK")
        outer = WebPolicy(blocked_networks=("64:ff9b::/96",))
        self.assertEqual(decide("https://[64:ff9b::909:909]/", public_dns, outer).code,
                         "DESTINATION_BLOCKED_NETWORK")

    def test_blocked_prefix_first_last_and_adjacent_addresses(self):
        for cidr in ["8.8.8.0/24", "2001:4860::/32"]:
            net = ipaddress.ip_network(cidr)
            self.assertEqual(classify(str(net[0]), (cidr,)), "BLOCKED_NETWORK")
            self.assertEqual(classify(str(net[-1]), (cidr,)), "BLOCKED_NETWORK")
            self.assertNotEqual(classify(str(net.broadcast_address + 1), (cidr,)), "BLOCKED_NETWORK")

    def test_redirect_blocked_even_from_public_and_policy_cannot_change(self):
        policy = WebPolicy(blocked_networks=("8.8.8.8",))
        start = decide("https://9.9.9.9/a", public_dns, policy)
        self.assertEqual(follow(start, "https://household.example/", public_dns, policy).code,
                         "DESTINATION_BLOCKED_NETWORK")
        with self.assertRaises(ContractError):
            follow(start, "https://8.8.8.8/", public_dns)  # dropping the policy is forbidden
        with self.assertRaises(ContractError):
            follow(replace(start, hop=-1), "/next", public_dns, policy)

    def test_dns_requires_unscoped_ip_strings(self):
        for answer in [["2001:4860::8888%eth0"], [134744072], [b"8.8.8.8"], [True],
                       "8.8.8.8", {"8.8.8.8": 1}, ["8.8.8.8 "]]:
            with self.subTest(answer=answer):
                self.assertEqual(decide("https://public.example/", lambda *a: answer).code,
                                 "RESOLUTION_INVALID")

    def test_dns_iteration_stops_after_33_addresses(self):
        count = []
        def resolve(*args):
            for n in itertools.count():
                count.append(n)
                if n > 33:
                    raise AssertionError("unbounded consumption")
                yield "8.8.8.8"
        d = decide("https://public.example/", resolve)
        self.assertEqual(d.code, "RESOLUTION_TOO_LARGE")
        self.assertEqual(len(count), 33)

    def test_dns_failure_after_first_address_is_not_a_partial_allow(self):
        def resolve(*args):
            yield "8.8.8.8"
            raise OSError("synthetic resolver unavailable")
        self.assertEqual(decide("https://public.example/", resolve).code, "RESOLUTION_FAILED")

    def test_local_nat64_prefix_refused_regardless_of_tail(self):
        for address in ["64:ff9b:1:7f00:1::808:808", "64:ff9b:1::808:808", "64:ff9b:1::a00:1"]:
            self.assertEqual(decide(f"https://[{address}]/", public_dns).code, "DESTINATION_NAT64_LOCAL")
        self.assertTrue(decide("https://[64:ff9b::808:808]/", public_dns).allowed)

    def test_hop_counter_cannot_be_negative_or_non_integer(self):
        for hop in [-1, True, "1", 1.5, 6]:
            with self.subTest(hop=hop), self.assertRaises(ContractError):
                decide("https://public.example/", public_dns, hop=hop)

    def test_exclusions_and_redirects_make_no_network_calls(self):
        with patch.object(socket, "socket", side_effect=AssertionError("no socket")), \
                patch.object(socket, "getaddrinfo", side_effect=AssertionError("no DNS")):
            policy = WebPolicy(blocked_networks=("8.8.8.8",))
            first = decide("https://9.9.9.9/", public_dns, policy)
            self.assertTrue(first.allowed)
            self.assertFalse(follow(first, "https://public.example/", public_dns, policy).allowed)


if __name__ == "__main__":
    unittest.main()
