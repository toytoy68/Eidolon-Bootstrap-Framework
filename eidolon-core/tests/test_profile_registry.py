# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_profile_registry.py
# Description : Import privé, concurrence et interruptions du registre préparatoire G170-A
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
import contextlib
import io
import json
import multiprocessing
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch

from eidolon_core.contracts import ContractError, digest
from eidolon_core import profile_registry as registry
from tests.test_profile_plan import fixture


def _race(plan, directory, barrier, results):
    barrier.wait(timeout=10)
    try:
        results.put(registry.prepare_registry(plan, directory, apply=True)["operation"])
    except ContractError as exc:
        results.put(str(exc))


def _crash(plan, directory, phase):
    def die(*args, **kwargs):
        os._exit(47)
    if phase == "before_replace":
        with patch.object(registry.os, "replace", die):
            registry.prepare_registry(plan, directory, apply=True)
    else:
        original = os.fsync
        def sync(fd):
            if stat.S_ISDIR(os.fstat(fd).st_mode):
                die()
            return original(fd)
        with patch.object(registry.os, "fsync", sync):
            registry.prepare_registry(plan, directory, apply=True)


class ProfileRegistryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.destination = self.root / "registry"
        self.destination.mkdir(mode=0o700)
        self.plan = self.root / "plan.json"
        self.write(self.plan, fixture())

    def write(self, path, value):
        path.write_text(json.dumps(value), encoding="utf-8")
        path.chmod(0o600)

    def prepare(self, **kwargs):
        return registry.prepare_registry(self.plan, self.destination, **kwargs)

    def test_dry_run_is_default_and_has_no_filesystem_side_effect(self):
        before = self.plan.read_bytes()
        result = self.prepare()
        self.assertEqual(result["operation"], "dry_run")
        self.assertTrue(result["would_import"])
        self.assertFalse(result["runtime_active"])
        self.assertEqual(list(self.destination.iterdir()), [])
        self.assertEqual(self.plan.read_bytes(), before)

    def test_explicit_import_is_private_and_remains_inactive(self):
        source = self.plan.read_bytes()
        result = self.prepare(apply=True)
        self.assertEqual(result["operation"], "imported")
        self.assertEqual(result["status"], "PREPARED_NOT_ACTIVE")
        self.assertEqual((result["profiles"], result["admins"], result["casual"]), (3, 1, 2))
        self.assertFalse(result["runtime_active"])
        self.assertEqual(self.plan.read_bytes(), source)
        self.assertEqual({p.name for p in self.destination.iterdir()}, {registry.SNAPSHOT, registry.LOCK})
        for path in self.destination.iterdir():
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        snapshot = json.loads((self.destination / registry.SNAPSHOT).read_text())
        self.assertEqual(snapshot["plan"], fixture())
        self.assertEqual(snapshot["plan_sha256"], digest(fixture()))
        for word in ["Operator", "Alex", "Visitor", "user-001", str(self.root), snapshot["plan_sha256"]]:
            self.assertNotIn(word, json.dumps(result))

    def test_same_plan_retry_does_not_rewrite_snapshot(self):
        self.prepare(apply=True)
        path = self.destination / registry.SNAPSHOT
        before = (path.read_bytes(), path.stat().st_ino, path.stat().st_mtime_ns)
        result = self.prepare(apply=True)
        self.assertEqual(result["operation"], "already_prepared")
        self.assertEqual((path.read_bytes(), path.stat().st_ino, path.stat().st_mtime_ns), before)
        self.assertFalse(self.prepare()["would_import"])

    def test_changed_plan_refused_without_overwriting(self):
        self.prepare(apply=True)
        path = self.destination / registry.SNAPSHOT
        before = path.read_bytes()
        changed = fixture(); changed["profiles"][1]["display_name"] = "Another Visitor"
        self.write(self.plan, changed)
        for apply in (False, True):
            with self.subTest(apply=apply), self.assertRaisesRegex(ContractError, "PROFILE_REGISTRY_CONFLICT"):
                self.prepare(apply=apply)
        self.assertEqual(path.read_bytes(), before)

    def test_invalid_plan_never_creates_a_lock_or_snapshot(self):
        changed = fixture(); changed["policy"]["capture_enabled"] = True
        self.write(self.plan, changed)
        with self.assertRaises(ContractError):
            self.prepare(apply=True)
        self.assertEqual(list(self.destination.iterdir()), [])

    def test_duplicate_json_keys_and_nonfinite_constants_are_rejected(self):
        for raw in ['{"schema":"a","schema":"b"}', '{"x": NaN}', '{"x": Infinity}', '[' * 2000]:
            with self.subTest(raw=raw[:30]):
                self.plan.write_text(raw)
                with self.assertRaisesRegex(ContractError, "PROFILE_JSON_INVALID"):
                    self.prepare(apply=True)
        self.assertEqual(list(self.destination.iterdir()), [])

    def test_bounded_input(self):
        self.plan.write_bytes(b" " * (registry.MAX_PLAN_BYTES + 1))
        with self.assertRaisesRegex(ContractError, "PROFILE_FILE_TOO_LARGE"):
            self.prepare()

    def test_source_must_be_private_owned_regular_single_link(self):
        self.plan.chmod(0o644)
        with self.assertRaisesRegex(ContractError, "PROFILE_FILE_NOT_PRIVATE"):
            self.prepare()
        self.plan.chmod(0o600)
        os.link(self.plan, self.root / "hardlink")
        with self.assertRaisesRegex(ContractError, "PROFILE_FILE_NOT_PRIVATE"):
            self.prepare()

    def test_fifo_source_is_refused_without_blocking(self):
        self.plan.unlink(); os.mkfifo(self.plan, 0o600)
        with self.assertRaisesRegex(ContractError, "PROFILE_FILE_NOT_PRIVATE"):
            self.prepare()

    def test_symlink_file_and_directory_components_are_refused(self):
        link = self.root / "plan-link.json"; link.symlink_to(self.plan)
        parent_link = self.root / "linked-root"; parent_link.symlink_to(self.root, target_is_directory=True)
        cases = [(link, self.destination), (parent_link / self.plan.name, self.destination),
                 (self.plan, parent_link / self.destination.name)]
        for plan, destination in cases:
            with self.subTest(plan=plan, destination=destination), self.assertRaises(ContractError):
                registry.prepare_registry(plan, destination, apply=True)
        self.assertEqual(list(self.destination.iterdir()), [])

    def test_nonprivate_directory_is_refused_without_chmod(self):
        for directory in (self.destination, self.root):
            directory.chmod(0o755)
            with self.subTest(directory=directory), self.assertRaisesRegex(ContractError, "PROFILE_DIRECTORY_NOT_PRIVATE"):
                self.prepare(apply=True)
            self.assertEqual(stat.S_IMODE(directory.stat().st_mode), 0o755)
            directory.chmod(0o700)

    def test_missing_destination_is_not_created(self):
        self.destination.rmdir()
        with self.assertRaisesRegex(ContractError, "PROFILE_REGISTRY_IO"):
            self.prepare(apply=True)
        self.assertFalse(self.destination.exists())

    def test_existing_symlink_and_corrupt_snapshot_are_not_replaced(self):
        target = self.root / "untouched"; target.write_text("untouched")
        path = self.destination / registry.SNAPSHOT; path.symlink_to(target)
        with self.assertRaises(ContractError):
            self.prepare(apply=True)
        self.assertTrue(path.is_symlink()); self.assertEqual(target.read_text(), "untouched")
        path.unlink(); self.write(path, {"not": "a registry"})
        before = path.read_bytes()
        with self.assertRaisesRegex(ContractError, "PROFILE_REGISTRY_FIELDS"):
            self.prepare(apply=True)
        self.assertEqual(path.read_bytes(), before)

    def test_snapshot_is_revalidated_not_trusted_by_filename(self):
        self.prepare(apply=True)
        path = self.destination / registry.SNAPSHOT
        original = json.loads(path.read_text())
        for key, value in [("runtime_active", True), ("revision", True), ("revision", 2),
                           ("status", "ACTIVE"), ("plan_sha256", "0" * 64),
                           ("prepared_at", "2026-10-12T18:00:00"), ("grants", ["admin"])]:
            changed = dict(original); changed[key] = value
            self.write(path, changed)
            with self.subTest(key=key), self.assertRaises(ContractError):
                registry.inspect_registry(self.destination)

    def test_inspection_of_absent_registry_does_not_create_files(self):
        with self.assertRaisesRegex(ContractError, "PROFILE_REGISTRY_MISSING"):
            registry.inspect_registry(self.destination)
        self.assertEqual(list(self.destination.iterdir()), [])

    def test_inspection_does_not_need_or_create_lock(self):
        self.prepare(apply=True)
        (self.destination / registry.LOCK).unlink()
        self.assertEqual(registry.inspect_registry(self.destination)["status"], "PREPARED_NOT_ACTIVE")
        self.assertEqual([p.name for p in self.destination.iterdir()], [registry.SNAPSHOT])

    def test_short_writes_are_completed(self):
        original = os.write
        with patch.object(registry.os, "write", lambda fd, raw: original(fd, raw[:7])):
            self.prepare(apply=True)
        self.assertEqual(registry.inspect_registry(self.destination)["profiles"], 3)

    def test_failed_write_removes_only_its_temporary_file(self):
        unrelated = self.destination / "operator-note"; unrelated.write_text("keep")
        with patch.object(registry.os, "write", side_effect=OSError("private path must not leak")):
            with self.assertRaisesRegex(ContractError, "^PROFILE_REGISTRY_IO$"):
                self.prepare(apply=True)
        self.assertFalse((self.destination / registry.SNAPSHOT).exists())
        self.assertEqual(unrelated.read_text(), "keep")
        self.assertEqual(list(self.destination.glob(".profiles-*.tmp")), [])

    def test_failed_file_sync_prevents_publication(self):
        with patch.object(registry.os, "fsync", side_effect=OSError("disk failure")):
            with self.assertRaisesRegex(ContractError, "PROFILE_REGISTRY_IO"):
                self.prepare(apply=True)
        self.assertFalse((self.destination / registry.SNAPSHOT).exists())

    def test_directory_sync_failure_reports_uncertainty_and_retry_confirms(self):
        original = os.fsync
        def sync(fd):
            if stat.S_ISDIR(os.fstat(fd).st_mode):
                raise OSError("directory sync failure")
            return original(fd)
        with patch.object(registry.os, "fsync", sync):
            with self.assertRaisesRegex(ContractError, "PROFILE_REGISTRY_COMMIT_UNCERTAIN"):
                self.prepare(apply=True)
        self.assertEqual(registry.inspect_registry(self.destination)["profiles"], 3)
        self.assertEqual(self.prepare(apply=True)["operation"], "already_prepared")

    def test_real_lock_contention_refuses_immediately(self):
        with registry._directory(self.destination) as fd, registry._writer_lock(fd):
            with self.assertRaisesRegex(ContractError, "PROFILE_REGISTRY_BUSY"):
                self.prepare(apply=True)
        self.assertFalse((self.destination / registry.SNAPSHOT).exists())

    def test_lock_symlink_is_not_followed(self):
        (self.destination / registry.LOCK).symlink_to(self.plan)
        before = self.plan.read_bytes()
        with self.assertRaises(ContractError):
            self.prepare(apply=True)
        self.assertEqual(self.plan.read_bytes(), before)

    def test_umask_is_preserved(self):
        old = os.umask(0o077)
        try:
            self.prepare(apply=True)
            self.assertEqual(os.umask(0o077), 0o077)
        finally:
            os.umask(old)

    def test_two_processes_cannot_publish_two_different_plans(self):
        second = self.root / "second.json"
        changed = fixture(); changed["profiles"][1]["display_name"] = "Changed"
        self.write(second, changed)
        ctx = multiprocessing.get_context("fork")
        barrier = ctx.Barrier(2); results = ctx.Queue()
        workers = [ctx.Process(target=_race, args=(p, self.destination, barrier, results))
                   for p in (self.plan, second)]
        try:
            for worker in workers: worker.start()
            for worker in workers:
                worker.join(15)
                self.assertEqual(worker.exitcode, 0)
            answers = [results.get(timeout=2) for _ in workers]
            self.assertEqual(answers.count("imported"), 1, answers)
            self.assertTrue(set(answers) <= {"imported", "PROFILE_REGISTRY_BUSY", "PROFILE_REGISTRY_CONFLICT"})
            self.assertEqual(registry.inspect_registry(self.destination)["profiles"], 3)
        finally:
            for worker in workers:
                if worker.is_alive(): worker.terminate(); worker.join(5)
            results.close(); results.join_thread()

    def test_process_death_before_replace_leaves_no_partial_registry_and_blocks_retry(self):
        self.run_crash("before_replace")
        self.assertFalse((self.destination / registry.SNAPSHOT).exists())
        self.assertEqual(len(list(self.destination.glob(".profiles-*.tmp"))), 1)
        for action in (self.prepare, lambda: self.prepare(apply=True),
                       lambda: registry.inspect_registry(self.destination)):
            with self.assertRaisesRegex(ContractError, "PROFILE_REGISTRY_PENDING"):
                action()

    def test_process_death_after_replace_leaves_complete_retriable_snapshot(self):
        self.run_crash("after_replace")
        self.assertEqual(registry.inspect_registry(self.destination)["profiles"], 3)
        self.assertEqual(self.prepare(apply=True)["operation"], "already_prepared")

    def run_crash(self, phase):
        worker = multiprocessing.get_context("fork").Process(target=_crash,
                                                             args=(self.plan, self.destination, phase))
        worker.start()
        try:
            worker.join(10)
            self.assertEqual(worker.exitcode, 47)
        finally:
            if worker.is_alive(): worker.terminate(); worker.join(5)

    def test_cli_output_is_json_without_private_identities_or_paths(self):
        for tail in ([], ["--apply"]):
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = registry.main(["prepare", "--plan", str(self.plan),
                                      "--directory", str(self.destination), *tail])
            self.assertEqual(code, 0)
            result = json.loads(output.getvalue())
            self.assertTrue(result["ok"]); self.assertFalse(result["runtime_active"])
            self.assertNotIn("Operator", output.getvalue()); self.assertNotIn(str(self.root), output.getvalue())
        self.plan.chmod(0o644)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = registry.main(["prepare", "--plan", str(self.plan), "--directory", str(self.destination)])
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(output.getvalue())["error"], "PROFILE_FILE_NOT_PRIVATE")


if __name__ == "__main__":
    unittest.main()
