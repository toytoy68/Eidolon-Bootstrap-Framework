# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : runtime_inspect.py
# Description : Diagnostic local de reprise, captures bornées sans exécution
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Observe existing state and artifacts; never authorize a retry or repair state.

SQLite is one snapshot. Filesystem locks are later, independent samples. A free
lease is neither proof of a dead process nor of absence of an external effect.
"""
import fcntl
import json
import os
import sqlite3
import stat

from .client_sync import decode_mission
from .contracts import ContractError, MAX_JSON_BYTES, digest
from .http_api import ReadOnlyStore
from .presentation import header, message
from .store import TERMINAL, now
from .worker import attempt_receipt_path

PROTOCOL = "eidolon-runtime-inspect/1"
MAX_MISSION_BYTES = 16 * 1024 * 1024
STATUSES = TERMINAL | {"NEW", "RUNNING", "BLOCKED", "REVIEW_REQUIRED"}
PHASES = {"RECALL", "PLAN", "READY", "EXECUTING", "VERIFY", "DONE"}
CALL_STATES = {"PREPARED", "STARTED", "RETURNED", "VERIFIED", "UNKNOWN"}


class InspectionError(ContractError):
    pass


def _json(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError()
            result[key] = value
        return result
    def nonfinite(_):
        raise ValueError()
    return json.loads(raw, object_pairs_hook=unique, parse_constant=nonfinite)


def _budget(db, identity, mission):
    """Audit just bounded reservation events, not the entire mission history."""
    config = mission.get("configuration")
    if type(config) is not dict:
        raise InspectionError("INVALID_INSPECTION_RECORD")
    value = mission.get("invocation_budget")
    if "max_invocations" not in config and value is None:
        return {"state": "LEGACY_UNBOUNDED", "audit_checked": False}
    if (type(value) is not dict or set(value) != {"limit", "used"}
            or type(value["limit"]) is not int or not 1 <= value["limit"] <= 4096
            or type(config.get("max_invocations")) is not int
            or value["limit"] != config["max_invocations"]
            or type(value["used"]) is not int or not 0 <= value["used"] <= value["limit"]):
        return {"state": "INVALID", "audit_checked": False}
    rows = db.execute("SELECT substr(CAST(detail AS BLOB),1,16385) FROM events "
                      "WHERE mission_id=? AND kind='INVOCATION_RESERVED' ORDER BY sequence LIMIT 4097",
                      (identity,)).fetchall()
    valid = len(rows) == value["used"]
    for ordinal, (raw,) in enumerate(rows, 1):
        try:
            if len(raw) > 16384:
                return {"state": "UNAVAILABLE", "audit_checked": False,
                        "reason": "RESERVATION_SIZE_LIMIT"}
            event = _json(raw)
            if (type(event) is not dict or type(event.get("ordinal")) is not int
                    or event["ordinal"] != ordinal or type(event.get("limit")) is not int
                    or event["limit"] != value["limit"]):
                valid = False
        except (ValueError, TypeError, RecursionError):
            valid = False
    return {"state": ("EXHAUSTED" if value["used"] == value["limit"] else "AVAILABLE") if valid else "INVALID",
            **value, "remaining": value["limit"] - value["used"] if valid else None, "audit_checked": True}


def _artifact(path, *, lease=False, marker=False):
    """No creation, PID lookup, receipt adoption or provider-controlled text."""
    fd = None
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid():
            return {"state": "UNTRUSTED_ARTIFACT"}
        if not lease:
            return {"state": "PRESENT_UNVERIFIED" if info.st_size <= MAX_JSON_BYTES else "OVERSIZED"}
        try:
            fcntl.flock(fd, fcntl.LOCK_SH | fcntl.LOCK_NB)
        except BlockingIOError:
            return {"state": "HELD_AT_SAMPLE", "authorization": "UNKNOWN"}
        result = {"state": "FREE_AT_SAMPLE", "authorization": "UNKNOWN"}
        if marker:
            raw = os.read(fd, 129)
            result["authorization"] = ("MARKED" if raw == b"authorized\n" else
                                       "NOT_MARKED" if raw == b"" else "INVALID_MARKER")
        current = path.lstat()
        if (current.st_dev, current.st_ino) != (info.st_dev, info.st_ino):
            return {"state": "CHANGED_DURING_SAMPLE", "authorization": "UNKNOWN"}
        return result
    except FileNotFoundError:
        return {"state": "MISSING", "authorization": "UNKNOWN"} if lease else {"state": "MISSING"}
    except OSError:
        return {"state": "UNAVAILABLE", "authorization": "UNKNOWN"} if lease else {"state": "UNAVAILABLE"}
    finally:
        if fd is not None:
            os.close(fd)


def _inspect(directory, identity):
    ReadOnlyStore.check_id(identity)
    store = ReadOnlyStore(directory)
    with store.connection() as db:
        db.execute("BEGIN")
        store_id = db.execute("SELECT value FROM sync_metadata WHERE key='store_id'").fetchone()[0]
        row = db.execute("SELECT revision,cancel_requested,substr(CAST(body AS BLOB),1,?) "
                         "FROM missions WHERE id=?", (MAX_MISSION_BYTES + 1, identity)).fetchone()
        if row is None:
            raise InspectionError("INSPECTION_MISSION_NOT_FOUND")
        if len(row[2]) > MAX_MISSION_BYTES:
            raise InspectionError("INSPECTION_SIZE_LIMIT")
        mission = decode_mission(identity, row[0], row[1], row[2])
        if (mission.get("status") not in STATUSES or mission.get("phase") not in PHASES
                or type(mission.get("calls")) is not list or len(mission["calls"]) > 5):
            raise InspectionError("INVALID_INSPECTION_RECORD")
        calls = []
        for index, call in enumerate(mission["calls"]):
            if (type(call) is not dict or type(call.get("id")) is not str
                    or not 1 <= len(call["id"]) <= 120
                    or type(call.get("attempt")) is not int or not 1 <= call["attempt"] <= 2**53-1
                    or call.get("status") not in CALL_STATES):
                raise InspectionError("INVALID_INSPECTION_RECORD")
            lease = store.directory / f"{identity}-{digest([call['id'], call['attempt']])}.worker.lock"
            calls.append((call, {"index": index, "attempt": call["attempt"], "status": call["status"]}, lease))
        budget = _budget(db, identity, mission)
        head = db.execute("SELECT max(sequence) FROM events WHERE mission_id=?", (identity,)).fetchone()[0]
        if type(head) is not int or not 1 <= head <= 2**53-1:
            raise InspectionError("INVALID_INSPECTION_RECORD")
        anchor = digest([row[0], row[1], row[2].decode("utf-8"), head])
    execution = _artifact(store.directory / f"{identity}.lock", lease=True)
    sampled = []
    for call, projection, lease in calls:
        known = call.get("worker_protocol") in {"lease-v1", "lease-v2"}
        projection["lease"] = (_artifact(lease, lease=True, marker=call.get("worker_protocol") == "lease-v2")
                               if known else {"state": "LEGACY_OR_NOT_STARTED", "authorization": "UNKNOWN"})
        projection["receipt"] = _artifact(attempt_receipt_path(lease))
        sampled.append(projection)
    # Sampling is not atomic with SQLite. Detect intervening changes without
    # presenting the second snapshot as permission to execute after this return.
    with store.connection() as db:
        db.execute("BEGIN")
        current_id = db.execute("SELECT value FROM sync_metadata WHERE key='store_id'").fetchone()[0]
        latest = db.execute("SELECT revision,cancel_requested,substr(CAST(body AS BLOB),1,?) "
                            "FROM missions WHERE id=?", (MAX_MISSION_BYTES + 1, identity)).fetchone()
        current_head = db.execute("SELECT max(sequence) FROM events WHERE mission_id=?", (identity,)).fetchone()[0]
        changed = (current_id != store_id or latest is None or latest != row or current_head != head)
    hints = []
    if changed:
        hints.append("SNAPSHOT_CHANGED_RESAMPLE")
    if execution["state"] == "HELD_AT_SAMPLE" or any(c["lease"]["state"] == "HELD_AT_SAMPLE" for c in sampled):
        hints.append("LOCAL_LOCK_HELD")
    if mission["status"] in TERMINAL:
        hints.append("TERMINAL_STATE_RETAIN_EVIDENCE")
    elif mission["status"] == "REVIEW_REQUIRED" or mission["phase"] == "EXECUTING":
        hints.append("EFFECT_UNKNOWN_REVIEW_REQUIRED")
    elif mission["phase"] == "VERIFY" and sampled and sampled[-1]["status"] == "RETURNED":
        hints.append("RETURNED_RESULT_AWAITS_VERIFICATION")
    elif mission["status"] == "BLOCKED":
        hints.append("BLOCKED_REVIEW_MISSION")
    else:
        hints.append("NO_AUTOMATIC_RESUME")
    if budget["state"] in {"INVALID", "EXHAUSTED", "UNAVAILABLE"}:
        hints.append("INVOCATION_BUDGET_" + budget["state"])
    if mission["cancel_requested"]:
        hints.append("CANCELLATION_REQUESTED_NOT_PROOF_OF_STOP")
    return {"protocol": PROTOCOL, "observed_at": now(), "store_id": store_id,
            "mission_id": identity, "revision": row[0], "as_of_sequence": head, "snapshot_sha256": anchor,
            "status": mission["status"], "phase": mission["phase"], "cancel_requested": mission["cancel_requested"],
            "changed_during_sampling": changed, "execution_lock": execution, "calls": sampled,
            "invocation_budget": budget, "hints": hints,
            "filesystem_samples_atomic": False, "receipt_content_verified": False,
            "external_effects_known": False, "authorizes_execution": False,
            "research_guard_checked": False, "snapshot_only": True}


def inspect_runtime(directory, identity):
    try:
        return _inspect(directory, identity)
    except InspectionError:
        raise
    except ContractError as exc:
        known = {"RECOVERY_REVIEW_ONLY", "BETA_PREPARATION_INCOMPLETE", "UNSUPPORTED_READ_SCHEMA", "INVALID_STORE_ID"}
        raise InspectionError(str(exc) if str(exc) in known else "INVALID_INSPECTION_RECORD") from None
    except sqlite3.Error:
        raise InspectionError("INSPECTION_STORAGE_UNAVAILABLE") from None
    except (ValueError, TypeError, KeyError, IndexError, UnicodeError, RecursionError):
        raise InspectionError("INVALID_INSPECTION_RECORD") from None
    except OSError:
        raise InspectionError("INSPECTION_STATE_UNAVAILABLE") from None


def render_inspection(report):
    explanations = {
        "SNAPSHOT_CHANGED_RESAMPLE": "La mission a changé pendant le diagnostic ; consulter une nouvelle capture.",
        "LOCAL_LOCK_HELD": "Un verrou local est détenu ; aucune reprise ne peut être déduite de cette capture.",
        "TERMINAL_STATE_RETAIN_EVIDENCE": "Mission terminée ; conserver les preuves et les éventuels effets inconnus.",
        "EFFECT_UNKNOWN_REVIEW_REQUIRED": "Un appel interrompu exige une revue de ses effets avant toute décision de reprise.",
        "RETURNED_RESULT_AWAITS_VERIFICATION": "Un résultat reçu attend sa vérification ; sa présence ne justifie pas de relancer l’outil.",
        "BLOCKED_REVIEW_MISSION": "Mission bloquée ; examiner sa demande et son erreur locales avant une reprise explicite.",
        "NO_AUTOMATIC_RESUME": "Aucune reprise automatique n’est proposée.",
        "INVOCATION_BUDGET_INVALID": "Le compteur et son audit ne concordent pas ; le budget restant n’est pas fiable.",
        "INVOCATION_BUDGET_UNAVAILABLE": "L’audit dépasse les bornes de ce diagnostic ; aucun budget restant fiable n’est affiché.",
        "INVOCATION_BUDGET_EXHAUSTED": "Le budget de la mission est épuisé ; le diagnostic ne le remet pas à zéro.",
        "CANCELLATION_REQUESTED_NOT_PROOF_OF_STOP": "Annulation demandée ; cela ne prouve ni l’arrêt ni l’absence d’effet.",
    }
    lines = [header(title="Diagnostic local de reprise"),
             message("INFO", f"{report['mission_id']} : {report['status']} / {report['phase']}"),
             message("INFO", "Verrou de mission : " + report["execution_lock"]["state"]),
             message("INFO", "Budget : " + report["invocation_budget"]["state"])]
    for call in report["calls"]:
        lines.append(message("INFO", f"Étape {call['index'] + 1}, tentative {call['attempt']} : {call['status']} ; "
                             f"verrou {call['lease']['state']}, reçu {call['receipt']['state']}"))
    lines.extend(message("ATTENTION", explanations[hint]) for hint in report["hints"])
    lines.append(message("INFO", "Capture locale seulement. Aucun appel relancé, effet confirmé ou droit de reprise accordé."))
    return "\n".join(lines)
