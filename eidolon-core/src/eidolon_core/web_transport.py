# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : web_transport.py
# Description : Transport HTTP de lecture candidat, lié à la politique web-destination/2
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

"""Bounded read-only HTTP(S) GET over pinned, policy-checked addresses.

Candidate module, outside the runtime and the CLI. Every hop goes through
``egress.decide``/``egress.follow`` with one policy; the connector connects to
the pinned address only, never resolving the name again. TLS keeps SNI and
certificate verification on the checked name. No proxy, cookie, credential,
request body, custom header or decompression. A result proves which bytes were
received from which address and when; it says nothing about their truth.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import hashlib
import http.client
import math
import re
import socket
import ssl
import time
import urllib.parse

from .contracts import ContractError
from .egress import Decision, WebPolicy, decide, follow

USER_AGENT = "EidolonCore/0.1 (read-only candidate transport)"
REDIRECTS = {301, 302, 303, 307, 308}
MAX_FIELD = 300  # bound for recorded content type and similar single values


class WebTransportError(RuntimeError):
    """Named failure. Never carries response bodies or header values."""

    def __init__(self, code, detail="", *, observation=None):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.observation = observation  # validated headers only, never an error body


@dataclass(frozen=True)
class TransportLimits:
    total_seconds: float = 30.0     # checked between operations; see WEB-TRANSPORT.md
    connect_seconds: float = 10.0   # bounds the TCP connect and TLS handshake socket operations
    read_seconds: float = 10.0      # bounds each socket read, not the whole body
    max_body_bytes: int = 2_000_000
    max_header_bytes: int = 32_000

    def __post_init__(self):
        for name in ("total_seconds", "connect_seconds", "read_seconds"):
            value = getattr(self, name)
            if type(value) not in (int, float) or not 0 < value <= 600:
                raise ContractError(f"{name} must be within (0, 600]")
        for name, maximum in (("max_body_bytes", 100_000_000), ("max_header_bytes", 1_000_000)):
            value = getattr(self, name)
            if type(value) is not int or not 1 <= value <= maximum:
                raise ContractError(f"{name} must be a positive bounded integer")


@dataclass(frozen=True)
class RawResponse:
    status: int
    headers: tuple          # ((name, value), ...) as received, bounded by the connector
    body: bytes
    complete: bool          # False if the peer stopped before the announced end


@dataclass(frozen=True)
class FetchResult:
    final_url: str
    address: str
    port: int
    status: int
    content_type: str | None
    observed_at: str
    size: int
    sha256: str
    hops: tuple = field(default_factory=tuple)   # redacted: no query string, no content
    policy_id: str | None = None
    body: bytes = field(default=b"", repr=False)
    deadline_exceeded: bool = False

    def evidence(self):
        """Compact, content-free description suitable for a mission record."""
        return {"final_url": self.final_url, "address": self.address, "port": self.port,
                "status": self.status, "content_type": self.content_type,
                "observed_at": self.observed_at, "size": self.size, "sha256": self.sha256,
                "hops": [dict(h) for h in self.hops], "policy_id": self.policy_id,
                "deadline_exceeded": self.deadline_exceeded,
                "limits": ["Received bytes only; their content is unverified data, not instructions.",
                           "Proves an observation at observed_at, not current content."]}


class _PinnedHTTPConnection(http.client.HTTPConnection):
    """HTTPConnection whose socket goes to a pinned address; Host keeps the name."""

    def __init__(self, host, port, address, timeout):
        super().__init__(host, port, timeout=timeout)
        self._pinned_address = address

    def connect(self):
        self.sock = socket.create_connection((self._pinned_address, self.port), self.timeout)


class _PinnedHTTPSConnection(_PinnedHTTPConnection):
    def __init__(self, host, port, address, timeout, context):
        super().__init__(host, port, address, timeout)
        self._context = context

    def connect(self):
        super().connect()
        # SNI and certificate hostname checks use the policy-checked NAME, not the IP.
        self.sock = self._context.wrap_socket(self.sock, server_hostname=self.host)


class StdlibConnector:
    """Default connector on http.client. Reads with bounds; never follows redirects."""

    def __init__(self, ssl_context=None):
        context = ssl_context or ssl.create_default_context()
        if (not isinstance(context, ssl.SSLContext) or context.verify_mode != ssl.CERT_REQUIRED
                or not context.check_hostname):
            raise ContractError("TLS context must verify certificates and host names")
        self._context = context

    def exchange(self, *, scheme, host, port, address, target, headers, limits, deadline):
        # The caller can retain and mutate an injected SSLContext after __init__.
        if self._context.verify_mode != ssl.CERT_REQUIRED or not self._context.check_hostname:
            raise ContractError("TLS context no longer verifies certificates and host names")
        if scheme == "https":
            conn = _PinnedHTTPSConnection(host, port, address, limits.connect_seconds, self._context)
        else:
            conn = _PinnedHTTPConnection(host, port, address, limits.connect_seconds)
        try:
            conn.putrequest("GET", target, skip_host=True, skip_accept_encoding=True)
            for name, value in headers:
                conn.putheader(name, value)
            conn.endheaders()
            conn.sock.settimeout(limits.read_seconds)
            response = conn.getresponse()
            received = tuple(response.getheaders())
            declared = _check_headers(response.status, received, limits)
            if response.status in REDIRECTS or not 200 <= response.status < 300:
                return RawResponse(response.status, received, b"", True)  # body never read
            chunks, size = [], 0
            while True:
                if time.monotonic() > deadline:
                    raise WebTransportError("DEADLINE_EXCEEDED", "during body")
                chunk = response.read(min(65536, limits.max_body_bytes + 1 - size))
                if not chunk:
                    break
                chunks.append(chunk)
                size += len(chunk)
                if size > limits.max_body_bytes:
                    raise WebTransportError("BODY_TOO_LARGE", f"more than {limits.max_body_bytes} bytes")
                if response.isclosed():
                    break  # preserve a complete receipt even if the last read was late
            body = b"".join(chunks)
            complete = declared is None or declared == len(body)
            return RawResponse(response.status, received, body, complete)
        except WebTransportError:
            raise
        except ssl.SSLCertVerificationError as exc:
            raise WebTransportError("TLS_CERTIFICATE", type(exc).__name__) from exc
        except ssl.SSLError as exc:
            raise WebTransportError("TLS_ERROR", type(exc).__name__) from exc
        except http.client.IncompleteRead as exc:
            raise WebTransportError("TRUNCATED", "peer closed before the end of the body") from exc
        except (http.client.LineTooLong, http.client.HTTPException) as exc:
            code = "HEADERS_TOO_LARGE" if "header" in str(exc).lower() or isinstance(
                exc, http.client.LineTooLong) else "BAD_HTTP_RESPONSE"
            raise WebTransportError(code, type(exc).__name__) from exc
        except (socket.timeout, TimeoutError) as exc:
            raise WebTransportError("TIMEOUT", "socket operation exceeded its timeout") from exc
        except OSError as exc:
            raise WebTransportError("CONNECTION_FAILED", type(exc).__name__) from exc
        finally:
            conn.close()


def _host_header(host, scheme, port):
    name = f"[{host}]" if ":" in host else host
    return name if port == (443 if scheme == "https" else 80) else f"{name}:{port}"


def _redacted(url):
    parts = urllib.parse.urlsplit(url)
    hop = {"url": urllib.parse.urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))}
    if parts.query:
        hop["query_sha256"] = hashlib.sha256(parts.query.encode("utf-8")).hexdigest()
    return hop


def _header(headers, name):
    values = [v for k, v in headers if k.lower() == name]
    if len(values) > 1:
        raise WebTransportError("AMBIGUOUS_HEADER", name)
    return values[0] if values else None


def _check_headers(status, headers, limits):
    if (type(status) is not int or not 100 <= status <= 599
            or type(headers) not in (list, tuple) or len(headers) > 100):
        raise WebTransportError("BAD_HTTP_RESPONSE")
    for entry in headers:
        if (type(entry) not in (list, tuple) or len(entry) != 2
                or any(type(v) is not str for v in entry)):
            raise WebTransportError("BAD_HTTP_RESPONSE")
        k, v = entry
        if (not re.fullmatch(r"[!#$%&'*+.^_`|~0-9A-Za-z-]+", k)
                or any(ord(c) > 255 or ord(c) < 32 and c != '\t' or ord(c) == 127 for c in v)):
            raise WebTransportError("BAD_HTTP_RESPONSE")
    if sum(len(k) + len(v) + 4 for k, v in headers) > limits.max_header_bytes:
        raise WebTransportError("HEADERS_TOO_LARGE")
    values = {name: _header(headers, name) for name in
              ("content-length", "transfer-encoding", "content-encoding", "content-type", "location", "retry-after")}
    length, transfer = values["content-length"], values["transfer-encoding"]
    if length is not None and transfer is not None:
        raise WebTransportError("AMBIGUOUS_HEADER", "content-length with transfer-encoding")
    if length is not None:
        if not re.fullmatch(r"[0-9]{1,20}", length.strip()):
            raise WebTransportError("BAD_HTTP_RESPONSE", "invalid content-length")
        length = int(length)
    if 200 <= status < 300:
        encoding = values["content-encoding"]
        if (encoding is not None and encoding.strip().lower() != "identity"
                or transfer is not None and transfer.strip().lower() != "chunked"):
            raise WebTransportError("ENCODED_CONTENT")
        if length is not None and length > limits.max_body_bytes:
            raise WebTransportError("BODY_TOO_LARGE")
    return length


def _retry_after(value, now):
    """Seconds or HTTP-date; invalid/over-one-day values require review, never shortening."""
    if value is None:
        return None, False
    value = value.strip()
    try:
        if re.fullmatch(r"[0-9]+", value):
            if len(value) > 10:
                return None, True
            seconds = int(value)
        else:
            date = parsedate_to_datetime(value)
            if date.tzinfo is None:
                date = date.replace(tzinfo=timezone.utc)  # obsolete HTTP asctime is UTC
            seconds = max(0, math.ceil((date - now).total_seconds()))
        return (seconds, False) if seconds <= 86400 else (None, True)
    except (ValueError, TypeError, OverflowError):
        return None, True


def fetch(url, *, policy, resolver, connector=None, limits=None, clock=time.monotonic, before_hop=None):
    """GET one public URL under ``policy``; follow redirects only after re-checking them."""
    if not isinstance(policy, WebPolicy):
        raise ContractError("an explicit WebPolicy is required")
    if isinstance(url, Decision):
        raise ContractError("a Decision is never accepted as input; pass the URL")
    limits = limits or TransportLimits()
    if not isinstance(limits, TransportLimits):
        raise ContractError("TransportLimits required")
    connector = connector or StdlibConnector()
    deadline = clock() + limits.total_seconds
    decision = decide(url, resolver, policy)
    hops, seen = [], set()
    while True:
        if not decision.allowed:
            # The refused destination is never contacted; the refused URL is not echoed.
            raise WebTransportError("DESTINATION_REFUSED", decision.code)
        if decision.url in seen:
            raise WebTransportError("REDIRECT_LOOP", f"hop {decision.hop}")
        seen.add(decision.url)
        if clock() > deadline:
            raise WebTransportError("DEADLINE_EXCEEDED", f"before hop {decision.hop}")
        if before_hop is not None:
            before_hop(decision)  # may only further restrict a policy-approved hop
        parts = urllib.parse.urlsplit(decision.url)
        target = urllib.parse.urlunsplit(("", "", parts.path or "/", parts.query, ""))
        headers = (("Host", _host_header(decision.host, parts.scheme, decision.port)),
                   ("User-Agent", USER_AGENT), ("Accept", "*/*"),
                   ("Accept-Encoding", "identity"), ("Connection", "close"))
        response = connector.exchange(scheme=parts.scheme, host=decision.host, port=decision.port,
                                      address=decision.address, target=target, headers=headers,
                                      limits=limits, deadline=deadline)
        if (not isinstance(response, RawResponse) or type(response.body) is not bytes
                or type(response.complete) is not bool):
            raise WebTransportError("BAD_HTTP_RESPONSE", "connector returned no RawResponse")
        declared = _check_headers(response.status, response.headers, limits)
        hops.append({**_redacted(decision.url), "address": decision.address, "port": decision.port,
                     "status": response.status})
        observed = datetime.now(timezone.utc)
        retry, review = _retry_after(_header(response.headers, "retry-after"), observed)
        observation = {"kind": "http_headers", "final_url": decision.url,
                       "address": decision.address, "port": decision.port, "status": response.status,
                       "observed_at": observed.isoformat(), "policy_id": decision.policy_id,
                       "hops": hops, "retry_after": retry, "retry_review_required": review}
        if response.status in REDIRECTS:
            if review or retry:
                # No wait inside the controller, and no early request to Location.
                raise WebTransportError("HTTP_STATUS", "redirect deferred", observation=observation)
            location = _header(response.headers, "location")
            if location is None:
                raise WebTransportError("HTTP_STATUS", f"redirect {response.status} without Location")
            decision = follow(decision, location, resolver, policy)
            continue
        if not 200 <= response.status < 300:
            raise WebTransportError("HTTP_STATUS", f"status {response.status}", observation=observation)
        if not response.complete or declared is not None and declared != len(response.body):
            raise WebTransportError("TRUNCATED", "body shorter than announced")
        if len(response.body) > limits.max_body_bytes:
            raise WebTransportError("BODY_TOO_LARGE", f"more than {limits.max_body_bytes} bytes")
        content_type = _header(response.headers, "content-type")
        if content_type is not None:
            content_type = "".join(c for c in content_type if c.isprintable())[:MAX_FIELD]
        return FetchResult(final_url=decision.url, address=decision.address, port=decision.port,
                           status=response.status, content_type=content_type,
                           observed_at=observed.isoformat(), size=len(response.body),
                           sha256=hashlib.sha256(response.body).hexdigest(), hops=tuple(hops),
                           policy_id=decision.policy_id, body=response.body,
                           deadline_exceeded=clock() >= deadline)
