# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : research.py
# Description : Recherche multi-fournisseurs, preuves et replis bornés
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

"""Candidate coordinator, independent of mission success and memory mutation.

Providers/readers are trusted injectable code. No network implementation here.
Complete UTF-8 text/Markdown is readable; HTML extraction is an explicit reader
option. Access-wall detection is deliberately partial, not a universal classifier.
"""
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from itertools import islice
import hashlib
import re
import time

from .contracts import ContractError, digest, encode, snapshot
from .egress import WebPolicy, decide
from .html_extract import ExtractLimits, extract
from .research_pauses import ResearchPauses, PauseStorageError, PauseCapacityError, provider_scope, origin_scope
from .research_report import project_report
from .query_cleanup import clean_query
from .research_guard import ResearchGuard

FAILURES = {"UNAVAILABLE", "RATE_LIMITED", "ACCESS_DENIED", "CHALLENGE", "TIMEOUT",
            "POLICY_REFUSED", "TOO_LARGE", "TRUNCATED", "UNSUPPORTED_CONTENT", "INVALID_RESPONSE", "TLS_ERROR",
            "RETRY_WAIT", "CANCELLED"}


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
    retry_review_required: bool = False
    deadline_exceeded: bool = False
    retrieval: dict | None = None
    html_limits: ExtractLimits | None = None


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
        self.title_done, self.foreign = False, 0

    def handle_starttag(self, tag, attrs):
        if tag in {"svg", "math"}:
            self.foreign += 1
        # First document title only, as html_extract: an SVG/MathML or later title is not one.
        if tag == "title" and not self.title_done and not self.foreign:
            self.in_title = True
        # Browsers keep the FIRST duplicated attribute; dict() would keep the last one.
        kind = next((v for k, v in attrs if k == "type"), None)
        if tag == "input" and (kind or "").lower() == "password":
            self.password = True

    def handle_endtag(self, tag):
        if tag in {"svg", "math"} and self.foreign:
            self.foreign -= 1
        if tag == "title" and self.in_title:
            self.in_title, self.title_done = False, True

    def handle_data(self, data):
        if self.in_title:
            self.title.append(data)


def _classify_page(page, limits):
    """Return a content state and optional readable text; HTTP 200 is insufficient."""
    if (not isinstance(page, Page) or type(page.status) is not int or not 100 <= page.status <= 599
            or type(page.complete) is not bool or type(page.body) is not bytes
            or type(page.retry_review_required) is not bool or type(page.deadline_exceeded) is not bool
            or (page.html_limits is not None and (not isinstance(page.html_limits, ExtractLimits)
                or page.html_limits.input_bytes > 128_000 or page.html_limits.output_chars > 64_000))
            or type(page.media_type) is not str or len(page.media_type) > 200
            or (page.retry_after is not None and (type(page.retry_after) is not int
                or not 0 <= page.retry_after <= 86400))):
        raise ContractError("invalid page envelope")
    # Refusal is known from the validated status even when its body is unusable.
    # Never downgrade a quota/access refusal into a retryable content problem.
    if page.status == 429:
        return "RATE_LIMITED", None, None
    if page.status in {401, 403}:
        return "ACCESS_DENIED", None, None
    if len(page.body) > limits.body_bytes:
        return "TOO_LARGE", None, None
    if not page.complete:
        return "TRUNCATED", None, None
    if page.status != 200:
        return "HTTP_ERROR", None, None
    try:
        content = page.body.decode("utf-8")
    except UnicodeError:
        return "INVALID_ENCODING", None, None
    if not content.strip():
        return "EMPTY_CONTENT", None, None
    media_type = page.media_type.partition(";")[0].strip().lower()
    # Scan the bounded prefix once; avoid backtracking across repeated comments.
    pos = 1 if content.startswith("\ufeff") else 0
    while pos < len(content):
        if content[pos].isspace():
            pos += 1
        elif content.startswith("<!--", pos):
            end = content.find("-->", pos + 4)
            if end < 0:
                break
            pos = end + 3
        else:
            break
    looks_html = re.match(r"<(?:!doctype\s+html|html|head|body|title|meta|form|div|p|input)(?:\s|/?>)",
                          content[pos:], re.I)
    if media_type == "text/html" or looks_html:
        parser = _HtmlSignals()
        parser.feed(content)
        title = " ".join(" ".join(parser.title).split()).lower()
        if title in {"just a moment...", "verify you are human", "verification required", "captcha"}:
            return "CHALLENGE_SUSPECTED", None, None
        if parser.password:
            return "LOGIN_SUSPECTED", None, None
        if title in {"subscribe to continue", "subscription required", "abonnez-vous pour continuer"}:
            return "PAYWALL_SUSPECTED", None, None
        if page.html_limits is None or media_type != "text/html":
            return "UNSUPPORTED_CONTENT", None, None
        # No charset guessing, extra parameters or extraction of mislabeled HTML.
        if not re.fullmatch(r'text/html(?:\s*;\s*charset\s*=\s*(?:utf-8|"utf-8"))?\s*',
                            page.media_type.strip(), re.I):
            return "UNSUPPORTED_CONTENT", None, None
        extracted = extract(page.body, page.html_limits)
        details = {k: v for k, v in extracted.items() if k not in {"text", "title", "signals"}}
        if extracted["status"] == "PARTIAL":
            return "EXTRACTION_PARTIAL", None, details
        if extracted["status"] == "REFUSED":
            return "EXTRACTION_REFUSED", None, details
        if extracted["status"] == "EMPTY":
            return "EMPTY_CONTENT", None, details
        return "READ", extracted["text"], details
    if media_type not in {"text/plain", "text/markdown"}:
        return "UNSUPPORTED_CONTENT", None, None
    return "READ", content, None


