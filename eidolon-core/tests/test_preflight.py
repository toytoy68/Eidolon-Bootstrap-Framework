# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_preflight.py
# Description : Diagnostic reproductible sans écoute ni état créé
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from eidolon_core import http_api, preflight
from eidolon_core.store import Store


class PreflightTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.state = self.root / "state"
        self.store = Store(self.state)
        self.token = self.root / "private-token"
        self.secret = "synthetic_private_" + "x" * 32
        self.token.write_text(self.secret + "\n")
        self.token.chmod(0o600)
        self.web = self.root / "web"
        self.web.mkdir()
        for name, _ in http_api.ASSETS.values():
            (self.web / name).write_text("synthetic client")

    def inspect(self, **kwargs):
        return preflight.inspect(self.state, self.token, web_root=self.web, **kwargs)

    def codes(self, report):
        return {c["name"]: c["code"] for c in report["checks"]}

    def files(self):
        return {str(p.relative_to(self.root)): p.read_bytes()
                for p in self.root.rglob("*") if p.is_file()}

    def test_success_does_not_bind_create_store_or_modify_files(self):
        before = self.files()
        with patch("socket.socket", side_effect=AssertionError("no network")), \
                patch.object(Store, "__init__", side_effect=AssertionError("no initialization")):
            report = self.inspect()
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(self.files(), before)
        for flag in ("server_started", "port_availability_checked", "client_browser_tested",
                     "full_database_audit", "authorizes_execution"):
            self.assertIs(report[flag], False)
        self.assertEqual(len(report["checks"]), 4)

    def test_missing_inputs_report_all_failures_without_creation_or_leaks(self):
        before = self.files()
        report = preflight.inspect(self.root / "absent-state", self.root / "absent-token",
                                   web_root=self.root / "absent-web", port=-1)
        self.assertEqual(report["status"], "FAIL")
        self.assertEqual(self.codes(report), {"token": "TOKEN_UNAVAILABLE", "state": "STATE_NOT_FOUND",
                                             "client": "INVALID_WEB_ROOT", "port": "INVALID_PORT"})
        self.assertEqual(self.files(), before)
        self.assertFalse((self.root / "absent-state").exists())
        for fmt in ("json", "human"):
            self.assertNotIn(str(self.root), preflight.render(report, fmt))
            self.assertNotIn(self.secret, preflight.render(report, fmt))

    def test_token_permissions_and_format(self):
        self.token.chmod(0o644)
        self.assertEqual(self.codes(self.inspect())["token"], "TOKEN_FILE_NOT_PRIVATE")
        self.token.chmod(0o600)
        for text in ("short", "x" * 129, self.secret + "\n\n"):
            self.token.write_text(text)
            self.assertEqual(self.codes(self.inspect())["token"], "INVALID_TOKEN")

    def test_token_symlink_and_fifo_do_not_block(self):
        self.token.unlink()
        self.token.symlink_to(self.web / "app.js")
        self.assertEqual(self.codes(self.inspect())["token"], "TOKEN_UNAVAILABLE")
        self.token.unlink()
        os.mkfifo(self.token, 0o600)
        self.assertEqual(self.codes(self.inspect())["token"], "TOKEN_FILE_NOT_PRIVATE")

    def test_recovery_guards(self):
        for name in ("RECOVERY-REVIEW-ONLY", "review.pending.sqlite3"):
            marker = self.state / name
            marker.touch()
            before = self.files()
            self.assertEqual(self.codes(self.inspect())["state"], "RECOVERY_REVIEW_ONLY")
            self.assertEqual(self.files(), before)
            marker.unlink()
        with self.store.connection() as db:
            db.execute("INSERT INTO sync_metadata(key,value) VALUES('recovery_mode','review')")
        self.assertEqual(self.codes(self.inspect())["state"], "RECOVERY_REVIEW_ONLY")

    def test_schema_and_identity_errors_are_specific(self):
        with self.store.connection() as db:
            db.execute("PRAGMA user_version=2")
        self.assertEqual(self.codes(self.inspect())["state"], "UNSUPPORTED_READ_SCHEMA")
        with self.store.connection() as db:
            db.execute("PRAGMA user_version=1")
            db.execute("UPDATE sync_metadata SET value='bad-id' WHERE key='store_id'")
        self.assertEqual(self.codes(self.inspect())["state"], "INVALID_STORE_ID")

    def test_unreadable_database_and_raw_errors_are_not_exported(self):
        self.store.path.write_bytes(b"not a database with private contents")
        report = self.inspect()
        self.assertEqual(self.codes(report)["state"], "STATE_UNAVAILABLE")
        self.assertNotIn("private contents", preflight.render(report))
        with patch.object(preflight, "read_token", side_effect=OSError(self.secret)):
            self.assertNotIn(self.secret, preflight.render(self.inspect(), "human"))

    def test_optional_client_is_explicitly_skipped(self):
        report = preflight.inspect(self.state, self.token)
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["checks"][2], {"name": "client", "status": "SKIP", "code": "NO_WEB_ROOT"})

    def test_assets_missing_symlink_and_oversize_match_server_validation(self):
        app = self.web / "app.js"
        for kind, expected in (("absent", "INVALID_WEB_ROOT"), ("link", "INVALID_WEB_ROOT"),
                               ("large", "ASSET_TOO_LARGE")):
            with self.subTest(kind=kind):
                if app.exists() or app.is_symlink():
                    app.unlink()
                if kind == "link":
                    app.symlink_to(self.web / "index.html")
                elif kind == "large":
                    app.write_bytes(b"x" * (http_api.MAX_ASSET + 1))
                self.assertEqual(self.codes(self.inspect())["client"], expected)
                with self.assertRaisesRegex(ValueError, expected):
                    http_api.ReadServer(self.state, self.secret, port=0, web_root=self.web)

    def test_port_format_is_checked_but_availability_is_not(self):
        for port in (True, "8765", -1, 65536):
            self.assertEqual(self.codes(self.inspect(port=port))["port"], "INVALID_PORT")
        for port in (0, 8765, 65535):
            self.assertEqual(self.codes(self.inspect(port=port))["port"], "PORT_VALID")

    def test_cli_json_human_and_exit_codes_without_starting_server(self):
        args = ["--state", str(self.state), "--token-file", str(self.token), "--check"]
        with patch.object(http_api, "ReadServer", side_effect=AssertionError("must not serve")):
            for fmt in ("json", "human"):
                out = io.StringIO()
                with redirect_stdout(out):
                    self.assertEqual(http_api.main(args + ["--format", fmt]), 0)
                if fmt == "json":
                    self.assertEqual(json.loads(out.getvalue())["status"], "PASS")
                else:
                    self.assertIn("Eidolon Core Technologies", out.getvalue())
                    self.assertIn("[INFO] NO_WEB_ROOT", out.getvalue())
            self.token.unlink()
            with redirect_stdout(io.StringIO()):
                self.assertEqual(http_api.main(args), 2)

    def test_actual_cli_process_default_json_and_failure(self):
        args = [sys.executable, "-m", "eidolon_core.http_api", "--state", str(self.state),
                "--token-file", str(self.token), "--web-root", str(self.web), "--check"]
        env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1] / "src"))
        for expected in (0, 2):
            result = subprocess.run(args, env=env, capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, expected, result.stderr)
            self.assertEqual(result.stderr, "")
            self.assertEqual(json.loads(result.stdout)["status"], "PASS" if expected == 0 else "FAIL")
            self.assertNotIn(self.secret, result.stdout)
            if self.token.exists():
                self.token.unlink()


if __name__ == "__main__":
    unittest.main()
