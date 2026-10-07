# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : archive_page.py
# Description : Projection paginée et privée du catalogue des archives
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Read-only metadata pages, never raw exports or query text.

A cursor selects a position in a checked catalog; it grants no authority.
One reader at a time bounds archive work independently of the HTTP workers.
"""
import os
import re
import threading

from .research_archive import MAX_ARCHIVES, read_catalog
from .store import now

PROTOCOL = "eidolon-research-archive-page/1"
READ_BUDGET_SECONDS = 2.0
CURSOR_FIELDS = {"version", "store_id", "catalog_sha256", "after_index"}
SUMMARY_FIELDS = ("file", "index", "sha256", "created_at_ms", "count",
                  "queries_with_text", "legacy_runs_without_text", "linked_missions")


class ArchivePageError(ValueError):
    def __init__(self, status, code):
        self.status, self.code = status, code
        super().__init__(code)


def validate_cursor(cursor):
    if (type(cursor) is not dict or set(cursor) != CURSOR_FIELDS
            or type(cursor["version"]) is not int or cursor["version"] != 1
            or type(cursor["store_id"]) is not str
            or re.fullmatch(r"s-[0-9a-f]{32}", cursor["store_id"]) is None
            or type(cursor["catalog_sha256"]) is not str
            or re.fullmatch(r"[0-9a-f]{64}", cursor["catalog_sha256"]) is None
            or type(cursor["after_index"]) is not int
            or not 1 <= cursor["after_index"] <= MAX_ARCHIVES):
        raise ArchivePageError(400, "INVALID_ARCHIVE_CURSOR")


class ArchivePages:
    def __init__(self, store, directory):
        self.store = store
        # Keep the final component unresolved: read_catalog must reject symlinks.
        self.directory = os.path.abspath(directory)
        self.lock = threading.Lock()

    def page(self, *, cursor=None, limit=50):
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ArchivePageError(400, "INVALID_PAGE_LIMIT")
        if cursor is not None:
            validate_cursor(cursor)
        if not self.lock.acquire(blocking=False):
            raise ArchivePageError(503, "ARCHIVES_BUSY")
        try:
            identity = self.store.health()["store_id"]
            catalog = read_catalog(self.directory, time_budget_seconds=READ_BUDGET_SECONDS)
            # Recheck Store identity/review guards after the filesystem snapshot.
            if identity != self.store.health()["store_id"]:
                raise ArchivePageError(503, "ARCHIVES_UNAVAILABLE")
            response = {"protocol": PROTOCOL, "status": "PAGE", "store_id": identity,
                        "catalog_sha256": catalog["catalog_sha256"], "chain_head": catalog["chain_head"],
                        "archive_count": catalog["archive_count"], "run_count": catalog["run_count"],
                        "observed_at": now(), "items": [], "has_more": False, "next_cursor": None,
                        "snapshot_only": True, "consistency_verified": True,
                        "authenticity_verified": False, "live_journal_checked": False,
                        "committed_status_known": False, "authorizes_execution": False,
                        "request_sent": False}
            after = 0
            if cursor is not None:
                reason = ("STORE_CHANGED" if cursor["store_id"] != identity else
                          "CATALOG_CHANGED" if cursor["catalog_sha256"] != catalog["catalog_sha256"] else None)
                if reason:
                    response.update(status="RESET_REQUIRED", reason=reason)
                    return response
                after = cursor["after_index"]
                if after >= catalog["archive_count"]:
                    raise ArchivePageError(400, "INVALID_ARCHIVE_CURSOR")
            response["items"] = [{key: item[key] for key in SUMMARY_FIELDS}
                                 for item in catalog["files"][after:after + limit]]
            end = after + len(response["items"])
            response["has_more"] = end < catalog["archive_count"]
            if response["has_more"]:
                response["next_cursor"] = {"version": 1, "store_id": identity,
                                           "catalog_sha256": catalog["catalog_sha256"], "after_index": end}
            return response
        finally:
            self.lock.release()
