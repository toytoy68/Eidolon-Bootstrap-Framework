import unittest

from eidolon_core.darme import Badge, DarmeMonitor, SecurityEvent, Severity


class DarmeTests(unittest.TestCase):
    def setUp(self):
        self.monitor = DarmeMonitor(["proxmox", "nas"])
        self.event = SecurityEvent("evt-1", "proxmox", "ssh_failures",
                                   Severity.WARNING, "2026-10-10T08:00:00+02:00",
                                   "192.0.2.10")

    def test_unavailable_is_not_healthy(self):
        self.assertEqual(self.monitor.snapshot()["badge"], "grey")

    def test_alert_persists_until_acknowledgement(self):
        self.monitor.health("proxmox", True)
        self.monitor.health("nas", True)
        self.monitor.ingest(self.event)
        self.assertEqual(self.monitor.snapshot()["badge"], "red")
        self.monitor.ingest(self.event)
        self.assertEqual(self.monitor.snapshot()["unacknowledged_alerts"], 1)
        self.monitor.acknowledge("evt-1")
        self.assertEqual(self.monitor.snapshot()["badge"], "gold")

    def test_intervention_badge(self):
        for source in self.monitor.sources:
            self.monitor.health(source, True)
        self.monitor.intervention = True
        self.assertEqual(self.monitor.snapshot()["badge"], "blue")

    def test_alert_overrides_bad_health(self):
        self.monitor.ingest(self.event)
        self.assertEqual(self.monitor.snapshot()["badge"], "red")
        self.assertEqual(self.monitor.snapshot()["visibility"], "partial")
        self.assertEqual(self.monitor.snapshot()["unacknowledged_alerts"], 1)

    def test_unknown_source_rejected(self):
        with self.assertRaises(ValueError):
            self.monitor.ingest(SecurityEvent("x", "internet", "x", Severity.CRITICAL,
                                               "2026-10-10T08:00:00Z"))

    def test_collision_rejected(self):
        self.monitor.ingest(self.event)
        with self.assertRaises(ValueError):
            self.monitor.ingest(SecurityEvent("evt-1", "proxmox", "different",
                                               Severity.CRITICAL, "2026-10-10T08:00:00Z"))

    def test_naive_timestamp_rejected(self):
        with self.assertRaises(ValueError):
            SecurityEvent("x", "nas", "x", Severity.INFO, "2026-10-10T08:00:00")

    def test_invalid_severity(self):
        with self.assertRaises(ValueError):
            SecurityEvent("x", "nas", "x", "critical", "2026-10-10T08:00:00Z")

    def test_control_characters_rejected(self):
        for field in ("source", "category", "subject"):
            values = dict(event_id="x", source="nas", category="ssh", severity=Severity.INFO,
                          observed_at="2026-10-10T08:00:00Z", subject="")
            values[field] = "bad\\x1b[31m".replace("\\x1b", chr(27))
            with self.assertRaises(ValueError):
                SecurityEvent(**values)

    def test_timezone_order(self):
        self.monitor.ingest(SecurityEvent("late", "nas", "x", Severity.INFO, "2026-10-10T07:30:00Z"))
        self.monitor.ingest(SecurityEvent("early", "nas", "x", Severity.INFO, "2026-10-10T08:00:00+02:00"))
        self.assertEqual([e["event_id"] for e in self.monitor.snapshot()["events"]], ["early", "late"])

    def test_event_capacity(self):
        monitor = DarmeMonitor(["nas"], max_events=1)
        monitor.ingest(SecurityEvent("one", "nas", "x", Severity.INFO, "2026-10-10T08:00:00Z"))
        with self.assertRaises(OverflowError):
            monitor.ingest(SecurityEvent("two", "nas", "x", Severity.INFO, "2026-10-10T08:00:00Z"))


if __name__ == "__main__":
    unittest.main()
