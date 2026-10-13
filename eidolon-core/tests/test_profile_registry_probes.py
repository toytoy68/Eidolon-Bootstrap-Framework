# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_profile_registry_probes.py
# Description : Contre-revue Claude du registre G184 : concurrence, idempotence, résidus, non-activation, non-divulgation
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Independent probes (Claude, G185 item 2). Positive tests pin what holds; R1 and R2 were findings, fixed in dace7e7. profile_registry.py itself is not modified (Codex's file)."""
import contextlib
import fcntl
import io
import json
import multiprocessing
import os
from pathlib import Path
import re
import tempfile
import unittest

from eidolon_core import profile_registry as registry
from eidolon_core.contracts import ContractError
from tests.test_profile_plan import fixture

SRC = Path(__file__).resolve().parents[1] / "src" / "eidolon_core"
PRIVATE = ("Operator", "Alex", "Visitor", "user-001", "user-002", "user-003")


def _apply(plan, directory, barrier, results):
    barrier.wait(timeout=20)
    try:
        results.put(registry.prepare_registry(plan, directory, apply=True)["operation"])
    except ContractError as exc:
        results.put(str(exc))


def _cli(*argv):
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        code = registry.main(list(argv))
    return code, output.getvalue()


class RegistryProbes(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.destination = self.root / "registry"
        self.destination.mkdir(mode=0o700)
        self.plan = self.root / "plan.json"
        self.write(self.plan, fixture())

    def write(self, path, value, **dump):
        path.write_text(json.dumps(value, **dump), encoding="utf-8")
        path.chmod(0o600)

    def test_eight_concurrent_imports_publish_exactly_once(self):
        context = multiprocessing.get_context("fork")
        barrier, results = context.Barrier(8), context.Queue()
        workers = [context.Process(target=_apply, args=(str(self.plan), str(self.destination), barrier, results))
                   for _ in range(8)]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join(30)
        outcomes = sorted(results.get(timeout=5) for _ in workers)
        self.assertEqual(outcomes.count("imported"), 1, outcomes)
        self.assertTrue(set(outcomes) <= {"imported", "already_prepared", "PROFILE_REGISTRY_BUSY"}, outcomes)
        self.assertEqual(sorted(os.listdir(self.destination)), [".profiles.lock", "profiles.json"])
        self.assertEqual(registry.inspect_registry(self.destination)["profiles"], 3)

    def test_same_plan_with_other_key_order_and_spacing_is_the_same_plan(self):
        registry.prepare_registry(self.plan, self.destination, apply=True)
        before = (self.destination / "profiles.json").read_bytes()
        reordered = json.loads(self.plan.read_text())
        reordered = {key: reordered[key] for key in reversed(list(reordered))}
        self.write(self.plan, reordered, indent=3)
        self.assertEqual(registry.prepare_registry(self.plan, self.destination, apply=True)["operation"],
                         "already_prepared")
        self.assertEqual((self.destination / "profiles.json").read_bytes(), before)

    def test_no_runtime_module_loads_the_registry(self):
        users = [p.name for p in SRC.glob("*.py") if p.name != "profile_registry.py"
                 and re.search(r"\bprofile_registry\b", p.read_text(encoding="utf-8"))]
        self.assertEqual(users, [])
        registry.prepare_registry(self.plan, self.destination, apply=True)
        snapshot = json.loads((self.destination / "profiles.json").read_text())
        self.assertEqual((snapshot["status"], snapshot["runtime_active"]), ("PREPARED_NOT_ACTIVE", False))
        policy = snapshot["plan"]["policy"]
        self.assertEqual((policy["biometric_authorization"], policy["capture_enabled"]), (False, False))

    def test_every_cli_outcome_stays_free_of_identities_paths_and_digest(self):
        outputs = [_cli("prepare", "--plan", str(self.plan), "--directory", str(self.destination), "--apply"),
                   _cli("inspect", "--directory", str(self.destination))]
        other = fixture()
        other["profiles"][1]["display_name"] = "Visitor C"
        changed = self.root / "other.json"
        self.write(changed, other)
        outputs.append(_cli("prepare", "--plan", str(changed), "--directory", str(self.destination)))  # conflict
        (self.destination / ".profiles-dead.tmp").write_text("residue")
        outputs.append(_cli("inspect", "--directory", str(self.destination)))                           # pending
        digest = json.loads((self.destination / "profiles.json").read_text())["plan_sha256"]
        for code, text in outputs:
            json.loads(text)
            for secret in PRIVATE + (str(self.root), digest):
                self.assertNotIn(secret, text)
        self.assertEqual([json.loads(t).get("error") for _, t in outputs[2:]],
                         ["PROFILE_REGISTRY_CONFLICT", "PROFILE_REGISTRY_PENDING"])

    def test_extreme_profile_ids_round_trip_and_stay_private(self):
        """G195: the shared PROFILE_ID grammar (1 and 64 characters) goes through import and inspection;
        the ids never appear in any output."""
        plan = fixture()
        short, long = "a", "b" + "-" * 62 + "z"
        plan["profiles"][1]["profile_id"], plan["profiles"][2]["profile_id"] = short, long
        self.write(self.plan, plan)
        outputs = [_cli("prepare", "--plan", str(self.plan), "--directory", str(self.destination), "--apply"),
                   _cli("inspect", "--directory", str(self.destination))]
        stored = json.loads((self.destination / "profiles.json").read_text())["plan"]["profiles"]
        self.assertEqual([p["profile_id"] for p in stored][1:], [short, long])
        for code, text in outputs:
            self.assertEqual(code, 0)
            self.assertNotIn(long, text)
            self.assertNotIn('"a"', text)
        for bad in ("", "c" * 65, "1abc", "Abc"):
            plan["profiles"][1]["profile_id"] = bad
            other = self.root / "bad.json"
            self.write(other, plan)
            code, text = _cli("prepare", "--plan", str(other), "--directory", str(self.destination))
            self.assertEqual((code, json.loads(text)["ok"]), (1, False), bad)
            self.assertNotIn(bad or "\"\"", text if bad else "")

    def test_a_crash_residue_blocks_import_until_reviewed_then_retry_is_identical(self):
        (self.destination / ".profiles-dead.tmp").write_text("residue")
        with self.assertRaises(ContractError) as caught:
            registry.prepare_registry(self.plan, self.destination, apply=True)
        self.assertEqual(str(caught.exception), "PROFILE_REGISTRY_PENDING")
        self.assertFalse((self.destination / "profiles.json").exists())
        (self.destination / ".profiles-dead.tmp").unlink()                 # operator reviewed it
        first = registry.prepare_registry(self.plan, self.destination, apply=True)
        again = registry.prepare_registry(self.plan, self.destination, apply=True)
        self.assertEqual((first["operation"], again["operation"]), ("imported", "already_prepared"))

    def test_inspect_during_an_import_in_flight_is_not_reported_as_a_crash_residue(self):
        """Claude finding R1, fixed in dace7e7 (core-patches/0001), now a regression test: inspect does not look at the writer lock, so a temporary file of a LIVE import
        is reported as PROFILE_REGISTRY_PENDING, whose documented remedy is to examine and remove a crash
        residue. Expected: a transient BUSY (e.g. a non-blocking shared try-lock on an existing lock file)."""
        registry.prepare_registry(self.plan, self.destination, apply=True)
        lock = os.open(self.destination / ".profiles.lock", os.O_RDWR)
        self.addCleanup(os.close, lock)
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)                 # a writer is publishing right now
        (self.destination / ".profiles-live.tmp").write_text("")
        with self.assertRaises(ContractError) as caught:
            registry.inspect_registry(self.destination)
        self.assertEqual(str(caught.exception), "PROFILE_REGISTRY_BUSY")

    def test_cli_turns_every_invalid_path_into_a_json_error(self):
        """Claude finding R2 (minor), fixed in dace7e7 (core-patches/0001), now a regression test: a path os.open rejects with ValueError (embedded NUL, reachable through
        the Python API, not a shell) escapes main() as a traceback instead of the JSON error contract."""
        code, text = _cli("inspect", "--directory", str(self.root) + "/a\x00b")
        self.assertEqual((code, json.loads(text)["ok"]), (1, False))


if __name__ == "__main__":
    unittest.main()
