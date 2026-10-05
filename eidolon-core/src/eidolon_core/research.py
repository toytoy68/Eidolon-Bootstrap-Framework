# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : research.py
# Description : Recherche multi-fournisseurs, preuves et replis bornés
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

"""Candidate coordinator, independent of mission success and memory mutation.

Providers/readers are trusted injectable code. No network implementation here.
Only complete UTF-8 plain text/Markdown is readable in this first slice. HTML
challenge/login detection is deliberately partial, not a universal classifier.
"""
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from itertools import islice
import hashlib
import re
import time

from .contracts import ContractError, digest, snapshot
from .egress import WebPolicy, decide

FAILURES = {"UNAVAILABLE", "RATE_LIMITED", "ACCESS_DENIED", "CHALLENGE", "TIMEOUT"}


class AccessFailure(Exception):
    def __init__(self, code, retry_after=None):
        if code not in FAILURES or (retry_after is not None and
                (type(retry_after) is not int or not 0 <= retry_after <= 86400)):
            raise ContractError("invalid access failure")
        self.code, self.retry_after = code, retry_after
        super().__init__(code)  # no provider error body or credentials


@dataclass(frozen=True)
class Hit:
    url: str
    title: str
    snippet: str = ""


@dataclass(frozen=True)
class Page:
    url: str
    status: int
    media_type: str
    body: bytes
    policy_id: str
    complete: bool = True
    retry_after: int | None = None


@dataclass(frozen=True)
class ResearchLimits:
    providers: int = 3
    hits_per_provider: int = 10
    reads: int = 5
    body_bytes: int = 128_000
    seconds: float = 30
    cache_entries: int = 16
    cache_seconds: float = 60

    def __post_init__(self):
        for name, maximum in (("providers", 8), ("hits_per_provider", 20), ("reads", 20),
                              ("body_bytes", 128_000), ("cache_entries", 64)):
            v = getattr(self, name)
            if type(v) is not int or not 1 <= v <= maximum:
                raise ContractError(f"invalid research limit {name}")
        for name, maximum in (("seconds", 600), ("cache_seconds", 3600)):
            v = getattr(self, name)
            if type(v) not in (int, float) or not 0 < v <= maximum:
                raise ContractError(f"invalid research limit {name}")


def _text(value, maximum, *, empty=False):
    if (type(value) is not str or len(value) > maximum or (not empty and not value.strip())):
        raise ContractError("invalid bounded text")
    try:
        value.encode("utf-8")
    except UnicodeError as exc:
        raise ContractError("text must be UTF-8") from exc
    return value


