import tempfile
import unittest
from pathlib import Path

from eidolon_core.darme import DarmeMonitor, SecurityEvent, Severity
from eidolon_core.darme_store import DarmeJournal


class DarmeJournalTests(unittest.TestCase):
    def test_persists_events_and_acknowledgements(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "darme.sqlite3"
            event = SecurityEvent("e1", "proxmox", "ssh", Severity.WARNING,
                                  "2026-10-10T08:00:00Z", "failed login")
            journal = DarmeJournal(path)
            self.assertTrue(journal.record(event))
            self.assertFalse(journal.record(event))
            journal.acknowledge("e1", "operator", "reviewed")
            journal.close()
            reopened = DarmeJournal(path)
            monitor = reopened.replay(DarmeMonitor(["proxmox"]))
            self.assertEqual(monitor.snapshot()["unacknowledged_alerts"], 0)
            self.assertEqual(len(monitor.snapshot()["events"]), 1)
            reopened.close()

    def test_rejects_collision(self):
        with tempfile.TemporaryDirectory() as folder:
            journal = DarmeJournal(Path(folder) / "darme.sqlite3")
            journal.record(SecurityEvent("e1", "nas", "ssh", Severity.INFO, "2026-10-10T08:00:00Z"))
            with self.assertRaises(ValueError):
                journal.record(SecurityEvent("e1", "nas", "ssh", Severity.CRITICAL,
                                             "2026-10-10T08:00:00Z"))
            journal.close()

    def test_unknown_acknowledgement(self):
        with tempfile.TemporaryDirectory() as folder:
            journal = DarmeJournal(Path(folder) / "darme.sqlite3")
            with self.assertRaises(ValueError):
                journal.acknowledge("missing", "operator", "reason")
            journal.close()


if __name__ == "__main__":
    unittest.main()
