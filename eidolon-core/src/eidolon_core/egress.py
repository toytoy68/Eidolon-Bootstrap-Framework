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
from itertools import islice
import ipaddress
import re
import socket
import urllib.parse

from .contracts import ContractError, digest

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
    blocked_networks: tuple = ()

    def __post_init__(self):
        for name, maximum in (("schemes", 2), ("ports", 128), ("blocked_networks", 256)):
            value = getattr(self, name)
            if not isinstance(value, (tuple, list)) or len(value) > maximum:
                raise ContractError(f"{name} must be a bounded list or tuple")
        if (not self.schemes or any(type(s) is not str or s not in {"http", "https"}
                                    for s in self.schemes)):
            raise ContractError("schemes limited to http and https")
        if not self.ports or any(type(p) is not int or not 1 <= p <= 65535 for p in self.ports):
            raise ContractError("ports must be valid TCP ports")
        if type(self.max_redirects) is not int or not 0 <= self.max_redirects <= 10:
            raise ContractError("max_redirects must be within [0, 10]")
        networks = []
        for value in self.blocked_networks:
            if type(value) is not str or not 1 <= len(value) <= 64 or "%" in value:
                raise ContractError("blocked networks must be IP or CIDR strings without scopes")
            try:
                networks.append(str(ipaddress.ip_network(value, strict=True)))
            except ValueError as exc:
                raise ContractError("invalid blocked network; CIDR must have no host bits") from exc
        object.__setattr__(self, "schemes", tuple(sorted(set(self.schemes))))
        object.__setattr__(self, "ports", tuple(sorted(set(self.ports))))
        object.__setattr__(self, "blocked_networks", tuple(sorted(set(networks))))

    def manifest(self):
        return {"version": "web-destination/2", "schemes": list(self.schemes),
                "ports": list(self.ports), "max_redirects": self.max_redirects,
                "blocked_networks": list(self.blocked_networks)}

    @property
    def policy_id(self):
        return digest(self.manifest())


@dataclass(frozen=True)
class Decision:
    allowed: bool
    code: str            # ALLOWED or the refusal reason
    url: str
    host: str | None = None
    port: int | None = None
    address: str | None = None  # pinned: the connector must connect to this address only
    hop: int = 0
    policy_id: str | None = None  # configuration binding, not an authorization token


def classify(address, blocked_networks=()):
    """Return None for a public unicast address, else the refusal reason."""
    if type(address) is not str or not 1 <= len(address) <= 45 or "%" in address:
        raise ValueError("address must be unscoped IP text")
    ip = ipaddress.ip_address(address)
    if any(ip in ipaddress.ip_network(network) for network in blocked_networks):
        return "BLOCKED_NETWORK"
    if ip.version == 6:
        if ip.ipv4_mapped is not None:
            return classify(str(ip.ipv4_mapped), blocked_networks)
        if ip in NAT64_LOCAL:
            # RFC 8215 allocates /48; actual translation subprefix lengths vary.
            # The last 32 bits alone cannot identify the translated destination.
            return "NAT64_LOCAL"
        if ip in NAT64:
            return classify(str(ipaddress.IPv4Address(int(ip) & 0xFFFFFFFF)), blocked_networks)
        if ip.sixtofour is not None:
            return classify(str(ip.sixtofour), blocked_networks)
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
    # Invalid inputs can contain credentials or non-serializable values. A
    # refusal carries only its reason; never echo the rejected URL.
    return Decision(False, code, "", host, port, None, hop)


def _url_text(value):
    if type(value) is not str or not 1 <= len(value) <= MAX_URL:
        raise ContractError("BAD_URL")
    if any(not c.isprintable() or c.isspace() or c == "\\" for c in value):
        raise ContractError("BAD_URL")
    try:
        value.encode("utf-8")
    except UnicodeError as exc:
        raise ContractError("BAD_URL") from exc
    if re.search(r"%(?![0-9a-fA-F]{2})", value):
        raise ContractError("BAD_URL")


