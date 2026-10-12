# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : probe_r6.py
# Description : Sonde R6 : un journal DARME plus grand que la projection perd l'alerte critique au redémarrage
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""From eidolon-core/: PYTHONPATH=src python3 -m unittest docs/validation/2026-10-12/claude-darme-counter-analysis/probe_r6.py

Asserts the EXPECTED behaviour; at 4249811 it fails (the finding). Synthetic events, temporary folder."""
import os
import tempfile
import unittest

from eidolon_core.darme import DarmeMonitor, SecurityEvent, Severity
from eidolon_core.darme_store import DarmeJournal


class R6(unittest.TestCase):
    def test_a_critical_alert_survives_a_restart_with_a_large_journal(self):
        with tempfile.TemporaryDirectory() as folder:
            os.chmod(folder, 0o700)
            path = os.path.join(folder, "journal.sqlite3")
            journal = DarmeJournal(path)
            for i in range(10001):                       # routine events, oldest first
                journal.record(SecurityEvent(f"e{i}", "nas", "ssh", Severity.INFO, "2026-10-14T08:00:00Z"))
            journal.record(SecurityEvent("crit", "nas", "intrusion", Severity.CRITICAL, "2026-10-14T08:01:00Z"))
            journal.close()
            journal = DarmeJournal(path)                 # restart
            monitor = DarmeMonitor(["nas"])
            monitor.health("nas", True)
            try:
                journal.replay(monitor)                  # must not crash the start
            finally:
                journal.close()
            self.assertEqual(monitor.snapshot()["badge"], "red")


if __name__ == "__main__":
    unittest.main()
