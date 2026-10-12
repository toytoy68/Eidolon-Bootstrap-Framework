# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : monitor_activation.py
# Description : Activation explicite des outils monitor.machine / monitor.darme dans un Runtime, sans élargir le défaut (G168)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Explicit, auditable opt-in of Codex's read-only monitoring tools (monitor_tools.py, G161).

Nothing changes unless the operator writes a private activation file (0600, owner, no link):

  {"schema": "eidolon-monitor-tools-activation/1", "tools": ["monitor.machine"],
   "approved_by": "toytoy", "reason": "…"}

`activate(runtime, activation)` then ADDS the listed tools (and only them) to that runtime's registry and
policy; every existing tool, grant and the policy id stay, the new policy id records the activation.
The tools take exactly {} as parameters: no command, path or target can come from a proposal. Their
result is a snapshot plus its SHA-256, verified later WITHOUT a second probe. Default registries and
policies are never modified (tested).
"""
import json
import os
import re
import stat

from .monitor_tools import monitoring_registry, monitoring_policy
from .tools import Policy, Registry

SCHEMA = "eidolon-monitor-tools-activation/1"
TOOLS = ("monitor.machine", "monitor.darme")


def load_activation(path):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as handle:
        info = os.fstat(handle.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise ValueError("MONITOR_ACTIVATION_NOT_PRIVATE")
        value = json.loads(handle.read(16 * 1024).decode("utf-8"))
    if (not isinstance(value, dict) or set(value) != {"schema", "tools", "approved_by", "reason"}
            or value["schema"] != SCHEMA):
        raise ValueError("MONITOR_ACTIVATION_INVALID: schema, tools, approved_by, reason")
    tools = value["tools"]
    if (not isinstance(tools, list) or not tools or len(set(tools)) != len(tools)
            or not all(t in TOOLS for t in tools)):
        raise ValueError("MONITOR_ACTIVATION_INVALID: tools among " + ", ".join(TOOLS))
    if not isinstance(value["approved_by"], str) or not re.fullmatch(r"[a-z][a-z0-9_-]{0,31}", value["approved_by"]):
        raise ValueError("MONITOR_ACTIVATION_INVALID: approved_by")
    if not isinstance(value["reason"], str) or not 3 <= len(value["reason"]) <= 200:
        raise ValueError("MONITOR_ACTIVATION_INVALID: reason")
    return {"tools": tuple(tools), "approved_by": value["approved_by"], "reason": value["reason"]}


def compose(registry, policy, activation):
    """(registry, policy) with the activated tools added; unchanged objects when activation is None."""
    if activation is None:
        return registry, policy
    extra = monitoring_registry()
    allowed_by_codex = set(monitoring_policy().allowed_tools)
    names = list(registry.manifest())
    tools = [registry.get(name) for name in names]
    for name in activation["tools"]:
        if name not in allowed_by_codex:
            raise ValueError("MONITOR_ACTIVATION_INVALID: tool outside the monitoring policy")
        if registry.get(name) is not None:
            raise ValueError("MONITOR_ACTIVATION_CONFLICT: " + name)
        tool = extra.get(name)
        if tool is None or tool.effect != "none":
            raise ValueError("MONITOR_ACTIVATION_INVALID: " + name)
        tools.append(tool)
    composed = Policy(allowed_tools=tuple(policy.allowed_tools) + tuple(activation["tools"]),
                      policy_id=policy.policy_id + "+monitor:" + ",".join(sorted(activation["tools"])),
                      target_grants=policy.target_grants)
    return Registry(tools), composed


def activate(runtime, activation):
    """Apply to ONE runtime instance (the Core conversation runtime); returns it."""
    runtime.registry, runtime.policy = compose(runtime.registry, runtime.policy, activation)
    return runtime
