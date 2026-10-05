# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : egress.py
# Description : Politique de destination Web publique, sans accès réseau
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

"""Decide whether a public Web URL may be contacted. Pure: DNS is injected.

Only globally routable unicast addresses pass. Every resolved address must
pass, and the chosen one is pinned so the connector connects to the address
that was checked (DNS rebinding). Redirects are re-checked hop by hop.
LAN, NAS and Memory Engine never go through this module: they are catalogue
targets (targets.py). This module opens no socket and sends no request.
"""
from __future__ import annotations

from dataclasses import dataclass
import ipaddress
import re
import socket
import urllib.parse

from .contracts import ContractError

MAX_URL = 2048
MAX_ADDRESSES = 32
NAT64 = ipaddress.ip_network("64:ff9b::/96")         # well-known NAT64 prefix (RFC 6052)
NAT64_LOCAL = ipaddress.ip_network("64:ff9b:1::/48")  # local-use NAT64 prefix (RFC 8215)
IPV4_COMPATIBLE = ipaddress.ip_network("::/96")       # deprecated IPv4-compatible IPv6
HOST_LABEL = re.compile(r"(?!-)[a-z0-9-]{1,63}(?<!-)")
# Forms that some resolvers read as IPv4 although they are not dotted quads:
# 2130706433, 0x7f000001, 017700000001, 127.1, 0x7f.0.0.1 ...
NUMERIC_HOST = re.compile(r"(0x[0-9a-f]*|[0-9]+)(\.(0x[0-9a-f]*|[0-9]+)){0,3}")


@dataclass(frozen=True)
class WebPolicy:
    schemes: tuple = ("https",)
    ports: tuple = (443,)
    max_redirects: int = 5

    def __post_init__(self):
        if not self.schemes or set(self.schemes) - {"http", "https"}:
            raise ContractError("schemes limited to http and https")
        if not self.ports or any(type(p) is not int or not 1 <= p <= 65535 for p in self.ports):
            raise ContractError("ports must be valid TCP ports")
        if type(self.max_redirects) is not int or not 0 <= self.max_redirects <= 10:
            raise ContractError("max_redirects must be within [0, 10]")


@dataclass(frozen=True)
class Decision:
    allowed: bool
    code: str            # ALLOWED or the refusal reason
    url: str
    host: str | None = None
    port: int | None = None
    address: str | None = None  # pinned: the connector must connect to this address only
    hop: int = 0


def classify(address):
    """Return None for a public unicast address, else the refusal reason."""
    ip = ipaddress.ip_address(address)
    if ip.version == 6:
        if ip.ipv4_mapped is not None:
            return classify(str(ip.ipv4_mapped))
        if ip in NAT64 or ip in NAT64_LOCAL:
            return classify(str(ipaddress.IPv4Address(int(ip) & 0xFFFFFFFF)))
        if ip.sixtofour is not None:
            return classify(str(ip.sixtofour))
        if ip.teredo is not None:
            return "TEREDO"
    if ip.is_multicast:
        return "MULTICAST"
    if ip.is_loopback:
        return "LOOPBACK"
    if ip.is_link_local:
        return "LINK_LOCAL"
    if ip.is_unspecified:
        return "UNSPECIFIED"
    if ip.version == 6 and ip in IPV4_COMPATIBLE:
        return "IPV4_COMPATIBLE"  # ::a.b.c.d is reported global by Python, yet embeds IPv4
    if not ip.is_global:
        return "NOT_GLOBAL"  # private, CGNAT, documentation, benchmarking, reserved ...
    return None


def system_resolver(host, port):
    """Default resolver for a future connector. Never used by the tests."""
    infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    return [info[4][0] for info in infos]


def _refuse(code, url, hop, host=None, port=None):
    return Decision(False, code, url, host, port, None, hop)


