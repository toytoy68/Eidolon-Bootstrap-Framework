# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : contracts.py
# Description : Contrats JSON des modèles, plans et rappels mémoire
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

"""Strict JSON boundaries. Source text is data, never permission."""
from __future__ import annotations

import hashlib
import json
import re
from typing import Protocol

MAX_JSON_BYTES = 1_000_000
MAX_PLAN_DEPTH = 32


class ContractError(ValueError):
    pass


def encode(value):
    try:
        raw = json.dumps(value, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":"), allow_nan=False)
        raw.encode("utf-8")  # Reject unpaired surrogates before any persistence.
        return raw
    except (TypeError, ValueError, RecursionError) as exc:
        raise ContractError("value is not finite UTF-8 JSON") from exc


def snapshot(value):
    raw = encode(value)
    if len(raw.encode("utf-8")) > MAX_JSON_BYTES:
        raise ContractError("JSON exceeds 1 MB")
    return json.loads(raw)


def digest(value):
    return hashlib.sha256(encode(value).encode("utf-8")).hexdigest()


def reference(item):
    return f"{item['information_id']}@{item['revision']}"


MEMORY_INDEX_STATES = ("INDEX_SNAPSHOT_MATCH", "INDEX_STALE", "INDEX_UNVERIFIED")


def _validate_index_status(value):
    """Optional G242 metadata; inconsistent claims invalidate the recall bundle."""
    if value is None:
        return
    keys = {"state", "reason", "generation", "source_digest", "canonical_digest"}
    if not isinstance(value, dict) or set(value) != keys:
        raise ContractError("invalid memory index status")
    state, reason = value["state"], value["reason"]
    generation, source, canonical = value["generation"], value["source_digest"], value["canonical_digest"]
    def digest_or_none(text):
        return text is None or (isinstance(text, str) and re.fullmatch(r"[0-9a-f]{64}", text))
    if (state not in MEMORY_INDEX_STATES
            or (generation is not None and (not isinstance(generation, str)
                or not re.fullmatch(r"[A-Za-z0-9_-]{1,256}", generation)))
            or not digest_or_none(source) or not digest_or_none(canonical)):
        raise ContractError("invalid memory index status")
    if state == "INDEX_UNVERIFIED":
        valid = (canonical is None and (
            (reason == "SNAPSHOT_NOT_SUPPORTED" and generation is None and source is None)
            or (reason == "NO_FULL_SOURCE_DIGEST" and generation is not None and source is None)
            or (reason == "CANONICAL_CHECK_INCOMPLETE" and generation is not None and source is not None)))
    else:
        match = state == "INDEX_SNAPSHOT_MATCH"
        valid = (generation is not None and source is not None and canonical is not None
                 and (source == canonical) == match
                 and reason == ("FULL_SOURCE_DIGEST_MATCH" if match else "FULL_SOURCE_DIGEST_MISMATCH"))
    if not valid:
        raise ContractError("inconsistent memory index status")


def validate_context(value):
    value = snapshot(value)
    if not isinstance(value, dict) or not isinstance(value.get("items"), list):
        raise ContractError("memory must provide an items list")
    _validate_index_status(value.get("index_status"))
    if len(value["items"]) > 5:
        raise ContractError("at most five memory items")
    seen = set()
    for item in value["items"]:
        if not isinstance(item, dict):
            raise ContractError("memory item must be an object")
        for key in ("information_id", "content"):
            if not isinstance(item.get(key), str) or not item[key]:
                raise ContractError(f"missing memory {key}")
        if type(item.get("revision")) is not int or item["revision"] < 1:
            raise ContractError("invalid memory revision")
        if len(item["content"]) > 4000 or type(item.get("needs_review")) is not bool:
            raise ContractError("invalid memory bounds/review flag")
        for key in ("provenance", "verification", "temporal"):
            if not isinstance(item.get(key), dict):
                raise ContractError(f"missing memory {key}")
        for key in ("epistemic_status", "operational_state", "confidence"):
            if key not in item or (item[key] is not None and not isinstance(item[key], str)):
                raise ContractError(f"missing memory label {key}")
        if type(item.get("truncated")) is not bool or "excerpt_reference" not in item:
            raise ContractError("missing excerpt boundaries")
        ref = reference(item)
        if ref in seen:
            raise ContractError("duplicate memory reference")
        seen.add(ref)
    return value


def parse_plan(raw):
    if not isinstance(raw, str):
        raise ContractError("model output must be bounded JSON text")
    try:
        size = len(raw.encode("utf-8"))
    except UnicodeError as exc:
        raise ContractError("model output must be UTF-8 text") from exc
    if size > 64_000:
        raise ContractError("model output must be bounded JSON text")

    # Bound nesting BEFORE parsing, independent of Python's recursion limit.
    # Brackets inside JSON strings do not contribute to structural depth.
    depth, quoted, escaped = 0, False, False
    for char in raw:
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        elif char in "[{":
            depth += 1
            if depth > MAX_PLAN_DEPTH:
                raise ContractError("model plan nesting exceeds 32 containers")
        elif char in "]}":
            depth -= 1

    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ContractError("duplicate JSON key")
            result[key] = value
        return result

    def nonfinite(_):
        raise ContractError("non-finite JSON number")

    try:
        plan = json.loads(raw, object_pairs_hook=unique, parse_constant=nonfinite)
    except (ValueError, RecursionError) as exc:
        raise ContractError("invalid model JSON") from exc
    if not isinstance(plan, dict) or set(plan) != {"version", "steps"}:
        raise ContractError("expected version and steps only; model success is not evidence")
    if type(plan["version"]) is not int or plan["version"] != 1:
        raise ContractError("unsupported plan version")
    steps = plan["steps"]
    if not isinstance(steps, list) or not 1 <= len(steps) <= 5:
        raise ContractError("plan needs one to five steps")
    ids = set()
    for step in steps:
        if not isinstance(step, dict) or set(step) != {"id", "tool", "parameters"}:
            raise ContractError("invalid step fields")
        if any(not isinstance(step[k], str) or not 1 <= len(step[k]) <= 80
               for k in ("id", "tool")) or step["id"] in ids:
            raise ContractError("invalid/duplicate step identity")
        if not isinstance(step["parameters"], dict):
            raise ContractError("parameters must be an object")
        ids.add(step["id"])
    # json.loads accepts exponent overflow (1e999) and escaped lone surrogates.
    # Validate the full decoded object, including nested parameters.
    return snapshot(plan)


class Model(Protocol):
    model_id: str

    def propose(self, request: str, context: dict) -> str: ...


class MemoryReader(Protocol):
    provider_id: str

    def recall(self, query: str) -> dict: ...
