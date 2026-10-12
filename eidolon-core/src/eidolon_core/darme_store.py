# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : darme_store.py
# Description : Journal passif borne et relecture priorisant les alertes
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Local journal only. Limits refuse writes; no automatic destructive retention."""
import heapq
import json
import os
import sqlite3
import stat
from datetime import datetime, timezone
from pathlib import Path

from .darme import SecurityEvent, Severity, _instant

class JournalCapacityError(OverflowError):
    """Admission stopped; the caller must degrade collector health."""

class DarmeJournal:
    def __init__(self, filename, *, max_records=100000, max_bytes=64 * 1024 * 1024):
        if type(max_records) is not int or not 1 <= max_records <= 1000000:
            raise ValueError("invalid journal record limit")
        if type(max_bytes) is not int or not 16384 <= max_bytes <= 1024 * 1024 * 1024:
            raise ValueError("invalid journal byte limit")
        path = Path(filename)
        if path.is_symlink() or any(parent.is_symlink() for parent in path.parents):
            raise ValueError("symlink refused")
        if path.exists():
            info = path.stat()
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
                raise ValueError("DARME journal must be an owner-only regular file (0600)")
        else:
            if path.parent.is_symlink() or not path.parent.is_dir():
                raise ValueError("invalid journal directory")
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
            os.close(fd)
        self.db = sqlite3.connect(path)
        self.max_records = max_records
        self.max_bytes = max_bytes
        try:
            self.db.execute("CREATE TABLE IF NOT EXISTS events (id TEXT PRIMARY KEY, payload TEXT NOT NULL)")
            self.db.execute("CREATE TABLE IF NOT EXISTS acknowledgements (id TEXT PRIMARY KEY, actor TEXT NOT NULL, reason TEXT NOT NULL, acknowledged_at TEXT)")
            columns = {row[1] for row in self.db.execute("PRAGMA table_info(acknowledgements)")}
            if "acknowledged_at" not in columns:
                self.db.execute("ALTER TABLE acknowledgements ADD COLUMN acknowledged_at TEXT")
            self.db.commit()
            self.page_size = self.db.execute("PRAGMA page_size").fetchone()[0]
            self.db.execute("PRAGMA max_page_count=" + str(max_bytes // self.page_size))
        except Exception:
            self.db.close()
            raise

    def close(self):
        self.db.close()

    def _check_bytes(self):
        pages = self.db.execute("PRAGMA page_count").fetchone()[0]
        if pages * self.page_size > self.max_bytes:
            raise JournalCapacityError("DARME_JOURNAL_CAPACITY: byte limit reached")

    @staticmethod
    def _capacity_error(exc):
        return getattr(exc, "sqlite_errorcode", 0) & 255 == sqlite3.SQLITE_FULL

    def record(self, event):
        if not isinstance(event, SecurityEvent):
            raise ValueError("invalid event")
        payload = json.dumps(dict(event_id=event.event_id, source=event.source,
                                  category=event.category, severity=event.severity.value,
                                  observed_at=event.observed_at, subject=event.subject), sort_keys=True)
        try:
            with self.db:
                self.db.execute("BEGIN IMMEDIATE")
                old = self.db.execute("SELECT payload FROM events WHERE id=?", (event.event_id,)).fetchone()
                if old:
                    if old[0] != payload:
                        raise ValueError("event id collision")
                    return False
                if self.db.execute("SELECT COUNT(*) FROM events").fetchone()[0] >= self.max_records:
                    raise JournalCapacityError("DARME_JOURNAL_CAPACITY: record limit reached")
                self._check_bytes()
                self.db.execute("INSERT INTO events VALUES (?,?)", (event.event_id, payload))
                self._check_bytes()
        except sqlite3.OperationalError as exc:
            if self._capacity_error(exc):
                raise JournalCapacityError("DARME_JOURNAL_CAPACITY: SQLite byte limit reached") from exc
            raise
        return True

    def acknowledge(self, event_id, actor, reason, *, acknowledged_at=None):
        from .darme import _safe
        _safe(actor, 128)
        _safe(reason, 512)
        explicit_time = acknowledged_at is not None
        timestamp = acknowledged_at or datetime.now(timezone.utc).isoformat()
        _instant(timestamp)
        try:
            with self.db:
                self.db.execute("BEGIN IMMEDIATE")
                if not self.db.execute("SELECT 1 FROM events WHERE id=?", (event_id,)).fetchone():
                    raise ValueError("unknown event")
                previous = self.db.execute(
                    "SELECT actor, reason, acknowledged_at FROM acknowledgements WHERE id=?", (event_id,)
                ).fetchone()
                if previous is not None:
                    if previous[:2] != (actor, reason) or (explicit_time and previous[2] != timestamp):
                        raise ValueError("acknowledgement already recorded with different details")
                    return False
                self._check_bytes()
                self.db.execute("INSERT INTO acknowledgements VALUES (?,?,?,?)",
                                (event_id, actor, reason, timestamp))
                self._check_bytes()
        except sqlite3.OperationalError as exc:
            if self._capacity_error(exc):
                raise JournalCapacityError("DARME_JOURNAL_CAPACITY: SQLite byte limit reached") from exc
            raise
        return True

    def replay(self, monitor):
        """Validate all rows before updating a bounded projection.

        Unacknowledged critical alerts precede warnings, then recent other events.
        Omitted alerts are counted so a flood cannot hide a red badge.
        No row is deleted. Health belongs to the caller, not to historical events.
        """
        if monitor.events or monitor.acknowledged:
            raise ValueError("replay requires an empty projection")
        monitor.ingestion_paused = True
        selected, total, active_total = [], 0, 0
        # A read transaction binds events and acknowledgements to one snapshot.
        self.db.execute("BEGIN")
        try:
            for identity, raw, acknowledged, rowid in self.db.execute(
                "SELECT e.id,e.payload,a.id,e.rowid FROM events e "
                "LEFT JOIN acknowledgements a ON a.id=e.id ORDER BY e.rowid"
            ):
                data = json.loads(raw)
                event = SecurityEvent(data["event_id"], data["source"], data["category"],
                                      Severity(data["severity"]), data["observed_at"], data["subject"])
                if event.event_id != identity or event.source not in monitor.sources:
                    raise ValueError("untrusted or inconsistent journal event")
                is_active = acknowledged is None and event.severity in (Severity.WARNING, Severity.CRITICAL)
                active_total += int(is_active)
                priority = 2 if is_active and event.severity == Severity.CRITICAL else 1 if is_active else 0
                item = (priority, _instant(event.observed_at), rowid, event, acknowledged is not None)
                if len(selected) < monitor.max_events:
                    heapq.heappush(selected, item)
                elif item[:3] > selected[0][:3]:
                    heapq.heapreplace(selected, item)
                total += 1
        finally:
            self.db.rollback()
        selected_active = 0
        for priority, instant, rowid, event, acknowledged in sorted(selected, key=lambda x: x[2]):
            monitor.ingest(event)
            if acknowledged:
                monitor.acknowledge(event.event_id)
            elif priority:
                selected_active += 1
        monitor.unrepresented_alerts = active_total - selected_active
        monitor.unrepresented_events = total - len(selected)
        monitor.ingestion_paused = total > len(selected)
        return monitor
