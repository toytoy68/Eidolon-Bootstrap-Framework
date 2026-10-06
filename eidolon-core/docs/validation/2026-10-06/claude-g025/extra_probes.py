# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : extra_probes.py
# Description : Sondes complémentaires G025 : refus persistants, cache après retard, URL minimisées
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""From eidolon-core/, with the frozen Core copy first on PYTHONPATH:
    PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=<frozen>/eidolon-core/src:<frozen>/eidolon-core \
        python docs/validation/2026-10-06/claude-g025/extra_probes.py
Synthetic doubles only (provider, reader, DNS); no socket."""
import tempfile
from pathlib import Path

from eidolon_core.research import Hit, Page, ResearchCoordinator, ResearchLimits
from eidolon_core.research_pauses import ResearchPauses, origin_scope

TEXT = b"Texte synthetique G025 : aucune affirmation n'est confirmee."


class Clock:
    def __init__(self): self.now = 1000.0
    def __call__(self): return self.now


class Provider:
    def __init__(self, hits): self.provider_id, self.hits, self.queries = "p", hits, []
    def search(self, query, limit): self.queries.append(query); return self.hits


class Reader:
    reader_id = "g025-reader/1"
    def __init__(self, replies, clock=None, slow=0): self.replies, self.calls, self.clock, self.slow = replies, [], clock, slow
    def read(self, url, policy):
        self.calls.append(url)
        if self.clock: self.clock.now += self.slow
        r = dict(status=200, media_type="text/plain", body=TEXT, deadline_exceeded=False); r.update(self.replies.get(url, {}))
        return Page(url, r["status"], r["media_type"], r["body"], policy.policy_id, retry_after=r.get("retry_after"),
                    deadline_exceeded=r["deadline_exceeded"])


dns = lambda h, p: ["93.184.215.10"]


def coord(provider, reader, clock, **kw):
    return ResearchCoordinator([provider], reader, resolver=dns, clock=clock, **kw)


print("== refusals that persist (W02 with durable pauses, coordinator rebuilt)")
temp = Path(tempfile.mkdtemp())
reader = Reader({"https://news.example/a": dict(status=429, retry_after=120, body=b"")})
for _ in range(2):
    r = coord(Provider([Hit("https://news.example/a", "t")]), reader, Clock(), pauses=ResearchPauses(temp / "p.sqlite3")).run("q")
print(f"  reads over two coordinators={len(reader.calls)} last state={r['sources'][0]['state']} paused={bool(ResearchPauses(temp / 'p.sqlite3').active(origin_scope('news.example', 443)))}")

print("== cache after a delay or a cancellation")
for label, kw in (("page with deadline_exceeded", dict(deadline_exceeded=True)), ("normal page", {})):
    clock = Clock(); reader = Reader({"https://news.example/a": kw}); c = coord(Provider([Hit("https://news.example/a", "t")]), reader, clock)
    first = c.run("q"); clock.now += 10; second = c.run("q")
    print(f"  {label:28} run1={first['status']} run2 cache_hit={second['sources'][0].get('cache_hit')} reads={len(reader.calls)}")
clock = Clock(); hits = [Hit("https://news.example/a", "a"), Hit("https://other.example/b", "b")]
reader = Reader({}, clock=clock, slow=20)
c = coord(Provider(hits), reader, clock, limits=ResearchLimits(seconds=30))
first = c.run("q", required_pages=2); clock.now += 5
second = c.run("q", required_pages=1)
print(f"  budget expires during page 2: run1={first['status']} (sources {[s['state'] for s in first['sources']]}) "
      f"| run2 cache_hit page1={second['sources'][0].get('cache_hit')} reads={len(reader.calls)}")

print("== displayed URLs after minimisation (duplicates and distinct documents)")
for label, urls in (("tracking parameter (W07)", ["https://news.example/a", "https://news.example/a?utm_source=x"]),
                    ("two documents, same path", ["https://news.example/item?id=1", "https://news.example/item?id=2"])):
    reader = Reader({}); r = coord(Provider([Hit(u, u) for u in urls]), reader, Clock()).run("q", required_pages=2)
    shown = [(s["url"], s.get("url_sha256", "")[:8], s["state"]) for s in r["sources"]]
    print(f"  {label:26} reads={len(reader.calls)} readable={r['readable_pages']} shown={shown}")

print("== snippets only, and personal data in the query (W06, W20)")
reader = Reader({"https://news.example/a": dict(status=503, body=b"")})
p = Provider([Hit("https://news.example/a", "t", "Un extrait affirmant un fait.")])
r = coord(p, reader, Clock()).run("joindre jean@example.invalid au 01 23 45 67 89")
print(f"  snippet only: readable={r['readable_pages']} text={r['sources'][0].get('text')} status={r['status']} "
      f"| query in report={'jean@' in str(r)} | query sent to provider={p.queries[0]!r}")
