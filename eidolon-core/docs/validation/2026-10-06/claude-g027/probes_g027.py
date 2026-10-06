# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : probes_g027.py
# Description : Contre-revue cache interrompu et rapport Web v2 (C-TASK-G027)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Run on base 3edcc9e and target 2bad4e6 (frozen copies):
    PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=<tree>/eidolon-core/src:<tree>/eidolon-core \
        python docs/validation/2026-10-06/claude-g027/probes_g027.py
No network: injected Reader, or the real WebReader/fetch with a simulated DNS
and HTTP peer that records the exact request target it receives."""
import hashlib, json, sys
from pathlib import Path

from eidolon_core.research import Hit, Page, ResearchCoordinator, ResearchLimits
from eidolon_core.web_reader import WebReader
from eidolon_core.web_transport import RawResponse

SECRET = "SECRET-G027"
TEXT = (200, (("Content-Type", "text/plain"),), b"Texte public G027, rien n'est confirme.")


def section(t): print(f"\n== {t}")
def sha(s): return hashlib.sha256(s.encode()).hexdigest()


class Clock:
    def __init__(self): self.now = 1000.0
    def __call__(self): return self.now


class Provider:
    provider_id = "p"
    def __init__(self, hits): self.hits = hits
    def search(self, query, limit): return self.hits


class Reader:
    reader_id = "g027-reader/1"
    def __init__(self, on_read=None, replies=None): self.calls, self.on_read, self.replies = [], on_read, replies or {}
    def read(self, url, policy):
        self.calls.append(url)
        if self.on_read: self.on_read(len(self.calls))
        r = dict(url=url, status=200, media_type="text/plain", body=b"Texte G027.", retrieval=None); r.update(self.replies.get(url, {}))
        return Page(r["url"], r["status"], r["media_type"], r["body"], policy.policy_id, retrieval=r["retrieval"])


class Connector:
    def __init__(self, script): self.script, self.targets = script, []
    def exchange(self, *, scheme, host, port, address, target, headers, limits, remaining_seconds):
        self.targets.append(host + target)
        return RawResponse(*self.script[host + target.split("?")[0]], True)


dns = lambda h, p: ["93.184.215.10"]


def p1_cache():
    section("1 cache: interruptions keep receipts but never feed the cache")
    flag = {"cancel": False}
    reader = Reader(on_read=lambda n: flag.update(cancel=(n == 1)))
    c = ResearchCoordinator([Provider([Hit("https://news.example/a", "t")])], reader, resolver=dns, clock=Clock())
    r1 = c.run("q", cancelled=lambda: flag["cancel"]); flag["cancel"] = False
    r2 = c.run("q"); r3 = c.run("q")
    print(f"  cancel after the read: run1 {r1['status']} source={r1['sources'][0]['state']} text={'kept' if r1['sources'][0].get('text') else None} "
          f"| run2 cache_hit={r2['sources'][0]['cache_hit']} | run3 cache_hit={r3['sources'][0]['cache_hit']} | reads={len(reader.calls)}")

    clock = Clock(); hits = [Hit("https://news.example/a", "a"), Hit("https://other.example/b", "b")]
    reader = Reader(on_read=lambda n: setattr(clock, "now", clock.now + (40 if n == 2 else 0)))
    c = ResearchCoordinator([Provider(hits)], reader, resolver=dns, clock=clock, limits=ResearchLimits(seconds=30))
    r1 = c.run("q", required_pages=2)
    r2 = c.run("q")
    print(f"  coordinator deadline after page 2: run1 {r1['status']} states={[s['state'] for s in r1['sources']]} "
          f"| run2 page1 cache_hit={r2['sources'][0]['cache_hit']} reads={len(reader.calls)}")

    # Slow DNS revalidation of a valid cache entry, then the budget is gone: page not adopted.
    clock = Clock(); calls = {"n": 0}
    def slow_dns(h, p):
        calls["n"] += 1
        if calls["n"] == 4: clock.now += 100  # 3rd lookup of run 2 = cache revalidation of the final URL
        return ["93.184.215.10"]
    reader = Reader()
    c = ResearchCoordinator([Provider([Hit("https://news.example/a", "t")])], reader, resolver=slow_dns, clock=clock, limits=ResearchLimits(seconds=30))
    c.run("q"); clock.now += 5
    r = c.run("q")
    s = r["sources"][0]
    print(f"  slow cache revalidation then deadline: status={r['status']} state={s['state']} cache_hit={s['cache_hit']} "
          f"text={'present' if s.get('text') else None} readable={r['readable_pages']} reads={len(reader.calls)}")

    clock = Clock(); reader = Reader()
    c = ResearchCoordinator([Provider([Hit("https://news.example/a", "t")])], reader, resolver=dns, clock=clock)
    c.run("q"); clock.now += 30; warm = c.run("q"); clock.now += 61; cold = c.run("q")
    other = ResearchCoordinator([Provider([Hit("https://news.example/a", "t")])], reader, resolver=dns, clock=clock).run("q")
    print(f"  normal cache: +30 s cache_hit={warm['sources'][0]['cache_hit']} | +91 s cache_hit={cold['sources'][0]['cache_hit']} "
          f"| other coordinator cache_hit={other['sources'][0]['cache_hit']} | reads={len(reader.calls)}")
    clock = Clock(); state = {"private": False}
    rebind = lambda h, p: ["10.0.0.5"] if state["private"] and h == "news.example" else ["93.184.215.10"]
    c = ResearchCoordinator([Provider([Hit("https://news.example/a", "t")])], Reader(), resolver=rebind, clock=clock)
    c.run("q"); state["private"] = True; r = c.run("q")
    print(f"  cache revalidation, final now private: {r['sources'][0]['state']} cache_hit={r['sources'][0]['cache_hit']}")


def p2_report():
    section("2 report v2: URL fields, fingerprints, transport untouched (real WebReader)")
    conn = Connector({"news.example/a": (302, (("Location", f"https://mirror.example/b?session={SECRET}#frag"),), b""),
                      "mirror.example/b": TEXT})
    url = f"https://news.example/a?token={SECRET}&x=1#top"
    r = ResearchCoordinator([Provider([Hit(url, "t")])], WebReader(dns, conn), resolver=dns).run("q")
    s = r["sources"][0]; text = json.dumps(r)
    print(f"  requests received by the peer: {conn.targets}")
    print(f"  version={r.get('version')} url={s['url']} final_url={s['final_url']} retrieval.final_url={s.get('retrieval', {}).get('final_url')}")
    print(f"  secret anywhere in report={SECRET in text} | 'frag' or '#' in URL fields={any('#' in str(s.get(k)) for k in ('url', 'final_url'))}")
    print(f"  url_sha256 == sha(canonical requested URL without fragment)={s.get('url_sha256') == sha(url.split('#')[0])} "
          f"| final_url_sha256 == sha(final)={s.get('final_url_sha256') == sha(f'https://mirror.example/b?session={SECRET}')} "
          f"| query hashes present={bool(s.get('url_query_sha256')) and bool(s.get('final_url_query_sha256'))}")
    hops = s.get("retrieval", {}).get("hops", [])
    print(f"  hops (keys)={[sorted(h) for h in hops]} urls={[h.get('url') for h in hops]}")

    r = ResearchCoordinator([Provider([Hit("https://news.example/item?id=1", "1"), Hit("https://news.example/item?id=2", "2")])],
                            Reader(), resolver=dns).run("q", required_pages=2)
    print(f"  two URLs differing by query: shown={[s['url'] for s in r['sources']]} distinct sha={len({s.get('url_sha256') for s in r['sources']} - {None}) == 2}")

    reader = Reader(replies={"https://news.example/c": dict(status=403, body=b"")})
    r = ResearchCoordinator([Provider([Hit(f"https://news.example/c?k={SECRET}", "t")])], Reader(replies={f"https://news.example/c?k={SECRET}": dict(status=403, body=b"")}), resolver=dns).run("q")
    print(f"  refusal 403: state={r['sources'][0]['state']} url={r['sources'][0]['url']} secret in report={SECRET in json.dumps(r)}")

    clock = Clock(); c = ResearchCoordinator([Provider([Hit(f"https://news.example/a?t={SECRET}", "t")])], Reader(), resolver=dns, clock=clock)
    first = c.run("q"); second = c.run("q")
    print(f"  cache hit report: cache_hit={second['sources'][0]['cache_hit']} url={second['sources'][0]['url']} "
          f"same sha={first['sources'][0].get('url_sha256') == second['sources'][0].get('url_sha256')} secret={SECRET in json.dumps(second)}")


def p3_hostile():
    section("3 hostile or unusual data (documented limits made concrete)")
    cases = [f"https://news.example/reset;jsessionid={SECRET}", f"https://news.example/a%3Ftoken%3D{SECRET}",
             f"https://news.example/u/{SECRET}/profile"]
    for u in cases:
        r = ResearchCoordinator([Provider([Hit(u, f"Titre {SECRET}", f"extrait https://x.example/?k={SECRET}")])], Reader(), resolver=dns).run("q")
        s = r["sources"][0]
        print(f"  {u[:52]:52} shown={s['url']} secret in url field={SECRET in str(s['url'])} in title/snippet={SECRET in json.dumps(s['found_by'])}")
    bad = Reader(replies={"https://news.example/h": dict(retrieval=None)})
    page_url = f"https://news.example/h?q={SECRET}"
    r = ResearchCoordinator([Provider([Hit("https://news.example/h", "t")])],
                            Reader(replies={"https://news.example/h": dict(url="https://news.example/h")}), resolver=dns).run("q")
    print(f"  injected reader, plain page: state={r['sources'][0]['state']} version={r['version']}")


if __name__ == "__main__":
    print(f"python {sys.version.split()[0]} | tree {Path(__import__('eidolon_core').__file__).parents[3].name}")
    for probe in (p1_cache, p2_report, p3_hostile):
        probe()
