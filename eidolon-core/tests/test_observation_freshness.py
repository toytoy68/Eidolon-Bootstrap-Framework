# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_observation_freshness.py
# Description : I1 (G210) : date des observations d'outil et fraîcheur calculée par Core
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""I1: an observation carries observed_at; Core computes its freshness. Synthetic data, no network."""
import json
import unittest
from datetime import datetime, timezone

from eidolon_core import dialogue as dg
from eidolon_core.contracts import ContractError
from tests.test_dialogue import Base

NOW = datetime(2026, 10, 12, 17, 10, tzinfo=timezone.utc).timestamp()


def observation(source="media-analysis", **extra):
    return {"source": source, "reference": "core@ok", "state": "ok", "text": "CPU 12 %", **extra}


def freshness(when, source="media-analysis", **kwargs):
    return dg.validate_observations([observation(source, observed_at=when)], now=NOW, **kwargs)[0]["freshness"]


class Freshness(unittest.TestCase):
    def test_core_computes_fresh_stale_and_unknown(self):
        self.assertEqual(freshness("2026-10-12T17:08:00+00:00"), "fresh")
        self.assertEqual(freshness("2026-10-12T19:08:00+02:00"), "fresh")           # same instant, other offset
        self.assertEqual(freshness("2026-10-12T17:00:00+00:00"), "stale")           # 600 s > 300 s
        self.assertEqual(freshness("2026-10-12T17:00:00+00:00", max_age=900), "fresh")
        self.assertEqual(freshness("2026-10-12T17:20:00+00:00"), "unknown")         # future: not trusted
        self.assertEqual(freshness("2026-10-12T17:10:30+00:00"), "fresh")           # within clock skew

    def test_the_limit_depends_on_the_source(self):
        """G212: 300 s by default, shorter for DARME live metrics; configurable per source."""
        two_minutes = "2026-10-12T17:08:00+00:00"
        self.assertEqual(dg.OBSERVATION_MAX_AGE, 300)
        self.assertLess(dg.OBSERVATION_MAX_AGE_BY_SOURCE["darme"], dg.OBSERVATION_MAX_AGE)
        self.assertEqual(freshness(two_minutes), "fresh")
        self.assertEqual(freshness(two_minutes, "darme"), "stale")
        self.assertEqual(freshness("2026-10-12T17:09:30+00:00", "darme"), "fresh")
        self.assertEqual(freshness(two_minutes, "darme", max_age={"darme": 180}), "fresh")
        self.assertEqual(freshness(two_minutes, max_age={"darme": 180}), "fresh")     # others keep 300 s
        for bad in (0, -1, float("nan"), True, "60", {"media-analysis": 0}):
            with self.assertRaises(ContractError, msg=repr(bad)):
                freshness(two_minutes, max_age=bad)

    def test_time_zones_and_boundaries(self):
        """G214-5: offsets, Z suffix, exact limits and clock skew."""
        self.assertEqual(freshness("2026-10-12T12:08:00-05:00"), "fresh")           # 17:08 UTC
        self.assertEqual(freshness("2026-10-12T17:08:00Z"), "fresh")
        self.assertEqual(freshness("2026-10-13T02:38:00+09:30"), "fresh")           # 17:08 UTC
        self.assertEqual(freshness("2026-10-12T17:05:00+00:00"), "fresh")           # exactly 300 s
        self.assertEqual(freshness("2026-10-12T17:04:59+00:00"), "stale")
        self.assertEqual(freshness("2026-10-12T17:09:00+00:00", "darme"), "fresh")  # exactly 60 s
        self.assertEqual(freshness("2026-10-12T17:08:59+00:00", "darme"), "stale")
        self.assertEqual(freshness("2026-10-12T17:11:00+00:00"), "fresh")           # +60 s: skew tolerated
        self.assertEqual(freshness("2026-10-12T17:11:01+00:00"), "unknown")         # beyond skew
        self.assertEqual(freshness("2027-01-01T00:00:00+00:00", "darme"), "unknown")

    def test_old_observations_keep_working(self):
        """G214-5: the pre-I1 shape (no observed_at) is accepted as unknown; other extra keys stay refused."""
        legacy = {"source": "media-analysis", "reference": "job-1", "state": "RESULT_UNVERIFIED", "text": "x"}
        self.assertEqual(dg.validate_observations([legacy], now=NOW),
                         [dict(legacy, freshness="unknown")])
        with self.assertRaises(ContractError):
            dg.validate_observations([dict(legacy, extra="y")], now=NOW)

    def test_an_undated_observation_is_unknown_never_fresh(self):
        self.assertEqual(dg.validate_observations([observation()], now=NOW)[0]["freshness"], "unknown")

    def test_freshness_cannot_be_supplied_by_the_caller(self):
        for extra in ({"stale": False}, {"freshness": "fresh"}):
            with self.assertRaises(ContractError):
                dg.validate_observations([observation(observed_at="2026-10-12T17:00:00+00:00", **extra)], now=NOW)

    def test_an_unreliable_date_is_refused(self):
        for bad in ("2026-10-12T17:00:00", "hier", "", "2026-13-40T00:00:00+00:00", 1760288400, None,
                    "2026-10-12T17:00:00+00:00" + " " * 30):
            with self.assertRaises(ContractError, msg=repr(bad)):
                dg.validate_observations([observation(observed_at=bad)], now=NOW)

    def test_the_input_is_not_mutated(self):
        item = observation(observed_at="2026-10-12T17:08:00+00:00")
        before = dict(item)
        dg.validate_observations([item], now=NOW)
        self.assertEqual(item, before)


class MixedBatch(unittest.TestCase):
    def test_five_mixed_observations_are_each_labelled_independently(self):
        """G218-6: the maximum batch, mixed sources and ages; one label per item, order kept."""
        batch = [observation("darme", observed_at="2026-10-12T17:09:30+00:00"),          # 30 s: fresh
                 observation("darme", observed_at="2026-10-12T17:08:00+00:00"),          # 120 s: stale (60 s)
                 observation("media-analysis", observed_at="2026-10-12T17:08:00+00:00"), # 120 s: fresh (300 s)
                 observation("media-analysis"),                                          # undated
                 observation("darme", observed_at="2026-10-12T18:00:00+00:00")]          # future
        labels = [o["freshness"] for o in dg.validate_observations(batch, now=NOW)]
        self.assertEqual(labels, ["fresh", "stale", "fresh", "unknown", "unknown"])
        with self.assertRaises(ContractError):
            dg.validate_observations(batch + [observation()], now=NOW)                 # six: refused


class FreshnessReachesTheModel(Base):
    def test_a_stale_reading_is_labelled_for_the_model(self):
        seen = []

        class Recording(dg.SimulatedDialogueModel):
            def reply(self, text, history, memory, observations=None, media=None, personality=None):
                seen.append(observations)
                return super().reply(text, history, memory, observations)
        old = datetime.fromtimestamp(0, timezone.utc).isoformat()
        self.dialogue(Recording(self.runtime.catalog)).respond(
            self.cid, client_id="pc", client_turn_key="old", text="Bonjour",
            observations=[observation(observed_at=old)])
        self.assertEqual(seen[0][0]["freshness"], "stale")
        self.assertIn("freshness is stale or unknown", dg.SYSTEM_PROMPT)
        self.assertIn('"freshness":"stale"', json.dumps(seen[0], separators=(",", ":")))


if __name__ == "__main__":
    unittest.main()
