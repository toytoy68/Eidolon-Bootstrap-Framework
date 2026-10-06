# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : client_sync.py
# Description : Capture cohérente et rattrapage paginé pour un futur client
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Local read-only protocol. No transport, authentication or execution authority.

Events are references, never patches to replay against a newer projection.
Each response reads mission + event head in ONE SQLite read transaction.
Cursor hashes detect stale anchors; they are neither signatures nor permissions.
"""
import json
import re

from .action_view import action_view
from .contracts import digest
from .store import now

PROTOCOL = "eidolon-client-sync/1"
MAX_SAFE_INTEGER = 2**53 - 1  # JSON numbers consumed by JavaScript without rounding
CURSOR_FIELDS = {"version", "store_id", "mission_id", "sequence", "event_count", "anchor_sha256"}


class SyncError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def project_mission(mission):
    """Allowlist: no request, context, raw output, configuration or event details."""
    return {"id": mission["id"], "revision": mission["revision"],
            "status": mission["status"], "phase": mission["phase"],
            "cancel_requested": mission["cancel_requested"],
            "progress": {k: mission["progress"][k] for k in ("completed", "total")},
            "objective_kind": mission["objective"]["kind"],
            "outcome_status": mission["outcome"]["status"],
            "action_view": action_view(mission)}


def _anchor(row):
    return digest(list(row))  # includes persisted detail, but exposes only its hash


def _cursor(store_id, identity, row, count):
    return {"version": 1, "store_id": store_id, "mission_id": identity,
            "sequence": row[0], "event_count": count, "anchor_sha256": _anchor(row)}


def _validate(cursor, identity):
    if (type(cursor) is not dict or set(cursor) != CURSOR_FIELDS
            or type(cursor["version"]) is not int or cursor["version"] != 1
            or type(cursor["store_id"]) is not str
            or not re.fullmatch(r"s-[0-9a-f]{32}", cursor["store_id"])
            or type(cursor["anchor_sha256"]) is not str
            or not re.fullmatch(r"[0-9a-f]{64}", cursor["anchor_sha256"])
            or any(type(cursor[k]) is not int or not 1 <= cursor[k] <= MAX_SAFE_INTEGER
                   for k in ("sequence", "event_count"))
            or cursor["event_count"] > cursor["sequence"]):
        raise SyncError("INVALID_CURSOR")
    if cursor["mission_id"] != identity:
        raise SyncError("CURSOR_MISSION_MISMATCH")


class ClientSync:
    """Read one explicitly selected mission; this object cannot run or decide."""
    def __init__(self, store):
        self.store = store

    def snapshot(self, identity):
        return self._read(identity, None, 50)

    def poll(self, identity, cursor, *, limit=50):
        _validate(cursor, identity)
        if type(limit) is not int or not 1 <= limit <= 100:
            raise SyncError("INVALID_PAGE_LIMIT")
        return self._read(identity, cursor, limit)

    def _read(self, identity, cursor, limit):
        self.store.check_id(identity)
        with self.store.connection() as db:
            db.execute("PRAGMA query_only=ON")
            db.execute("BEGIN")  # all SELECTs share a snapshot, including cancel_requested
            meta = db.execute("SELECT value FROM sync_metadata WHERE key='store_id'").fetchone()
            if not meta or not re.fullmatch(r"s-[0-9a-f]{32}", meta[0]):
                raise SyncError("INVALID_STORE_ID")
            store_id = meta[0]
            row = db.execute("SELECT revision,cancel_requested,body FROM missions WHERE id=?",
                             (identity,)).fetchone()
            if row is None:
                raise KeyError("mission not found")
            mission = json.loads(row[2])
            mission.update(revision=row[0], cancel_requested=bool(row[1]))
            fields = "sequence,mission_id,at,kind,detail"
            head = db.execute(f"SELECT {fields} FROM events WHERE mission_id=? ORDER BY sequence DESC LIMIT 1",
                              (identity,)).fetchone()
            count = db.execute("SELECT count(*) FROM events WHERE mission_id=?", (identity,)).fetchone()[0]
            if head is None:
                raise SyncError("HISTORY_MISSING")
            if (not 1 <= head[0] <= MAX_SAFE_INTEGER or not 1 <= count <= MAX_SAFE_INTEGER
                    or type(row[0]) is not int or not 0 <= row[0] <= MAX_SAFE_INTEGER):
                raise SyncError("UNSUPPORTED_INTEGER_RANGE")
            head_cursor = _cursor(store_id, identity, head, count)
            capture = {"observed_at": now(), "as_of_sequence": head[0], "event_count": count,
                       "mission": project_mission(mission)}
            response = {"protocol": PROTOCOL, "snapshot_only": True, "authorizes_execution": False,
                        "store_id": store_id, "mission_id": identity, "status": "SNAPSHOT",
                        "snapshot": capture, "events": [], "cursor": head_cursor, "has_more": False}
            if cursor is None:
                return response
            reason = None
            if cursor["store_id"] != store_id:
                reason = "STORE_CHANGED"
            elif cursor["sequence"] > head[0]:
                reason = "CURSOR_AHEAD"
            else:
                anchor = db.execute(f"SELECT {fields} FROM events WHERE mission_id=? AND sequence=?",
                                    (identity, cursor["sequence"])).fetchone()
                prior_count = db.execute("SELECT count(*) FROM events WHERE mission_id=? AND sequence<=?",
                                         (identity, cursor["sequence"])).fetchone()[0]
                if anchor is None or _anchor(anchor) != cursor["anchor_sha256"]:
                    reason = "ANCHOR_CHANGED"
                elif prior_count != cursor["event_count"]:
                    reason = "HISTORY_CHANGED"
            if reason:
                response.update(status="RESET_REQUIRED", reason=reason)
                return response  # replace the view explicitly; never silently reuse a stale cursor
            rows = db.execute(f"SELECT {fields} FROM events WHERE mission_id=? AND sequence>? "
                              "ORDER BY sequence LIMIT ?", (identity, cursor["sequence"], limit+1)).fetchall()
            page = rows[:limit]
            response.update(status="DELTA", has_more=len(rows) > limit,
                            events=[{"sequence": r[0], "at": r[2], "kind": r[3]} for r in page],
                            cursor=_cursor(store_id, identity, page[-1], cursor["event_count"]+len(page))
                            if page else dict(cursor))
            return response
