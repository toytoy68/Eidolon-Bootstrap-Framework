# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : qualification.py
# Description : Validateur pur des rapports de qualification G-017
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

"""Offline consistency checks for inference qualification reports.

The validator checks that a report is complete, internally consistent and
within its fixed criteria. It cannot check that the telemetry is authentic,
and its best verdict is PASSED_SCOPE: valid for the announced scope only,
never a general qualification of a model, an engine or a machine.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import hashlib
import json
import math
import re

SCHEMA = "eidolon-qualification-report/1"
MAX_BYTES = 1_000_000
MAX_DEPTH = 8
MAX_CASES = 10_000
MAX_ITEMS = 64
MAX_TEXT = 200

ORIGINS = ("synthetic", "hardware_reported")
PROFILES = ("1", "2a", "2b", "3")
OUTCOMES = ("PASS", "FAIL", "ERROR")
METRIC_UNITS = {
    "ttft": "ms", "prefill_throughput": "tokens/s", "decode_throughput": "tokens/s",
    "vram_peak_gpu0": "MiB", "vram_peak_gpu1": "MiB", "power_gpu0": "W", "power_gpu1": "W",
    "p2p_bandwidth_ratio": "ratio", "p2p_latency": "us", "latency_degradation": "percent",
    "error_rate": "ratio",
}
OPERATORS = ("<=", ">=")
HEX64 = re.compile(r"[0-9a-f]{64}")
IDENT = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,99}")


class ReportError(ValueError):
    """The document is not a well-formed report; no verdict is possible."""


@dataclass(frozen=True)
class Verdict:
    status: str                     # PASSED_SCOPE, INCOMPLETE or REJECTED
    reasons: tuple = ()             # (code, detail) pairs; empty only for PASSED_SCOPE
    scope: dict = field(default_factory=dict)

    def to_dict(self):
        return {"status": self.status, "scope": dict(self.scope),
                "reasons": [{"code": c, "detail": d} for c, d in self.reasons],
                "limits": ["Consistency of the report only; telemetry authenticity is not checked.",
                           "PASSED_SCOPE covers the announced profile, engine, model and origin only."]}


def criteria_fingerprint(thresholds):
    """SHA-256 of the canonical threshold list, as recorded before the run."""
    canonical = json.dumps(thresholds, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def load(raw):
    """Strict, bounded JSON: no NaN/Infinity, no duplicate keys, bounded depth."""
    if isinstance(raw, (bytes, bytearray)):
        if len(raw) > MAX_BYTES:
            raise ReportError("report exceeds 1 MB")
        try:
            raw = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ReportError("report is not UTF-8") from exc
    if not isinstance(raw, str) or len(raw.encode("utf-8", "surrogatepass")) > MAX_BYTES:
        raise ReportError("report must be JSON text of at most 1 MB")

    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ReportError(f"duplicate key {key!r}")
            result[key] = value
        return result

    def constant(name):
        raise ReportError(f"non-finite number {name}")

    try:
        value = json.loads(raw, object_pairs_hook=unique, parse_constant=constant)
    except RecursionError as exc:
        raise ReportError("report nesting too deep") from exc
    except ValueError as exc:
        if isinstance(exc, ReportError):
            raise
        raise ReportError("report is not valid JSON") from exc
    _depth(value, 0)
    return value


def _depth(value, level):
    if level > MAX_DEPTH:
        raise ReportError(f"report nesting exceeds {MAX_DEPTH}")
    if isinstance(value, dict):
        for item in value.values():
            _depth(item, level + 1)
    elif isinstance(value, list):
        for item in value:
            _depth(item, level + 1)


def _object(value, keys, where, optional=()):
    if not isinstance(value, dict):
        raise ReportError(f"{where} must be an object")
    missing = set(keys) - set(value)
    unknown = set(value) - set(keys) - set(optional)
    if missing or unknown:
        raise ReportError(f"{where}: missing {sorted(missing)} unknown {sorted(unknown)}")
    return value


def _text(value, where, pattern=None):
    if not isinstance(value, str) or not value.strip() or len(value) > MAX_TEXT:
        raise ReportError(f"{where} must be a non-empty string of at most {MAX_TEXT} characters")
    if pattern is not None and not pattern.fullmatch(value):
        raise ReportError(f"{where} has an invalid format")
    return value


def _count(value, where, limit=MAX_CASES):
    if type(value) is not int or not 0 <= value <= limit:
        raise ReportError(f"{where} must be an integer within [0, {limit}]")
    return value


def _number(value, where):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ReportError(f"{where} must be a finite number")
    return value


def _timestamp(value, where):
    _text(value, where)
    try:
        moment = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ReportError(f"{where} must be an ISO 8601 timestamp") from exc
    if moment.tzinfo is None:
        raise ReportError(f"{where} must carry a time zone")
    return moment


def _parse(report):
    _object(report, ("schema", "run", "scope", "fingerprints", "criteria", "cases", "measurements"), "report")
    if report["schema"] != SCHEMA:
        raise ReportError(f"unsupported schema, expected {SCHEMA}")
    run = _object(report["run"], ("id", "started_at", "origin"), "run")
    _text(run["id"], "run.id", IDENT)
    started = _timestamp(run["started_at"], "run.started_at")
    if run["origin"] not in ORIGINS:
        raise ReportError(f"run.origin must be one of {ORIGINS}")
    scope = _object(report["scope"], ("profile", "engine", "model", "statement"), "scope")
    if scope["profile"] not in PROFILES:
        raise ReportError(f"scope.profile must be one of {PROFILES}")
    for key in ("engine", "model", "statement"):
        _text(scope[key], f"scope.{key}")
    prints = _object(report["fingerprints"], ("corpus_sha256", "configuration_sha256", "criteria_sha256"),
                     "fingerprints")
    for key, value in prints.items():
        _text(value, f"fingerprints.{key}", HEX64)
    criteria = _object(report["criteria"], ("fixed_at", "thresholds"), "criteria")
    fixed = _timestamp(criteria["fixed_at"], "criteria.fixed_at")
    thresholds = criteria["thresholds"]
    if not isinstance(thresholds, list) or not 1 <= len(thresholds) <= MAX_ITEMS:
        raise ReportError(f"criteria.thresholds must hold 1 to {MAX_ITEMS} entries")
    seen = set()
    for i, item in enumerate(thresholds):
        _object(item, ("metric", "unit", "op", "value"), f"criteria.thresholds[{i}]")
        _unit(item["metric"], item["unit"], f"criteria.thresholds[{i}]")
        if item["op"] not in OPERATORS:
            raise ReportError(f"criteria.thresholds[{i}].op must be one of {OPERATORS}")
        _number(item["value"], f"criteria.thresholds[{i}].value")
        if (item["metric"], item["op"]) in seen:
            raise ReportError(f"criteria.thresholds[{i}] duplicates a metric/operator pair")
        seen.add((item["metric"], item["op"]))
    cases = _object(report["cases"], ("expected", "executed", "results"), "cases")
    _count(cases["expected"], "cases.expected")
    _count(cases["executed"], "cases.executed")
    if not isinstance(cases["results"], list) or len(cases["results"]) > MAX_CASES:
        raise ReportError(f"cases.results must be a list of at most {MAX_CASES}")
    for i, result in enumerate(cases["results"]):
        _object(result, ("id", "outcome", "violations", "origin"), f"cases.results[{i}]")
        _text(result["id"], f"cases.results[{i}].id", IDENT)
        if result["outcome"] not in OUTCOMES:
            raise ReportError(f"cases.results[{i}].outcome must be one of {OUTCOMES}")
        if result["origin"] not in ORIGINS:
            raise ReportError(f"cases.results[{i}].origin must be one of {ORIGINS}")
        if not isinstance(result["violations"], list) or len(result["violations"]) > MAX_ITEMS:
            raise ReportError(f"cases.results[{i}].violations must be a list of at most {MAX_ITEMS}")
        for j, violation in enumerate(result["violations"]):
            _text(violation, f"cases.results[{i}].violations[{j}]")
    measurements = report["measurements"]
    if not isinstance(measurements, dict) or len(measurements) > MAX_ITEMS:
        raise ReportError(f"measurements must be an object of at most {MAX_ITEMS} metrics")
    for metric, entry in measurements.items():
        _object(entry, ("value", "unit", "origin"), f"measurements.{metric}")
        _unit(metric, entry["unit"], f"measurements.{metric}")
        if entry["value"] is not None:
            _number(entry["value"], f"measurements.{metric}.value")
        if entry["origin"] not in ORIGINS:
            raise ReportError(f"measurements.{metric}.origin must be one of {ORIGINS}")
    return started, fixed


def _unit(metric, unit, where):
    if metric not in METRIC_UNITS:
        raise ReportError(f"{where}: unknown metric {metric!r}")
    if unit != METRIC_UNITS[metric]:
        raise ReportError(f"{where}: unit for {metric} must be {METRIC_UNITS[metric]!r}")


def validate(raw):
    """Return a Verdict for a report given as JSON text, bytes or decoded object."""
    report = load(raw) if isinstance(raw, (str, bytes, bytearray)) else load(_reencode(raw))
    started, fixed = _parse(report)
    run, cases, criteria = report["run"], report["cases"], report["criteria"]
    measurements = report["measurements"]
    rejected, incomplete = [], []

    # Criteria must be fixed before the run and match their recorded fingerprint.
    if fixed > started:
        rejected.append(("CRITERIA_AFTER_RUN", "criteria fixed after the run started"))
    if criteria_fingerprint(criteria["thresholds"]) != report["fingerprints"]["criteria_sha256"]:
        rejected.append(("CRITERIA_FINGERPRINT", "thresholds differ from the recorded fingerprint"))

    # Synthetic and hardware data never mix in one report.
    origins = {run["origin"]} | {r["origin"] for r in cases["results"]} | {
        m["origin"] for m in measurements.values()}
    if len(origins) > 1:
        rejected.append(("MIXED_ORIGIN", "synthetic and hardware-reported data in one report"))

    # Counts must agree with the listed results.
    results = cases["results"]
    ids = [r["id"] for r in results]
    if len(set(ids)) != len(ids):
        rejected.append(("DUPLICATE_CASE", "a case id appears more than once"))
    if cases["executed"] != len(results):
        rejected.append(("COUNT_MISMATCH", f"executed={cases['executed']} but {len(results)} results listed"))
    if cases["executed"] > cases["expected"]:
        rejected.append(("COUNT_MISMATCH", "more cases executed than expected"))
    elif len(results) < cases["expected"]:
        incomplete.append(("CASES_MISSING", f"{cases['expected'] - len(results)} expected case(s) without result"))

    # One violation or failure rejects the run, whatever the other results.
    for result in results:
        if result["violations"]:
            rejected.append(("VIOLATION", f"{result['id']}: {', '.join(result['violations'])}"))
        if result["outcome"] != "PASS":
            rejected.append(("CASE_" + result["outcome"], result["id"]))

    # Thresholds: an absent measurement is incomplete, never zero.
    for item in criteria["thresholds"]:
        entry = measurements.get(item["metric"])
        if entry is None or entry["value"] is None:
            incomplete.append(("MEASUREMENT_MISSING", item["metric"]))
            continue
        ok = entry["value"] <= item["value"] if item["op"] == "<=" else entry["value"] >= item["value"]
        if not ok:
            rejected.append(("THRESHOLD", f"{item['metric']}={entry['value']} {item['unit']}, "
                                          f"required {item['op']} {item['value']}"))

    scope = {**report["scope"], "origin": run["origin"], "run_id": run["id"],
             "cases": {"expected": cases["expected"], "listed": len(results)}}
    if rejected:
        return Verdict("REJECTED", tuple(rejected + incomplete), scope)
    if incomplete:
        return Verdict("INCOMPLETE", tuple(incomplete), scope)
    return Verdict("PASSED_SCOPE", (), scope)


def _reencode(value):
    try:
        return json.dumps(value, allow_nan=False, ensure_ascii=False)
    except (TypeError, ValueError, RecursionError) as exc:
        raise ReportError("report object is not finite, bounded JSON") from exc
