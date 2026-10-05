"""Trusted implementations, strict inputs, deterministic deny-by-default policy."""
from dataclasses import dataclass
import hashlib
from typing import Callable

from .contracts import ContractError, reference


def source_for(parameters, context):
    if (set(parameters) != {"reference"}
            or not isinstance(parameters["reference"], str)):
        raise ContractError("text.stats requires exactly one string reference")
    matches = [i for i in context["items"] if reference(i) == parameters["reference"]]
    if len(matches) != 1:
        raise ContractError("reference absent from persisted memory snapshot")
    return matches[0]


def text_stats(parameters, context):
    text = source_for(parameters, context)["content"]
    return {"characters": len(text), "utf8_bytes": len(text.encode("utf-8")),
            "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest()}


def verify_stats(parameters, context, result):
    if not isinstance(result, dict) or set(result) != {"characters", "utf8_bytes", "sha256"}:
        return False
    text = source_for(parameters, context)["content"]
    return (type(result["characters"]) is int and type(result["utf8_bytes"]) is int
            and result["characters"] == sum(1 for _ in text)
            and result["utf8_bytes"] == sum(len(c.encode("utf-8")) for c in text)
            and result["sha256"] == hashlib.sha256(text.encode("utf-8")).hexdigest())


@dataclass(frozen=True)
class Tool:
    name: str
    version: str
    effect: str
    validate: Callable
    execute: Callable
    verify: Callable
    verifier_id: str


class Registry:
    def __init__(self, tools):
        self._tools = {}
        for tool in tools:
            if tool.name in self._tools:
                raise ValueError("duplicate tool")
            self._tools[tool.name] = tool

    def get(self, name):
        return self._tools.get(name)

    def manifest(self):
        return {name: {"version": t.version, "effect": t.effect, "verifier": t.verifier_id}
                for name, t in sorted(self._tools.items())}


@dataclass(frozen=True)
class Policy:
    allowed_tools: tuple[str, ...] = ("text.stats",)
    policy_id: str = "local-pure-only/1"

    def allows(self, tool):
        # Even a listed tool is denied if it declares external effects.
        return tool is not None and tool.name in self.allowed_tools and tool.effect == "none"

    def manifest(self):
        return {"id": self.policy_id, "allowed_tools": sorted(self.allowed_tools),
                "allowed_effect": "none"}


def default_registry():
    return Registry([Tool("text.stats", "1", "none", source_for, text_stats,
                          verify_stats, "text-stats-recompute/1")])