def _parse(url, policy):
    _url_text(url)
    try:
        parts = urllib.parse.urlsplit(url)
    except ValueError as exc:
        raise ContractError("BAD_URL") from exc
    scheme = parts.scheme.lower()
    if scheme not in policy.schemes:
        raise ContractError("SCHEME_REFUSED")
    if parts.username is not None or parts.password is not None or "@" in parts.netloc:
        raise ContractError("CREDENTIALS_IN_URL")
    try:
        port = parts.port
    except ValueError as exc:
        raise ContractError("BAD_PORT") from exc
    if parts.netloc.endswith(":") or port == 0:
        raise ContractError("BAD_PORT")
    port = port if port is not None else (443 if scheme == "https" else 80)
    if port not in policy.ports:
        raise ContractError("PORT_REFUSED")
    host = parts.hostname
    if not host:
        raise ContractError("BAD_HOST")
    literal = False
    if ":" in host:
        if not re.fullmatch(r"\[[0-9a-fA-F:.]+\](?::[0-9]+)?", parts.netloc):
            raise ContractError("BAD_HOST")
        try:
            host = str(ipaddress.IPv6Address(host))
        except ValueError as exc:
            raise ContractError("BAD_HOST") from exc
        literal = True
    else:
        host = host[:-1] if host.endswith(".") else host
        try:
            host = host.encode("idna").decode("ascii").lower()
        except UnicodeError as exc:
            raise ContractError("BAD_HOST") from exc
        try:
            host = str(ipaddress.IPv4Address(host))
            literal = True
        except ValueError:
            if NUMERIC_HOST.fullmatch(host):
                raise ContractError("AMBIGUOUS_NUMERIC_HOST")
            labels = host.split(".")
            if len(host) > 253 or len(labels) < 2 or not all(HOST_LABEL.fullmatch(l) for l in labels):
                raise ContractError("BAD_HOST")
            if labels[-1] in {"localhost", "local", "internal", "lan", "home", "localdomain", "arpa"}:
                raise ContractError("LOCAL_NAME")
    authority = f"[{host}]" if ":" in host else host
    if port != (443 if scheme == "https" else 80):
        authority += f":{port}"
    path = urllib.parse.quote(parts.path or "/", safe="/:@!$&'()*+,;=-._~%")
    query = urllib.parse.quote(parts.query, safe="/?:@!$&'()*+,;=-._~%")
    canonical = urllib.parse.urlunsplit((scheme, authority, path, query, ""))
    if len(canonical) > MAX_URL:
        raise ContractError("BAD_URL")
    return scheme, host, port, literal, canonical


def _policy(value):
    if value is None:
        return WebPolicy()
    if not isinstance(value, WebPolicy):
        raise ContractError("policy must be WebPolicy")
    return value


def decide(url, resolver, policy=None, *, hop=0):
    """Check one URL; return a Decision with a pinned public address or a refusal."""
    policy = _policy(policy)
    if type(hop) is not int or not 0 <= hop <= policy.max_redirects:
        raise ContractError("hop must be within the configured redirect budget")
    try:
        scheme, host, port, literal, url = _parse(url, policy)
    except ContractError as exc:
        return _refuse(str(exc), url, hop)
    if literal:
        addresses = [host]
    else:
        try:
            resolved = resolver(host, port)
            if isinstance(resolved, (str, bytes, dict)):
                return _refuse("RESOLUTION_INVALID", url, hop, host, port)
            addresses = list(islice(resolved, MAX_ADDRESSES + 1))
        except Exception:  # noqa: BLE001 - any resolver failure is a refusal, never a pass
            return _refuse("RESOLUTION_FAILED", url, hop, host, port)
        if not addresses:
            return _refuse("RESOLUTION_EMPTY", url, hop, host, port)
        if len(addresses) > MAX_ADDRESSES:
            return _refuse("RESOLUTION_TOO_LARGE", url, hop, host, port)
    for address in addresses:
        try:
            reason = classify(address, policy.blocked_networks)
        except (ValueError, TypeError):
            return _refuse("RESOLUTION_INVALID", url, hop, host, port)
        if reason is not None:
            # One non-public answer refuses the name: a mixed answer is how rebinding starts.
            return _refuse("DESTINATION_" + reason, url, hop, host, port)
    return Decision(True, "ALLOWED", url, host, port, str(ipaddress.ip_address(addresses[0])), hop, policy.policy_id)


def follow(previous, location, resolver, policy=None):
    """Check a redirect target relative to an allowed previous Decision."""
    policy = _policy(policy)
    if not isinstance(previous, Decision) or not previous.allowed:
        raise ContractError("a redirect can only follow an allowed decision")
    if (previous.policy_id != policy.policy_id or type(previous.hop) is not int
            or not 0 <= previous.hop <= policy.max_redirects):
        raise ContractError("redirect must retain its original policy and valid hop")
    hop = previous.hop + 1
    if hop > policy.max_redirects:
        return _refuse("TOO_MANY_REDIRECTS", location, hop)
    try:
        _url_text(location)  # Before urljoin can silently remove controls.
        _parse(previous.url, policy)
        target = urllib.parse.urljoin(previous.url, location)
        scheme = urllib.parse.urlsplit(target).scheme.lower()
    except (ValueError, UnicodeError):
        return _refuse("BAD_URL", location, hop)
    if urllib.parse.urlsplit(previous.url).scheme.lower() == "https" and scheme != "https":
        return _refuse("DOWNGRADE_REFUSED", target, hop)
    return decide(target, resolver, policy, hop=hop)
