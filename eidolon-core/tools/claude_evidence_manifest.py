# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : tools/claude_evidence_manifest.py
# Description : Validateur EXPÉRIMENTAL du manifeste de preuves de la recette bêta (Claude, G264-5)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""EXPERIMENTAL. Validates a manifest the operator FILLED (format: docs/proposals/2026-10-15-beta-acceptance-plan.md,
section 6). It collects nothing from the host, runs nothing, and never turns test results into a permission:
the report always says ``authorizes_deployment: false``. Verdicts:

- INVALID: the file does not follow the schema (refused, with codes);
- INCOMPLETE: valid, but a step is missing, unknown, failed, or a CI difference is unclassified or class C;
- COMPLETE: every step 0-9 observed with evidence. Still a record for a human decision, nothing more.

  python tools/claude_evidence_manifest.py MANIFEST.json --now 2026-10-16T09:00:00+02:00
Exit: 0 COMPLETE, 1 INCOMPLETE, 2 INVALID.
"""
import argparse
from datetime import datetime
import json
import re
import sys

SCHEMA = "eidolon-beta-evidence/1"
STEPS = tuple(range(10))
VERDICTS = ("PASS", "FAIL", "UNKNOWN", "SKIPPED")
_SHA = re.compile(r"[0-9a-f]{40}")
_HEX64 = re.compile(r"[0-9a-f]{64}")
_ENTRY = {"step", "environment", "command", "result", "limits", "evidence", "date"}
_ENV = {"machine", "os", "python", "account"}
MAX_BYTES = 1 << 20


def _text(value, limit=4000):
    return type(value) is str and value.strip() != "" and len(value) <= limit


def _date(value, now):
    if not _text(value, 40):
        return None
    try:
        moment = datetime.fromisoformat(value)
    except ValueError:
        return None
    if moment.tzinfo is None or (now is not None and moment > now):
        return None
    return moment


def validate(manifest, *, now=None):
    errors, gaps = [], []

    def bad(code, where=""):
        errors.append(f"{code}{':' + where if where else ''}")

    if type(manifest) is not dict or manifest.get("schema") != SCHEMA:
        bad("SCHEMA")
        return _report(errors, gaps)
    if set(manifest) != {"schema", "sha", "entries"}:
        bad("UNEXPECTED_OR_MISSING_FIELD")
    sha = manifest.get("sha")
    if type(sha) is not dict or set(sha) != {"core", "memory"} or not all(
            type(v) is str and _SHA.fullmatch(v) for v in sha.values()):
        bad("SHA_NOT_FULL")                                  # an abbreviated SHA is not a reproducible base
    entries = manifest.get("entries")
    if type(entries) is not list:
        bad("ENTRIES")
        return _report(errors, gaps)
    seen = {}
    for n, entry in enumerate(entries):
        where = f"entries[{n}]"
        if type(entry) is not dict or set(entry) - {"differences"} != _ENTRY:
            bad("ENTRY_FIELDS", where)
            continue
        step = entry["step"]
        if type(step) is not int or step not in STEPS:
            bad("STEP", where)
            continue
        env = entry["environment"]
        if type(env) is not dict or set(env) != _ENV or not all(_text(v, 200) for v in env.values()):
            bad("ENVIRONMENT", where)                        # the account is mandatory: root != ordinary UID
        if not _text(entry["command"]) or not _text(entry["limits"]):
            bad("COMMAND_OR_LIMITS", where)
        if _date(entry["date"], now) is None:
            bad("DATE", where)
        result = entry["result"]
        if type(result) is not dict or set(result) != {"verdict", "observed"} or not _text(result.get("observed")):
            bad("RESULT", where)
            continue
        verdict = result["verdict"]
        if verdict not in VERDICTS:
            bad("VERDICT", where)
            continue
        evidence = entry["evidence"]
        if type(evidence) is not list or any(
                type(e) is not dict or set(e) - {"sha256"} != {"kind", "ref"} or e.get("kind") not in ("log", "ci", "file")
                or not _text(e.get("ref"), 500) or ("sha256" in e and not (type(e["sha256"]) is str
                                                                             and _HEX64.fullmatch(e["sha256"])))
                for e in evidence):
            bad("EVIDENCE", where)
            continue
        if verdict == "PASS" and not evidence:
            bad("PASS_WITHOUT_EVIDENCE", where)
        if "differences" in entry:
            for d in entry["differences"] if type(entry["differences"]) is list else [None]:
                if (type(d) is not dict or set(d) != {"test", "class", "reason"} or d.get("class") not in "ABC"
                        or len(d.get("class", "")) != 1 or not _text(d.get("test"), 500)
                        or not _text(d.get("reason"))):
                    bad("DIFFERENCE", where)
                elif d["class"] == "C":
                    gaps.append(f"UNEXPLAINED_DIFFERENCE:step{step}")
        if step in seen and seen[step] != verdict:
            bad("CONTRADICTION", f"step{step}")              # two observations of one step disagree
        seen.setdefault(step, verdict)
        if verdict != "PASS":
            gaps.append(f"{verdict}:step{step}")
    for step in STEPS:
        if step not in seen:
            gaps.append(f"MISSING:step{step}")
    return _report(errors, sorted(set(gaps)))


def _report(errors, gaps):
    verdict = "INVALID" if errors else "INCOMPLETE" if gaps else "COMPLETE"
    return {"verdict": verdict, "errors": errors, "gaps": gaps if not errors else [],
            "authorizes_deployment": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Validate a filled beta evidence manifest (no collection).")
    parser.add_argument("manifest")
    parser.add_argument("--now", required=True, help="validation time, ISO 8601 with time zone")
    args = parser.parse_args(argv)
    now = datetime.fromisoformat(args.now) if len(args.now) <= 40 else None
    if now is None or now.tzinfo is None:
        parser.error("--now needs a time zone")
    with open(args.manifest, "rb") as handle:
        raw = handle.read(MAX_BYTES + 1)
    try:
        if len(raw) > MAX_BYTES:
            raise ValueError
        pairs_seen = []

        def unique(pairs):
            keys = [k for k, _ in pairs]
            if len(keys) != len(set(keys)):
                pairs_seen.append(True)
            return dict(pairs)
        manifest = json.loads(raw.decode("utf-8"), object_pairs_hook=unique,
                              parse_constant=lambda c: (_ for _ in ()).throw(ValueError()))
        if pairs_seen:
            raise ValueError
    except (ValueError, UnicodeError):
        report = {"verdict": "INVALID", "errors": ["JSON"], "gaps": [], "authorizes_deployment": False}
    else:
        report = validate(manifest, now=now)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return {"COMPLETE": 0, "INCOMPLETE": 1, "INVALID": 2}[report["verdict"]]


if __name__ == "__main__":
    sys.exit(main())
