# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : receipt_lookup.py
# Description : Lecture bornée de reçus historiques liés à une mission
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Read existing command receipts without granting write or retry authority.

Unlike the trusted local CLI lookup, this boundary validates the persisted
envelope before exporting it. SQLite is the trusted source, not a signed ledger.
"""
from datetime import datetime
import json
import re

from .contracts import ContractError, digest

PROTOCOL = "eidolon-http-receipt/1"
QUERY_FIELDS = {"store_id", "client_id", "command_key", "mission_id"}
COMMON = QUERY_FIELDS | {"protocol", "status", "request_sha256", "mission_revision",
                         "event_sequence", "recorded_at", "execution_evidence"}
DECISION = COMMON | {"decision", "proposal_sha256", "approval_status_at_recording"}
CANCEL = COMMON | {"cancel_outcome", "mission_status_at_recording",
                   "cancel_requested_at_recording", "effect_absence_evidence"}
MAX_RECEIPT_BYTES = 32768
MAX_SAFE_INTEGER = 2**53 - 1
STATUSES = {"NEW", "RUNNING", "BLOCKED", "REVIEW_REQUIRED", "SUCCEEDED", "FAILED",
            "CANCELLED", "ABANDONED"}
TERMINAL = {"SUCCEEDED", "FAILED", "CANCELLED", "ABANDONED"}


class ReceiptLookupError(ValueError):
    def __init__(self, status, code):
        self.status, self.code = status, code
        super().__init__(code)


def _match(pattern, value):
    return type(value) is str and re.fullmatch(pattern, value) is not None


def _scope(value):
    return (type(value) is dict and QUERY_FIELDS <= set(value)
            and _match(r"s-[0-9a-f]{32}", value["store_id"])
            and _match(r"m-[0-9a-f]{32}", value["mission_id"])
            and all(_match(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}", value[k])
                    for k in ("client_id", "command_key")))


def _fail():
    raise ReceiptLookupError(503, "RECEIPT_UNAVAILABLE")


def _object(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate key")
            result[key] = value
        return result

    def nonfinite(_):
        raise ValueError("nonfinite")

    if type(raw) is not bytes or len(raw) > MAX_RECEIPT_BYTES:
        _fail()
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=unique, parse_constant=nonfinite)
    except (ValueError, UnicodeError, RecursionError):
        _fail()
    if type(value) is not dict:
        _fail()
    return value


def _decode(raw):
    value = _object(raw)
    if not _scope(value):
        _fail()
    protocol = value.get("protocol")
    if protocol == "eidolon-command-receipt/1":
        fields = DECISION
    elif protocol == "eidolon-cancel-receipt/1":
        fields = CANCEL
    else:
        _fail()
    if set(value) != fields or value["status"] != "RECORDED" or value["execution_evidence"] is not False:
        _fail()
    if (not _match(r"[0-9a-f]{64}", value["request_sha256"])
            or type(value["mission_revision"]) is not int
            or not 0 <= value["mission_revision"] <= MAX_SAFE_INTEGER
            or type(value["event_sequence"]) is not int
            or not 1 <= value["event_sequence"] <= MAX_SAFE_INTEGER):
        _fail()
    at = value["recorded_at"]
    if type(at) is not str or len(at) > 64 or not at.isascii() or not at.isprintable():
        _fail()
    try:
        if datetime.fromisoformat(at).utcoffset() is None:
            _fail()
    except ValueError:
        _fail()
    if fields == DECISION:
        states = {"approve": "APPROVED", "reject": "REJECTED", "revoke": "REVOKED"}
        decision = value["decision"]
        if (type(decision) is not str or decision not in states
                or value["approval_status_at_recording"] != states[decision]
                or not _match(r"[0-9a-f]{64}", value["proposal_sha256"])
                or value["mission_revision"] < 1):
            _fail()
    else:
        state, outcome = value["mission_status_at_recording"], value["cancel_outcome"]
        if (type(state) is not str or state not in STATUSES
                or type(outcome) is not str
                or outcome not in {"REQUESTED", "ALREADY_REQUESTED", "ALREADY_TERMINAL"}
                or type(value["cancel_requested_at_recording"]) is not bool
                or value["effect_absence_evidence"] is not False):
            _fail()
        if ((outcome == "ALREADY_TERMINAL") != (state in TERMINAL)
                or outcome != "ALREADY_TERMINAL" and not value["cancel_requested_at_recording"]):
            _fail()
    return value


def _bind_event(receipt, raw, *, require_hash=False):
    """Rebuild only the recorded command, never export the event's private detail."""
    detail = _object(raw)
    binding = "LEGACY_FIELDS"
    if require_hash and "receipt_sha256" not in detail:
        _fail()
    if "receipt_sha256" in detail:
        if not _match(r"[0-9a-f]{64}", detail["receipt_sha256"]) or detail["receipt_sha256"] != digest(receipt):
            _fail()
        binding = "EVENT_HASH"
    for name, bound in (("actor", 200), ("reason", 4000)):
        value = detail.get(name)
        if type(value) is not str or not value.strip() or len(value) > bound:
            _fail()
    command = {k: receipt[k] for k in QUERY_FIELDS}
    command.update(actor=detail["actor"], reason=detail["reason"])
    if receipt["protocol"] == "eidolon-command-receipt/1":
        if any(detail.get(k) != receipt[k] for k in ("decision", "proposal_sha256")):
            _fail()
        command.update(protocol="eidolon-decision-command/1", decision=receipt["decision"],
                       proposal_sha256=receipt["proposal_sha256"],
                       expected_revision=receipt["mission_revision"] - 1)
    else:
        if any(detail.get(k) != receipt[k] for k in ("client_id", "command_key", "cancel_outcome")):
            _fail()
        command.update(protocol="eidolon-cancel-command/1")
    try:
        if digest(command) != receipt["request_sha256"]:
            _fail()
    except (ContractError, UnicodeError, RecursionError):
        _fail()
    return binding


