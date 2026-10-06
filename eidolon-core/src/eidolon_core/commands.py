# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : commands.py
# Description : Décisions locales et reçus atomiques consultables après coupure
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

"""Trusted local decisions only. A receipt proves recording, never execution."""
import re
import sqlite3
import json

from .contracts import ContractError, digest, snapshot
from .store import Store

PROTOCOL = "eidolon-decision-command/1"
MAX_SAFE_INTEGER = 2**53 - 1
FIELDS = {"protocol", "store_id", "client_id", "command_key", "mission_id",
          "expected_revision", "proposal_sha256", "decision", "actor", "reason"}
CANCEL_PROTOCOL = "eidolon-cancel-command/1"
CANCEL_FIELDS = {"protocol", "store_id", "client_id", "command_key", "mission_id", "actor", "reason"}


def _parse_command(raw, validator):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ContractError("INVALID_COMMAND: duplicate JSON key")
            result[key] = value
        return result

    try:
        if not isinstance(raw, (str, bytes)):
            raise ContractError("INVALID_COMMAND: JSON text or bytes required")
        if len(raw if isinstance(raw, bytes) else raw.encode("utf-8")) > 32768:
            raise ContractError("INVALID_COMMAND: command exceeds 32768 bytes")
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        return validator(json.loads(raw, object_pairs_hook=unique))
    except ContractError:
        raise  # Preserve bounded contract diagnostics, including duplicate keys.
    except (ValueError, RecursionError) as exc:
        raise ContractError("INVALID_COMMAND: invalid bounded UTF-8 JSON command") from exc


def parse_command(raw):
    return _parse_command(raw, validate_command)


def parse_cancel_command(raw):
    return _parse_command(raw, validate_cancel_command)


def _identifier(value, pattern, name):
    if not isinstance(value, str) or re.fullmatch(pattern, value) is None:
        raise ContractError("INVALID_COMMAND: invalid " + name)


def validate_scope(store_id, client_id, command_key):
    _identifier(store_id, r"s-[0-9a-f]{32}", "store_id")
    for name, value in (("client_id", client_id), ("command_key", command_key)):
        _identifier(value, r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}", name)


def validate_command(value):
    value = snapshot(value)
    if not isinstance(value, dict) or set(value) != FIELDS or value["protocol"] != PROTOCOL:
        raise ContractError("INVALID_COMMAND: exact versioned decision fields required")
    validate_scope(value["store_id"], value["client_id"], value["command_key"])
    Store.check_id(value["mission_id"])
    if type(value["expected_revision"]) is not int or not 0 <= value["expected_revision"] < MAX_SAFE_INTEGER:
        raise ContractError("INVALID_COMMAND: revision must be a safe nonnegative integer")
    _identifier(value["proposal_sha256"], r"[0-9a-f]{64}", "proposal_sha256")
    if value["decision"] not in ("approve", "reject", "revoke"):
        raise ContractError("INVALID_COMMAND: unsupported decision")
    for name, bound in (("actor", 200), ("reason", 4000)):
        text = value[name]
        if not isinstance(text, str) or not text.strip() or len(text) > bound:
            raise ContractError("INVALID_COMMAND: bounded explicit " + name + " required")
    return value


def validate_cancel_command(value):
    value = snapshot(value)
    if not isinstance(value, dict) or set(value) != CANCEL_FIELDS or value["protocol"] != CANCEL_PROTOCOL:
        raise ContractError("INVALID_COMMAND: exact versioned cancellation fields required")
    validate_scope(value["store_id"], value["client_id"], value["command_key"])
    Store.check_id(value["mission_id"])
    for name, bound in (("actor", 200), ("reason", 4000)):
        text = value[name]
        if not isinstance(text, str) or not text.strip() or len(text) > bound:
            raise ContractError("INVALID_COMMAND: bounded explicit " + name + " required")
    return value


class CancelCommands:
    """Record a stop request without acquiring the runtime's mission lock."""
    def __init__(self, store):
        self.store = store

    def submit(self, value):
        return self.store.record_cancellation(validate_cancel_command(value))


def lookup_receipt(store, *, store_id, client_id, command_key):
    validate_scope(store_id, client_id, command_key)
    receipt = store.command_receipt(client_id, command_key, store_id=store_id)
    return {"protocol": "eidolon-command-lookup/1", "store_id": store_id,
            "client_id": client_id, "command_key": command_key,
            "status": "FOUND" if receipt else "NOT_FOUND", "receipt": receipt,
            "execution_evidence": False, "authorizes_resend": False}


class DecisionCommands:
    def __init__(self, runtime):
        self.runtime = runtime
        self.store = runtime.store

    def _existing(self, command):
        receipt = self.store.command_receipt(command["client_id"], command["command_key"],
                                             store_id=command["store_id"])
        if receipt is not None and receipt["request_sha256"] != digest(command):
            raise ContractError("COMMAND_KEY_REUSED: key already bound to another request")
        return receipt

    def submit(self, value):
        command = validate_command(value)
        # A historical receipt remains readable while the mission is running.
        existing = self._existing(command)
        if existing is not None:
            return existing
        with self.store.lock(command["mission_id"]):
            existing = self._existing(command)
            if existing is not None:
                return existing
            mission = self.store.get(command["mission_id"])
            if mission["revision"] != command["expected_revision"]:
                raise ContractError("STALE_REVISION: refresh and review the proposal")
            entry = self.runtime._prepare_decision(
                mission, expected_sha256=command["proposal_sha256"],
                decision=command["decision"], actor=command["actor"], reason=command["reason"])
            try:
                receipt = self.store.save(mission, "ACTION_DECISION", entry, command=command)
            except sqlite3.IntegrityError:
                # Same client/key submitted concurrently for distinct missions:
                # SQLite rolls back the losing decision AND its journal event.
                existing = self._existing(command)
                if existing is None:
                    raise
                return existing
            self.runtime.checkpoint("COMMAND_RECORDED")  # Test-only crash AFTER commit.
            return receipt
