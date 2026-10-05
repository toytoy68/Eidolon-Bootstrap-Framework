# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : check_corpus.py
# Description : Vérifie la cohérence du corpus synthétique de recherche (C-TASK-G007)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

"""Self-consistency checks for cases.json. Exit 0 only if every check passes.

From this directory:  python check_corpus.py
It checks the corpus, not a coordinator: running research.py against it is
Codex's adapter work.
"""
import hashlib
import json
from pathlib import Path
import re
import sys
import urllib.parse

HERE = Path(__file__).resolve().parent

OUTCOMES = {"ANSWERED", "ANSWERED_WITH_CONFLICT", "PARTIAL", "NO_EVIDENCE", "NO_RESULTS",
            "UNAVAILABLE", "NEEDS_USER", "BUDGET_EXHAUSTED"}
ITEM_STATES = {"READ", "SNIPPET_ONLY", "RATE_LIMITED", "ACCESS_DENIED", "CHALLENGE", "LOGIN_REQUIRED",
               "NOT_FOUND", "PARTIAL_CONTENT", "NOT_EXPLOITABLE", "POLICY_REFUSED", "ROBOTS_DISALLOWED",
               "CACHE_STALE", "NOT_FETCHED_BUDGET"}
PROVIDER_STATES = {"USED", "RATE_LIMITED", "PROVIDER_UNAVAILABLE"}
# The twelve situations required by C-TASK-G007, by case id.
REQUIRED = {"429/retry": "W01", "403": "W03", "challenge 200": "W04", "CAPTCHA article": "W05",
            "snippet only": "W06", "duplicate across engines": "W07", "stale cache": "W09",
            "policy change": "W11", "login page": "W12", "contradictory results": "W13",
            "provider down": "W14", "insufficient budget": "W16"}
PERSONAL = [re.compile(r"[A-Za-z0-9._%+-]+@(?!example\.invalid\b)[A-Za-z0-9.-]+\.[a-z]{2,}"),
            re.compile(r"\b(?:10|172\.(?:1[6-9]|2\d|3[01])|192\.168)\.\d+\.\d+\b")]


def fail(errors, message):
    errors.append(message)


def check():
    errors = []
    corpus = json.loads((HERE / "cases.json").read_text(encoding="utf-8"))
    if corpus.get("schema") != "eidolon-research-corpus/1" or corpus.get("synthetic") is not True:
        fail(errors, "schema or synthetic flag")
    ids = [c["id"] for c in corpus["cases"]]
    if len(ids) != len(set(ids)):
        fail(errors, "duplicate case id")
    by_id = {c["id"]: c for c in corpus["cases"]}
    for need, cid in REQUIRED.items():
        if cid not in by_id:
            fail(errors, f"required situation missing: {need}")
    for case in corpus["cases"]:
        cid, setup, expected = case["id"], case["setup"], case["expected"]
        outcomes = expected.get("outcome_any_of") or [expected.get("outcome")]
        if not set(outcomes) <= OUTCOMES:
            fail(errors, f"{cid}: unknown outcome {outcomes}")
        for item in expected.get("items", []):
            states = item.get("state_any_of") or [item.get("state")]
            if not set(states) <= ITEM_STATES:
                fail(errors, f"{cid}: unknown item state {states}")
            if urllib.parse.urlsplit(item["url"]).hostname is None or not item["url"].startswith("https://"):
                fail(errors, f"{cid}: item url must be https with a host")
        for name, state in expected.get("providers", {}).items():
            if state not in PROVIDER_STATES or name not in setup["providers"]:
                fail(errors, f"{cid}: provider expectation {name}={state}")
        if not case.get("why"):
            fail(errors, f"{cid}: justification missing")
        bodies = [p for p in setup["pages"].values()] + list(setup["cache"]) + list(setup["robots"].values())
        bodies += [p["sequence_after_retry"] for p in setup["pages"].values() if "sequence_after_retry" in p]
        for entry in bodies:
            if "body" not in entry:
                continue
            path = HERE / entry["body"]
            if not path.is_file():
                fail(errors, f"{cid}: missing body {entry['body']}")
                continue
            raw = path.read_bytes()
            if hashlib.sha256(raw).hexdigest() != entry["body_sha256"] or len(raw) != entry["size"]:
                fail(errors, f"{cid}: body hash or size mismatch for {entry['body']}")
        for url in list(setup["pages"]) + [r["url"] for p in setup["providers"].values() for r in p.get("results", [])]:
            host = urllib.parse.urlsplit(url).hostname or ""
            if not host.endswith(".example"):
                fail(errors, f"{cid}: non-reserved host {host}")
        for entry in setup["cache"]:
            if entry["url"] not in setup["pages"]:
                fail(errors, f"{cid}: cache entry without a page definition")
    text = (HERE / "cases.json").read_text(encoding="utf-8") + "".join(
        p.read_text(encoding="utf-8") for p in sorted((HERE / "bodies").iterdir()))
    for pattern in PERSONAL:
        if pattern.search(text):
            fail(errors, f"possible personal data: {pattern.pattern}")
    return corpus, errors


def main():
    corpus, errors = check()
    categories = sorted({c["category"] for c in corpus["cases"]})
    print(f"cases: {len(corpus['cases'])} | categories: {', '.join(categories)}")
    print(f"required situations covered: {len(REQUIRED)}/{len(REQUIRED)}" if not any(
        "required" in e for e in errors) else "required situations: MISSING")
    for error in errors:
        print("ERROR", error)
    print("OK" if not errors else f"{len(errors)} error(s)")
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
