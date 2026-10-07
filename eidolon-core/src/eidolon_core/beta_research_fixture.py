# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : beta_research_fixture.py
# Description : Missions et copies d'archives synthétiques pour la recette PC
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Optional beta_fixture profile, only inside a newly owned private destination.

These exports are COPIES, not committed retention. No active row is removed.
They deliberately exercise the reader's unknown-commit semantics.
"""
import os

from .client_sync import ClientSync
from .contracts import digest, encode
from .research_archive import EXPORT_PROTOCOL, read_catalog, validate_export, write_index
from .research_guard import ResearchGuard
from .research_runtime import ResearchRuntime
from .store import Store


def _copy_exports(guard, directory):
    directory.mkdir(mode=0o700)
    directory.chmod(0o700)
    previous = "0" * 64
    with guard._exclusive(), guard._connection() as db:
        db.execute("PRAGMA query_only=ON")
        db.execute("BEGIN")
        records = sorted(guard._records(db), key=lambda r: (r["started_at_ms"], r["id"]))
        if len(records) != 3 or any(r["state"] != "COMPLETED" for r in records):
            raise ValueError("fixture research evidence mismatch")
        for index, record in enumerate(records, 1):
            identity = record["id"]
            body = db.execute("SELECT body FROM runs WHERE id=?", (identity,)).fetchone()[0]
            events = [list(row) for row in db.execute(
                "SELECT sequence,kind,body FROM run_events WHERE run_id=? ORDER BY sequence", (identity,))]
            query = db.execute("SELECT body FROM cleaned_queries WHERE run_id=?", (identity,)).fetchone()[0]
            meta = {"protocol": EXPORT_PROTOCOL, "guard_id": guard.guard_id,
                    "chain_index": index, "previous_chain_sha256": previous,
                    "created_at_ms": record["ended_at_ms"], "authorizes_execution": False,
                    "removed_ids_sha256": digest([identity]),
                    "runs": [{"id": identity, "body": body, "events": events, "cleaned_query": query}]}
            name = f"research-archive-{index:06d}.json"
            data = encode(meta).encode("utf-8")
            checked = validate_export(data, name)
            with os.fdopen(os.open(directory / name, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600), "wb") as handle:
                if handle.write(data) != len(data):
                    raise OSError("incomplete fixture export")
                handle.flush()
                os.fsync(handle.fileno())
            previous = digest(checked["entry"])
    catalog = read_catalog(directory)
    if catalog["archive_count"] != 3 or catalog["run_count"] != 3:
        raise ValueError("fixture archive mismatch")
    write_index(directory)
    # Export creation must leave the active evidence untouched.
    if len(guard.inspect()["runs"]) != 3:
        raise ValueError("fixture active evidence mismatch")
    return catalog


def populate(directory):
    store = Store(directory)
    scenarios = []
    for scenario, status, outcome, pages in (("readable", "SUCCEEDED", "ACHIEVED", 2),
                                            ("partial", "BLOCKED", "PARTIAL", 1),
                                            ("empty", "BLOCKED", "NOT_ACHIEVED", 0)):
        runtime = ResearchRuntime(store, scenario=scenario)
        mission = runtime.run(runtime.create_research("notice pont", required_pages=2)["id"])
        projected = ClientSync(store).snapshot(mission["id"])["snapshot"]["mission"]
        if (mission["status"] != status or mission["outcome"]["status"] != outcome
                or mission["outcome"]["readable_pages"] != pages
                or projected["status"] != status):
            raise ValueError("fixture mission mismatch")
        scenarios.append({"role": "research_" + scenario, "mission_id": mission["id"],
                          "expected_status": status, "expected_outcome": outcome,
                          "readable_pages": pages, "required_pages": 2})
    guard = ResearchGuard(directory / "research-fixture" / "guard", create=False)
    catalog = _copy_exports(guard, directory.parent / "archives")
    return {"protocol": "eidolon-beta-fixture/1", "profile": "research-archives", "synthetic": True,
            "store_id": ClientSync(store).snapshot(scenarios[0]["mission_id"])["store_id"],
            "state_directory": "state", "token_file": "read-token", "archive_directory": "archives",
            "scenarios": scenarios, "receipt_queries": [], "archive_count": catalog["archive_count"],
            "active_research_count": 3, "active_runs_removed": 0, "exports_are_copies": True,
            "rotation_enabled": False, "external_services_contacted": False,
            "server_started": False, "authorizes_execution": False}
