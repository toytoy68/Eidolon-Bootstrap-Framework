# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : media_preflight.py
# Description : Précontrôle média hors ligne et sondes locales sans génération
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Diagnostics are observations, never an execution permit or a reusable plan.

Offline by default. An explicit probe sends node class/model names only, never
the user's prompt or source bytes. No upload, inference, download or repair.
ComfyUI custom node metadata runs inside the trusted engine; it is not a sandbox.
"""
import hashlib
import json
import re
from urllib.parse import quote

from .media_agents import MediaError, prepare, read_source
from .media_backends import LocalMediaBackend, json_http
from .presentation import header, message, safe_text, section

MAX_NODE_CLASSES = 32
PROBE_SOCKET_TIMEOUT = 5


def fingerprint(value):
    try:
        raw = json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False,
                         separators=(",", ":")).encode("utf-8")
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise MediaError("INVALID_PREFLIGHT_INPUT") from None
    return hashlib.sha256(raw).hexdigest()


def _classes(workflow):
    classes = {}
    for node_id, node in workflow.items():
        name = node["class_type"]
        if (not isinstance(name, str) or not 1 <= len(name) <= 160 or name in {".", ".."}
                or any(not c.isprintable() or c in "/\\?#%" for c in name)):
            raise MediaError("INVALID_PROBE_NODE_CLASS")
        try:
            name.encode("utf-8")
        except UnicodeError:
            raise MediaError("INVALID_PROBE_NODE_CLASS") from None
        classes.setdefault(name, []).append(node_id)
    if len(classes) > MAX_NODE_CLASSES:
        raise MediaError("PROBE_NODE_LIMIT")
    return classes


def _node_metadata(name, node_ids, value, workflow, source_binding):
    info = value.get(name) if type(value) is dict else None
    if type(info) is not dict or "error" in value or info.get("name") != name or type(info.get("input")) is not dict:
        raise MediaError("NODE_METADATA_UNAVAILABLE")
    if "api_node" in info and type(info["api_node"]) is not bool:
        raise MediaError("INVALID_NODE_METADATA")
    if info.get("api_node") is True:
        raise MediaError("REMOTE_NODE_DECLARED")
    required = info["input"].get("required", {})
    optional = info["input"].get("optional", {})
    if (type(required) is not dict or type(optional) is not dict
            or len(required) + len(optional) > 1024
            or any(not isinstance(k, str) or not 1 <= len(k) <= 160 for k in (*required, *optional))):
        raise MediaError("INVALID_NODE_METADATA")
    choices_checked = 0
    for node_id in node_ids:
        inputs = workflow[node_id]["inputs"]
        if set(required) - set(inputs):
            raise MediaError("WORKFLOW_REQUIRED_INPUT_MISSING")
        for field, spec in {**required, **optional}.items():
            if field not in inputs or [node_id, field] == source_binding:
                continue  # a planned upload is not yet in LoadImage's file choices
            if type(spec) is not list or not spec:
                raise MediaError("INVALID_NODE_METADATA")
            if type(spec[0]) is list:
                if len(spec[0]) > 4096:
                    raise MediaError("NODE_CHOICES_LIMIT")
                chosen = inputs[field]
                # Links are engine-validated; do not mistake them for literal choices.
                if type(chosen) is list:
                    continue
                if chosen not in spec[0]:
                    raise MediaError("WORKFLOW_CHOICE_UNAVAILABLE")
                choices_checked += 1
    return {"node_class": name, "nodes": list(node_ids), "literal_choices_checked": choices_checked}


def preflight(request, config, *, probe_local=False, transport=None):
    if type(probe_local) is not bool:
        raise MediaError("INVALID_PROBE_OPTION")
    req = prepare(request)
    configuration_sha = fingerprint(config)
    runner = LocalMediaBackend(config)
    source, evidence = read_source(req, config)
    del source  # no content survives in the diagnostic or reaches a probe
    plan = runner.plan(req, evidence)
    workflow = None
    if req["operation"] != "analyze":
        workflow = runner.workflow(req, evidence)
    calls = ([{"method": "POST", "route": "/api/generate"}] if workflow is None else
             ([{"method": "POST", "route": "/upload/image"}] if evidence and plan["source_transfer"] == "upload-verified" else [])
             + ([{"method": "GET", "route": "/view"}] if evidence else [])
             + [{"method": "POST", "route": "/prompt"}])
    report = {"schema": "media-preflight/1", "state": "LOCAL_INPUTS_VALID",
              "agent": req["agent"], "operation": req["operation"],
              "request_sha256": fingerprint(req), "configuration_sha256": configuration_sha,
              "source_evidence": evidence, "diagnostic_backend": plan,
              "future_run_calls": calls, "probe_requested": probe_local,
              "probe_calls": [], "checks": [], "submitted": False,
              "execution_authorized": False, "plan_reusable": False,
              "hardware_qualified": False, "semantic_content_verified": False}
    if not probe_local:
        return report
    # Validate ALL route suffixes and the count before any network contact.
    classes = _classes(workflow) if workflow is not None else None
    send = transport or json_http
    def call(method, route, payload=None):
        report["probe_calls"].append({"method": method, "route": route})
        return send(method, plan["endpoint"] + route, payload, timeout=PROBE_SOCKET_TIMEOUT)
    try:
        if workflow is None:
            data = call("POST", "/api/show", {"model": plan["model"], "verbose": False})
            if type(data) is dict and "error" in data:
                raise MediaError("MODEL_METADATA_ERROR")
            caps = data.get("capabilities") if type(data) is dict else None
            if (type(caps) is not list or len(caps) > 32 or
                    any(not isinstance(c, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", c) for c in caps)):
                raise MediaError("MODEL_CAPABILITIES_UNAVAILABLE")
            if data.get("remote_host") or data.get("remote_model"):
                raise MediaError("REMOTE_MODEL_DECLARED")
            if "vision" not in caps:
                raise MediaError("VISION_NOT_ADVERTISED")
            report["checks"].append({"code": "VISION_ADVERTISED", "model": plan["model"]})
        else:
            binding = config["workflows"][req["agent"] + "." + req["operation"]]["bindings"].get("source")
            for name, node_ids in classes.items():
                data = call("GET", "/object_info/" + quote(name, safe=""))
                observation = _node_metadata(name, node_ids, data, workflow, binding)
                report["checks"].append(dict(observation, code="NODE_METADATA_CHECKED"))
        report["state"] = "PREREQUISITES_OBSERVED"
        return report
    except Exception as exc:
        code = exc.code if isinstance(exc, MediaError) else "PROBE_FAILED"
        if not isinstance(code, str) or not re.fullmatch(r"[A-Z0-9_]{1,80}", code):
            code = "PROBE_FAILED"
        report["state"] = "PROBE_INCOMPLETE"
        report["failure_code"] = code
        return report


def render_preflight(report):
    """Shared ECT presentation, without changing the JSON protocol or exit status."""
    lines = [header(title="Précontrôle des agents média"),
             message("INFO", "Diagnostic local : aucune génération, aucun upload, aucun téléchargement."),
             "Agent / opération : " + safe_text(report["agent"] + " / " + report["operation"]),
             section("Contrôles"), message("OK", "Demande, configuration sélectionnée et source éventuelle contrôlées localement.")]
    if report["probe_requested"]:
        lines.append(message("INFO", "Sondes de métadonnées tentées : " + str(len(report["probe_calls"]))))
        for check in report["checks"]:
            lines.append(message("OK", check["code"] + " : " + check.get("node_class", check.get("model", ""))))
        if report["state"] == "PROBE_INCOMPLETE":
            lines.append(message("ERREUR", report["failure_code"]))
    else:
        lines.append(message("INFO", "Moteur non contacté. Utiliser --probe-local pour les sondes de métadonnées."))
    lines.extend([section("Limites"), message("ATTENTION", "Ce diagnostic n'autorise aucune exécution et ne qualifie ni modèle, ni GPU, ni résultat."),
                  message("INFO", "Le lancement explicite revérifie la demande ; ce plan de diagnostic n'est pas réutilisable.")])
    return "\n".join(lines)
