#!/usr/bin/env python3
# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : tools/wake_training/gate.py
# Description : Critères du mot d'appel écrits avant entraînement, appliqués au banc (G296 v3)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Pre-registered acceptance gate for a synthetic bench row (eidolon-wake-gate/1).

wake_eval_g296 stays the scorer for *real* recordings, where false activations per hour
of the timeline are meaningful. On the synthetic bench the negative clips are trap words
read back to back, so their "per hour" is a density artefact; the gate measures them as
a *rate of trap clips that fire*, overall and per trap word, and keeps the 0.5/h ceiling
on ordinary audio that train.py never saw: train.py selects and merges checkpoints on
``false_positive_validation_data_path``, so the bench must use the other half of the
openWakeWord validation features (half B) and the model must have been selected on
half A only. Every floor also applies per spelling and per voice, so
an average cannot hide a broken spelling or speaker. Passing this gate only allows the
human recordings on Windows; activation needs the human gate.
"""
import hashlib
import json
from pathlib import Path

SYNTHETIC_KEYS = {"min_recall", "min_recall_per_spelling", "min_recall_per_voice",
                  "max_false_per_hour_general", "max_trap_fire_rate",
                  "max_trap_fire_rate_per_word", "max_latency_p95_ms"}


def load_gate(path):
    raw = Path(path).read_bytes()
    gate = json.loads(raw)
    if gate.get("schema") != "eidolon-wake-gate/1" or set(gate.get("synthetic", {})) != SYNTHETIC_KEYS:
        raise ValueError("invalid gate file")
    for key, value in gate["synthetic"].items():
        if type(value) not in (int, float) or value < 0:
            raise ValueError("invalid gate value: " + key)
    gate["_source"], gate["_sha256"] = str(path), hashlib.sha256(raw).hexdigest()
    return gate


def _rate(cell):
    return cell["fired"] / cell["total"] if cell["total"] else None


def evaluate_gate(row, gate):
    """row: one bench sweep row with breakdown and negative_features. -> {pass, reasons}."""
    g, reasons = gate["synthetic"], []
    if row["recall"] is None or row["recall"] < g["min_recall"]:
        reasons.append("RECALL")
    holdout = row.get("holdout_features") or {}
    if holdout.get("false_per_hour") is None:
        reasons.append("GENERAL_AUDIO_NOT_MEASURED")
    else:
        if holdout.get("clean") is not True:      # train.py selected checkpoints on these windows
            reasons.append("GENERAL_AUDIO_NOT_HELD_OUT")
        if holdout["false_per_hour"] > g["max_false_per_hour_general"]:
            reasons.append("FALSE_PER_HOUR_GENERAL")
    if row.get("latency_p95_ms") is None or row["latency_p95_ms"] > g["max_latency_p95_ms"]:
        reasons.append("LATENCY")
    b = row.get("breakdown")
    if b is None:
        reasons.append("BREAKDOWN_NOT_MEASURED")
    else:
        positive = b.get("positive", {})
        for axis, floor, code in (("phrase", g["min_recall_per_spelling"], "SPELLING"),
                                  ("voice", g["min_recall_per_voice"], "VOICE")):
            for key, cell in sorted(positive.get(axis, {}).items()):
                if _rate(cell) is not None and _rate(cell) < floor:
                    reasons.append(f"{code}:{key}")
        traps = b.get("negative", {}).get("phrase", {})
        fired = sum(c["fired"] for c in traps.values())
        total = sum(c["total"] for c in traps.values())
        if not total:
            reasons.append("TRAPS_NOT_MEASURED")
        elif fired / total > g["max_trap_fire_rate"]:
            reasons.append("TRAP_RATE")
        for key, cell in sorted(traps.items()):
            if _rate(cell) is not None and _rate(cell) > g["max_trap_fire_rate_per_word"]:
                reasons.append(f"TRAP:{key}")
    return {"pass": not reasons, "reasons": reasons}
