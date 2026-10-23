#!/usr/bin/env python3
# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : wake_eval_g296.py
# Description : Mesure des mots d'appel : détections, fausses activations, latence (G296)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Score any wake detector against an annotated recording timeline. Pure, offline.

The same report compares the current G282 path (energy gate + Whisper on the VM)
and a local detector (openWakeWord in the client): give each one's detection log.

Annotation (eidolon-wake-annotation/1):
  {"duration_s": 3600, "utterances": [{"start": 12.3, "end": 12.9, "phrase": "eidolon"}],
   "playback": [[40.0, 52.5]]}          # optional: intervals where Eidolon itself speaks
Detections (eidolon-wake-detections/1):
  {"detector": "oww-eidolon-v1", "events": [{"at": 13.1, "phrase": "eidolon", "score": 0.81}]}

A detection matches an utterance of the same phrase if it lands within
[start, end + window_s]. Latency = detection time - end of the phrase. Each
utterance matches at most one detection; extra detections are false activations,
counted separately when they fall inside Eidolon's own playback (echo).
"""
import argparse
import json
import math
from pathlib import Path

PHRASES = ("eidolon", "dis-moi")
DEFAULT_CRITERIA = {"min_recall": 0.95, "max_false_per_hour": 0.5, "max_latency_p95_ms": 500}


def _num(value, name, low=0.0, high=1e7):
    if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError("invalid " + name)
    return float(value)


def validate(annotation, detections):
    if annotation.get("schema") != "eidolon-wake-annotation/1" or detections.get("schema") != "eidolon-wake-detections/1":
        raise ValueError("unknown schema")
    duration = _num(annotation["duration_s"], "duration_s", 1)
    utterances = []
    for u in annotation["utterances"]:
        if u.get("phrase") not in PHRASES:
            raise ValueError("unknown phrase")
        start, end = _num(u["start"], "start", 0, duration), _num(u["end"], "end", 0, duration)
        if end < start:
            raise ValueError("utterance ends before it starts")
        utterances.append({"start": start, "end": end, "phrase": u["phrase"]})
    playback = [(_num(a, "playback", 0, duration), _num(b, "playback", 0, duration)) for a, b in annotation.get("playback", [])]
    events = []
    for e in detections["events"]:
        if e.get("phrase") not in PHRASES:
            raise ValueError("unknown phrase")
        events.append({"at": _num(e["at"], "at", 0, duration), "phrase": e["phrase"],
                       "score": _num(e.get("score", 1.0), "score", 0, 1)})
    return duration, utterances, playback, sorted(events, key=lambda e: e["at"])


def _p(values, q):
    if not values:
        return None
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, math.ceil(q * len(ordered)) - 1)]


def score(annotation, detections, *, window_s=1.5, criteria=None):
    duration, utterances, playback, events = validate(annotation, detections)
    criteria = dict(DEFAULT_CRITERIA, **(criteria or {}))
    used, per = set(), {}
    for phrase in PHRASES:
        targets = [u for u in utterances if u["phrase"] == phrase]
        hits, latencies = 0, []
        for u in sorted(targets, key=lambda x: x["start"]):
            for i, e in enumerate(events):
                if i in used or e["phrase"] != phrase or not u["start"] <= e["at"] <= u["end"] + window_s:
                    continue
                used.add(i); hits += 1; latencies.append(round((e["at"] - u["end"]) * 1000, 1))
                break
        false = [e for i, e in enumerate(events) if i not in used and e["phrase"] == phrase]
        echo = [e for e in false if any(a <= e["at"] <= b for a, b in playback)]
        per[phrase] = {"utterances": len(targets), "detected": hits,
                       "recall": round(hits / len(targets), 4) if targets else None,
                       "false_activations": len(false), "false_during_playback": len(echo),
                       "false_per_hour": round(len(false) * 3600 / duration, 3),
                       "latency_median_ms": _p(latencies, .5), "latency_p95_ms": _p(latencies, .95)}
    verdict = {}
    for phrase, m in per.items():
        if not m["utterances"]:
            verdict[phrase] = "NOT_MEASURED"
            continue
        ok = (m["recall"] >= criteria["min_recall"] and m["false_per_hour"] <= criteria["max_false_per_hour"]
              and m["latency_p95_ms"] is not None and m["latency_p95_ms"] <= criteria["max_latency_p95_ms"])
        verdict[phrase] = "ACCEPTED" if ok else "REJECTED"
    return {"schema": "eidolon-wake-report/1", "detector": detections.get("detector"), "duration_s": duration,
            "window_s": window_s, "criteria": criteria, "phrases": per, "verdict": verdict,
            "hardware_measured": bool(annotation.get("hardware_measured", False))}


def main():
    p = argparse.ArgumentParser(description="Mesure hors ligne d'un détecteur de mots d'appel")
    p.add_argument("--annotation", required=True, type=Path)
    p.add_argument("--detections", required=True, type=Path)
    p.add_argument("--window", type=float, default=1.5)
    a = p.parse_args()
    report = score(json.loads(a.annotation.read_text()), json.loads(a.detections.read_text()), window_s=a.window)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
