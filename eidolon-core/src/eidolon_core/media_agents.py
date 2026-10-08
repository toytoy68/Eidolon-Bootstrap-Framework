# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : media_agents.py
# Description : Agents média natifs, contrats et travaux locaux explicites
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Installable Image/Video agents. Local jobs are NOT Core mission receipts.

No model download, default engine, HTTP command route or automatic retry.
A durable INTENT precedes the backend call; an incomplete job requires review.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import stat
import uuid


class MediaError(ValueError):
    def __init__(self, code, message=""):
        self.code = code
        super().__init__(code + (": " + message if message else ""))


def read_regular(path, limit):
    """Bounded read, no terminal symlink/FIFO; caller owns the parent directory."""
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_size > limit:
            raise MediaError("FILE_REFUSED")
        body = stream.read(limit + 1)
        after = os.fstat(stream.fileno())
        if len(body) > limit or (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
                after.st_size, after.st_mtime_ns, after.st_ctime_ns):
            raise MediaError("FILE_CHANGED_OR_TOO_LARGE")
        return body


def parse_json(body):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise MediaError("DUPLICATE_JSON_KEY")
            result[key] = value
        return result
    def constant(_):
        raise MediaError("INVALID_JSON_NUMBER")
    try:
        return json.loads(body, object_pairs_hook=pairs, parse_constant=constant)
    except (ValueError, UnicodeError, RecursionError) as exc:
        if isinstance(exc, MediaError):
            raise
        raise MediaError("INVALID_JSON") from None


def load_json(path, limit=1_000_000):
    return parse_json(read_regular(path, limit))


def catalog():
    return {"schema": "media-agents/1", "agents": [
        {"id": agent, "label": label, "installed": True,
         "operations": ["create", "edit", "analyze"], "engine": "NOT_CONFIGURED",
         "execution_from_home": False}
        for agent, label in (("image", "Image"), ("video", "Vidéo"))]}


def prepare(request):
    """Pure validation; a draft is neither permission nor a submitted job."""
    keys = {"agent", "operation", "prompt", "source", "format", "duration_seconds"}
    if type(request) is not dict or set(request) - keys:
        raise MediaError("INVALID_REQUEST")
    agent, op, prompt = (request.get(k) for k in ("agent", "operation", "prompt"))
    if agent not in ("image", "video") or op not in ("create", "edit", "analyze"):
        raise MediaError("INVALID_OPERATION")
    if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 4000:
        raise MediaError("INVALID_PROMPT")
    try:
        prompt.encode("utf-8", errors="strict")
    except UnicodeError:
        raise MediaError("INVALID_PROMPT") from None
    source = request.get("source")
    if source is not None and (not isinstance(source, str) or not source or len(source) > 4096
                               or any(ord(c) < 32 for c in source)):
        raise MediaError("INVALID_SOURCE")
    if op != "create" and not source:
        raise MediaError("SOURCE_REQUIRED")
    fmt, duration = request.get("format"), request.get("duration_seconds")
    if op == "analyze":
        if fmt is not None or duration is not None:
            raise MediaError("ANALYSIS_HAS_NO_OUTPUT_FORMAT")
    else:
        if fmt not in ("square", "landscape", "portrait"):
            raise MediaError("INVALID_FORMAT")
        if agent == "video":
            if type(duration) is not int or duration not in (5, 10, 15):
                raise MediaError("INVALID_DURATION")
        elif duration is not None:
            raise MediaError("IMAGE_HAS_NO_DURATION")
    return {"agent": agent, "operation": op, "prompt": prompt.strip(), "source": source,
            "format": fmt, "duration_seconds": duration}


def identify(body):
    if body.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if body.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if body.startswith(b"RIFF") and body[8:12] == b"WEBP":
        return "image/webp"
    if body[4:8] == b"ftyp":
        return "video/mp4"
    if body.startswith(b"\x1a\x45\xdf\xa3"):
        return "video/webm"
    raise MediaError("UNSUPPORTED_MEDIA_HEADER")


def read_source(request):
    if not request["source"]:
        return None, None
    body = read_regular(request["source"], 200 * 1024 * 1024)
    kind = identify(body)
    image = kind.startswith("image/")
    if image and len(body) > 20 * 1024 * 1024:
        raise MediaError("IMAGE_TOO_LARGE")
    if request["agent"] == "image" and not image or (
            request["agent"] == "video" and request["operation"] != "create" and image):
        raise MediaError("SOURCE_TYPE_MISMATCH")
    return body, {"sha256": hashlib.sha256(body).hexdigest(), "size": len(body), "type": kind}


def write_record(directory, record):
    """Atomic record publication inside an owned, private job directory."""
    temp = directory / (".record-" + uuid.uuid4().hex)
    try:
        with temp.open("xb") as stream:
            stream.write(json.dumps(record, ensure_ascii=False, allow_nan=False).encode("utf-8"))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, directory / "job.json")
        fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    finally:
        temp.unlink(missing_ok=True)


def execute(request, config, directory, *, backend=None):
    """Explicit local execution, once per NEW directory. No recovery by resubmit."""
    from .media_backends import LocalMediaBackend
    req = prepare(request)
    runner = backend or LocalMediaBackend(config)
    source, evidence = read_source(req)
    plan = runner.plan(req, evidence)  # reject missing models/workflows BEFORE any job/network
    target = Path(directory)
    target.mkdir(mode=0o700, parents=False, exist_ok=False)
    record = {"schema": "media-job/1", "id": "media-" + uuid.uuid4().hex,
              "agent": req["agent"], "operation": req["operation"], "state": "INTENT",
              "request": req, "source_evidence": evidence, "backend": plan,
              "core_mission": None, "verified": False, "automatic_retry": False}
    write_record(target, record)
    try:
        result = runner.run(req, source, evidence, plan)
        record["result"] = result
        record["state"] = result["state"]
        write_record(target, record)
        return record
    except Exception:
        # May already have queued work remotely. Preserve uncertainty, never claim no effect.
        record["state"] = "REVIEW_REQUIRED"
        record["error"] = "BACKEND_OR_RESULT_UNCERTAIN"
        write_record(target, record)
        raise MediaError("REVIEW_REQUIRED", "inspect the existing job; do not resubmit automatically") from None


def inspect(directory):
    record = load_json(Path(directory) / "job.json", 2_000_000)
    if type(record) is not dict or record.get("schema") != "media-job/1":
        raise MediaError("INVALID_JOB")
    if record.get("state") == "INTENT":
        record["observed_state"] = "REVIEW_REQUIRED"
    record["automatic_retry"] = False
    return record
