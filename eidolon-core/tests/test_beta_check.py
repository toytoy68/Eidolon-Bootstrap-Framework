# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_beta_check.py
# Description : Contrat et nettoyage de la recette locale autonome
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
from contextlib import redirect_stdout
import io
import json
import os
import selectors
import signal
import socket
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from eidolon_core import beta_check

CORE = Path(__file__).resolve().parents[1]
WEB = CORE / "desktop" / "connected"


class BetaCheckTests(unittest.TestCase):
    def test_research_archive_recipe_reports_scope_and_preserves_unowned_files(self):
        with tempfile.TemporaryDirectory() as directory:
            sentinel = Path(directory) / "keep.txt"
            sentinel.write_bytes(b"unowned sentinel")
            result = subprocess.run(
                [sys.executable, "-m", "eidolon_core.beta_check", "--web-root", str(WEB),
                 "--profile", "research-archives"], cwd=directory,
                env={**os.environ, "PYTHONPATH": str(CORE / "src"), "TMPDIR": directory},
                capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            report = json.loads(result.stdout)
            self.assertEqual(report["profile"], "research-archives")
            self.assertEqual(report["checks_passed"], 25)
            for check in ("three_research_missions", "archive_catalog_complete_private_no_authority",
                          "archive_change_requires_reset", "read_state_unchanged", "restart_preserves_store_and_cursor"):
                self.assertIn(check, report["checks"])
            for flag in ("model_tested", "browser_tested", "windows_tested", "user_server_tested", "ssh_tested"):
                self.assertIs(report[flag], False)
            self.assertEqual(list(Path(directory).iterdir()), [sentinel])
            self.assertEqual(sentinel.read_bytes(), b"unowned sentinel")

    def test_research_archive_request_failure_closes_owned_server(self):
        original = beta_check.HTTPConnection.request
        ports = []
        def fail_archive(connection, method, path, *args, **kwargs):
            if path == "/v1/research-archives":
                ports.append(connection.port)
                raise OSError("private archive failure")
            return original(connection, method, path, *args, **kwargs)
        with tempfile.TemporaryDirectory() as directory:
            output = io.StringIO()
            with patch.object(tempfile, "tempdir", directory), \
                    patch.object(beta_check.HTTPConnection, "request", fail_archive), redirect_stdout(output):
                code = beta_check.main(["--web-root", str(WEB), "--profile", "research-archives"])
            self.assertEqual(code, 2)
            self.assertNotIn("private archive failure", output.getvalue())
            self.assertEqual(json.loads(output.getvalue())["error"], "LOCAL_RECIPE_FAILED")
            self.assertEqual(list(Path(directory).iterdir()), [])
            self.assertTrue(ports)
            with socket.socket() as client:
                client.settimeout(1)
                self.assertNotEqual(client.connect_ex(("127.0.0.1", ports[0])), 0)

    def test_sigterm_and_sigint_report_interruption_and_close_owned_server(self):
        code = '''import signal,sys
from eidolon_core import beta_check
def pause_at_request(self,*args,**kwargs):
 print('READY '+str(self.port),flush=True)
 signal.pause()
beta_check.HTTPConnection.request=pause_at_request
raise SystemExit(beta_check.main(['--web-root',sys.argv[1]]))
'''
        for signum in (signal.SIGTERM, signal.SIGINT):
            with self.subTest(signal=signum), tempfile.TemporaryDirectory() as directory:
                child = subprocess.Popen([sys.executable, "-c", code, str(WEB)],
                    env={**os.environ, "PYTHONPATH": str(CORE / "src"), "TMPDIR": directory},
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                try:
                    with selectors.DefaultSelector() as selector:
                        selector.register(child.stdout, selectors.EVENT_READ)
                        self.assertTrue(selector.select(timeout=15), "recipe did not reach HTTP phase")
                    ready = child.stdout.readline().strip()
                    self.assertTrue(ready.startswith("READY "), ready)
                    port = int(ready.partition(" ")[2])
                    child.send_signal(signum)
                    stdout, stderr = child.communicate(timeout=10)
                    self.assertEqual(child.returncode, 2, stderr)
                    report = json.loads(stdout)
                    self.assertEqual((report["status"], report["error"], report["signal"]), ("FAIL", "INTERRUPTED", signum))
                    self.assertEqual(list(Path(directory).iterdir()), [])
                    with socket.socket() as client:
                        client.settimeout(1)
                        self.assertNotEqual(client.connect_ex(("127.0.0.1", port)), 0)
                finally:
                    if child.poll() is None:
                        child.kill()
                    child.communicate(timeout=5)

    def test_owned_process_group_cleanup_includes_descendant_ignoring_term(self):
        grandchild_code = "import signal,socket,time;signal.signal(signal.SIGTERM,signal.SIG_IGN);s=socket.socket();s.bind(('127.0.0.1',0));s.listen();print(s.getsockname()[1],flush=True);time.sleep(60)"
        code = "import subprocess,sys,time;p=subprocess.Popen([sys.executable,'-c',sys.argv[1]],stdout=subprocess.PIPE,text=True);print(p.stdout.readline().strip(),flush=True);time.sleep(60)"
        child = subprocess.Popen([sys.executable, "-c", code, grandchild_code], start_new_session=True,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            with selectors.DefaultSelector() as selector:
                selector.register(child.stdout, selectors.EVENT_READ)
                self.assertTrue(selector.select(timeout=5))
            port = int(child.stdout.readline().strip())
            beta_check._stop_owned(child)
            self.assertIsNotNone(child.returncode)
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline:
                with socket.socket() as client:
                    client.settimeout(.1)
                    if client.connect_ex(("127.0.0.1", port)) != 0:
                        break
                time.sleep(.01)
            else:
                self.fail("owned descendant still running")
        finally:
            try:
                os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            child.communicate(timeout=5)

    def test_signal_handlers_are_restored_after_failed_recipe(self):
        previous = {s: signal.getsignal(s) for s in (signal.SIGINT, signal.SIGTERM)}
        with redirect_stdout(io.StringIO()):
            self.assertEqual(beta_check.main(["--web-root", "/nonexistent/private-assets"]), 2)
        self.assertEqual({s: signal.getsignal(s) for s in previous}, previous)

    def test_real_recipe_from_unrelated_directory_has_machine_report(self):
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(
                [sys.executable, "-m", "eidolon_core.beta_check", "--web-root", str(WEB)],
                cwd=directory, env={**os.environ, "PYTHONPATH": str(CORE / "src")},
                capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            report = json.loads(result.stdout)
            self.assertEqual(report["status"], "PASS")
            self.assertEqual(report["checks_passed"], 24)
            self.assertIn("read_state_unchanged", report["checks"])
            self.assertIn("restart_preserves_store_and_cursor", report["checks"])
            self.assertFalse(report["browser_tested"])
            self.assertFalse(report["ssh_tested"])
            self.assertNotIn(directory, result.stdout)
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_missing_assets_fail_before_preparing_state_without_path_leak(self):
        output = io.StringIO()
        with patch.object(beta_check.tempfile, "TemporaryDirectory", side_effect=AssertionError("must not prepare")), redirect_stdout(output):
            code = beta_check.main(["--web-root", "/nonexistent/private-core-assets"])
        report = json.loads(output.getvalue())
        self.assertEqual(code, 2)
        self.assertEqual(report["checks_passed"], 0)
        self.assertEqual(report["error"], "LOCAL_RECIPE_FAILED")
        self.assertNotIn("private-core-assets", output.getvalue())

    def test_server_spawn_failure_cleans_owned_files_and_hides_raw_error(self):
        original = subprocess.Popen

        def fail_server(args, *a, **kw):
            if "eidolon_core.http_api" in args and "--check" not in args:
                raise OSError("private fixture failure")
            return original(args, *a, **kw)

        with tempfile.TemporaryDirectory() as directory:
            output = io.StringIO()
            with patch.object(tempfile, "tempdir", directory), patch.object(subprocess, "Popen", side_effect=fail_server), redirect_stdout(output):
                code = beta_check.main(["--web-root", str(WEB)])
            self.assertEqual(code, 2)
            self.assertEqual(json.loads(output.getvalue())["checks_passed"], 2)
            self.assertNotIn("private fixture failure", output.getvalue())
            self.assertEqual(list(Path(directory).iterdir()), [])


if __name__ == "__main__":
    unittest.main()
