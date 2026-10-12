# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : web_search.py
# Description : Recherche Web G187 par une instance SearXNG locale : contrat web.search, budget, reçus, sans clé
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Candidate provider, outside the runtime, the CLI and the dialogue (toytoy, 12/10/2026: free search, SearXNG).

SearXNG runs on the SAME machine as Core: the client only accepts a loopback base URL (127.0.0.1 or ::1),
sends one fixed GET /search?q=...&format=json, follows no redirect, uses no proxy and no credential, and
bounds time and size. Results are candidates: every URL is re-checked by egress.decide before any read
(ResearchCoordinator already does so), and their text is untrusted data, never instructions.

Two entry points:
- SearxngProvider.search(query, limit) -> [Hit]: the ResearchCoordinator provider interface;
- web_search(provider, query, ...) -> dict: the G187 contract (status, results, receipt), with an explicit
  approval of the exact query and a call budget. The receipt never holds the query text.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import http.client
import ipaddress
import json
import socket
import threading
import time
import urllib.parse

from .contracts import ContractError
from .research import AccessFailure, Hit

SCHEMA = "eidolon-web-search/1"
STATUSES = ("OK", "EMPTY", "BLOCKED", "TIMEOUT", "ERROR")
MAX_QUERY_CHARS = 400
USER_AGENT = "EidolonCore/0.1 (local SearXNG client)"


@dataclass(frozen=True)
class SearchLimits:
    timeout_seconds: float = 10.0
    max_body_bytes: int = 512_000
    max_results: int = 10
    title_chars: int = 300
    snippet_chars: int = 500

    def __post_init__(self):
        if type(self.timeout_seconds) not in (int, float) or not 0 < self.timeout_seconds <= 60:
            raise ContractError("timeout_seconds must be within (0, 60]")
        for name, maximum in (("max_body_bytes", 4_000_000), ("max_results", 20), ("title_chars", 500),
                              ("snippet_chars", 1000)):
            value = getattr(self, name)
            if type(value) is not int or not 1 <= value <= maximum:
                raise ContractError(f"invalid search limit {name}")


class Budget:
    """Calls per UTC day, in memory (a durable budget belongs to the Mission Manager integration)."""

    def __init__(self, per_day=100, *, clock=lambda: datetime.now(timezone.utc)):
        if type(per_day) is not int or not 1 <= per_day <= 10_000:
            raise ContractError("invalid daily budget")
        self.per_day, self._clock, self._lock = per_day, clock, threading.Lock()
        self._day, self._used = None, 0

    def take(self):
        with self._lock:
            day = self._clock().date()
            if day != self._day:
                self._day, self._used = day, 0
            if self._used >= self.per_day:
                return False
            self._used += 1
            return True

    def used(self):
        with self._lock:
            return self._used if self._day == self._clock().date() else 0


def _loopback_base(url):
    try:
        parts = urllib.parse.urlsplit(url)
        address = ipaddress.ip_address((parts.hostname or "").strip("[]"))
        port = parts.port
    except ValueError:
        raise ContractError("SearXNG base URL must be http(s)://127.0.0.1:port or [::1]") from None
    if (parts.scheme not in ("http", "https") or not address.is_loopback or parts.username or parts.password
            or parts.query or parts.fragment or parts.path not in ("", "/") or port is None):
        raise ContractError("SearXNG base URL must be http(s)://127.0.0.1:port or [::1]")
    return parts.scheme, str(address), port


def _clean(value, maximum):
    if not isinstance(value, str):
        return ""
    text = " ".join("".join(c if c.isprintable() else " " for c in value).split())
    return text[:maximum]


def _candidate_url(value):
    """Syntax only: http(s), a host, no credentials. Destination checks happen later, per hop (egress)."""
    if not isinstance(value, str) or not 1 <= len(value) <= 2048:
        return None
    try:
        parts = urllib.parse.urlsplit(value)
        host = parts.hostname
    except ValueError:
        return None
    if parts.scheme not in ("http", "https") or not host or parts.username or parts.password:
        return None
    return value


