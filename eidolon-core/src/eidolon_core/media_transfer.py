# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : media_transfer.py
# Description : Transfert local ComfyUI, reçu strict et relecture de la source
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""One upload at most, then exact byte verification. Never submits a workflow.

No proxy, redirect or retry. Each HTTP exchange has a 90-second wall budget.
The engine is trusted to preserve the checked input until its workflow reads it.
"""
import hashlib
import urllib.parse
import uuid

from .media_agents import MediaError, parse_json

EXTENSIONS = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp",
              "video/mp4": ".mp4", "video/webm": ".webm"}


def raw_http(method, url, body, content_type, max_response, *, timeout=90):
    from .media_http import exchange
    if body is not None and len(body) > 200 * 1024 * 1024 + 4096:
        raise MediaError("MEDIA_TRANSFER_TOO_LARGE")
    headers = {"Accept": "*/*"}
    if content_type is not None:
        headers["Content-Type"] = content_type
    return exchange(method, url, body, headers, max_response, timeout=timeout, status_error="MEDIA_TRANSFER_STATUS")


def multipart(source, filename, media_type):
    boundary = "eidolon-" + uuid.uuid4().hex
    while boundary.encode() in source:
        boundary = "eidolon-" + uuid.uuid4().hex
    marker = boundary.encode("ascii")
    fields = [b"--" + marker + b'\r\nContent-Disposition: form-data; name="type"\r\n\r\ninput\r\n',
              b"--" + marker + b'\r\nContent-Disposition: form-data; name="overwrite"\r\n\r\nfalse\r\n',
              b"--" + marker + b'\r\nContent-Disposition: form-data; name="image"; filename="' + filename.encode("ascii")
              + b'"\r\nContent-Type: ' + media_type.encode("ascii") + b"\r\n\r\n",
              source, b"\r\n--" + marker + b"--\r\n"]
    return b"".join(fields), "multipart/form-data; boundary=" + boundary


def ensure_source(source, evidence, plan, *, transport=None, progress=None):
    from .media_backends import endpoint
    transport = transport or raw_http
    progress = progress or (lambda stage, info: None)
    base = endpoint(plan["endpoint"])
    filename = plan["source_name"]
    # Names come from validated plans, but retain a boundary here for direct callers.
    import re
    if not isinstance(filename, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,180}", filename) or ".." in filename:
        raise MediaError("INVALID_SOURCE_NAME")
    if (type(source) is not bytes or not source or len(source) > 200 * 1024 * 1024
            or hashlib.sha256(source).hexdigest() != evidence["sha256"] or len(source) != evidence["size"]
            or evidence["type"] not in EXTENSIONS):
        raise MediaError("SOURCE_EVIDENCE_MISMATCH")
    if plan["source_transfer"] not in {"upload-verified", "verify-staged"}:
        raise MediaError("INVALID_SOURCE_TRANSFER")
    if plan["source_transfer"] == "upload-verified":
        progress("SOURCE_UPLOAD_STARTED", {"name": filename, "sha256": evidence["sha256"]})
        body, kind = multipart(source, filename, evidence["type"])
        content_type, response = transport("POST", base + "/upload/image", body, kind, 64_000)
        if content_type != "application/json":
            raise MediaError("INVALID_UPLOAD_RECEIPT")
        receipt = parse_json(response)
        if (type(receipt) is not dict or receipt.get("name") != filename
                or receipt.get("subfolder") != "" or receipt.get("type") != "input"):
            raise MediaError("INVALID_UPLOAD_RECEIPT")
        progress("SOURCE_UPLOAD_ACKNOWLEDGED", {"name": filename, "type": "input"})
    progress("SOURCE_VERIFYING", {"name": filename})
    query = urllib.parse.urlencode({"filename": filename, "type": "input", "subfolder": ""})
    content_type, remote = transport("GET", base + "/view?" + query, None, None, evidence["size"])
    if (content_type not in {evidence["type"], "application/octet-stream"}
            or len(remote) != evidence["size"] or hashlib.sha256(remote).hexdigest() != evidence["sha256"]):
        raise MediaError("STAGED_SOURCE_MISMATCH")
    progress("SOURCE_VERIFIED", {"name": filename, "sha256": evidence["sha256"], "size": evidence["size"]})
