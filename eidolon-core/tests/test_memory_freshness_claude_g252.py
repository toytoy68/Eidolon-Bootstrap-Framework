# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_memory_freshness_claude_g252.py
# Description : Contre-revue Claude G252 (tâches 4 et 6) : contrat de fraîcheur, contexte affiché, fuseaux extrêmes
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""The first test kills a mutant of contracts._validate_index_status (UNVERIFIED accepted with a canonical
digest) that survives GPT's 102 related tests. Synthetic values only."""
import unittest

from eidolon_core.contracts import ContractError, validate_context
from eidolon_core.conversation import validate_context_note
from eidolon_core.maintenance_observations import ObservationRefused, normalize_host_observation

D1, D2 = "a" * 64, "b" * 64


def status(**over):
    value = {"state": "INDEX_STALE", "reason": "FULL_SOURCE_DIGEST_MISMATCH", "generation": "eidolon_x__1",
             "source_digest": D1, "canonical_digest": D2}
    value.update(over)
    return value


def context(index_status):
    return {"items": [], "index_status": index_status}


class ContractCoherence(unittest.TestCase):
    def test_unverified_can_never_carry_a_canonical_digest(self):
        for reason, generation, source in (("SNAPSHOT_NOT_SUPPORTED", None, None),
                                           ("NO_FULL_SOURCE_DIGEST", "eidolon_x__1", None),
                                           ("CANONICAL_CHECK_INCOMPLETE", "eidolon_x__1", D1)):
            ok = status(state="INDEX_UNVERIFIED", reason=reason, generation=generation, source_digest=source,
                        canonical_digest=None)
            validate_context(context(ok))
            with self.subTest(reason=reason), self.assertRaises(ContractError):
                validate_context(context(dict(ok, canonical_digest=D2)))

    def test_incoherent_match_or_stale_claims_are_refused(self):
        for bad in (status(state="INDEX_SNAPSHOT_MATCH", reason="FULL_SOURCE_DIGEST_MATCH"),      # digests differ
                    status(canonical_digest=D1),                                                 # stale, equal
                    status(reason="FULL_SOURCE_DIGEST_MATCH"),                                    # wrong reason
                    status(generation=None), status(extra=1), status(state="INDEX_ABSENT")):
            with self.subTest(bad=bad), self.assertRaises(ContractError):
                validate_context(context(bad))


class VisibleContext(unittest.TestCase):
    NOTE = {"history_sent": 0, "history_excluded": 0, "memory": "sent", "memory_items": 0,
            "memory_truncated_items": 0, "observations_sent": 0, "observations_excluded": 0}

    def test_zero_items_with_a_stale_index_is_still_announced_partial(self):
        for state in ("INDEX_STALE", "INDEX_UNVERIFIED"):
            self.assertTrue(validate_context_note(dict(self.NOTE, memory_index=state))["partial"])
        self.assertFalse(validate_context_note(dict(self.NOTE, memory_index="INDEX_SNAPSHOT_MATCH"))["partial"])

    def test_an_index_state_is_never_shown_for_memory_that_was_not_sent(self):
        for memory in ("dropped_for_budget", "unavailable", "none"):
            with self.subTest(memory=memory), self.assertRaises(ContractError):
                validate_context_note(dict(self.NOTE, memory=memory, memory_index="INDEX_SNAPSHOT_MATCH"))
        self.assertTrue(validate_context_note(dict(self.NOTE, memory="dropped_for_budget"))["partial"])


class ExtremeZones(unittest.TestCase):
    LOAD = {"observed_at": "2026-10-15T03:00:00+00:00", "ratio": 0.1, "limit": 0.7}

    def test_extreme_but_valid_offsets_name_the_same_instant(self):
        for at in ("2026-10-15T17:00:00+14:00", "2026-10-14T15:00:00-12:00", "2026-10-15T02:59:00-00:01"):
            obs = normalize_host_observation({"source": "host.proc", "at": at, "load": self.LOAD})
            self.assertLessEqual(abs((obs.at - normalize_host_observation(
                {"source": "host.proc", "at": "2026-10-15T03:00:00+00:00"}).at).total_seconds()), 60)

    def test_dates_at_the_edges_of_the_calendar_fail_with_the_public_error(self):
        for at in ("9999-12-31T23:59:59-23:59", "0001-01-01T00:00:00+23:59", "2026-10-15T03:00:00+24:00"):
            with self.subTest(at=at), self.assertRaises(ObservationRefused):
                normalize_host_observation({"source": "host.proc", "at": at})


if __name__ == "__main__":
    unittest.main()


class RunnerFloor(unittest.TestCase):
    """G254 review: the execution clock goes through the same plausibility floor, before the factory."""

    def test_an_implausible_execution_clock_is_refused_before_any_controller_exists(self):
        from datetime import datetime, timedelta, timezone
        from eidolon_core.maintenance_runner import run_maintenance_tick
        made = []
        raw = {"source": "host.proc", "at": "1970-01-01T00:00:00+00:00"}
        with self.assertRaises(ObservationRefused):
            run_maintenance_tick(raw, now=datetime(1970, 1, 1, 0, 0, 5, tzinfo=timezone.utc),
                                 expected_source="host.proc", max_observation_age=timedelta(minutes=5),
                                 max_load_age=timedelta(minutes=2), make_maintenance=lambda: made.append(1))
        self.assertEqual(made, [])

    def test_an_epoch_boot_sentinel_reaches_the_controller_as_just_now(self):
        from datetime import datetime, timedelta, timezone
        from eidolon_core.maintenance_runner import run_maintenance_tick
        seen = []

        class Engine:
            def tick(self, **kwargs):
                seen.append(kwargs)
                return "DEFERRED"
        now = datetime(2026, 10, 15, 3, 0, 30, tzinfo=timezone.utc)
        raw = {"source": "host.proc", "at": "2026-10-15T03:00:00+00:00", "boot_at": "1970-01-01T00:00:00+00:00",
               "last_activity": "2026-10-15T01:00:00+00:00",
               "load": {"observed_at": "2026-10-15T03:00:00+00:00", "ratio": 0.1, "limit": 0.7}}
        result = run_maintenance_tick(raw, now=now, expected_source="host.proc",
                                      max_observation_age=timedelta(minutes=5), max_load_age=timedelta(minutes=2),
                                      make_maintenance=Engine)
        self.assertEqual(seen[0]["boot_at"], now)                       # recent boot: the window defers
        self.assertIn("BOOT_AT_IMPLAUSIBLE", result.observation.notes)