class _HtmlSignals(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_title, self.title, self.password = False, [], False

    def handle_starttag(self, tag, attrs):
        if tag == "title":
            self.in_title = True
        if tag == "input" and dict(attrs).get("type", "").lower() == "password":
            self.password = True

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False

    def handle_data(self, data):
        if self.in_title:
            self.title.append(data)


def classify_page(page, limits):
    """Return a content state and optional readable text; HTTP 200 is insufficient."""
    if (not isinstance(page, Page) or type(page.status) is not int or not 100 <= page.status <= 599
            or type(page.complete) is not bool or type(page.body) is not bytes
            or type(page.media_type) is not str or len(page.media_type) > 200
            or (page.retry_after is not None and (type(page.retry_after) is not int
                or not 0 <= page.retry_after <= 86400))):
        raise ContractError("invalid page envelope")
    if len(page.body) > limits.body_bytes:
        return "TOO_LARGE", None
    if not page.complete:
        return "TRUNCATED", None
    if page.status == 429:
        return "RATE_LIMITED", None
    if page.status in {401, 403}:
        return "ACCESS_DENIED", None
    if page.status != 200:
        return "HTTP_ERROR", None
    try:
        content = page.body.decode("utf-8")
    except UnicodeError:
        return "INVALID_ENCODING", None
    if not content.strip():
        return "EMPTY_CONTENT", None
    media_type = page.media_type.partition(";")[0].strip().lower()
    looks_html = re.match(r"\s*<(?:!doctype\s+html|html|head|title|form)(?:\s|>)", content, re.I)
    if media_type == "text/html" or looks_html:
        parser = _HtmlSignals()
        parser.feed(content)
        title = " ".join(" ".join(parser.title).split()).lower()
        if title in {"just a moment...", "verify you are human", "verification required", "captcha"}:
            return "CHALLENGE_SUSPECTED", None
        if parser.password:
            return "LOGIN_SUSPECTED", None
        return "UNSUPPORTED_CONTENT", None  # no HTML extractor silently invented
    if media_type not in {"text/plain", "text/markdown"}:
        return "UNSUPPORTED_CONTENT", None
    return "READ", content


class ResearchCoordinator:
    """One sequential research operation; bounded RAM cache, no automatic retries.

    provider.search(query, limit) -> iterable[Hit]; provider.provider_id
    reader.read(canonical_url, policy) -> Page; reader.reader_id
    Reader MUST enforce policy on every redirect/actual connection. This class
    prechecks candidates and checks the final URL but cannot sandbox a provider.
    """
    def __init__(self, providers, reader, *, resolver, policy=None, limits=None, clock=time.monotonic):
        if not isinstance(providers, (list, tuple)) or not 1 <= len(providers) <= 8:
            raise ContractError("one to eight providers required")
        identities = [p.provider_id for p in providers]
        if (any(type(v) is not str or re.fullmatch(r"[a-zA-Z0-9._/-]{1,100}", v) is None
                for v in identities + [reader.reader_id]) or len(set(identities)) != len(identities)):
            raise ContractError("unique bounded provider identities required")
        self.providers, self.reader, self.resolver = tuple(providers), reader, resolver
        self.policy = policy if policy is not None else WebPolicy()
        self.limits = limits if limits is not None else ResearchLimits()
        if not isinstance(self.policy, WebPolicy) or not isinstance(self.limits, ResearchLimits):
            raise ContractError("invalid research configuration")
        self.clock, self._cache, self._cooldowns = clock, OrderedDict(), {}
        self._pause_until = 0

    def _rate_limit(self, domain, retry_after):
        until = self.clock() + (retry_after if retry_after is not None else 60)
        if len(self._cooldowns) >= 64 and domain not in self._cooldowns:
            # Bound memory without forgetting an active refusal: pause all reads.
            self._pause_until = max(until, *self._cooldowns.values())
            self._cooldowns.clear()
        else:
            self._cooldowns[domain] = until

    def run(self, query, *, required_pages=1, cancelled=lambda: False):
        _text(query, 1000)
        if type(required_pages) is not int or not 1 <= required_pages <= self.limits.reads:
            raise ContractError("required_pages must fit the read budget")
        start = self.clock()
        self._cooldowns = {k: v for k, v in self._cooldowns.items() if v > start}
        report = {"version": 1, "query_sha256": digest(query), "policy_id": self.policy.policy_id,
                  "required_pages": required_pages, "readable_pages": 0, "read_calls": 0,
                  "providers": [], "sources": [], "status": None,
                  "scope": "retrieved text only; no claim verification or mission success"}
        seen, final_seen = {}, set()

        def stop():
            if cancelled():
                return "CANCELLED"
            if self.clock() - start >= self.limits.seconds:
                return "DEADLINE"
            return None

        def enough():
            return report["readable_pages"] >= required_pages

        for provider in self.providers[:self.limits.providers]:
            if stop() or enough():
                break
            provider_record = {"provider_id": provider.provider_id, "status": "OK"}
            report["providers"].append(provider_record)
            try:
                hits = list(islice(provider.search(query, self.limits.hits_per_provider),
                                   self.limits.hits_per_provider + 1))
                if len(hits) > self.limits.hits_per_provider:
                    raise ContractError("too many search results")
                for hit in hits:
                    if not isinstance(hit, Hit):
                        raise ContractError("invalid search result")
                    _text(hit.url, 2048); _text(hit.title, 500); _text(hit.snippet, 1000, empty=True)
                if not hits:
                    provider_record["status"] = "EMPTY"
            except AccessFailure as exc:
                provider_record.update(status=exc.code, retry_after=exc.retry_after)
                continue
            except Exception:
                provider_record["status"] = "PROVIDER_ERROR"
                continue
            # If interrupted after search, preserve discovery without starting reads.
            for hit in hits:
                decision = decide(hit.url, self.resolver, self.policy) if not stop() else None
                origin = {"provider_id": provider.provider_id, "title": hit.title, "snippet": hit.snippet}
                url = decision.url if decision and decision.allowed else None
                if url in seen:
                    seen[url]["found_by"].append(origin)
                    continue
                source = {"id": "s-" + digest(hit.url), "found_by": [origin], "state": "DISCOVERED",
                          "url": url, "final_url": None, "text": None, "cache_hit": False}
                report["sources"].append(source)
                if decision is None:
                    continue
                if not decision.allowed:
                    source.update(state="POLICY_REFUSED", reason=decision.code)
                    continue
                seen[url] = source
                if enough() or stop():
                    continue
                key = (self.reader.reader_id, self.policy.policy_id, url)
                cached = self._cache.get(key)
                if cached and self.clock() < cached[0]:
                    # Revalidate the cached FINAL destination against current DNS too.
                    final = decide(cached[1]["final_url"], self.resolver, self.policy)
                    if final.allowed:
                        source.update(snapshot(cached[1]), cache_hit=True)
                        self._cache.move_to_end(key)
                    else:
                        source.update(state="POLICY_REFUSED", reason=final.code)
                else:
                    self._cache.pop(key, None)
                    domain = (decision.host, decision.port)
                    if max(self._pause_until, self._cooldowns.get(domain, 0)) > self.clock():
                        source["state"] = "RATE_LIMITED"
                        continue
                    if report["read_calls"] >= self.limits.reads:
                        source["state"] = "READ_BUDGET"
                        continue
                    report["read_calls"] += 1
                    try:
                        page = self.reader.read(url, self.policy)
                        state, content = classify_page(page, self.limits)
                        if page.policy_id != self.policy.policy_id:
                            raise ContractError("reader policy mismatch")
                        final = decide(page.url, self.resolver, self.policy)
                        if not final.allowed:
                            source.update(state="POLICY_REFUSED", reason=final.code)
                            continue
                        source.update(state=state, final_url=final.url,
                                      http_status=page.status, retry_after=page.retry_after)
                        if state == "RATE_LIMITED":
                            self._rate_limit(domain, page.retry_after)
                        if state == "READ":
                            evidence = {"state": "READ", "final_url": final.url, "text": content,
                                        "observed_at": datetime.now(timezone.utc).isoformat(),
                                        "body_sha256": hashlib.sha256(page.body).hexdigest(),
                                        "body_bytes": len(page.body), "media_type": page.media_type,
                                        "reader_id": self.reader.reader_id, "policy_id": page.policy_id}
                            source.update(evidence)
                            self._cache[key] = (self.clock() + self.limits.cache_seconds, snapshot(evidence))
                            while len(self._cache) > self.limits.cache_entries:
                                self._cache.popitem(last=False)
                    except AccessFailure as exc:
                        source.update(state=exc.code, retry_after=exc.retry_after)
                        if exc.code == "RATE_LIMITED":
                            self._rate_limit(domain, exc.retry_after)
                    except Exception:
                        source["state"] = "READER_ERROR"
                if source["state"] == "READ":
                    if source["final_url"] in final_seen:
                        source["state"] = "DUPLICATE_FINAL"
                    else:
                        final_seen.add(source["final_url"])
                        report["readable_pages"] += 1
            if report["read_calls"] >= self.limits.reads and not enough():
                break
        report["status"] = stop() or ("READ_TARGET_MET" if enough() else
            "PARTIAL" if report["readable_pages"] else "NO_READABLE_SOURCE")
        report["limitation"] = ("READ_BUDGET" if not enough() and report["read_calls"] >= self.limits.reads
            else "PROVIDER_BUDGET" if not enough() and len(self.providers) > self.limits.providers else None)
        return report
