# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : tests/test_module_cache_g296.py
# Description : Cache des modules G296 : durée de vie, repli daté, invalidation, propriétaires
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
import threading
import time

import pytest

from eidolon_core.module_cache import CacheKey, CollectError, ModuleCache

FP = "a" * 16


class Clock:
    def __init__(self): self.t = 1000.0
    def __call__(self): return self.t


def key(owner="toytoy", fp=FP, source="maison", module="meteo"):
    return CacheKey(module, source, owner, fp)


def collector(values):
    calls = []
    def collect():
        calls.append(1)
        v = values.pop(0)
        if isinstance(v, Exception):
            raise v
        return {"data": v}
    return collect, calls


def test_fresh_then_cached_then_refreshed_with_provenance():
    clock = Clock(); cache = ModuleCache(clock=clock)
    collect, calls = collector(["12 °C", "14 °C"])
    first = cache.read(key(), collect, ttl_s=600)
    assert (first.status, first.data, first.provenance["from_cache"]) == ("fresh", "12 °C", False)
    assert first.provenance["fresh_until"] == 1600.0 and first.provenance["owner"] == "toytoy"
    clock.t += 599
    again = cache.read(key(), collect, ttl_s=600)
    assert (again.status, again.data, again.provenance["observed_at"]) == ("cached", "12 °C", 1000.0)
    clock.t += 2
    assert cache.read(key(), collect, ttl_s=600).data == "14 °C" and len(calls) == 2


def test_failure_falls_back_to_dated_last_success_only_within_stale_window():
    clock = Clock(); cache = ModuleCache(clock=clock)
    collect, _ = collector(["12 °C", CollectError("SOURCE_DOWN"), CollectError("SOURCE_DOWN")])
    cache.read(key(), collect, ttl_s=60, stale_max_s=300)
    clock.t += 200
    stale = cache.read(key(), collect, ttl_s=60, stale_max_s=300)
    assert (stale.status, stale.data, stale.provenance["stale"], stale.provenance["error"]) == ("stale", "12 °C", True, "SOURCE_DOWN")
    assert stale.provenance["observed_at"] == 1000.0           # original date, never refreshed
    clock.t += 200                                             # 400 s after the success: too old
    gone = cache.read(key(), collect, ttl_s=60, stale_max_s=300)
    assert (gone.status, gone.data) == ("error", None)


def test_unexpected_exception_detail_is_not_exposed():
    cache = ModuleCache(clock=Clock())
    collect, _ = collector([RuntimeError("/home/toytoy/secret.json not found")])
    r = cache.read(key(), collect, ttl_s=60)
    assert r.provenance["error"] == "COLLECT_FAILED" and "secret" not in repr(r)


def test_owner_and_configuration_isolation():
    clock = Clock(); cache = ModuleCache(clock=clock)
    collect, calls = collector(["toytoy", "autre", "nouvelle config"])
    assert cache.read(key("toytoy"), collect, ttl_s=600).data == "toytoy"
    assert cache.read(key("autre"), collect, ttl_s=600).data == "autre"      # never the other profile's entry
    changed = cache.read(key("toytoy", fp="b" * 16), collect, ttl_s=600)
    assert (changed.status, changed.data) == ("fresh", "nouvelle config")
    # the old configuration's reading is gone, not merely shadowed
    assert cache.read(key("toytoy", fp=FP), lambda: {"data": "relu"}, ttl_s=600).data == "relu"
    assert len(calls) == 3


def test_identical_concurrent_reads_share_one_collect():
    cache = ModuleCache()
    gate, calls = threading.Event(), []
    def slow():
        calls.append(1); gate.wait(5); return {"data": "bus 12 min"}
    results = []
    threads = [threading.Thread(target=lambda: results.append(cache.read(key(), slow, ttl_s=60))) for _ in range(8)]
    for t in threads: t.start()
    time.sleep(.2); gate.set()
    for t in threads: t.join(5)
    assert len(calls) == 1 and len(results) == 8 and all(r.data == "bus 12 min" for r in results)


def test_invalidation_discards_a_collect_already_running():
    cache = ModuleCache()
    started, release = threading.Event(), threading.Event()
    def slow():
        started.set(); release.wait(5); return {"data": "avant le changement"}
    out = []
    t = threading.Thread(target=lambda: out.append(cache.read(key(), slow, ttl_s=600)))
    t.start(); started.wait(5)
    cache.invalidate(owner="toytoy")                           # e.g. profile switched, source edited
    release.set(); t.join(5)
    assert out[0].status == "discarded" and out[0].data is None
    assert cache.read(key(), lambda: {"data": "après"}, ttl_s=600).data == "après"


def test_invalidate_scope_and_bounds():
    cache = ModuleCache(clock=Clock(), max_entries=2)
    for owner in ("a", "b", "c"):
        cache.read(key(owner), lambda: {"data": owner}, ttl_s=600)
    assert cache.read(key("a"), lambda: {"data": "a2"}, ttl_s=600).data == "a2"   # evicted (LRU)
    assert cache.invalidate(module="meteo", owner="c") == 1
    with pytest.raises(ValueError):
        cache.invalidate()


@pytest.mark.parametrize("bad", [
    lambda: CacheKey("meteo", "maison", "toy toy", FP),
    lambda: CacheKey("meteo", "maison", "toytoy", "short"),
    lambda: ModuleCache().read(key(), lambda: {"data": 1}, ttl_s=float("nan")),
    lambda: ModuleCache().read(key(), lambda: {"data": 1}, ttl_s=-1),
    lambda: ModuleCache(max_entries=0),
])
def test_invalid_inputs(bad):
    with pytest.raises((ValueError, TypeError)):
        bad()


def test_malformed_or_future_collect_result_is_an_error():
    clock = Clock(); cache = ModuleCache(clock=clock)
    assert cache.read(key(), lambda: "no envelope", ttl_s=60).provenance["error"] == "COLLECT_INVALID"
    assert cache.read(key("b"), lambda: {"data": 1, "observed_at": clock.t + 3600}, ttl_s=60).status == "error"
