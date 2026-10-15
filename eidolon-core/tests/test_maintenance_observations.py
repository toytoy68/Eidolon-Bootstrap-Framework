# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_maintenance_observations.py
# Description : Tests de la normalisation des observations hôte (Claude, G236-8)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
import unittest
from datetime import datetime, timedelta, timezone

from eidolon_core.maintenance_observations import (ObservationRefused, TickObservation,
                                                   normalize_host_observation)

AT = "2026-10-15T03:00:00+00:00"


def raw(**extra):
    value = {"source": "host.proc", "at": AT, "last_activity": "2026-10-15T01:00:00+00:00",
             "boot_at": "2026-10-14T20:00:00+00:00",
             "load": {"observed_at": "2026-10-15T02:59:30+00:00", "ratio": 0.2, "limit": 0.7}}
    value.update(extra)
    return value


class Normalize(unittest.TestCase):
    def test_a_complete_observation_gives_tick_arguments(self):
        obs = normalize_host_observation(raw())
        self.assertIsInstance(obs, TickObservation)
        kwargs = obs.tick_kwargs()
        self.assertEqual(set(kwargs), {"at", "last_activity", "boot_at", "load_ok"})
        self.assertTrue(kwargs["load_ok"] and obs.notes == ())
        self.assertTrue(all(kwargs[k].tzinfo is timezone.utc for k in ("at", "last_activity", "boot_at")))

    def test_offsets_are_normalised_to_utc(self):
        obs = normalize_host_observation(raw(at="2026-10-15T05:00:00+02:00"))
        self.assertEqual(obs.at, datetime(2026, 10, 15, 3, tzinfo=timezone.utc))

    def test_unknown_values_are_conservative(self):
        obs = normalize_host_observation({"source": "host.proc", "at": AT})
        self.assertEqual((obs.last_activity, obs.boot_at), (obs.at, obs.at))      # defers the window
        self.assertFalse(obs.load_ok)
        self.assertEqual(obs.notes, ("LAST_ACTIVITY_UNKNOWN", "BOOT_AT_UNKNOWN", "LOAD_UNKNOWN"))

    def test_stale_or_high_load_is_never_ok(self):
        stale = normalize_host_observation(raw(load={"observed_at": "2026-10-15T02:50:00+00:00",
                                                     "ratio": 0.1, "limit": 0.7}))
        high = normalize_host_observation(raw(load={"observed_at": AT, "ratio": 0.9, "limit": 0.7}))
        self.assertEqual((stale.load_ok, stale.notes), (False, ("LOAD_STALE",)))
        self.assertEqual((high.load_ok, high.notes), (False, ("LOAD_HIGH",)))
        shorter = normalize_host_observation(raw(), max_load_age=timedelta(seconds=10))
        self.assertFalse(shorter.load_ok)

    def test_untrustworthy_observations_are_refused(self):
        for bad in (raw(at="2026-10-15T03:00:00"), raw(at="hier"), raw(at=None), raw(source="Host"),
                    raw(source=""), raw(extra=1), raw(last_activity="2026-10-15T03:05:00+00:00"),
                    raw(boot_at="2027-01-01T00:00:00+00:00"),
                    raw(load={"observed_at": AT, "ratio": float("nan"), "limit": 0.7}),
                    raw(load={"observed_at": AT, "ratio": 0.1, "limit": 0}),
                    raw(load={"observed_at": AT, "ratio": True, "limit": 0.7}),
                    raw(load={"observed_at": "2026-10-15T03:05:00+00:00", "ratio": 0.1, "limit": 0.7}),
                    raw(load={"ratio": 0.1, "limit": 0.7}), "not a dict"):
            with self.subTest(bad=bad), self.assertRaises(ObservationRefused):
                normalize_host_observation(bad)
        with self.assertRaises(ObservationRefused):
            normalize_host_observation(raw(), max_load_age=timedelta(0))

    def test_a_small_clock_skew_is_tolerated_and_clamped(self):
        obs = normalize_host_observation(raw(last_activity="2026-10-15T03:00:30+00:00"))
        self.assertEqual(obs.last_activity, obs.at)

    def test_refusal_is_a_value_error_for_existing_callers(self):
        self.assertTrue(issubclass(ObservationRefused, ValueError))


if __name__ == "__main__":
    unittest.main()
