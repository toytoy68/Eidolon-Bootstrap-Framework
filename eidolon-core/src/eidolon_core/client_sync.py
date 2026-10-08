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
MAX_MISSION_BYTES = 16 * 1024 * 1024
MAX_EVENT_BYTES = 16 * 1024 * 1024
CURSOR_FIELDS = {"version", "store_id", "mission_id", "sequence", "event_count", "anchor_sha256"}


class SyncError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def project_mission(mission):
    """Allowlist: no request, context, raw output, configuration or event details."""
    try:
        result = {"id": mission["id"], "revision": mission["revision"],
                  "status": mission["status"], "phase": mission["phase"],
                  "cancel_requested": mission["cancel_requested"],
                  "progress": {k: mission["progress"][k] for k in ("completed", "total")},
                  "objective_kind": mission["objective"]["kind"],
                  "outcome_status": mission["outcome"]["status"],
                  "action_view": action_view(mission)}
        if type(result["id"]) is not str or not re.fullmatch(r"m-[0-9a-f]{32}", result["id"]):
            raise SyncError("INVALID_MISSION_IDENTITY")
        if type(result["cancel_requested"]) is not bool:
            raise SyncError("INVALID_MISSION_PROJECTION")
        _integer(result["revision"])
        for key in ("status", "phase", "outcome_status"):
            _text(result[key], 40)
        if result["objective_kind"] is not None:
            _text(result["objective_kind"], 80)
        _integer(result["progress"]["completed"])
        if result["progress"]["total"] is not None:
            _integer(result["progress"]["total"])
        view = result["action_view"]
        if view is not None:
            if type(view["proposal_sha256"]) is not str or not re.fullmatch(r"[0-9a-f]{64}", view["proposal_sha256"]):
                raise SyncError("INVALID_MISSION_PROJECTION")
            _text(view["call_id"], 80)
            _integer(view["attempt"], 1)
            for key in ("decision", "applicability", "effect"):
                _text(view[key]["status" if key == "decision" else "code"], 64)
                _text(view[key]["message"], 500)
        return result
    except SyncError:
        raise
    except (ValueError, TypeError, KeyError, IndexError, RecursionError):
        raise SyncError("INVALID_MISSION_PROJECTION") from None


def _integer(value, minimum=0):
    if type(value) is not int or not minimum <= value <= MAX_SAFE_INTEGER:
        raise SyncError("UNSUPPORTED_INTEGER_RANGE")


def _text(value, maximum):
    if type(value) is not str or not 1 <= len(value) <= maximum:
        raise SyncError("INVALID_MISSION_PROJECTION")
    value.encode("utf-8")  # no escaped isolated surrogate may leave the reader


def decode_mission(identity, revision, cancel, body):
    """Bind a durable JSON body to its actual selected row, without coercion."""
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate field")
            result[key] = value
        return result

    def nonfinite(_):
        raise ValueError("nonfinite number")

    try:
        if type(body) is bytes:
            body = body.decode('utf-8')  # Never infer UTF-16/32 from a stored BLOB.
        mission = json.loads(body, object_pairs_hook=unique, parse_constant=nonfinite)
    except (ValueError, TypeError, RecursionError):
        raise SyncError("INVALID_MISSION_JSON") from None
    if type(mission) is not dict or mission.get("id") != identity:
        raise SyncError("INVALID_MISSION_IDENTITY")
    if type(cancel) is not int or cancel not in (0, 1):
        raise SyncError("INVALID_CANCEL_FLAG")
    _integer(revision)
    mission.update(revision=revision, cancel_requested=bool(cancel))
    return mission


def _stored_text(storage_type, raw, maximum, code):
    if storage_type != 'text' or type(raw) is not bytes:
        raise SyncError('INVALID_' + code + '_STORAGE_TYPE')
    if len(raw) > maximum:
        raise SyncError(code + '_SIZE_LIMIT')
    try:
        return raw.decode('utf-8')
    except UnicodeError:
        raise SyncError('INVALID_' + code + '_UTF8') from None


def read_mission_row(db, identity):
    row = db.execute('SELECT revision,cancel_requested,typeof(body),'
                     'substr(CAST(body AS BLOB),1,?) FROM missions WHERE id=?',
                     (MAX_MISSION_BYTES + 1, identity)).fetchone()
    if row is None:
        raise KeyError('mission not found')
    return row[0], row[1], _stored_text(row[2], row[3], MAX_MISSION_BYTES, 'MISSION')


def read_event_row(db, *, identity=None, sequence=None):
    conditions, parameters = [], [MAX_EVENT_BYTES + 1]
    if identity is not None:
        conditions.append('mission_id=?'); parameters.append(identity)
    if sequence is not None:
        conditions.append('sequence=?'); parameters.append(sequence)
    where = ' WHERE ' + ' AND '.join(conditions) if conditions else ''
    row = db.execute('SELECT sequence,substr(mission_id,1,35),substr(at,1,65),substr(kind,1,65),typeof(detail),'
                     'substr(CAST(detail AS BLOB),1,?) FROM events' + where +
                     ' ORDER BY sequence DESC LIMIT 1', parameters).fetchone()
    if row is None:
        return None
    _event_reference(row)
    if type(row[1]) is not str or re.fullmatch(r'm-[0-9a-f]{32}', row[1]) is None:
        raise SyncError('INVALID_EVENT_REFERENCE')
    return (*row[:4], _stored_text(row[4], row[5], MAX_EVENT_BYTES, 'EVENT'))


def _event_reference(row):
    _integer(row[0], 1)
    try:
        _text(row[2], 64)
        _text(row[3], 64)
    except (SyncError, UnicodeError):
        raise SyncError("INVALID_EVENT_REFERENCE") from None
    return {"sequence": row[0], "at": row[2], "kind": row[3]}


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
            meta = db.execute("SELECT substr(value,1,35) FROM sync_metadata WHERE key='store_id'").fetchone()
            if not meta or type(meta[0]) is not str or not re.fullmatch(r"s-[0-9a-f]{32}", meta[0]):
                raise SyncError("INVALID_STORE_ID")
            store_id = meta[0]
            row = read_mission_row(db, identity)
            mission = decode_mission(identity, *row)
            fields = "sequence,substr(mission_id,1,35),substr(at,1,65),substr(kind,1,65)"
            head = read_event_row(db, identity=identity)
            count = db.execute("SELECT count(*) FROM events WHERE mission_id=?", (identity,)).fetchone()[0]
            if head is None:
                raise SyncError("HISTORY_MISSING")
            _event_reference(head)
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
                anchor = read_event_row(db, identity=identity, sequence=cursor['sequence'])
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
                            events=[_event_reference(r) for r in page],
                            cursor=_cursor(store_id, identity, read_event_row(db, identity=identity, sequence=page[-1][0]), cursor["event_count"]+len(page))
                            if page else dict(cursor))
            return response