def classify_page(page, limits):
    """Compatibility API: content state and text only; the coordinator retains details."""
    state, text, _ = _classify_page(page, limits)
    return state, text


class ResearchCoordinator:
    """One sequential research operation; bounded RAM cache, no automatic retries.

    provider.search(query, limit) -> iterable[Hit]; provider.provider_id
    reader.read(canonical_url, policy) -> Page; reader.reader_id
    Reader MUST enforce policy on every redirect/actual connection. This class
    prechecks candidates and checks the final URL but cannot sandbox a provider.
    Optional ResearchPauses persists refusals until explicit local review/release.
    Without it, legacy cooldowns remain RAM-only; no durability is claimed.
    """
    def __init__(self, providers, reader, *, resolver, policy=None, limits=None, clock=time.monotonic, pauses=None, guard=None):
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
        if pauses is not None and not isinstance(pauses, ResearchPauses):
            raise ContractError("invalid persistent pause store")
        self.pauses, self._pause_fault = pauses, False
        if guard is not None and not isinstance(guard, ResearchGuard):
            raise ContractError("invalid research guard")
        self.guard = guard

    def _persistent(self, operation, *args, **kwargs):
        if self._pause_fault:
            raise PauseStorageError("PAUSE_STORAGE_UNAVAILABLE: prior write uncertain; review before reuse")
        if self.pauses is None:
            return None
        try:
            return getattr(self.pauses, operation)(*args, **kwargs)
        except PauseCapacityError:
            # A refused read-only preflight has not lost any observation. Keep
            # its actual diagnosis, and permit a later explicit run after review.
            # A refused write follows an exchange: retain the conservative latch.
            if operation != 'check_capacity':
                self._pause_fault = True
            raise
        except PauseStorageError:
            self._pause_fault = True
            raise  # never turn failed persistence into a fallback or empty gate


    def _rate_limit(self, domain, retry_after, review=False, state="RATE_LIMITED"):
        if self.pauses is not None:
            return  # durable gate owns release, including after coordinator reconstruction
        until = float("inf") if review else self.clock() + (retry_after if retry_after is not None else 60)
        if len(self._cooldowns) >= 64 and domain not in self._cooldowns:
            # Bound memory without forgetting an active refusal: pause all reads.
            self._pause_until = max(self._pause_until, until, *(v[0] for v in self._cooldowns.values()))
            self._cooldowns.clear()
        else:
            self._cooldowns[domain] = (until, state, review)

    def run(self, query, *, required_pages=1, cancelled=lambda: False):
        if self.guard is None:
            return self._run(query, required_pages=required_pages, cancelled=cancelled)
        # Invalid local requests do not create an uncertain research intent.
        cleaned = clean_query(query)
        if type(required_pages) is not int or not 1 <= required_pages <= self.limits.reads:
            raise ContractError("required_pages must fit the read budget")
        return self.guard.execute(
            lambda: self._run(query, required_pages=required_pages, cancelled=cancelled),
            descriptor={"query_sha256": cleaned.cleaned_sha256,
                        "policy_id": self.policy.policy_id,
                        "providers": [p.provider_id for p in self.providers[:self.limits.providers]]})

    def _run(self, query, *, required_pages=1, cancelled=lambda: False):
        if self._pause_fault:
            raise PauseStorageError("PAUSE_STORAGE_UNAVAILABLE: prior write uncertain; review before reuse")
        _text(query, 1000)
        if type(required_pages) is not int or not 1 <= required_pages <= self.limits.reads:
            raise ContractError("required_pages must fit the read budget")
        cleaned = clean_query(query)
        start = self.clock()
        self._cooldowns = {k: v for k, v in self._cooldowns.items() if v[0] > start}
        late_receipt = False
        report = {"version": 1, "query_sha256": cleaned.cleaned_sha256, "query_hash_scope": "cleaned_utf8", "policy_id": self.policy.policy_id,
                  "required_pages": required_pages, "readable_pages": 0, "read_calls": 0,
                  "providers": [], "sources": [], "status": None,
                  "scope": "retrieved text only; no claim verification or mission success"}
        report["query_cleanup"] = cleaned.receipt()
        # Cleanup does not grant permission to send. This candidate still relies
        # on its trusted caller/providers; no real provider is enabled here.
        query = cleaned.text
        if not query:
            report.update(status="QUERY_EMPTY_AFTER_CLEANUP", discovery_status="NOT_REQUESTED", limitation=None)
            return project_report(report)
        seen, final_seen, body_seen, new_cache_keys = {}, set(), {}, set()

        def stop():
            if cancelled():
                return "CANCELLED"
            if late_receipt or self.clock() - start >= self.limits.seconds:
                return "DEADLINE"
            return None

        def enough():
            return report["readable_pages"] >= required_pages

        def before_hop(decision):
            interrupted = stop()
            if interrupted:
                raise AccessFailure("CANCELLED" if interrupted == "CANCELLED" else "TIMEOUT")
            if self._persistent('active', origin_scope(decision.host, decision.port)):
                raise AccessFailure("RETRY_WAIT")
            # A refusal on this hop may need both initial and final scopes.
            self._persistent('check_capacity', [origin_scope(*domain),
                                               origin_scope(decision.host, decision.port)])
            until = self._cooldowns.get((decision.host, decision.port), (0,))[0]
            if max(self._pause_until, until) > self.clock():
                raise AccessFailure("RETRY_WAIT")
            interrupted = stop()  # Durable lookups can consume time or observe cancellation.
            if interrupted:
                raise AccessFailure("CANCELLED" if interrupted == "CANCELLED" else "TIMEOUT")

        for provider in self.providers[:self.limits.providers]:
            if stop() or enough():
                break
            provider_record = {"provider_id": provider.provider_id, "status": "OK"}
            report["providers"].append(provider_record)
            held = self._persistent('active', provider_scope(provider.provider_id))
            if held:
                provider_record.update(status="RETRY_WAIT", pause_id=held['id'], pause_revision=held['revision'],
                                       retry_review_required=True)
                continue
            self._persistent('check_capacity', [provider_scope(provider.provider_id)])
            interrupted = stop()  # SQLite gate lookup may itself consume the remaining budget.
            if interrupted:
                provider_record['status'] = interrupted
                break
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
            except PauseStorageError:
                raise
            except AccessFailure as exc:
                if exc.code in {"RATE_LIMITED", "ACCESS_DENIED", "CHALLENGE"} or exc.retry_after is not None:
                    self._persistent('pause', [provider_scope(provider.provider_id)],
                                     reason=exc.code if exc.code in {"RATE_LIMITED", "ACCESS_DENIED", "CHALLENGE"} else "RETRY_WAIT", retry_after=exc.retry_after)
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
                        if stop():
                            continue  # No cached receipt adopted after slow DNS/cancellation.
                        source.update(snapshot(cached[1]), cache_hit=True)
                        self._cache.move_to_end(key)
                    else:
                        source.update(state="POLICY_REFUSED", reason=final.code)
                else:
                    self._cache.pop(key, None)
                    domain = (decision.host, decision.port)
                    held = self._persistent('active', origin_scope(*domain))
                    if held:
                        source.update(state="RETRY_WAIT", pause_id=held['id'], pause_revision=held['revision'],
                                      retry_review_required=True)
                        continue
                    self._persistent('check_capacity', [origin_scope(*domain)])
                    until, waiting_state, review = self._cooldowns.get(domain, (0, "RETRY_WAIT", False))
                    if max(self._pause_until, until) > self.clock():
                        source.update(state=waiting_state,
                                      retry_review_required=review or self._pause_until == float("inf"))
                        continue
                    if stop():
                        continue  # no read after a slow gate lookup exhausts the budget
                    if report["read_calls"] >= self.limits.reads:
                        source["state"] = "READ_BUDGET"
                        continue
                    report["read_calls"] += 1
                    try:
                        guarded = getattr(self.reader, "read_guarded", None)
                        page = (guarded(url, self.policy, before_hop) if callable(guarded)
                                else self.reader.read(url, self.policy))
                        state, content, extraction = _classify_page(page, self.limits)
                        if page.policy_id != self.policy.policy_id:
                            raise ContractError("reader policy mismatch")
                        retrieval = snapshot(page.retrieval) if page.retrieval is not None else None
                        if retrieval is not None:
                            if (type(retrieval) is not dict or len(encode(retrieval).encode()) > 32_000
                                    or retrieval.get("final_url") != page.url
                                    or retrieval.get("policy_id") != page.policy_id
                                    or type(retrieval.get("status")) is not int or retrieval.get("status") != page.status
                                    or type(retrieval.get("observed_at")) is not str
                                    or datetime.fromisoformat(retrieval["observed_at"]).tzinfo is None):
                                raise ContractError("retrieval envelope mismatch")
                            if (state == "READ" or extraction is not None) and (type(retrieval.get("size")) is not int
                                    or retrieval.get("sha256") != hashlib.sha256(page.body).hexdigest()
                                    or retrieval.get("size") != len(page.body)):
                                raise ContractError("retrieval body mismatch")
                        final = decide(page.url, self.resolver, self.policy)
                        source.update(state=state, final_url=final.url if final.allowed else None,
                                      http_status=page.status, retry_after=page.retry_after,
                                      retry_review_required=page.retry_review_required,
                                      deadline_exceeded=page.deadline_exceeded)
                        if extraction is not None:
                            source["extraction"] = extraction
                        late_receipt = late_receipt or page.deadline_exceeded
                        if retrieval is not None:
                            source["retrieval"] = retrieval
                        if (state in {"RATE_LIMITED", "ACCESS_DENIED", "CHALLENGE_SUSPECTED", "LOGIN_SUSPECTED", "PAYWALL_SUSPECTED"}
                                or page.retry_after is not None or page.retry_review_required):
                            pause_reason = state if state in {"RATE_LIMITED", "ACCESS_DENIED", "CHALLENGE_SUSPECTED", "LOGIN_SUSPECTED", "PAYWALL_SUSPECTED"} else "RETRY_WAIT"
                            scopes = [origin_scope(*domain)]
                            # A parsed origin can be suspended even if its DNS
                            # has failed/changed since the completed request.
                            # Recording a refusal does not authorize a connection.
                            if final.host is not None and final.port is not None:
                                scopes.append(origin_scope(final.host, final.port))
                            self._persistent('pause', scopes,
                                             reason=pause_reason, retry_after=page.retry_after,
                                             review=page.retry_review_required)
                        if state == "RATE_LIMITED" or page.retry_after is not None or page.retry_review_required:
                            wait_state = "RATE_LIMITED" if state == "RATE_LIMITED" else "RETRY_WAIT"
                            self._rate_limit(domain, page.retry_after, page.retry_review_required, wait_state)
                            # A quota returned after redirect applies to the final domain too.
                            if final.host is not None and final.port is not None:
                                self._rate_limit((final.host, final.port), page.retry_after, page.retry_review_required, wait_state)
                        if not final.allowed:
                            source.update(state="POLICY_REFUSED", reason=final.code)
                            continue
                        if state == "READ":
                            evidence = {"state": "READ", "final_url": final.url, "text": content,
                                        "observed_at": retrieval["observed_at"] if retrieval else datetime.now(timezone.utc).isoformat(),
                                        "body_sha256": hashlib.sha256(page.body).hexdigest(),
                                        "body_bytes": len(page.body), "media_type": page.media_type,
                                        "reader_id": self.reader.reader_id, "policy_id": page.policy_id}
                            if extraction is not None:
                                evidence["extraction"] = extraction
                            if retrieval is not None:
                                evidence["retrieval"] = retrieval
                            source.update(evidence)
                            if not page.deadline_exceeded and not stop():
                                self._cache[key] = (self.clock() + self.limits.cache_seconds, snapshot(evidence))
                                new_cache_keys.add(key)
                            while len(self._cache) > self.limits.cache_entries:
                                self._cache.popitem(last=False)
                    except PauseStorageError:
                        raise
                    except AccessFailure as exc:
                        if exc.code in {"RATE_LIMITED", "ACCESS_DENIED", "CHALLENGE"} or exc.retry_after is not None:
                            self._persistent('pause', [origin_scope(*domain)], reason=exc.code if exc.code in {"RATE_LIMITED", "ACCESS_DENIED", "CHALLENGE"} else "RETRY_WAIT", retry_after=exc.retry_after)
                        source.update(state=exc.code, retry_after=exc.retry_after)
                        if exc.code == "RATE_LIMITED":
                            self._rate_limit(domain, exc.retry_after)
                    except Exception:
                        source["state"] = "READER_ERROR"
                if source["state"] == "READ":
                    content_hash = source.get("extraction", {}).get("text_sha256", source["body_sha256"])
                    if source["final_url"] in final_seen:
                        source["state"] = "DUPLICATE_FINAL"
                    elif content_hash in body_seen:
                        source.update(state="DUPLICATE_CONTENT", duplicate_of=body_seen[content_hash])
                    else:
                        body_seen[content_hash] = source['id']
                        report["readable_pages"] += 1
                    # Even duplicate content has an observed final URL; a later
                    # response from that same URL cannot count as a new page.
                    final_seen.add(source["final_url"])
            if report["read_calls"] >= self.limits.reads and not enough():
                break
        report["status"] = stop() or ("READ_TARGET_MET" if enough() else
            "PARTIAL" if report["readable_pages"] else "NO_READABLE_SOURCE")
        if report["status"] in {"CANCELLED", "DEADLINE"}:
            # Keep receipts in this report, but do not publish fresh cache
            # entries from an interrupted operation (including earlier pages).
            for key in new_cache_keys:
                self._cache.pop(key, None)
        report["limitation"] = ("READ_BUDGET" if not enough() and report["read_calls"] >= self.limits.reads
            else "PROVIDER_BUDGET" if not enough() and len(self.providers) > self.limits.providers else None)
        statuses = [item['status'] for item in report['providers']]
        discovery_complete = (len(statuses) == len(self.providers)
                              and report['status'] not in {'CANCELLED', 'DEADLINE'})
        # This describes discovery, independently of whether any page was read.
        # EMPTY requires every configured provider to have answered successfully.
        report['discovery_status'] = (
            'HITS_FOUND' if report['sources'] else
            'EMPTY' if discovery_complete and all(s == 'EMPTY' for s in statuses) else
            'UNAVAILABLE' if discovery_complete and all(s not in {'EMPTY', 'OK'} for s in statuses) else
            'INCOMPLETE')
        return project_report(report)
