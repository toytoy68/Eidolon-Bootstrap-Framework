# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : media_outputs.py
# Description : Import explicite de sorties ComfyUI avec historique et empreintes
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Collect bounded engine outputs into the private artifact store.

Only GETs against a validated literal loopback endpoint. The historical workflow
must match the recorded plan. A NEW collection directory prevents automatic replay;
partial imports retain provenance for manual review. No semantic success claim.
"""
import hashlib
import json
from pathlib import Path
import re
import urllib.parse
import uuid

from .media_agents import MediaError, identify, inspect, load_json, write_record
from .media_artifacts import ArtifactStore, MAX_FILE, MAX_IMAGE
from .media_backends import endpoint, json_http
from .media_transfer import raw_http

MAX_OUTPUTS = 16
MAX_COLLECTION_BYTES = 256 * 1024 * 1024
SUFFIX_TYPE = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "webp": "image/webp",
               "mp4": "video/mp4", "webm": "video/webm"}


def _receipt(record):
    if (record.get("schema") != "media-job/1" or not isinstance(record.get("id"), str)
            or not re.fullmatch(r"media-[0-9a-f]{32}", record["id"])
            or record.get("agent") not in ("image", "video") or record.get("operation") not in ("create", "edit")):
        raise MediaError("INVALID_JOB")
    if record.get("state") == "QUEUED":
        value = record.get("result")
    elif record.get("state") in {"INTENT", "REVIEW_REQUIRED"} and record.get("phase") == "QUEUE_ACKNOWLEDGED":
        value = record.get("phase_evidence")
    else:
        raise MediaError("JOB_NOT_QUEUED")
    if type(value) is not dict or not isinstance(value.get("prompt_id"), str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", value["prompt_id"]):
        raise MediaError("INVALID_JOB")
    plan = record.get("backend")
    if (type(plan) is not dict or plan.get("adapter") not in ("comfyui-prompt/1", "comfyui-prompt/2")
            or not isinstance(plan.get("workflow_sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", plan["workflow_sha256"])):
        raise MediaError("INVALID_JOB")
    return value["prompt_id"], plan


def descriptors(history, record):
    prompt_id, plan = _receipt(record)
    entry = history.get(prompt_id) if type(history) is dict else None
    if type(entry) is not dict or type(entry.get("status")) is not dict:
        raise MediaError("OUTPUT_HISTORY_UNAVAILABLE")
    if entry["status"].get("completed") is not True or entry["status"].get("status_str") != "success":
        raise MediaError("OUTPUT_HISTORY_INCOMPLETE")
    prompt = entry.get("prompt")
    if type(prompt) is not list or len(prompt) < 3 or prompt[1] != prompt_id or type(prompt[2]) is not dict:
        raise MediaError("OUTPUT_WORKFLOW_UNPROVEN")
    try:
        digest = hashlib.sha256(json.dumps(prompt[2], sort_keys=True, allow_nan=False).encode()).hexdigest()
    except (TypeError, ValueError, UnicodeError, RecursionError):
        raise MediaError("OUTPUT_WORKFLOW_UNPROVEN") from None
    if digest != plan["workflow_sha256"]:
        raise MediaError("OUTPUT_WORKFLOW_MISMATCH")
    outputs = entry.get("outputs")
    if type(outputs) is not dict or len(outputs) > 128 or not all(isinstance(k, str) for k in outputs):
        raise MediaError("INVALID_OUTPUT_HISTORY")
    selected, seen = [], set()
    for node in sorted(outputs):
        if not isinstance(node, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", node) or node not in prompt[2] or type(outputs[node]) is not dict:
            raise MediaError("INVALID_OUTPUT_NODE")
        for field in ("images", "gifs", "videos", "video"):
            values = outputs[node].get(field, [])
            if type(values) is not list or len(values) > MAX_OUTPUTS:
                raise MediaError("INVALID_OUTPUT_LIST")
            for value in values:
                if type(value) is not dict or value.get("type") != "output":
                    raise MediaError("OUTPUT_NOT_DURABLE")
                filename, folder = value.get("filename"), value.get("subfolder", "")
                if (not isinstance(filename, str) or not re.fullmatch(r"[A-Za-z0-9_-][A-Za-z0-9_.-]{0,179}", filename)
                        or ".." in filename or not isinstance(folder, str) or len(folder) > 240
                        or folder and (len(folder.split("/")) > 4 or any(not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", p) for p in folder.split("/")))):
                    raise MediaError("INVALID_OUTPUT_REFERENCE")
                media_type = SUFFIX_TYPE.get(filename.rsplit(".", 1)[-1].lower())
                if media_type is None or not media_type.startswith(record["agent"] + "/"):
                    raise MediaError("OUTPUT_TYPE_MISMATCH")
                key = (folder, filename)
                if key in seen:
                    raise MediaError("DUPLICATE_OUTPUT_REFERENCE")
                seen.add(key)
                selected.append({"node_id": node, "filename": filename, "subfolder": folder,
                                 "type": "output", "media_type": media_type})
                if len(selected) > MAX_OUTPUTS:
                    raise MediaError("OUTPUT_COUNT_LIMIT")
    if not selected:
        raise MediaError("NO_SUPPORTED_OUTPUT")
    return selected


def collect(job_directory, store_root, store_id, collection_directory, *, transport=None, binary_transport=None):
    transport = transport or json_http
    binary_transport = binary_transport or raw_http
    job = inspect(job_directory)
    prompt_id, plan = _receipt(job)
    base = endpoint(plan["endpoint"])
    store = ArtifactStore(store_root, expected_store_id=store_id)
    target = Path(collection_directory); target.mkdir(mode=0o700, parents=False, exist_ok=False)
    record = {"schema": "media-collection/1", "id": "mc-" + uuid.uuid4().hex,
              "job_id": job["id"], "prompt_id": prompt_id, "store_id": store.store_id,
              "state": "INTENT", "phase": "HISTORY_READING", "artifacts": [],
              "semantic_content_verified": False, "automatic_retry": False}
    write_record(target, record)
    try:
        history = transport("GET", base + "/history/" + prompt_id, None)
        selected = descriptors(history, job)
        record["history_workflow_matched"] = True
        record["expected_outputs"] = selected
        record["phase"] = "OUTPUTS_SELECTED"; write_record(target, record)
        total = 0
        for index, value in enumerate(selected):
            record["phase"] = "OUTPUT_FETCHING"; record["output_index"] = index; write_record(target, record)
            limit = min(MAX_IMAGE if value["media_type"].startswith("image/") else MAX_FILE, MAX_COLLECTION_BYTES - total)
            if limit <= 0:
                raise MediaError("OUTPUT_BYTES_LIMIT")
            query = urllib.parse.urlencode({k: value[k] for k in ("filename", "subfolder", "type")})
            kind, body = binary_transport("GET", base + "/view?" + query, None, None, limit)
            if (type(body) is not bytes or not 1 <= len(body) <= limit
                    or kind not in {value["media_type"], "application/octet-stream"}
                    or identify(body) != value["media_type"]):
                raise MediaError("OUTPUT_CONTENT_MISMATCH")
            provenance = {"kind": "comfy-output", "job_id": job["id"], "prompt_id": prompt_id,
                          "node_id": value["node_id"], "output_index": index, "collection_id": record["id"]}
            record["phase"] = "OUTPUT_IMPORTING"
            record["pending_import"] = {"sha256": hashlib.sha256(body).hexdigest(), "size": len(body), "provenance": provenance}
            write_record(target, record)
            manifest = store.import_bytes(body, display_name=value["filename"], provenance=provenance)
            total += len(body)
            record["artifacts"].append(manifest)
            del record["pending_import"]
            record["bytes"] = total; record["phase"] = "OUTPUT_IMPORTED"; write_record(target, record)
        record["state"] = "OUTPUTS_IMPORTED_UNVERIFIED"; record["phase"] = "DONE"
        write_record(target, record)
        return record
    except Exception as exc:
        record["state"] = "COLLECTION_INCOMPLETE"
        record["failure_code"] = exc.code if isinstance(exc, MediaError) else "COLLECTION_STORAGE_OR_TRANSPORT_ERROR"
        write_record(target, record)
        raise MediaError("COLLECTION_INCOMPLETE", "inspect the existing collection; no automatic restart") from None


def inspect_collection(directory):
    record = load_json(Path(directory) / "job.json", 1_000_000)
    if type(record) is not dict or record.get("schema") != "media-collection/1":
        raise MediaError("INVALID_COLLECTION")
    if record.get("state") == "INTENT":
        record["observed_state"] = "COLLECTION_INCOMPLETE"
    record["automatic_retry"] = False
    return record
