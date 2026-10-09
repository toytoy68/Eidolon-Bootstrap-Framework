# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : conversation_export.py
# Description : Export explicite d'une conversation et inspection hors ligne, historique seulement (C-TASK-G093)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

"""An export is a HISTORICAL record, never a command.

There is deliberately no import: an export cannot reactivate a mission, bring back an agreement or
drive a server. It holds the turns, Core's replies, the frozen proposals and a SUMMARY of submissions
(status, mission, verified link) — no credential, no token, no submission body that could be resent.
inspect() checks it offline: digest chains and links are recomputed; consistency is not authenticity.
"""
import argparse
import json
import os
from pathlib import Path
import stat
import sys

from . import conversation as cv
from .contracts import ContractError, digest, encode
from .store import now

SCHEMA = "eidolon-conversation-export/1"
MAX_EXPORT_BYTES = 16 * 1024 * 1024
FIELDS = {"schema", "exported_at", "store_id", "conversation_id", "client_id", "turns", "proposals",
          "submissions", "historical", "authorizes_execution", "import_supported"}
SUBMISSION_FIELDS = {"command_key", "status", "proposal_id", "proposal_version", "proposal_sha256",
                     "reserved_at", "mission_id", "link"}


class ExportError(ContractError):
    pass


def export_conversation(conversations, *, client_id, conversation_id):
    """Build the export of ONE conversation owned by client_id (the operator names both)."""
    if conversations.owner(conversation_id) != client_id:
        raise ExportError("CONVERSATION_UNKNOWN: no such conversation for this client")
    turns, after = [], 0
    while True:
        page = conversations.page(conversation_id, after=after, limit=50)
        turns.extend({"turn": item["turn"], "received_at": item["received_at"], "reply": item["reply"]}
                     for item in page["items"])
        after = page["next_after"]
        if not page["has_more"]:
            break
    with conversations._db() as db:                       # same module family: read-only use
        proposals = [json.loads(r[0]) for r in db.execute(
            "SELECT body FROM proposals WHERE conversation_id=? ORDER BY version", (conversation_id,))]
        rows = db.execute("SELECT body, status, reserved_at, mission_id, link FROM submissions "
                          "WHERE conversation_id=? ORDER BY reserved_at, command_key", (conversation_id,)).fetchall()
    submissions = []
    for body, status, reserved_at, mission_id, link in rows:
        sub = json.loads(body)
        submissions.append({"command_key": sub["command_key"], "status": status, "proposal_id": sub["proposal_id"],
                            "proposal_version": sub["proposal_version"], "proposal_sha256": sub["proposal_sha256"],
                            "reserved_at": reserved_at, "mission_id": mission_id,
                            "link": json.loads(link) if link else None})
    export = {"schema": SCHEMA, "exported_at": now(), "store_id": conversations.store_id,
              "conversation_id": conversation_id, "client_id": client_id, "turns": turns, "proposals": proposals,
              "submissions": submissions, "historical": True, "authorizes_execution": False, "import_supported": False}
    if len(encode(export).encode("utf-8")) > MAX_EXPORT_BYTES:
        raise ExportError("EXPORT_TOO_LARGE: conversation exceeds the export bound")
    return export


def write_export(export, path):
    """New private file only: never overwrite, never through a link."""
    raw = (json.dumps(export, ensure_ascii=False, sort_keys=True, indent=1) + "\n").encode("utf-8")
    if len(raw) > MAX_EXPORT_BYTES:
        raise ExportError("EXPORT_TOO_LARGE: conversation exceeds the export bound")
    parent = os.lstat(Path(path).parent)
    if stat.S_ISLNK(parent.st_mode) or not stat.S_ISDIR(parent.st_mode):
        raise ExportError("EXPORT_PATH_REFUSED: the output folder must be a real directory")
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    except FileExistsError:
        raise ExportError("EXPORT_PATH_REFUSED: the output file already exists") from None
    with os.fdopen(fd, "wb") as handle:
        handle.write(raw)
    return {"path": str(path), "bytes": len(raw), "sha256": __import__("hashlib").sha256(raw).hexdigest()}