class SearxngProvider:
    """One local SearXNG instance. Thread-safe; holds no secret."""

    def __init__(self, base_url, *, limits=None, language="fr", safesearch=1, connection_factory=None):
        self.scheme, self.host, self.port = _loopback_base(base_url)
        self.limits = limits or SearchLimits()
        if not isinstance(self.limits, SearchLimits):
            raise ContractError("SearchLimits required")
        if not isinstance(language, str) or not 2 <= len(language) <= 10 or not language.replace("-", "").isalpha():
            raise ContractError("invalid language")
        if safesearch not in (0, 1, 2):
            raise ContractError("safesearch must be 0, 1 or 2")
        self.language, self.safesearch = language, safesearch
        self._factory = connection_factory
        self.provider_id = "searxng/1"

    def _connection(self):
        if self._factory is not None:
            return self._factory(self.host, self.port, self.limits.timeout_seconds)
        cls = http.client.HTTPSConnection if self.scheme == "https" else http.client.HTTPConnection
        return cls(self.host, self.port, timeout=self.limits.timeout_seconds)

    def query(self, query, limit):
        """Raw exchange -> (results, unresponsive_engines). Raises AccessFailure with a named code only."""
        if not isinstance(query, str) or not query.strip() or len(query) > MAX_QUERY_CHARS:
            raise ContractError("invalid search query")
        if any(ord(c) < 32 for c in query):
            raise ContractError("invalid search query")
        target = "/search?" + urllib.parse.urlencode({"q": query, "format": "json", "language": self.language,
                                                       "safesearch": self.safesearch, "pageno": 1})
        deadline = time.monotonic() + self.limits.timeout_seconds
        conn = self._connection()
        try:
            conn.request("GET", target, headers={"User-Agent": USER_AGENT, "Accept": "application/json",
                                                 "Accept-Encoding": "identity", "Connection": "close"})
            response = conn.getresponse()
            if response.status == 429:
                raise AccessFailure("RATE_LIMITED")
            if response.status in (401, 403):
                raise AccessFailure("ACCESS_DENIED")
            if response.status != 200:
                raise AccessFailure("UNAVAILABLE")
            if (response.getheader("Content-Encoding") or "identity").strip().lower() != "identity":
                raise AccessFailure("UNSUPPORTED_CONTENT")
            chunks, size = [], 0
            while True:
                if time.monotonic() > deadline:
                    raise AccessFailure("TIMEOUT")
                chunk = response.read(min(65536, self.limits.max_body_bytes + 1 - size))
                if not chunk:
                    break
                chunks.append(chunk)
                size += len(chunk)
                if size > self.limits.max_body_bytes:
                    raise AccessFailure("TOO_LARGE")
        except AccessFailure:
            raise
        except (socket.timeout, TimeoutError):
            raise AccessFailure("TIMEOUT") from None
        except (OSError, http.client.HTTPException):
            raise AccessFailure("UNAVAILABLE") from None
        finally:
            conn.close()
        try:
            value = json.loads(b"".join(chunks).decode("utf-8"), parse_constant=_no_constant)
        except (ValueError, UnicodeError, RecursionError):
            raise AccessFailure("INVALID_RESPONSE") from None
        if not isinstance(value, dict) or not isinstance(value.get("results"), list):
            raise AccessFailure("INVALID_RESPONSE")
        results, seen = [], set()
        for item in value["results"]:
            if len(results) >= min(limit, self.limits.max_results):
                break
            if not isinstance(item, dict):
                continue
            url = _candidate_url(item.get("url"))
            title = _clean(item.get("title"), self.limits.title_chars)
            if url is None or not title or url in seen:
                continue
            seen.add(url)
            engines = item.get("engines") if isinstance(item.get("engines"), list) else [item.get("engine")]
            results.append({"url": url, "title": title,
                            "snippet": _clean(item.get("content"), self.limits.snippet_chars),
                            "engines": sorted({_clean(e, 40) for e in engines if isinstance(e, str)})[:8],
                            "published": _clean(item.get("publishedDate"), 40) or None})
        unresponsive = value.get("unresponsive_engines")
        return results, len(unresponsive) if isinstance(unresponsive, list) else 0

    def search(self, query, limit):
        """ResearchCoordinator interface."""
        results, _ = self.query(query, limit)
        return [Hit(r["url"], r["title"], r["snippet"]) for r in results]


def _no_constant(_):
    raise ValueError("non-finite value")


_STATUS_OF = {"RATE_LIMITED": "BLOCKED", "ACCESS_DENIED": "BLOCKED", "TIMEOUT": "TIMEOUT"}


def web_search(provider, query, *, approved, budget, max_results=10, clock=lambda: datetime.now(timezone.utc)):
    """G187 web.search. ``approved`` must be True: the caller showed this exact query to the user.

    Never raises on provider failures: the status says what happened, and an EMPTY or failed search is
    never completed with invented sources.
    """
    if not isinstance(provider, SearxngProvider) or not isinstance(budget, Budget):
        raise ContractError("SearxngProvider and Budget required")
    if type(max_results) is not int or not 1 <= max_results <= provider.limits.max_results:
        raise ContractError("invalid max_results")
    query_sha256 = hashlib.sha256(query.encode("utf-8")).hexdigest() if isinstance(query, str) else None
    receipt = {"schema": SCHEMA, "provider": provider.provider_id, "query_sha256": query_sha256,
               "query_shown_to_user": approved is True, "sent_at": None, "results_count": 0,
               "unresponsive_engines": 0, "budget_used": None, "error_code": None}

    def out(status, results=(), code=None):
        receipt.update(error_code=code, results_count=len(results), budget_used=budget.used())
        return {"status": status, "results": [dict(r, rank=i + 1, provider=provider.provider_id)
                                             for i, r in enumerate(results)],
                "receipt": dict(receipt), "untrusted": True}

    if approved is not True:
        return out("BLOCKED", code="QUERY_NOT_APPROVED")
    if (not isinstance(query, str) or not query.strip() or len(query) > MAX_QUERY_CHARS
            or any(ord(c) < 32 for c in query)):
        return out("ERROR", code="INVALID_QUERY")
    if not budget.take():
        return out("BLOCKED", code="BUDGET_EXHAUSTED")
    receipt["sent_at"] = clock().isoformat()
    try:
        results, unresponsive = provider.query(query, max_results)
    except AccessFailure as exc:
        return out(_STATUS_OF.get(exc.code, "ERROR"), code=exc.code)
    receipt["unresponsive_engines"] = unresponsive
    return out("OK" if results else "EMPTY", results)
