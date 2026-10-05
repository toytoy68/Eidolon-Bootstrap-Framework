"""Strict JSON boundaries. Source text is data, never permission."""
from __future__ import annotations

import hashlib
import json
from typing import Protocol

MAX_JSON_BYTES = 1_000_000


class ContractError(ValueError):
    pass


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False)


def snapshot(value):
    raw = encode(value)
    if len(raw.encode("utf-8")) > MAX_JSON_BYTES:
        raise ContractError("JSON exceeds 1 MB")
    return json.loads(raw)


def digest(value):
    return hashlib.sha256(encode(value).encode("utf-8")).hexdigest()


def reference(item):
    return f"{item['information_id']}@{item['revision']}"


def validate_context(value):
    value = snapshot(value)
    if not isinstance(value, dict) or not isinstance(value.get("items"), list):
        raise ContractError("memory must provide an items list")
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
    if not isinstance(raw, str) or len(raw.encode("utf-8")) > 64_000:
        raise ContractError("model output must be bounded JSON text")

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
    return plan


class Model(Protocol):
    model_id: str

    def propose(self, request: str, context: dict) -> str: ...


class MemoryReader(Protocol):
    provider_id: str

    def recall(self, query: str) -> dict: ...
