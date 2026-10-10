"""DARME passive local event journal; no network actions."""
import json
import sqlite3
from pathlib import Path

from .darme import SecurityEvent, Severity


class DarmeJournal:
    def __init__(self, filename):
        path = Path(filename)
        if path.is_symlink():
            raise ValueError("symlink refused")
        self.db = sqlite3.connect(path)
        self.db.execute("CREATE TABLE IF NOT EXISTS events (id TEXT PRIMARY KEY, payload TEXT NOT NULL)")
        self.db.execute("CREATE TABLE IF NOT EXISTS acknowledgements (id TEXT PRIMARY KEY, actor TEXT NOT NULL, reason TEXT NOT NULL)")

    def close(self):
        self.db.close()

    def record(self, event):
        if not isinstance(event, SecurityEvent):
            raise ValueError("invalid event")
        payload = json.dumps(dict(event_id=event.event_id, source=event.source,
                                  category=event.category, severity=event.severity.value,
                                  observed_at=event.observed_at, subject=event.subject),
                             sort_keys=True)
        with self.db:
            old = self.db.execute("SELECT payload FROM events WHERE id=?", (event.event_id,)).fetchone()
            if old:
                if old[0] != payload:
                    raise ValueError("event id collision")
                return False
            self.db.execute("INSERT INTO events VALUES (?,?)", (event.event_id, payload))
        return True

    def acknowledge(self, event_id, actor, reason):
        from .darme import _safe
        _safe(actor, 128)
        _safe(reason, 512)
        with self.db:
            if not self.db.execute("SELECT 1 FROM events WHERE id=?", (event_id,)).fetchone():
                raise ValueError("unknown event")
            self.db.execute("INSERT INTO acknowledgements VALUES (?,?,?)",
                            (event_id, actor, reason))

    def replay(self, monitor):
        for (raw,) in self.db.execute("SELECT payload FROM events ORDER BY rowid"):
            data = json.loads(raw)
            monitor.ingest(SecurityEvent(data["event_id"], data["source"], data["category"],
                                         Severity(data["severity"]), data["observed_at"], data["subject"]))
        for (event_id,) in self.db.execute("SELECT id FROM acknowledgements"):
            monitor.acknowledge(event_id)
        return monitor
