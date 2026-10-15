# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_maintenance_observations_floor.py
# Description : Dates sentinelles (époque Unix) jamais prises pour un passé réel (Claude, contre-revue G251)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
import unittest

from eidolon_core.maintenance_observations import ObservationRefused, normalize_host_observation

AT = "2026-10-15T03:00:00+00:00"
LOAD = {"observed_at": AT, "ratio": 0.1, "limit": 0.7}


class EpochSentinel(unittest.TestCase):
    def test_an_epoch_boot_or_activity_is_unknown_and_defers(self):
        obs = normalize_host_observation({"source": "host.proc", "at": AT, "load": LOAD,
                                          "boot_at": "1970-01-01T00:00:00+00:00",
                                          "last_activity": "1970-01-01T00:00:00+00:00"})
        self.assertEqual((obs.boot_at, obs.last_activity), (obs.at, obs.at))      # "just now": the window defers
        self.assertEqual(obs.notes, ("LAST_ACTIVITY_IMPLAUSIBLE", "BOOT_AT_IMPLAUSIBLE"))

    def test_a_plausible_old_boot_is_kept(self):
        obs = normalize_host_observation({"source": "host.proc", "at": AT, "load": LOAD,
                                          "boot_at": "2026-09-01T00:00:00+00:00",
                                          "last_activity": "2026-10-15T01:00:00+00:00"})
        self.assertEqual((obs.boot_at.month, obs.notes), (9, ()))

    def test_an_implausible_host_clock_is_refused(self):
        with self.assertRaises(ObservationRefused):
            normalize_host_observation({"source": "host.proc", "at": "1970-01-01T00:00:10+00:00"})

    def test_an_epoch_load_date_is_stale_never_ok(self):
        obs = normalize_host_observation({"source": "host.proc", "at": AT,
                                          "load": dict(LOAD, observed_at="1970-01-01T00:00:00+00:00")})
        self.assertFalse(obs.load_ok)
        self.assertIn("LOAD_STALE", obs.notes)


if __name__ == "__main__":
    unittest.main()
