# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : media_workflows.py
# Description : Validation commune des modèles de workflow média, sans exécution
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Validate bindings without inventing source evidence or executing a workflow."""
import copy
import re

from .media_agents import MediaError

OPERATIONS = tuple(a + "." + op for a in ("image", "video") for op in ("create", "edit", "analyze"))
WORKFLOW_OPERATIONS = frozenset(k for k in OPERATIONS if not k.endswith(".analyze"))


def definition(config, key, *, has_source=None):
    """Return a detached template and bindings; None inspects declared source needs.

    An execution supplies its actual source presence; an inspection requires a
    source binding for edit and accepts either shape for create. No fictitious
    file, artifact reference or content hash enters an execution plan.
    """
    if key not in WORKFLOW_OPERATIONS or has_source is not None and type(has_source) is not bool:
        raise MediaError("INVALID_OPERATION")
    configs = config.get("workflows", {})
    if type(configs) is not dict or key not in configs:
        raise MediaError("WORKFLOW_NOT_CONFIGURED")
    entry = configs[key]
    if type(entry) is not dict or set(entry) != {"prompt", "bindings"}:
        raise MediaError("INVALID_WORKFLOW_CONFIG")
    prompt, bindings = copy.deepcopy(entry["prompt"]), copy.deepcopy(entry["bindings"])
    if type(prompt) is not dict or not 1 <= len(prompt) <= 128 or type(bindings) is not dict:
        raise MediaError("INVALID_WORKFLOW_CONFIG")
    for node_id, node in prompt.items():
        if not isinstance(node_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", node_id):
            raise MediaError("INVALID_WORKFLOW_NODE")
        if (type(node) is not dict or not isinstance(node.get("class_type"), str)
                or not 1 <= len(node["class_type"]) <= 160 or not node["class_type"].isprintable()
                or type(node.get("inputs")) is not dict):
            raise MediaError("INVALID_WORKFLOW_NODE")
    required = {"prompt", "width", "height"}
    if key.startswith("video."):
        required.add("duration_seconds")
    if has_source is None:
        has_source = key.endswith(".edit") or "source" in bindings
    if has_source:
        required.add("source")
    if set(bindings) != required:
        raise MediaError("WORKFLOW_BINDINGS_MISMATCH")
    used = set()
    for where in bindings.values():
        if (type(where) is not list or len(where) != 2 or not all(isinstance(v, str) for v in where)
                or where[0] not in prompt or where[1] not in prompt[where[0]]["inputs"]
                or tuple(where) in used):
            raise MediaError("INVALID_WORKFLOW_BINDING")
        used.add(tuple(where))
    return prompt, bindings