def _parse(url, policy):
    if not isinstance(url, str) or not url or len(url) > MAX_URL:
        raise ContractError("BAD_URL")
    if any(ord(c) < 33 or ord(c) == 127 for c in url):
        raise ContractError("BAD_URL")  # spaces and control characters are never repaired
    parts = urllib.parse.urlsplit(url)
    scheme = parts.scheme.lower()
    if scheme not in policy.schemes:
        raise ContractError("SCHEME_REFUSED")
    if parts.username is not None or parts.password is not None or "@" in parts.netloc:
        raise ContractError("CREDENTIALS_IN_URL")
    try:
        port = parts.port
    except ValueError as exc:
        raise ContractError("BAD_PORT") from exc
    port = port or (443 if scheme == "https" else 80)
    if port not in policy.ports:
        raise ContractError("PORT_REFUSED")
    host = parts.hostname
    if not host:
        raise ContractError("BAD_HOST")
    if host.startswith("[") or ":" in host:
        literal = host.strip("[]")
        try:
            ipaddress.IPv6Address(literal.split("%")[0])
        except ValueError as exc:
            raise ContractError("BAD_HOST") from exc
        if "%" in literal:
            raise ContractError("BAD_HOST")  # zone identifiers designate a local interface
        return scheme, literal, port, True
    host = host.rstrip(".")
    try:
        ipaddress.IPv4Address(host)
        return scheme, host, port, True
    except ValueError:
        pass
    if NUMERIC_HOST.fullmatch(host):
        raise ContractError("AMBIGUOUS_NUMERIC_HOST")
    try:
        ascii_host = host.encode("idna").decode("ascii").lower()
    except UnicodeError as exc:
        raise ContractError("BAD_HOST") from exc
    labels = ascii_host.split(".")
    if len(ascii_host) > 253 or len(labels) < 2 or not all(HOST_LABEL.fullmatch(l) for l in labels):
        raise ContractError("BAD_HOST")  # single-label names resolve through local search domains
    if labels[-1] in {"localhost", "local", "internal", "lan", "home", "localdomain", "arpa"}:
        raise ContractError("LOCAL_NAME")
    return scheme, ascii_host, port, False


def decide(url, resolver, policy=None, *, hop=0):
    """Check one URL; return a Decision with a pinned public address or a refusal."""
    policy = policy or WebPolicy()
    try:
        scheme, host, port, literal = _parse(url, policy)
    except ContractError as exc:
        return _refuse(str(exc), url, hop)
    if literal:
        addresses = [host]
    else:
        try:
            addresses = list(resolver(host, port))
        except Exception:  # noqa: BLE001 - any resolver failure is a refusal, never a pass
            return _refuse("RESOLUTION_FAILED", url, hop, host, port)
        if not addresses:
            return _refuse("RESOLUTION_EMPTY", url, hop, host, port)
        if len(addresses) > MAX_ADDRESSES:
            return _refuse("RESOLUTION_TOO_LARGE", url, hop, host, port)
    for address in addresses:
        try:
            reason = classify(address)
        except (ValueError, TypeError):
            return _refuse("RESOLUTION_INVALID", url, hop, host, port)
        if reason is not None:
            # One non-public answer refuses the name: a mixed answer is how rebinding starts.
            return _refuse("DESTINATION_" + reason, url, hop, host, port)
    return Decision(True, "ALLOWED", url, host, port, str(ipaddress.ip_address(addresses[0])), hop)


def follow(previous, location, resolver, policy=None):
    """Check a redirect target relative to an allowed previous Decision."""
    policy = policy or WebPolicy()
    if not isinstance(previous, Decision) or not previous.allowed:
        raise ContractError("a redirect can only follow an allowed decision")
    hop = previous.hop + 1
    if hop > policy.max_redirects:
        return _refuse("TOO_MANY_REDIRECTS", str(location), hop)
    if not isinstance(location, str) or not location or len(location) > MAX_URL:
        return _refuse("BAD_URL", str(location)[:MAX_URL], hop)
    target = urllib.parse.urljoin(previous.url, location)
    if (urllib.parse.urlsplit(previous.url).scheme.lower() == "https"
            and urllib.parse.urlsplit(target).scheme.lower() != "https"):
        return _refuse("DOWNGRADE_REFUSED", target, hop)
    return decide(target, resolver, policy, hop=hop)