def lookup(store, query):
    """Exact key, Store and expected mission; never submit/cancel/run anything."""
    if not _scope(query) or set(query) != QUERY_FIELDS:
        raise ReceiptLookupError(400, "INVALID_RECEIPT_QUERY")
    query = dict(query)
    result = {"protocol": PROTOCOL, **query, "status": "NOT_FOUND", "receipt": None,
              "execution_evidence": False, "effect_absence_evidence": False,
              "authorizes_resend": False, "authorizes_execution": False}
    with store.connection() as db:
        db.execute("PRAGMA query_only=ON")
        db.execute("BEGIN")
        row = db.execute("SELECT value FROM sync_metadata WHERE key='store_id'").fetchone()
        if row is None:
            _fail()
        if row[0] != query["store_id"]:
            raise ReceiptLookupError(409, "STORE_CHANGED")
        # Slice bytes inside SQLite, before loading an arbitrarily large row.
        row = db.execute("SELECT substr(CAST(body AS BLOB),1,?) FROM command_receipts "
                         "WHERE client_id=? AND command_key=?",
                         (MAX_RECEIPT_BYTES + 1, query["client_id"], query["command_key"])).fetchone()
        if row is None:
            return result
        receipt = _decode(row[0])
        if any(receipt[k] != query[k] for k in ("store_id", "client_id", "command_key")):
            _fail()
        if receipt["mission_id"] != query["mission_id"]:
            raise ReceiptLookupError(409, "RECEIPT_MISSION_MISMATCH")
        if db.execute("SELECT 1 FROM missions WHERE id=?", (query["mission_id"],)).fetchone() is None:
            _fail()
        event = db.execute("SELECT mission_id,at,kind,substr(CAST(detail AS BLOB),1,?) "
                           "FROM events WHERE sequence=?",
                           (MAX_RECEIPT_BYTES + 1, receipt["event_sequence"])).fetchone()
        kind = ("ACTION_DECISION" if receipt["protocol"] == "eidolon-command-receipt/1" else
                "CANCEL_REQUESTED" if receipt["cancel_outcome"] == "REQUESTED" else "CANCEL_COMMAND_RECORDED")
        if event is None or event[:3] != (query["mission_id"], receipt["recorded_at"], kind):
            _fail()
        boundary = db.execute("SELECT substr(CAST(value AS BLOB),1,32) FROM sync_metadata "
                              "WHERE key='receipt_hash_required_from'").fetchone()
        required = False
        if boundary is not None:
            try:
                start = boundary[0].decode('ascii')
                if not _match(r'[1-9][0-9]{0,15}', start) or int(start) > MAX_SAFE_INTEGER:
                    _fail()
                if int(start) > db.execute('SELECT max(sequence) FROM events').fetchone()[0]:
                    _fail()
                required = receipt['event_sequence'] >= int(start)
                if not required and "receipt_sha256" in _object(event[3]):
                    _fail()
            except (ValueError, TypeError, UnicodeError, AttributeError):
                _fail()
        binding = _bind_event(receipt, event[3], require_hash=required)
        result.update(status="FOUND", receipt=receipt, receipt_binding=binding)
    return result
