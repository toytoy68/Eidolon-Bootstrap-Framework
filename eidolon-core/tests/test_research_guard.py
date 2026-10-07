# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_research_guard.py
# Description : Crashs réels, exclusion, revue et transactions de recherche
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
from contextlib import contextmanager
import json
import os
from pathlib import Path
import selectors
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from eidolon_core.contracts import digest
from eidolon_core.query_cleanup import clean_query
from eidolon_core.research import AccessFailure, ResearchCoordinator
from eidolon_core.research_guard import GuardError, ResearchGuard
from eidolon_core.research_pauses import ResearchPauses, provider_scope
from tests.test_research import Clock, Provider, Reader, dns, hit

DESC = {"query_sha256": "a"*64, "policy_id": "synthetic/1", "providers": ["p"]}
RESULT = {"status": "NO_READABLE_SOURCE"}

CHILD = '''import os,sys
from pathlib import Path
from eidolon_core.research import AccessFailure,ResearchCoordinator
from eidolon_core.research_guard import ResearchGuard
from eidolon_core.research_pauses import ResearchPauses
from tests.test_research import Provider,Reader,dns
root=Path(sys.argv[1]);stage=sys.argv[2]
guard=ResearchGuard(root/'guard')
if stage=='before_contact':
 guard.execute(lambda:os._exit(41),descriptor={'query_sha256':'a'*64,'policy_id':'synthetic/1','providers':['p']})
class P(Provider):
 def search(self,query,limit):
  with (root/'contacts').open('a') as f:f.write('contact\\n')
  if stage=='during_contact':os._exit(41)
  if stage=='alive':
   print('READY',flush=True);sys.stdin.read(1);os._exit(41)
  raise AccessFailure('RATE_LIMITED',0)
class Pauses(ResearchPauses):
 def pause(self,*a,**kw):
  if stage=='before_pause':os._exit(41)
  result=super().pause(*a,**kw)
  if stage=='after_pause':os._exit(41)
  return result
c=ResearchCoordinator([P('p',[])],Reader(),resolver=dns,guard=guard,pauses=Pauses(root/'pauses.sqlite3'))
c.run('synthetic')
os._exit(42)
'''


class ResearchGuardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.clock = Clock(); self.clock.value = 1000
        self.guard = ResearchGuard(self.root / "guard", clock=self.clock)

    def execute(self, callback=lambda: RESULT):
        return self.guard.execute(callback, descriptor=DESC)

    def uncertain(self):
        with self.assertRaises(RuntimeError):
            self.execute(lambda: (_ for _ in ()).throw(RuntimeError("synthetic")))
        return self.guard.inspect()["runs"][-1]

    def resolve(self, record, **kw):
        return self.guard.resolve(record["id"], expected_revision=record["revision"],
                                  actor="fixture-operator", reason="accept uncertainty", **kw)

    @contextmanager
    def child(self, stage):
        p = subprocess.Popen([sys.executable, "-c", CHILD, str(self.root), stage],
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            yield p
        finally:
            if p.poll() is None:
                p.kill()
            p.communicate(timeout=5)

    def test_complete_run_has_atomic_receipt_and_survives_reopen(self):
        result = self.execute()
        info = result["research_guard"]
        self.assertEqual(info["state"], "COMPLETED")
        reopened = ResearchGuard(self.guard.directory)
        record = reopened.inspect()["runs"][0]
        self.assertEqual(record["report_sha256"], digest(RESULT))
        self.assertEqual(record["revision"], 2)
        self.assertEqual(record["id"], info["run_id"])
        self.assertFalse(reopened.inspect()["automatic_release"])

    def test_exception_leaves_uncertain_and_never_retries_callback(self):
        record = self.uncertain()
        self.assertEqual(record["observed_state"], "UNCERTAIN")
        reopened = ResearchGuard(self.guard.directory)
        with self.assertRaisesRegex(GuardError, "WEB_RESEARCH_UNCERTAIN"):
            reopened.execute(lambda: self.fail("callback retried"), descriptor=DESC)

    def test_review_preserves_unknown_and_sends_nothing(self):
        record = self.uncertain()
        result = self.resolve(record)
        self.assertFalse(result["request_sent"])
        self.assertFalse(result["authorizes_execution"])
        self.assertFalse(result["effect_known"])
        self.assertEqual(result["state"], "RESOLVED_UNKNOWN")
        with self.assertRaisesRegex(GuardError, "STALE_RESEARCH_RUN"):
            self.resolve(record)
        self.execute()
        self.assertEqual(len(self.guard.inspect()["runs"]), 2)

    def test_global_guard_blocks_unrelated_provider_until_review(self):
        self.uncertain()
        other = {**DESC, "providers": ["unrelated"]}
        with self.assertRaisesRegex(GuardError, "WEB_RESEARCH_UNCERTAIN"):
            self.guard.execute(lambda: self.fail("unrelated bypass"), descriptor=other)

    def test_crash_windows_block_reconstructed_coordinator(self):
        for stage, contacts in (("before_contact", 0), ("during_contact", 1), ("before_pause", 1), ("after_pause", 1)):
            with self.subTest(stage=stage), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                result = subprocess.run([sys.executable, "-c", CHILD, str(root), stage], capture_output=True, text=True, timeout=10)
                self.assertEqual(result.returncode, 41, result.stderr)
                g = ResearchGuard(root / "guard")
                provider = Provider("p", [hit()])
                pauses = ResearchPauses(root / "pauses.sqlite3")
                c = ResearchCoordinator([provider], Reader(), resolver=dns, guard=g, pauses=pauses)
                with self.assertRaisesRegex(GuardError, "WEB_RESEARCH_UNCERTAIN"):
                    c.run("synthetic")
                self.assertEqual(provider.calls, 0)
                observed = (root / "contacts").read_text().count("contact") if (root / "contacts").exists() else 0
                self.assertEqual(observed, contacts)
                self.assertEqual(g.inspect()["runs"][0]["observed_state"], "UNCERTAIN")
                self.assertEqual(pauses.active(provider_scope("p")) is not None, stage == "after_pause")

    def test_live_process_blocks_execution_review_and_constructor_then_becomes_uncertain(self):
        with self.child("alive") as child:
            with selectors.DefaultSelector() as selector:
                selector.register(child.stdout, selectors.EVENT_READ)
                self.assertTrue(selector.select(timeout=5), "child did not reach provider")
            self.assertEqual(child.stdout.readline().strip(), "READY")
            record = self.guard.inspect()["runs"][0]
            self.assertEqual(record["observed_state"], "IN_FLIGHT")
            for operation in (lambda: self.execute(lambda: self.fail("live callback")),
                              lambda: self.resolve(record), lambda: ResearchGuard(self.guard.directory)):
                with self.assertRaisesRegex(GuardError, "WEB_RESEARCH_IN_FLIGHT"):
                    operation()
            child.kill(); child.wait(timeout=5)
        self.assertEqual(self.guard.inspect()["runs"][0]["observed_state"], "UNCERTAIN")

    def test_intent_write_failure_prevents_callback(self):
        with self.guard._connection() as db:
            db.execute("CREATE TRIGGER fail BEFORE INSERT ON run_events BEGIN SELECT RAISE(ABORT,'SQL-SECRET'); END")
        with self.assertRaisesRegex(GuardError, "^RESEARCH_GUARD_UNAVAILABLE$"):
            self.execute(lambda: self.fail("callback before committed intent"))
        self.assertEqual(self.guard.inspect()["runs"], [])

    def test_finish_failure_leaves_intent_with_audit_after_reopen(self):
        calls = []
        with self.guard._connection() as db:
            db.execute("CREATE TRIGGER fail BEFORE INSERT ON run_events WHEN NEW.kind='COMPLETED' BEGIN SELECT RAISE(ABORT,'SQL-SECRET'); END")
        with self.assertRaisesRegex(GuardError, "^RESEARCH_GUARD_UNAVAILABLE$"):
            self.execute(lambda: calls.append(1) or RESULT)
        self.assertEqual(calls, [1])
        reopened = ResearchGuard(self.guard.directory)
        self.assertEqual(reopened.inspect()["runs"][0]["state"], "INTENT")
        with self.assertRaisesRegex(GuardError, "WEB_RESEARCH_UNCERTAIN"):
            reopened.execute(lambda: self.fail("retry after finish failure"), descriptor=DESC)

    def test_review_write_failure_is_atomic(self):
        record = self.uncertain()
        with self.guard._connection() as db:
            db.execute("CREATE TRIGGER fail BEFORE INSERT ON run_events WHEN NEW.kind='RESOLVED_UNKNOWN' BEGIN SELECT RAISE(ABORT,'SQL-SECRET'); END")
        with self.assertRaises(GuardError):
            self.resolve(record)
        self.assertEqual(self.guard.inspect()["runs"][0], record)

    def test_record_corruption_or_event_loss_never_means_empty(self):
        self.execute()
        with self.guard._connection() as db:
            db.execute("DELETE FROM run_events WHERE kind='COMPLETED'")
        for action in (self.guard.inspect, lambda: ResearchGuard(self.guard.directory), self.execute):
            with self.assertRaisesRegex(GuardError, "INVALID_RESEARCH_AUDIT"):
                action()

    def test_duplicate_json_and_identity_changes_are_refused(self):
        record = self.uncertain()
        with self.guard._connection() as db:
            raw = db.execute("SELECT body FROM runs").fetchone()[0]
            raw = raw[:-1] + ',"state":"COMPLETED"}'
            db.execute("UPDATE runs SET body=?", (raw,))
        with self.assertRaisesRegex(GuardError, "INVALID_RESEARCH_RECORD"):
            self.guard.inspect()
        with sqlite3.connect(self.guard.path) as db:
            db.execute("UPDATE metadata SET value=?", ("g-" + "0"*32,))
        with self.assertRaisesRegex(GuardError, "RESEARCH_GUARD_CHANGED"):
            self.guard.inspect()

    def test_clock_failure_keeps_intent_and_time_never_unlocks(self):
        def backwards():
            self.clock.value -= 1
            return RESULT
        with self.assertRaisesRegex(GuardError, "RESEARCH_CLOCK_REGRESSION"):
            self.execute(backwards)
        record = self.guard.inspect()["runs"][0]
        with self.assertRaisesRegex(GuardError, "RESEARCH_CLOCK_REGRESSION"):
            self.resolve(record)
        self.clock.value += 1_000_000
        with self.assertRaisesRegex(GuardError, "WEB_RESEARCH_UNCERTAIN"):
            self.execute()
        self.resolve(record)

    def test_bounded_history_refuses_before_callback_and_does_not_evict(self):
        with patch("eidolon_core.research_guard.MAX_RUNS", 2):
            self.execute(); self.execute()
            with self.assertRaisesRegex(GuardError, "RESEARCH_HISTORY_CAPACITY_REACHED"):
                self.execute(lambda: self.fail("capacity callback"))
            self.assertEqual(len(self.guard.inspect()["runs"]), 2)

    def test_no_query_page_path_or_exception_text_in_journal(self):
        class P(Provider):
            def search(self, query, limit):
                raise RuntimeError("PROVIDER_SECRET")
        c = ResearchCoordinator([P("p", [])], Reader(), resolver=dns, guard=self.guard)
        raw = "person@example.invalid /home/alice/notes.txt REMAINING_PRIVATE_TOPIC"
        result = c.run(raw)
        self.assertEqual(result["providers"][0]["status"], "PROVIDER_ERROR")
        body = self.guard.path.read_bytes()
        for sensitive in (b"person@example", b"/home/alice", b"REMAINING_PRIVATE_TOPIC", b"PROVIDER_SECRET"):
            self.assertNotIn(sensitive, body)
        record = self.guard.inspect()["runs"][0]
        self.assertEqual(record["descriptor"]["query_sha256"], clean_query(raw).cleaned_sha256)

    def test_guard_resolution_does_not_release_committed_pause(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = subprocess.run([sys.executable, "-c", CHILD, str(root), "after_pause"], capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 41, result.stderr)
            g = ResearchGuard(root / "guard")
            record = g.inspect()["runs"][0]
            g.resolve(record["id"], expected_revision=1, actor="fixture", reason="reviewed")
            p = Provider("p", [hit()])
            c = ResearchCoordinator([p], Reader(), resolver=dns, guard=g, pauses=ResearchPauses(root / "pauses.sqlite3"))
            r = c.run("synthetic")
            self.assertEqual(r["providers"][0]["status"], "RETRY_WAIT")
            self.assertEqual(p.calls, 0)

    def test_real_loopback_response_before_pause_crash_is_not_contacted_again(self):
        from examples.research_http_demo import fixture_server
        code = '''import os,sys
from pathlib import Path
from eidolon_core.egress import WebPolicy
from eidolon_core.research import ResearchCoordinator,Hit
from eidolon_core.research_guard import ResearchGuard
from eidolon_core.research_pauses import ResearchPauses
from eidolon_core.web_reader import WebReader
from examples.research_http_demo import LocalFixtureConnector,fixture_dns
from tests.test_research import Provider
root=Path(sys.argv[1]);port=int(sys.argv[2])
class CrashPause(ResearchPauses):
 def pause(self,*args,**kwargs):os._exit(43)
p=Provider('local-http',[Hit(f'http://docs.example:{port}/quota','fixture')])
c=ResearchCoordinator([p],WebReader(fixture_dns,LocalFixtureConnector()),resolver=fixture_dns,
 policy=WebPolicy(schemes=('http',),ports=(port,)),guard=ResearchGuard(root/'guard'),pauses=CrashPause(root/'pauses.sqlite3'))
c.run('synthetic')
'''
        with fixture_server() as server:
            result = subprocess.run([sys.executable, "-c", code, str(self.root), str(server.server_port)],
                                    capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 43, result.stderr)
            self.assertEqual(len(server.requests), 1)
            rerun = subprocess.run([sys.executable, "-c", code, str(self.root), str(server.server_port)],
                                   capture_output=True, text=True, timeout=10)
            self.assertNotEqual(rerun.returncode, 0)
            self.assertIn("WEB_RESEARCH_UNCERTAIN", rerun.stderr)
            self.assertEqual(len(server.requests), 1)

    def test_invalid_input_creates_no_intent(self):
        c = ResearchCoordinator([Provider("p", [])], Reader(), resolver=dns, guard=self.guard)
        for raw in ("", "x"*1001, "x\x00"):
            with self.assertRaises(ValueError):
                c.run(raw)
        with self.assertRaises(ValueError):
            c.run("synthetic", required_pages=True)
        for bad in ({}, {**DESC, "providers": ["p", "p"]}, {**DESC, "query_sha256": "secret"}):
            with self.assertRaisesRegex(GuardError, "INVALID_RESEARCH_DESCRIPTOR"):
                self.guard.execute(lambda: self.fail("invalid descriptor"), descriptor=bad)
        self.assertEqual(self.guard.inspect()["runs"], [])

    def test_deleted_database_is_not_recreated_by_existing_guard(self):
        self.guard.path.unlink()
        with self.assertRaisesRegex(GuardError, "RESEARCH_GUARD_UNAVAILABLE"):
            self.execute(lambda: self.fail("missing database"))
        self.assertFalse(self.guard.path.exists())

    def test_nonfinite_clock_and_invalid_result_never_claim_completion(self):
        self.clock.value = float("nan")
        with self.assertRaisesRegex(GuardError, "INVALID_RESEARCH_CLOCK"):
            self.execute(lambda: self.fail("invalid clock"))
        self.assertEqual(self.guard.inspect()["runs"], [])
        self.clock.value = 1000
        with self.assertRaisesRegex(GuardError, "INVALID_RESEARCH_RESULT"):
            self.execute(lambda: {"status": "INVENTED"})
        self.assertEqual(self.guard.inspect()["runs"][0]["state"], "INTENT")

    def test_private_files_and_symlink_refusal(self):
        for p in (self.guard.path, self.guard.lock_path):
            self.assertEqual(p.stat().st_mode & 0o777, 0o600)
        self.guard.lock_path.unlink()
        target = self.root / "target"; target.write_text("untouched")
        self.guard.lock_path.symlink_to(target)
        with self.assertRaises(GuardError):
            self.execute(lambda: self.fail("symlink lock"))
        self.assertEqual(target.read_text(), "untouched")

    def test_missing_lock_is_not_recreated_for_execution_or_review(self):
        record = self.uncertain()
        self.guard.lock_path.unlink()
        for action in (self.execute, lambda: self.resolve(record), self.guard.inspect):
            with self.assertRaisesRegex(GuardError, "RESEARCH_GUARD_UNAVAILABLE"):
                action()
        self.assertFalse(self.guard.lock_path.exists())

    def test_cli_inspect_and_review_never_create_missing_journal_or_restart(self):
        missing = self.root / "MISSING_PRIVATE_PATH"
        args = [sys.executable, "-m", "eidolon_core.research_guard", "--directory"]
        failed = subprocess.run([*args, str(missing), "inspect"], capture_output=True, text=True, timeout=5)
        self.assertEqual(failed.returncode, 2)
        self.assertEqual(json.loads(failed.stderr)["error"], "RESEARCH_GUARD_NOT_FOUND")
        self.assertNotIn("MISSING_PRIVATE_PATH", failed.stderr)
        self.assertFalse(missing.exists())
        record = self.uncertain()
        before = self.guard.path.read_bytes()
        result = subprocess.run([*args, str(self.guard.directory), "inspect"], capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["runs"][0]["observed_state"], "UNCERTAIN")
        self.assertEqual(self.guard.path.read_bytes(), before)
        human = subprocess.run([*args, str(self.guard.directory), "--format", "human", "inspect"], capture_output=True, text=True, timeout=5)
        self.assertIn("Eidolon Core Technologies (ECT)", human.stdout)
        self.assertIn("Eidolon Core", human.stdout)
        resolved = subprocess.run([*args, str(self.guard.directory), "resolve", record["id"], "--revision", "1",
                                   "--actor", "fixture", "--reason", "reviewed uncertainty"], capture_output=True, text=True, timeout=5)
        self.assertEqual(resolved.returncode, 0, resolved.stderr)
        self.assertFalse(json.loads(resolved.stdout)["request_sent"])
        self.assertEqual(len(self.guard.inspect()["runs"]), 1)


if __name__ == "__main__":
    unittest.main()
