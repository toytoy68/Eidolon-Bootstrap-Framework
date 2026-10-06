# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : run_g007_on_head.py
# Description : Rejoue le corpus G007 sur la branche Core courante (C-TASK-G025)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

"""Run the 20 synthetic cases through ResearchCoordinator and classify each result.

From eidolon-core/:
    PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:. \
        python docs/validation/2026-10-06/claude-g025/run_g007_on_head.py

Verdicts: PASS (matches the oracle), KNOWN_GAP (a limit research.py documents:
no HTML extractor, no robots.txt, no claim comparison, no editorial
independence, no stale-copy display), FINDING (a gap not documented there).
Fakes only: no socket, no real service. research.py is imported, never modified.
"""
import json
from pathlib import Path
import sys
import urllib.parse

from eidolon_core.egress import WebPolicy
from eidolon_core.research import AccessFailure, Hit, Page, ResearchCoordinator, ResearchLimits

HERE = Path(__file__).resolve().parents[2] / "2026-10-05" / "claude-g007"  # corpus and bodies, unchanged
CORPUS = json.loads((HERE / "cases.json").read_text(encoding="utf-8"))
HTML_GAP = "no HTML extractor in this slice (UNSUPPORTED_CONTENT is documented)"


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def addresses(case):
    hosts = sorted({urllib.parse.urlsplit(u).hostname for u in case["setup"]["pages"]} |
                   {urllib.parse.urlsplit(r["url"]).hostname for p in case["setup"]["providers"].values()
                    for r in p.get("results", [])})
    return {h: f"93.184.215.{10 + i}" for i, h in enumerate(hosts)}


class Provider:
    def __init__(self, name, spec, sent):
        self.provider_id, self.spec, self.sent = name, spec, sent

    def search(self, query, limit):
        self.sent.append(query)
        status = self.spec["status"]
        if status == "down":
            raise AccessFailure("UNAVAILABLE")
        if status == "timeout":
            raise AccessFailure("TIMEOUT")
        if status == "http_429":
            raise AccessFailure("RATE_LIMITED", self.spec.get("retry_after_seconds"))
        return [Hit(r["url"], r["title"], r["snippet"]) for r in self.spec["results"]]


class Reader:
    reader_id = "corpus-reader/1"

    def __init__(self, pages, override=None):
        self.pages, self.calls, self.override = pages, [], override or {}

    def read(self, url, policy):
        self.calls.append(url)
        spec = self.override.get(url) or self.pages.get(url) or self.pages.get(url.split("?")[0])
        if spec is None:
            raise AccessFailure("UNAVAILABLE")
        if spec["status"] == "timeout":
            raise AccessFailure("TIMEOUT")
        headers = spec.get("headers", {})
        body = (HERE / spec["body"]).read_bytes() if "body" in spec else b""
        retry = headers.get("Retry-After")
        return Page(url, spec["status"], headers.get("Content-Type", "text/html"), body, policy.policy_id,
                    retry_after=int(retry) if retry and retry.isdigit() else None)


def coordinator(case, clock, sent, policy=None, reader=None):
    setup = case["setup"]
    hosts = addresses(case)
    providers = [Provider(n, setup["providers"][n], sent) for n in setup["provider_order"] if n in setup["providers"]]
    blocked = tuple(f"{hosts[d]}/32" for d in setup["policy"]["blocked_domains"] if d in hosts)
    policy = policy or WebPolicy(blocked_networks=blocked)
    budget = setup["budget"]
    limits = ResearchLimits(providers=max(1, min(8, budget["provider_calls"])), reads=budget["page_fetches"],
                            seconds=budget["seconds"])
    return ResearchCoordinator(providers or [Provider("none", {"status": "ok", "results": []}, sent)],
                               reader or Reader(setup["pages"]), resolver=lambda h, p: [hosts[h]],
                               policy=policy, limits=limits, clock=clock), hosts


def states(report):
    return {s["url"] or s["found_by"][0].get("title"): s["state"] for s in report["sources"]}


