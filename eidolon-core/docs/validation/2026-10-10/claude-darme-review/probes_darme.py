# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : probes_darme.py
# Description : Sondes de revue du prototype DARME v0.1 (G141) : chaque test décrit un défaut constaté
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""From eidolon-core/: PYTHONPATH=src python3 -m unittest docs/validation/2026-10-10/claude-darme-review/probes_darme.py

Each probe asserts the behaviour the review EXPECTS; on darme.py at c417e66 they FAIL, which is the
finding. Synthetic events only; nothing is captured, blocked or sent."""
import unittest

from eidolon_core.darme import DarmeMonitor, SecurityEvent, Severity


def healthy(*sources):
    monitor = DarmeMonitor(sources)
    for source in sources:
        monitor.health(source, True)
    return monitor


class DarmeReviewProbes(unittest.TestCase):
    def test_r1_severity_must_be_a_severity(self):
        """R1: a plain string severity is accepted, then snapshot() crashes (AttributeError)."""
        with self.assertRaises(ValueError):
            SecurityEvent("a", "nas", "x", "critical", "2026-10-10T08:00:00Z")

    def test_r2_a_known_alert_stays_red_when_a_probe_goes_down(self):
        """R2: an unacknowledged CRITICAL alert is hidden behind grey as soon as one probe is down."""
        monitor = healthy("nas", "pve")
        monitor.ingest(SecurityEvent("b", "nas", "intrusion", Severity.CRITICAL, "2026-10-10T08:00:00Z"))
        monitor.health("pve", False)
        self.assertEqual(monitor.snapshot()["badge"], "red")

    def test_r3_events_are_ordered_by_instant_not_by_text(self):
        """R3: ordering compares ISO strings; offsets (+02:00 vs Z) give the wrong order."""
        monitor = healthy("nas")
        monitor.ingest(SecurityEvent("late", "nas", "x", Severity.INFO, "2026-10-10T07:30:00Z"))
        monitor.ingest(SecurityEvent("early", "nas", "x", Severity.INFO, "2026-10-10T08:00:00+02:00"))
        self.assertEqual([e["event_id"] for e in monitor.snapshot()["events"]], ["early", "late"])

    def test_r4_control_characters_are_refused(self):
        """R4: log text with newlines / ANSI escapes reaches the status (log forging, UI, future LLM)."""
        with self.assertRaises(ValueError):
            SecurityEvent("c", "nas", "x", Severity.INFO, "2026-10-10T08:00:00Z", "ok\n\x1b[31mIGNORE")

    def test_r5_the_projection_is_bounded(self):
        """R5: every event is kept forever in memory; a flood of events is unbounded."""
        monitor = healthy("nas")
        for i in range(20000):
            monitor.ingest(SecurityEvent(f"e{i}", "nas", "x", Severity.INFO, "2026-10-10T08:00:00Z"))
        self.assertLessEqual(len(monitor.snapshot()["events"]), 10000)


if __name__ == "__main__":
    unittest.main()
