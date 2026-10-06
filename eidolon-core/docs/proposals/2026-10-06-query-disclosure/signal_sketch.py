# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : signal_sketch.py
# Description : Esquisse de signaux pour mesurer les limites des motifs (C-TASK-G029)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Measurement sketch only. Not wired to research.py and not a detector to ship.

It shows what a handful of obvious patterns catch and miss on corpus.json, so the
proposal can state the limits with evidence. A signal is a reason to ask, never a
permission: an empty result does not mean a query is safe to send.
"""
import json
from pathlib import Path
import re
import sys
import unicodedata

INVISIBLE = re.compile(r"[​-‍⁠﻿]")
PATTERNS = {
    "EMAIL": re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"),
    "PHONE": re.compile(r"(?<![\w.])(?:\+\d{1,3}[ .]?)?(?:\d[ .]?){9,10}\d?(?![\w.])"),
    "IBAN": re.compile(r"\b[A-Z]{2}\d{2}(?: ?[0-9A-Z]{4}){3,7}(?: ?[0-9A-Z]{1,3})?\b"),
    "URL_QUERY": re.compile(r"https?://\S+\?\S+"),
    "URL": re.compile(r"https?://\S+"),
    "LOCAL_PATH": re.compile(r"(?:\b[A-Za-z]:\\|\\\\[\w.-]+\\|(?:^|\s)/(?:home|Users|etc|var|root|mnt)/)"),
    "QUOTED": re.compile(r"[\"«“][^\"»”]{12,}[\"»”]"),
    "NETWORK_ADDRESS": re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
}


def signals(query):
    text = INVISIBLE.sub("", unicodedata.normalize("NFKC", query))
    found = {name for name, pattern in PATTERNS.items() if pattern.search(text)}
    if "URL_QUERY" in found:
        found.discard("URL")
    if "IBAN" in found:
        found.discard("PHONE")  # IBAN digits also look like a phone number
    return sorted(found)


def main(path):
    corpus = json.loads(Path(path).read_text(encoding="utf-8"))
    rows, missed, extra = [], 0, 0
    for case in corpus["queries"]:
        got, want = signals(case["query"]), sorted(case["expected_signals"])
        flagged = bool(got)
        protect = case["label"] != "PUBLIC"
        verdict = ("ok" if got == want else "DIFF")
        if protect and not flagged:
            missed += 1
            verdict += " / NON SIGNALÉ"
        if not protect and flagged:
            extra += 1
            verdict += " / FAUX POSITIF"
        rows.append(f"{case['id']} {case['label']:<15} attendu={','.join(want) or '-':<18} obtenu={','.join(got) or '-':<18} {verdict}")
    print("\n".join(rows))
    total = len(corpus["queries"])
    public = sum(c["label"] == "PUBLIC" for c in corpus["queries"])
    print(f"\n{total} requêtes ; à protéger non signalées : {missed}/{total - public} ; "
          f"publiques signalées : {extra}/{public}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).with_name("corpus.json"))
