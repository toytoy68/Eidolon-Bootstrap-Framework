"""Observation freshness is calculated by Core, never trusted from caller."""
import unittest
from eidolon_core.dialogue import validate_observations
from eidolon_core.contracts import ContractError

NOW = 1791825000.0

def observation(source="darme", **kw):
    return {"source": source, "reference": "status@1", "state": "ok", "text": "CPU 12 %", **kw}

class FreshnessTests(unittest.TestCase):
    def test_undated_is_unknown(self):
        self.assertEqual(validate_observations([observation()], now=NOW)[0]["freshness"], "unknown")

    def test_per_source_limits(self):
        from datetime import datetime, timezone
        date = datetime.fromtimestamp(NOW - 120, timezone.utc).isoformat()
        self.assertEqual(validate_observations([observation("darme", observed_at=date)], now=NOW)[0]["freshness"], "stale")
        self.assertEqual(validate_observations([observation("media-analysis", observed_at=date)], now=NOW)[0]["freshness"], "fresh")

    def test_caller_cannot_forge_freshness(self):
        with self.assertRaises(ContractError):
            validate_observations([observation(freshness="fresh")], now=NOW)

    def test_timezone_is_required(self):
        with self.assertRaises(ContractError):
            validate_observations([observation(observed_at="2026-10-14T07:00:00")], now=NOW)

    def test_invalid_clock_and_limit_fail_closed(self):
        with self.assertRaises(ContractError):
            validate_observations([observation()], now=float("nan"))
        with self.assertRaises(ContractError):
            validate_observations([observation(observed_at="2026-10-14T07:00:00+00:00")], now=NOW, max_age=float("nan"))

    def test_original_observation_not_mutated(self):
        item = observation()
        self.assertEqual(validate_observations([item], now=NOW)[0]["freshness"], "unknown")
        self.assertEqual(item, observation())
