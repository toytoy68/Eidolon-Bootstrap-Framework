# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : query_history.py
# Description : Historique local borné des requêtes nettoyées et de leurs tentatives
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Private local query history; shares the guard's transaction, never HTTP.

A completed run is not proof of delivery to a provider. Neither history nor its
cursor grants a retry. No eviction, migration on read, or retention duration.
"""
import argparse
import hashlib
import re
import sys
import unicodedata

from .contracts import ContractError, digest, encode
from .presentation import header, message
from .query_cleanup import CleanedQuery, MAX_QUERY_CHARS, PROTOCOL as CLEANUP_PROTOCOL

PROTOCOL = "eidolon-query-history/1"
MAX_PAGE = 50
CATEGORIES = {"LOCAL_PATH", "URL", "EMAIL", "IBAN_SHAPE", "PHONE_SHAPE", "NETWORK_ADDRESS"}


class QueryHistoryError(ContractError):
    pass


def validate_payload(value):
    """Strictly bounded, text + public cleanup metadata, never a raw-query hash."""
    try:
        if type(value) is not dict or set(value) != {"text", "cleanup"}:
            raise ValueError()
        text, receipt = value["text"], value["cleanup"]
        if (type(text) is not str or len(text) > MAX_QUERY_CHARS
                or text != " ".join(text.split())
                or any(unicodedata.category(c) in {"Cc", "Cf"} for c in text)
                or type(receipt) is not dict
                or set(receipt) != {"protocol", "cleaned_sha256", "removed", "normalized", "empty",
                                    "anonymity_guaranteed", "authorizes_transmission"}
                or receipt["protocol"] != CLEANUP_PROTOCOL
                or receipt["cleaned_sha256"] != hashlib.sha256(text.encode("utf-8")).hexdigest()
                or type(receipt["normalized"]) is not bool
                or receipt["empty"] is not (not bool(text))
                or receipt["anonymity_guaranteed"] is not False
                or receipt["authorizes_transmission"] is not False
                or type(receipt["removed"]) is not dict
                or not set(receipt["removed"]) <= CATEGORIES
                or any(type(v) is not int or not 1 <= v <= MAX_QUERY_CHARS for v in receipt["removed"].values())):
            raise ValueError()
        return value
    except (ValueError, TypeError, KeyError, UnicodeError, RecursionError):
        raise QueryHistoryError("INVALID_QUERY_HISTORY_RECORD") from None


def payload_for(cleaned):
    if not isinstance(cleaned, CleanedQuery):
        raise QueryHistoryError("CLEANED_QUERY_REQUIRED")
    return validate_payload({"text": cleaned.text, "cleanup": cleaned.receipt()})


def verify_rows(db, records, *, enabled):
    from .research_guard import _json
    expected = {r["id"]: r for r in records if "query_history_sha256" in r["descriptor"]}
    if not enabled:
        if expected:
            raise QueryHistoryError("QUERY_HISTORY_NOT_ENABLED")
        return {}
    # LIMIT also catches orphan rows without loading an unbounded table.
    rows = db.execute("SELECT run_id,substr(body,1,16001) FROM cleaned_queries LIMIT ?", (len(expected) + 1,)).fetchall()
    if len(rows) != len(expected):
        raise QueryHistoryError("QUERY_HISTORY_BINDING_MISMATCH")
    result = {}
    for identity, raw in rows:
        if identity not in expected or identity in result:
            raise QueryHistoryError("QUERY_HISTORY_BINDING_MISMATCH")
        payload = validate_payload(_json(raw))
        descriptor = expected[identity]["descriptor"]
        if (digest(payload) != descriptor["query_history_sha256"]
                or payload["cleanup"]["cleaned_sha256"] != descriptor["query_sha256"]):
            raise QueryHistoryError("QUERY_HISTORY_BINDING_MISMATCH")
        result[identity] = payload
    return result


def read_history(guard, *, limit=20, cursor=None):
    """One read snapshot with a revision-bound cursor; excludes pre-history runs."""
    if type(limit) is not int or not 1 <= limit <= MAX_PAGE:
        raise QueryHistoryError("INVALID_QUERY_HISTORY_LIMIT")
    if cursor is not None and (type(cursor) is not str or len(cursor) > 150
                              or not re.fullmatch(r"g-[0-9a-f]{32}:[0-9a-f]{64}:[0-9]{1,3}", cursor)):
        raise QueryHistoryError("INVALID_QUERY_HISTORY_CURSOR")
    if not guard.retain_queries:
        raise QueryHistoryError("QUERY_HISTORY_NOT_ENABLED")
    with guard._connection() as db:
        db.execute("PRAGMA query_only=ON")
        db.execute("BEGIN")
        records = guard._records(db)
        values = verify_rows(db, records, enabled=True)
    revision = digest(records)
    offset = 0
    if cursor is not None:
        identity, expected, offset = cursor.split(":")
        offset = int(offset)
        if identity != guard.guard_id or expected != revision:
            raise QueryHistoryError("QUERY_HISTORY_RESET_REQUIRED")
    eligible = sorted((r for r in records if r["id"] in values), key=lambda r: (r["started_at_ms"], r["id"]))
    if offset > len(eligible):
        raise QueryHistoryError("INVALID_QUERY_HISTORY_CURSOR")
    entries = []
    for r in eligible[offset:offset+limit]:
        payload = values[r["id"]]
        # No liveness guess and no claim that an INTENT actually reached a socket.
        emission = ("NOT_REQUESTED" if not payload["text"] else
                    "CALL_SEQUENCE_COMPLETED" if r["state"] == "COMPLETED" else "UNKNOWN")
        entries.append({"run_id": r["id"], **payload, "state": r["state"], "revision": r["revision"],
                        "started_at_ms": r["started_at_ms"], "ended_at_ms": r["ended_at_ms"],
                        "outcome": r["outcome"], "emission": emission, "delivery_confirmed": False,
                        "policy_id": r["descriptor"]["policy_id"], "providers": r["descriptor"]["providers"]})
    following = offset + len(entries)
    return {"protocol": PROTOCOL, "guard_id": guard.guard_id, "entries": entries,
            "next_cursor": f"{guard.guard_id}:{revision}:{following}" if following < len(eligible) else None,
            "total": len(eligible), "legacy_runs_without_text": len(records) - len(eligible),
            "authorizes_execution": False, "request_sent": False}


def main(argv=None):
    from .research_guard import GuardError, ResearchGuard
    parser = argparse.ArgumentParser(description="Relire localement les requêtes nettoyées, sans émission.")
    parser.add_argument("--directory", required=True)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--cursor")
    parser.add_argument("--format", choices=("json", "human"), default="json")
    args = parser.parse_args(argv)
    try:
        guard = ResearchGuard(args.directory, create=False)
        result = read_history(guard, limit=args.limit, cursor=args.cursor)
    except (GuardError, QueryHistoryError, OSError) as exc:
        code = str(exc) if isinstance(exc, (GuardError, QueryHistoryError)) else "QUERY_HISTORY_UNAVAILABLE"
        print(encode({"protocol": PROTOCOL, "error": code, "request_sent": False}), file=sys.stderr)
        return 2
    if args.format == "json":
        print(encode(result))
    else:
        print(header(title="Historique local des requêtes"))
        for entry in result["entries"]:
            print(message("INFO", f"{entry['run_id']} : {entry['state']} / {entry['emission']}"))
            print(message("INFO", entry["text"] or "Requête vide après nettoyage."))
        if result["next_cursor"]:
            print(message("INFO", "Page suivante : --cursor " + result["next_cursor"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
