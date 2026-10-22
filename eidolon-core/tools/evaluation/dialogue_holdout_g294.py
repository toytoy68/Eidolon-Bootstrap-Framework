#!/usr/bin/env python3
# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : dialogue_holdout_g294.py
# Description : Holdout indépendant, parcours conversation complet, notation stricte
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Independent holdout through the production conversation path (Claude, G294).

Each case goes through ConversationAPI → Dialogue → ChatDialogueModel.reply →
decide_reply, exactly as a paired client turn does; only Memory is replaced by
the case's synthetic notes. The model adaptation is therefore the one production
applies to that model (no extra --grounding prompt). Read-only: no tool, mission,
memory write or service change. The verdict separates five things:

  retrieval   not measured here (notes are given); see Memory run_memory_50
  evidence    abstention when the notes do not answer (``abstain``)
  citations   cited ids exist in what Core sent AND the expected one is cited
  answer      required/forbidden content, numbers not taken from elsewhere
  latency     seconds per turn

PASS / FAIL / REVIEW. REVIEW means a human must read the text (for instance an
abstention that also quotes a number from an unrelated note). Never tune the
expected values to a model's output.
"""
import argparse
import copy
import hashlib
import json
import re
import tempfile
import time
from pathlib import Path

SCHEMA = "eidolon-dialogue-holdout/1"
# Explicit statements of missing or insufficient evidence, not any "pas".
ABSTAIN = re.compile(
    r"ne (?:trouve|sais|connais|dispose|vois|peux (?:pas )?(?:confirmer|affirmer|indiquer|donner))\b"
    r"|n'(?:ai|y a) (?:pas|aucun)|pas (?:d'|de )(?:information|trace|preuve|donnée|résultat|mesure|score|date|mention)"
    r"|aucun(?:e)? (?:information|trace|preuve|donnée|résultat|mesure|score|date|mention|exécution)"
    r"|non (?:établi|trouvé|disponible|précisé|indiqué|mentionné|confirmé|communiqué|connu)"
    r"|(?:n'est|ne sont) pas (?:indiqué|mentionné|précisé|établi|connu|disponible|confirmé)"
    r"|ne (?:précise|mentionne|indique|donne|contient) pas|inconnu|insuffisant|impossible de (?:savoir|dire|confirmer)",
    re.IGNORECASE)
CITATION = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,120}@[0-9]{1,9}")
NUMBER = re.compile(r"(?<![\w.,])\d+(?:[.,]\d+)?(?![\w])")


def numbers(text):
    return {n.replace(",", ".") for n in NUMBER.findall(CITATION.sub(" ", text or ""))}


def _any(text, spec):
    return any(alt.lower() in text.lower() for alt in spec.split("|"))


def score(case, reply, seconds=None):
    """Verdict for one Core reply (decide_reply output). Pure; tested offline."""
    text = reply.get("model_text") or ""
    citations = reply.get("citations") or {"claimed": [], "unsupported": []}
    checks, review = {}, []
    checks["kind"] = reply.get("kind") in case["kind"]
    checks["required"] = all(_any(text, spec) for spec in case["contains"])
    checks["forbidden"] = not any(_any(text, spec) for spec in case["excludes"])
    checks["citations_sent"] = not citations["unsupported"]
    if case["cite"]:
        checks["cites_expected"] = any(c in citations["claimed"] for c in case["cite"])
    if case.get("abstain"):
        checks["abstention"] = bool(ABSTAIN.search(text))
    if case.get("foreign_numbers"):
        foreign = numbers(text) - numbers(case["question"]) - {n.replace(",", ".") for n in case.get("numbers", [])}
        allowed = set()
        for spec in case["contains"]:
            allowed |= numbers(spec)
        foreign -= allowed
        if foreign:
            if case["foreign_numbers"] == "fail" or not checks.get("abstention"):
                checks["no_foreign_numbers"] = False
            else:
                review.append("numbers " + ",".join(sorted(foreign)))
    verdict = "PASS" if all(checks.values()) else "FAIL"
    if verdict == "PASS" and review:
        verdict = "REVIEW"
    return {"case": case["id"], "family": case["family"], "verdict": verdict, "kind": reply.get("kind"),
            "failed": sorted(k for k, v in checks.items() if not v), "review": review,
            "cited": citations["claimed"], "unsupported": citations["unsupported"],
            "seconds": seconds}


def load(path):
    data = json.loads(Path(path).read_text())
    if data.get("schema") != SCHEMA or len({c["id"] for c in data["cases"]}) != len(data["cases"]):
        raise ValueError("invalid holdout")
    return data


class CaseMemory:
    """Recall-contract context built from the case notes; no store or network."""

    def __init__(self, items):
        from eidolon_core.memory import SyntheticMemory
        self.items, self.base = items, SyntheticMemory()

    def recall(self, query):
        value = self.base.recall(query)
        template = value["items"][0]
        value["items"] = []
        for identity, content in self.items:
            item = copy.deepcopy(template)
            item.update(information_id=identity, revision=1, content=content)
            item["excerpt_reference"] = {"source": identity + "/1", "start": 0, "end": len(content)}
            value["items"].append(item)
        return value


def run_case(case, model_factory, workdir):
    """One case on a fresh Store and paired client, through ConversationAPI.handle."""
    from eidolon_core.client_credentials import ClientCredentials
    from eidolon_core.conversation_api import ConversationAPI
    from eidolon_core.conversation_store import ConversationStore
    from eidolon_core.diagnostics import synthetic_runtime
    from eidolon_core.store import Store
    runtime = synthetic_runtime(Store(Path(workdir) / case["id"]))
    ConversationStore(runtime.store, create=True)
    key = ClientCredentials(runtime.store, create=True).pair(client_id="holdout", actor="holdout")["token"]
    api = ConversationAPI(runtime, dialogue_model=model_factory(runtime.catalog),
                          memory=CaseMemory(case["items"]) if case["items"] else None)

    def call(route, body):
        return api.handle("POST", "/v1/conversations/" + route,
                          {"Authorization": ["Bearer " + key], "Content-Type": ["application/json"]},
                          json.dumps(body).encode())
    try:
        status, opened = call("open", {"client_key": "holdout"})
        if status != 200:
            raise RuntimeError("open refused")
        start = time.monotonic()
        status, result = call("turn", {"conversation_id": opened["conversation_id"],
                                       "client_turn_key": "t1", "text": case["question"]})
        seconds = round(time.monotonic() - start, 3)
        if status != 200:
            return {"case": case["id"], "family": case["family"], "verdict": "FAIL",
                    "failed": ["http_" + str(status)], "review": [], "seconds": seconds}
        row = score(case, result["reply"], seconds)
        row["text"] = result["reply"].get("model_text")
        return row
    finally:
        api.close()


def summary(rows):
    families = {}
    for r in rows:
        f = families.setdefault(r["family"], {"PASS": 0, "FAIL": 0, "REVIEW": 0})
        f[r["verdict"]] += 1
    failures = {}
    for r in rows:
        for k in r["failed"]:
            failures[k] = failures.get(k, 0) + 1
    return {"cases": len(rows), "pass": sum(r["verdict"] == "PASS" for r in rows),
            "fail": sum(r["verdict"] == "FAIL" for r in rows),
            "review": sum(r["verdict"] == "REVIEW" for r in rows),
            "failed_checks": dict(sorted(failures.items())), "families": families}


def main():
    p = argparse.ArgumentParser(description="Holdout G294 par le parcours de conversation réel, lecture seule")
    p.add_argument("--model-config", required=True, help="configuration privée du modèle (même format que Core)")
    p.add_argument("--cases", default=str(Path(__file__).with_name("dialogue_holdout_g294.json")))
    p.add_argument("--out", required=True)
    a = p.parse_args()
    from eidolon_core.dialogue import ChatDialogueModel
    from eidolon_core.model_config import load_model
    data = load(a.cases)
    suite = hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    rows = []
    with tempfile.TemporaryDirectory(prefix="eidolon-holdout-") as workdir:
        for case in data["cases"]:
            row = run_case(case, lambda catalog: ChatDialogueModel(load_model(a.model_config), catalog), workdir)
            row["suite_sha256"] = suite
            rows.append(row)
            print(row["case"], row["verdict"], row["failed"], row["seconds"], flush=True)
    report = {"schema": "eidolon-dialogue-holdout-report/1", "suite_sha256": suite,
              "summary": summary(rows), "rows": rows}
    Path(a.out).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print("SUMMARY", json.dumps(report["summary"], ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
