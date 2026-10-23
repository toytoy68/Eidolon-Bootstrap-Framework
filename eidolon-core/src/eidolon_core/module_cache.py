# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : module_cache.py
# Description : Cache des modules avec durée de vie, invalidation et provenance (G296)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""In-memory cache for module readings (weather, transit, DARME status...). Clean-room, G296.

Not wired yet (lot M1 wires it). Rules:
- the key binds module, source, OWNER and the source configuration fingerprint: a
  reading is never served to another profile, nor after its configuration changed;
- a reading younger than ``ttl_s`` is served as ``cached``; otherwise ``collect`` runs;
- a failed collect falls back to the last success only within ``stale_max_s``, marked
  ``stale`` with its original dates and the error code: never presented as current;
- identical concurrent reads share one collect (no duplicate network call);
- ``invalidate`` drops entries and discards the result of a collect already running;
- every reading carries its provenance (who, what, when observed and fetched, until when).
Nothing is written to disk; values are kept as returned by ``collect`` (caller-bounded).
"""
from collections import OrderedDict
from dataclasses import dataclass, field
import re
import threading
import time

_ID = re.compile(r"[A-Za-z0-9_.:-]{1,120}")
_FINGERPRINT = re.compile(r"[0-9a-f]{16,64}")


class CollectError(Exception):
    """Raised by a collector with a stable code; any other exception becomes COLLECT_FAILED."""

    def __init__(self, code):
        if type(code) is not str or not re.fullmatch(r"[A-Z][A-Z0-9_]{1,40}", code):
            code = "COLLECT_FAILED"
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class CacheKey:
    module: str
    source_id: str
    owner: str
    config_fingerprint: str

    def __post_init__(self):
        for name in ("module", "source_id", "owner"):
            if type(getattr(self, name)) is not str or not _ID.fullmatch(getattr(self, name)):
                raise ValueError("invalid " + name)
        if type(self.config_fingerprint) is not str or not _FINGERPRINT.fullmatch(self.config_fingerprint):
            raise ValueError("invalid config_fingerprint")


@dataclass(frozen=True)
class Reading:
    status: str                 # fresh | cached | stale | error | discarded
    data: object
    provenance: dict = field(default_factory=dict)


@dataclass
class _Entry:
    data: object
    observed_at: float
    fetched_at: float
    fresh_until: float


class ModuleCache:
    def __init__(self, *, clock=time.time, max_entries=256):
        if type(max_entries) is not int or not 1 <= max_entries <= 100000:
            raise ValueError("invalid max_entries")
        self.clock, self.max_entries = clock, max_entries
        self._entries = OrderedDict()
        self._inflight = {}
        self._generation = {}
        self._lock = threading.Lock()

    @staticmethod
    def _scope(key):
        return key.module, key.source_id, key.owner

    def _provenance(self, key, entry, *, from_cache, stale, error=None):
        p = {"module": key.module, "source_id": key.source_id, "owner": key.owner,
             "config_fingerprint": key.config_fingerprint, "from_cache": from_cache, "stale": stale,
             "observed_at": entry.observed_at if entry else None, "fetched_at": entry.fetched_at if entry else None,
             "fresh_until": entry.fresh_until if entry else None, "served_at": self.clock()}
        if error:
            p["error"] = error
        return p

    def read(self, key, collect, *, ttl_s, stale_max_s=0):
        if type(key) is not CacheKey or not callable(collect):
            raise TypeError("CacheKey and collect required")
        for name, value, high in (("ttl_s", ttl_s, 86400), ("stale_max_s", stale_max_s, 86400)):
            if type(value) not in (int, float) or not 0 <= value <= high or value != value:
                raise ValueError("invalid " + name)
        with self._lock:
            now = self.clock()
            # A configuration change replaces the source: older fingerprints of this scope go.
            for other in [k for k in self._entries if self._scope(k) == self._scope(key) and k != key]:
                del self._entries[other]
            entry = self._entries.get(key)
            if entry is not None and now < entry.fresh_until:
                self._entries.move_to_end(key)
                return Reading("cached", entry.data, self._provenance(key, entry, from_cache=True, stale=False))
            waiter = self._inflight.get(key)
            leader = waiter is None
            if leader:
                waiter = self._inflight[key] = {"done": threading.Event(), "result": None}
            generation = self._generation.get(self._scope(key), 0)
        if not leader:
            waiter["done"].wait()
            return waiter["result"]
        result = None
        try:
            fetched = self.clock()
            try:
                value = collect()
                if type(value) is not dict or "data" not in value:
                    raise CollectError("COLLECT_INVALID")
                observed = value.get("observed_at", fetched)
                if type(observed) not in (int, float) or not observed <= fetched + 60:
                    raise CollectError("COLLECT_INVALID")
                fresh = _Entry(value["data"], float(observed), fetched, fetched + ttl_s)
                with self._lock:
                    if self._generation.get(self._scope(key), 0) != generation:
                        result = Reading("discarded", None, self._provenance(key, None, from_cache=False, stale=False,
                                                                             error="INVALIDATED"))
                    else:
                        self._entries[key] = fresh
                        self._entries.move_to_end(key)
                        while len(self._entries) > self.max_entries:
                            self._entries.popitem(last=False)
                        result = Reading("fresh", fresh.data, self._provenance(key, fresh, from_cache=False, stale=False))
            except Exception as exc:  # noqa: BLE001 - collector failures never leak details
                code = exc.code if isinstance(exc, CollectError) else "COLLECT_FAILED"
                with self._lock:
                    last = self._entries.get(key)
                    usable = (last is not None and self._generation.get(self._scope(key), 0) == generation
                              and self.clock() - last.fetched_at <= ttl_s + stale_max_s)
                if usable:
                    result = Reading("stale", last.data, self._provenance(key, last, from_cache=True, stale=True, error=code))
                else:
                    result = Reading("error", None, self._provenance(key, None, from_cache=False, stale=False, error=code))
            return result
        finally:
            with self._lock:
                waiter["result"] = result or Reading("error", None, self._provenance(
                    key, None, from_cache=False, stale=False, error="COLLECT_FAILED"))
                self._inflight.pop(key, None)
            waiter["done"].set()

    def invalidate(self, *, module=None, source_id=None, owner=None):
        """Drop matching entries and discard the result of matching collects in flight."""
        if module is None and source_id is None and owner is None:
            raise ValueError("explicit scope required")
        with self._lock:
            def match(scope):
                return ((module is None or scope[0] == module) and (source_id is None or scope[1] == source_id)
                        and (owner is None or scope[2] == owner))
            removed = [k for k in self._entries if match(self._scope(k))]
            for k in removed:
                del self._entries[k]
            for scope in {self._scope(k) for k in list(self._entries) + list(self._inflight) + removed} | set(self._generation):
                if match(scope):
                    self._generation[scope] = self._generation.get(scope, 0) + 1
            return len(removed)