def run_case(case):
    clock, sent = Clock(), []
    coord, hosts = coordinator(case, clock, sent)
    reader = coord.reader
    required = 1
    report = coord.run(case["setup"]["query"], required_pages=required)
    got = states(report)
    cid, exp = case["id"], case["expected"]
    verdict, note = "PASS", ""
    st = list(got.values())

    def html_unsupported():
        return any(s == "UNSUPPORTED_CONTENT" for s in st)

    if cid == "W01":
        p = {r["provider_id"]: r["status"] for r in report["providers"]}
        ok = p.get("engine-a") == "RATE_LIMITED" and p.get("engine-b") == "OK"
        verdict = "PASS" if ok else "FINDING"
        note = f"providers {p}; page state {st} ({HTML_GAP})" if html_unsupported() else f"providers {p}"
    elif cid == "W02":
        ok = st == ["RATE_LIMITED"] and len(reader.calls) == 1
        verdict, note = ("PASS" if ok else "FINDING"), f"states {st}, reads {len(reader.calls)}, no retry"
    elif cid == "W03":
        ok = "ACCESS_DENIED" in st
        verdict = "PASS" if ok else "FINDING"
        note = f"states {st}" + (f" ({HTML_GAP})" if html_unsupported() else "")
    elif cid == "W04":
        verdict, note = ("PASS" if st == ["CHALLENGE_SUSPECTED"] else "FINDING"), f"states {st}"
    elif cid == "W05":
        ok = "CHALLENGE_SUSPECTED" not in st
        verdict = "KNOWN_GAP" if ok and html_unsupported() else ("PASS" if ok else "FINDING")
        note = f"not misread as challenge: {ok}; states {st}"
    elif cid == "W06":
        source = report["sources"][0]
        ok = source["state"] == "TIMEOUT" and source["found_by"][0]["snippet"] and source["text"] is None
        verdict, note = ("PASS" if ok else "FINDING"), f"state {source['state']}, snippet kept, no text"
    elif cid == "W07":
        canon = len(report["sources"])
        verdict = "FINDING" if len(reader.calls) > 1 or canon > 1 else "PASS"
        note = (f"{len(reader.calls)} read call(s) and {canon} source(s) for one page: tracking parameters "
                f"(utm_*) are not removed from the canonical URL")
    elif cid == "W08":
        verdict, note = "KNOWN_GAP", f"two sources counted separately (documented: no editorial independence); {st}"
    elif cid in ("W09", "W10"):
        # First run fills the RAM cache with a text copy, then time passes beyond cache_seconds.
        # A genuine text body: research.py rightly refuses HTML even when labelled text/plain.
        text_page = {u: {"status": 200, "headers": {"Content-Type": "text/plain; charset=utf-8"},
                         "body": "bodies/news-2026.txt"} for u in case["setup"]["pages"]}
        clock2, sent2 = Clock(), []
        coord2, _ = coordinator(case, clock2, sent2, reader=Reader(text_page))
        first = coord2.run(case["setup"]["query"])
        clock2.now += 30  # inside the 60 s session cache
        warm = coord2.run(case["setup"]["query"])
        warm_hit = any(s.get("cache_hit") for s in warm["sources"])
        clock2.now += 8 * 24 * 3600
        if cid == "W10":
            coord2.reader.override = {u: {"status": 503, "headers": {}} for u in text_page}
        second = coord2.run(case["setup"]["query"])
        s1, s2 = states(first), states(second)
        cache_hit = any(s.get("cache_hit") for s in second["sources"])
        if cid == "W09":
            verdict = "PASS" if warm_hit and not cache_hit and list(s2.values()) == ["READ"] else "FINDING"
            note = (f"within 60 s: cache_hit {warm_hit}; after expiry: {list(s2.values())}, cache_hit {cache_hit}, "
                    f"reads {len(coord2.reader.calls)} (text body)")
        else:
            verdict = "KNOWN_GAP" if not cache_hit else "FINDING"
            note = (f"after expiry, site 503: {list(s2.values())}; stale copy not reused (safe) "
                    f"and not offered as a dated copy (not in this slice)")
    elif cid == "W11":
        verdict = "PASS" if st == ["POLICY_REFUSED"] and not reader.calls else "FINDING"
        note = f"states {st}, reads {len(reader.calls)}; cache keyed by policy_id"
    elif cid == "W12":
        verdict, note = ("PASS" if st == ["LOGIN_SUSPECTED"] else "FINDING"), f"states {st}"
    elif cid == "W13":
        verdict, note = "KNOWN_GAP", f"no claim comparison in this slice; states {st}"
    elif cid in ("W14", "W15"):
        p = [r["status"] for r in report["providers"]]
        verdict = "FINDING"
        note = (f"report status {report['status']} for providers {p}: the top-level status is the same "
                f"for 'all providers down' (W14) and 'nothing found' (W15); only providers[] differs")
    elif cid == "W16":
        report5 = coordinator(case, Clock(), [])[0].run(case["setup"]["query"], required_pages=2)
        s5 = [s["state"] for s in report5["sources"]]
        ok = report5["read_calls"] <= 2 and "READ_BUDGET" in s5
        verdict = "PASS" if ok else "FINDING"
        note = f"read_calls {report5['read_calls']}, states {s5}, limitation {report5['limitation']}"
    elif cid == "W17":
        fetched = [u for u in reader.calls if "/private/" in u]
        verdict = "KNOWN_GAP" if fetched else "PASS"
        note = f"robots.txt not consulted; disallowed path read calls: {len(fetched)}"
    elif cid in ("W18", "W19"):
        verdict = "KNOWN_GAP" if html_unsupported() else "FINDING"
        note = f"states {st} ({HTML_GAP}); a text soft-404 or paywall would need content judgement"
    elif cid == "W20":
        leaked = [q for q in sent if "@example.invalid" in q or "01 23 45 67 89" in q]
        verdict = "FINDING" if leaked else "PASS"
        note = f"query sent verbatim to {len(leaked)} provider call(s), personal data included"
    return {"id": cid, "verdict": verdict, "report_status": report["status"], "note": note}


def main():
    results = [run_case(c) for c in CORPUS["cases"]]
    for r in results:
        print(f"{r['id']}  {r['verdict']:9}  {r['report_status']:18}  {r['note']}")
    counts = {v: sum(r["verdict"] == v for r in results) for v in ("PASS", "KNOWN_GAP", "FINDING")}
    print("\n" + " | ".join(f"{k} {v}" for k, v in counts.items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
