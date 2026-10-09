# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_media_resources.py
# Description : Réservations média : concurrence, coupures, stockage et CLI
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
from contextlib import redirect_stderr, redirect_stdout
import io
import json
import multiprocessing
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from eidolon_core.media_agents import MediaError, execute, inspect
from eidolon_core.media_backends import LocalMediaBackend
from eidolon_core.media_cli import main
from eidolon_core.media_preflight import preflight, render_preflight
from eidolon_core.media_resources import ResourcePool, configured, initialize
from eidolon_core.media_setup import check_configuration
from eidolon_core.media_status import render_job
from tests.test_media_agents import PNG, config, request


def contend(root, pool_id, barrier, output, number):
    pool = ResourcePool(root, pool_id)
    barrier.wait(timeout=10)
    try:
        value = pool.reserve("media-" + f"{number:032x}", "image.create")
        output.put(("RESERVED", value["job_id"]))
    except MediaError as exc:
        output.put((exc.code, None))


class ResourceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.path = self.root / "pool"
        self.marker = initialize(self.path)
        self.pool = ResourcePool(self.path, self.marker["pool_id"])
        self.cfg = config()
        self.cfg["resource_pool"] = {"root": str(self.path), "pool_id": self.marker["pool_id"]}

    def reserve(self):
        return self.pool.reserve("media-" + "1" * 32, "image.create")

    def test_lifecycle_exact_lease_release_no_reuse_and_bounded_audit(self):
        self.assertEqual(self.pool.inspect()["state"], "AVAILABLE")
        a = self.reserve()
        with self.assertRaisesRegex(MediaError, "RESOURCE_RESERVED"):
            self.reserve()
        with self.assertRaisesRegex(MediaError, "RESOURCE_RELEASE_REVIEW_REQUIRED"):
            self.pool.release(a["lease_id"], reason="unchecked")
        with self.assertRaisesRegex(MediaError, "RESOURCE_RESERVATION_MISMATCH"):
            self.pool.release("mrl-" + "0" * 32, reviewed_idle=True, reason="checked")
        for reason in ("", "x" * 501, "line\nbreak", "\x1b[31m", "\ud800"):
            with self.subTest(reason=repr(reason)), self.assertRaises(MediaError):
                self.pool.release(a["lease_id"], reviewed_idle=True, reason=reason)
        released = self.pool.release(a["lease_id"], reviewed_idle=True, reason="synthetic engine reviewed")
        self.assertFalse(released["engine_idle_verified"])
        b = self.reserve()
        self.assertNotEqual(a["lease_id"], b["lease_id"])
        with self.assertRaisesRegex(MediaError, "RESOURCE_RESERVATION_MISMATCH"):
            self.pool.release(a["lease_id"], reviewed_idle=True, reason="stale operator tab")
        report = self.pool.inspect()
        self.assertEqual(report["current"]["lease_id"], b["lease_id"])
        self.assertEqual(report["last_release"]["lease_id"], a["lease_id"])
        self.assertFalse(report["automatic_release"])
        self.assertFalse(report["execution_authorized"])

    def test_eight_processes_can_only_reserve_one_slot(self):
        ctx = multiprocessing.get_context("fork")
        barrier, output = ctx.Barrier(8), ctx.Queue()
        children = [ctx.Process(target=contend, args=(str(self.path), self.marker["pool_id"], barrier, output, i))
                    for i in range(8)]
        try:
            for child in children:
                child.start()
            outcomes = [output.get(timeout=15) for _ in children]
            for child in children:
                child.join(5)
                self.assertEqual(child.exitcode, 0)
            accepted = [job for status, job in outcomes if status == "RESERVED"]
            self.assertEqual(len(accepted), 1, outcomes)
            self.assertTrue(all(s in {"RESERVED", "RESOURCE_RESERVED", "RESOURCE_POOL_BUSY"} for s, _ in outcomes))
            self.assertEqual(self.pool.inspect()["current"]["job_id"], accepted[0])
        finally:
            for child in children:
                if child.is_alive():
                    child.kill()
                child.join()
            output.close()

    def test_generation_and_analysis_hold_slot_until_explicit_release(self):
        image = self.root / "image.png"
        image.write_bytes(PNG)
        for op in ("create", "analyze"):
            calls = []
            def response(*args):
                calls.append(args)
                return ({"prompt_id": "fixture"} if op == "create" else
                        {"model": "test-vision:local", "done": True, "done_reason": "stop", "response": "fixture"})
            backend = LocalMediaBackend(self.cfg, transport=response)
            value = execute(request(operation=op, source=str(image) if op == "analyze" else None),
                            self.cfg, self.root / op, backend=backend)
            self.assertEqual(len(calls), 1)
            self.assertEqual(value["resource_reservation"]["job_id"], value["id"])
            self.assertEqual(self.pool.inspect()["current"]["job_id"], value["id"])
            with self.assertRaisesRegex(MediaError, "RESOURCE_RESERVED"):
                execute(request(), self.cfg, self.root / (op + "-blocked"), backend=backend)
            self.assertEqual(len(calls), 1)
            self.assertFalse((self.root / (op + "-blocked")).exists())
            self.pool.release(value["resource_reservation"]["lease_id"], reviewed_idle=True, reason="synthetic completion")

    def test_backend_failure_keeps_reservation_and_job_uncertainty(self):
        calls = []
        def lost(*args):
            calls.append(args)
            raise TimeoutError("response lost")
        with self.assertRaisesRegex(MediaError, "REVIEW_REQUIRED"):
            execute(request(), self.cfg, self.root / "lost", backend=LocalMediaBackend(self.cfg, transport=lost))
        self.assertEqual(len(calls), 1)
        value = inspect(self.root / "lost")
        self.assertEqual(value["state"], "REVIEW_REQUIRED")
        self.assertEqual(value["phase"], "QUEUE_SUBMITTING")
        self.assertEqual(self.pool.inspect()["current"]["lease_id"], value["resource_reservation"]["lease_id"])

    def test_abrupt_process_exit_cannot_release_or_hide_reservation(self):
        # Kill the actual worker after its durable phase, no Python finally/atexit.
        script = '''import json,os,sys
from eidolon_core.media_agents import execute
class Backend:
 def plan(self,*a):return {"adapter":"fixture"}
 def run(self,*a,progress):
  progress("QUEUE_SUBMITTING",{})
  os._exit(77)
execute(json.loads(sys.argv[1]),json.loads(sys.argv[2]),sys.argv[3],backend=Backend())
'''
        child = subprocess.run([sys.executable, "-c", script, json.dumps(request()), json.dumps(self.cfg),
                                str(self.root / "killed")], capture_output=True, timeout=10)
        self.assertEqual(child.returncode, 77, child.stderr)
        value = inspect(self.root / "killed")
        self.assertEqual(value["observed_state"], "REVIEW_REQUIRED")
        self.assertEqual(value["phase"], "QUEUE_SUBMITTING")
        reopened = ResourcePool(self.path, self.marker["pool_id"])
        self.assertEqual(reopened.inspect()["current"]["job_id"], value["id"])
        with self.assertRaisesRegex(MediaError, "RESOURCE_RESERVED"):
            reopened.reserve("media-" + "2" * 32, "video.create")

    def test_storage_failure_after_admission_stays_visible_without_network(self):
        backend = LocalMediaBackend(self.cfg, transport=lambda *a: self.fail("network"))
        with patch("eidolon_core.media_agents.write_record", side_effect=OSError("disk unavailable")):
            with self.assertRaises(OSError):
                execute(request(), self.cfg, self.root / "disk", backend=backend)
        self.assertEqual(self.pool.inspect()["state"], "RESERVED")
        self.assertFalse((self.root / "disk/job.json").exists())

    def test_bad_plan_and_existing_job_do_not_take_reservation(self):
        with self.assertRaises(MediaError):
            execute(request(), {"resource_pool": self.cfg["resource_pool"]}, self.root / "bad")
        existing = self.root / "existing"
        existing.mkdir()
        with self.assertRaises(FileExistsError):
            execute(request(), self.cfg, existing)
        self.assertEqual(self.pool.inspect()["state"], "AVAILABLE")

    def test_private_paths_links_hardlinks_and_foreign_identity_refused(self):
        parent_alias = self.root / "parent-alias"
        parent_alias.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(OSError):
            initialize(parent_alias / "unexpected")
        self.assertFalse((self.root / "unexpected").exists())
        with self.assertRaises(FileExistsError):
            initialize(self.path)
        with self.assertRaisesRegex(MediaError, "RESOURCE_POOL_MISMATCH"):
            ResourcePool(self.path, "mrp-" + "0" * 32)
        self.path.chmod(0o755)
        with self.assertRaises(MediaError):
            self.pool.inspect()
        self.path.chmod(0o700)
        alias = self.root / "alias"; alias.symlink_to(self.path, target_is_directory=True)
        with self.assertRaises(OSError):
            ResourcePool(alias, self.marker["pool_id"])
        for name in ("pool.json", "writer.lock"):
            path = self.path / name
            link = self.root / (name + ".link")
            os.link(path, link)
            with self.assertRaises(MediaError):
                self.pool.inspect()
            link.unlink()
            saved = path.read_bytes()
            path.unlink(); path.symlink_to(self.root / "foreign")
            with self.assertRaises(OSError):
                self.pool.inspect()
            self.assertFalse((self.root / "foreign").exists())
            path.unlink(); path.write_bytes(saved); path.chmod(0o600)
            self.pool = ResourcePool(self.path, self.marker["pool_id"])

    def test_replacement_corruption_and_missing_files_are_not_repaired(self):
        other = self.root / "other"; initialize(other)
        original = self.path / "pool.json"
        shutil.copyfile(other / "pool.json", original)
        before = original.read_bytes()
        with self.assertRaisesRegex(MediaError, "RESOURCE_POOL_MISMATCH"):
            self.reserve()
        self.assertEqual(original.read_bytes(), before)
        original.write_bytes(b'{}')
        with self.assertRaisesRegex(MediaError, "INVALID_RESOURCE_POOL"):
            self.pool.inspect()
        original.unlink()
        with self.assertRaises(FileNotFoundError):
            self.pool.inspect()
        self.assertFalse(original.exists())
        original.write_text(json.dumps(self.marker)); original.chmod(0o600)
        moved = self.root / "moved"
        self.path.rename(moved)
        shutil.copytree(moved, self.path)
        with self.assertRaisesRegex(MediaError, "RESOURCE_POOL_CHANGED"):
            self.pool.inspect()

    def test_inspection_config_and_human_output_have_no_effects(self):
        lease = self.reserve()
        before = (self.path / "pool.json").read_bytes()
        with patch("socket.socket", side_effect=AssertionError("network")), patch(
                "subprocess.run", side_effect=AssertionError("process")):
            report = check_configuration(self.cfg, require=["image.create"])
            self.assertEqual(report["state"], "CONFIGURED_SCOPE")
            self.assertEqual(report["resource_pool"]["state"], "RESERVED")
            pre = preflight(request(), self.cfg)
            self.assertEqual(pre["resource_pool"]["state"], "RESERVED")
            self.assertIn("serait bloqué", render_preflight(pre))
            out = io.StringIO()
            with redirect_stdout(out):
                rc = main(["resource-inspect", "--root", str(self.path), "--pool-id", self.marker["pool_id"],
                           "--format", "human"])
            self.assertEqual(rc, 0)
            self.assertIn(lease["lease_id"], out.getvalue())
            self.assertNotIn("[OK]", out.getvalue())
        self.assertEqual((self.path / "pool.json").read_bytes(), before)
        job = {"schema": "media-job/1", "resource_reservation": {"pool_id": "\x1b[31m", "lease_id": []}}
        self.assertNotIn("\x1b", render_job(job))
        self.assertIn("non reconnus", render_job(job))

    def test_cli_exact_release_and_unconfigured_compatibility(self):
        lease = self.reserve()
        out, err = io.StringIO(), io.StringIO()
        args = ["resource-release", "--root", str(self.path), "--pool-id", self.marker["pool_id"],
                "--lease-id", lease["lease_id"], "--reviewed-idle", "--reason", "synthetic operator review"]
        with redirect_stdout(out), redirect_stderr(err):
            self.assertEqual(main(args), 0)
        self.assertEqual(json.loads(out.getvalue())["state"], "RELEASED_BY_OPERATOR")
        self.assertEqual(err.getvalue(), "")
        with redirect_stdout(io.StringIO()), redirect_stderr(err):
            self.assertEqual(main(args), 2)
        self.assertIn("RESOURCE_RESERVATION_MISMATCH", err.getvalue())
        self.assertIsNone(configured({}))
        for item in (None, {}, {"root": str(self.path), "pool_id": "bad"}):
            with self.assertRaises(MediaError):
                configured({"resource_pool": item})
        legacy = config()
        value = execute(request(), legacy, self.root / "legacy", backend=LocalMediaBackend(
            legacy, transport=lambda *a: {"prompt_id": "legacy"}))
        self.assertNotIn("resource_reservation", value)


if __name__ == "__main__":
    unittest.main()