def inspect(value):
    """Offline consistency checks of an export. Never contacts a server; never authorizes anything."""
    problems = []

    def fail(code):
        if code not in problems:
            problems.append(code)

    if not isinstance(value, dict) or set(value) != FIELDS or value.get("schema") != SCHEMA:
        return _verdict(["SCHEMA"], value)
    if value["historical"] is not True or value["authorizes_execution"] is not False or value["import_supported"] is not False:
        fail("FLAGS")
    previous = None
    for index, item in enumerate(value["turns"] if isinstance(value["turns"], list) else []):
        if not isinstance(item, dict) or set(item) != {"turn", "received_at", "reply"}:
            fail("TURN_SHAPE")
            continue
        try:
            turn = cv.check_turn_order(previous, item["turn"])
        except ContractError:
            fail("TURN_CHAIN")
            previous = item["turn"] if isinstance(item["turn"], dict) else None
            continue
        if turn["conversation_id"] != value["conversation_id"] or turn["store_id"] != value["store_id"]:
            fail("TURN_FOREIGN")
        reply = item["reply"]
        if reply is not None and (not isinstance(reply, dict) or reply.get("turn_sha256") != digest(turn)
                                  or reply.get("in_reply_to") != turn["turn_id"]
                                  or reply.get("authorizes_execution") is not False):
            fail("REPLY_BINDING")
        if isinstance(reply, dict) and reply.get("proposal") is not None:
            try:
                if cv.proposal_sha256(reply["proposal"]) != reply.get("proposal_sha256"):
                    fail("REPLY_PROPOSAL_DIGEST")
            except ContractError:
                fail("REPLY_PROPOSAL_DIGEST")
        previous = turn
    digests, latest = {}, None
    for proposal in value["proposals"] if isinstance(value["proposals"], list) else []:
        try:
            sha = cv.proposal_sha256(proposal)
        except ContractError:
            fail("PROPOSAL_INVALID")
            continue
        expected = (latest["version"] + 1, cv.proposal_sha256(latest)) if latest else (1, None)
        if (proposal["version"], proposal["supersedes_sha256"]) != expected:
            fail("PROPOSAL_CHAIN")
        digests[(proposal["proposal_id"], proposal["version"])] = sha
        latest = proposal
    for sub in value["submissions"] if isinstance(value["submissions"], list) else []:
        if not isinstance(sub, dict) or set(sub) != SUBMISSION_FIELDS:
            fail("SUBMISSION_SHAPE")
            continue
        if digests.get((sub["proposal_id"], sub["proposal_version"])) != sub["proposal_sha256"]:
            fail("SUBMISSION_PROPOSAL")
        link = sub["link"]
        if link is not None and (not isinstance(link, dict) or link.get("proposal_sha256") != sub["proposal_sha256"]
                                 or link.get("mission_id") != sub["mission_id"]):
            fail("LINK")
    return _verdict(problems, value)


def _verdict(problems, value):
    ok = not problems
    turns = value.get("turns") if isinstance(value, dict) and isinstance(value.get("turns"), list) else []
    return {"protocol": "eidolon-conversation-export-inspection/1", "status": "CONSISTENT" if ok else "INCONSISTENT",
            "problems": problems, "turns": len(turns), "authenticity": "NOT_ESTABLISHED",
            "authorizes_execution": False, "import_supported": False,
            "meaning": ("Les empreintes et les liens concordent ; ce n'est pas une preuve d'authenticité."
                        if ok else "Export incohérent : ne pas s'y fier.")}


def read_export(path):
    info = os.lstat(path)
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode) or info.st_size > MAX_EXPORT_BYTES:
        raise ExportError("EXPORT_PATH_REFUSED: a regular file of bounded size is required")
    with open(path, "rb") as handle:
        raw = handle.read(MAX_EXPORT_BYTES + 1)

    def unique(pairs):
        result = {}
        for key, item in pairs:
            if key in result:
                raise ValueError("duplicate key")
            result[key] = item
        return result
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=unique)
    except (ValueError, UnicodeError, RecursionError):
        raise ExportError("EXPORT_INVALID_JSON") from None


def main(argv=None):
    from .conversation_store import ConversationStore
    from .store import Store
    parser = argparse.ArgumentParser(prog="python -m eidolon_core.conversation_export",
                                     description="Export historique d'une conversation et inspection hors ligne")
    sub = parser.add_subparsers(dest="command", required=True)
    out = sub.add_parser("export")
    out.add_argument("--state", required=True)
    out.add_argument("--client-id", required=True)
    out.add_argument("--conversation-id", required=True)
    out.add_argument("--output", required=True)
    check = sub.add_parser("inspect")
    check.add_argument("file")
    args = parser.parse_args(argv)
    try:
        if args.command == "export":
            if not (Path(args.state) / "missions.sqlite3").is_file():
                raise ExportError("STATE_MISSING: an existing state folder is required (nothing is created)")
            export = export_conversation(ConversationStore(Store(args.state)), client_id=args.client_id,
                                         conversation_id=args.conversation_id)
            print(json.dumps(write_export(export, args.output), ensure_ascii=False))
            return 0
        report = inspect(read_export(args.file))
        print(json.dumps(report, ensure_ascii=False, indent=1))
        return 0 if report["status"] == "CONSISTENT" else 2
    except (ContractError, OSError) as exc:
        print(json.dumps({"error": str(exc).split(":")[0]}))
        return 2


if __name__ == "__main__":
    sys.exit(main())
