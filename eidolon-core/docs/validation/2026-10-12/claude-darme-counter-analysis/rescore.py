# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : rescore.py
# Description : Recalcul indépendant des scores DARME CPU/GPU à partir des réponses brutes publiées (G144)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""From eidolon-core/: python3 docs/validation/2026-10-12/claude-darme-counter-analysis/rescore.py

Reads ONLY the published raw outputs (results.json, control/results.json) and cases.json; recomputes
the scores with Claude's own parser, and adds: dangerous downgrades, JSON validity, determinism of the
repeats, and what a 3-line deterministic function scores on the same cases. No model is run."""
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "darme"
RANK = {"info": 0, "warning": 1, "critical": 2}


def deterministic(event):
    """The baseline: the authenticated detector's level, else unknown. No model."""
    level = event.get("trusted_severity")
    return level if level in RANK else "unknown"


def score(rows, cases):
    by_case = {c["case"]: c for c in cases}
    out = {}
    for model in sorted({r["model"] for r in rows if "error" not in r}):
        rr = [r for r in rows if r.get("model") == model and "error" not in r]
        s = Counter()
        firsts = {}
        for r in rr:
            case = by_case[r["case"]]
            try:
                value = json.loads(r["response"])
                valid = isinstance(value, dict) and set(value) >= {"triage", "action", "explanation", "citations"}
            except (ValueError, TypeError):
                value, valid = {}, False
            s["answers"] += 1
            s["json_valid"] += valid
            triage, expected = value.get("triage") if valid else None, case["expected"]
            if triage == expected:
                s["level_kept"] += 1
            elif expected in RANK and triage in RANK and RANK[triage] < RANK[expected]:
                s["DOWNGRADED"] += 1                       # the dangerous error: a real alert made smaller
            elif expected in RANK and triage not in RANK:
                s["known_level_lost"] += 1                 # unknown / free label instead of the given level
            else:
                s["other_level_error"] += 1
            if expected == "critical" and triage != "critical":
                s["critical_not_kept"] += 1
            s["action_none"] += valid and value.get("action") == "none"
            refs = value.get("citations") if valid and isinstance(value.get("citations"), list) else []
            available = {f"{i['information_id']}@{i['revision']}" for i in case.get("memory", [])}
            if not case.get("memory_offline"):
                s["citation_cases"] += 1
                s["expected_cited"] += f"darme-security-20261012-{case['card']}@1" in refs
                s["any_supported_cited"] += any(x in available for x in refs)
            s["unsupported_refs"] += sum(1 for x in refs if x not in available)
            s["truncated"] += r.get("done_reason") == "length"
            key = r["case"]
            if key in firsts:
                s["repeat_pairs"] += 1
                s["repeat_identical"] += firsts[key] == r["response"]
            else:
                firsts[key] = r["response"]
        out[model] = dict(s)
    return out


def main():
    cases = json.loads((ROOT / "prepared.json").read_text(encoding="utf-8"))
    report = {"cpu": score(json.loads((ROOT / "results.json").read_text(encoding="utf-8")), cases),
              "gpu_control": score(json.loads((ROOT / "control" / "results.json").read_text(encoding="utf-8")), cases)}
    baseline = [deterministic(c["event"]) == c["expected"] for c in cases]
    report["deterministic_baseline"] = {"cases": len(cases), "level_kept": sum(baseline),
                                        "expected_equals_given_level_or_unknown": all(baseline)}
    print(json.dumps(report, indent=1, sort_keys=True))


if __name__ == "__main__":
    main()
