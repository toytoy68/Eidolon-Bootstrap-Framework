# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_qualification_cli.py
# Description : Vérification hors ligne et frontières de fichiers CLI
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Synthetic reports only; no model, real telemetry or personal report."""
from contextlib import redirect_stderr, redirect_stdout
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from eidolon_core.cli import main
from eidolon_core.qualification_io import QualificationCheckError, check_report, read_report
from eidolon_core.qualification import MAX_BYTES
from tests.test_qualification import FIXTURES, base


class QualificationCLITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.report = self.root / "report.json"
        self.report.write_text(json.dumps(base()), encoding="utf-8")
        self.state = self.root / "must-not-exist"

    def invoke(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = main(["--state", str(self.state), *args])
        return code, out.getvalue(), err.getvalue()

    def test_three_verdicts_with_digest_without_runtime_or_mutation(self):
        before = {path.name: path.read_bytes() for path in FIXTURES.glob("*.json")}
        for name, status, code in (("passed-scope-synthetic.json", "PASSED_SCOPE", 0),
                                   ("incomplete-missing-measure.json", "INCOMPLETE", 2),
                                   ("rejected-one-violation.json", "REJECTED", 3)):
            with self.subTest(status=status), \
                 patch("eidolon_core.cli.Store", side_effect=AssertionError("store started")), \
                 patch("eidolon_core.cli.Runtime", side_effect=AssertionError("runtime started")), \
                 patch("socket.socket", side_effect=AssertionError("network started")):
                actual, out, err = self.invoke("qualification-check", "--report", str(FIXTURES / name))
                self.assertEqual((actual, err), (code, ""))
                result = json.loads(out)
                self.assertEqual(result["status"], status)
                self.assertEqual(result["schema"], "eidolon-qualification-check/1")
                self.assertEqual(result["scope"]["origin"], "synthetic")
                self.assertFalse(result["authorizes_execution"])
                self.assertFalse(result["telemetry_authenticated"])
                self.assertEqual(result["report_sha256"], hashlib.sha256(before[name]).hexdigest())
        self.assertEqual(before, {path.name: path.read_bytes() for path in FIXTURES.glob("*.json")})
        self.assertFalse(self.state.exists())

    def test_existing_state_is_untouched(self):
        self.state.mkdir()
        database = self.state / "missions.sqlite3"
        database.write_bytes(b"synthetic-state-must-not-be-opened")
        before = database.stat()
        code, _, err = self.invoke("qualification-check", "--report", str(self.report))
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(database.read_bytes(), b"synthetic-state-must-not-be-opened")
        self.assertEqual(database.stat().st_mtime_ns, before.st_mtime_ns)
        self.assertEqual(list(self.state.iterdir()), [database])

    def test_malformed_diagnostics_do_not_echo_report_or_path(self):
        canary = "private-synthetic-canary"
        path = self.root / canary
        for raw in (f'{{"{canary}":1,"{canary}":2}}'.encode(),
                    json.dumps({canary: "unknown"}).encode(), b'"\\ud800"', b"\xff"):
            with self.subTest(raw=raw):
                path.write_bytes(raw)
                code, out, err = self.invoke("qualification-check", "--report", str(path))
                self.assertEqual((code, out), (2, ""))
                self.assertNotIn(canary, err)
                self.assertEqual(json.loads(err), {"error": "QualificationCheckError", "message": "REPORT_MALFORMED"})
        path.unlink()
        code, out, err = self.invoke("qualification-check", "--report", str(path))
        self.assertEqual((code, out), (2, ""))
        self.assertEqual(json.loads(err)["message"], "REPORT_UNAVAILABLE")
        self.assertNotIn(canary, err)

    def test_nonregular_and_oversize_files_are_refused_without_waiting(self):
        link = self.root / "link"
        link.symlink_to(self.report)
        fifo = self.root / "fifo"
        os.mkfifo(fifo)
        huge = self.root / "large"
        with huge.open("wb") as stream:
            stream.truncate(MAX_BYTES + 1)
        for path, error in ((link, "REPORT_UNAVAILABLE"), (fifo, "REPORT_NOT_REGULAR"),
                            (self.root, "REPORT_NOT_REGULAR"), (huge, "REPORT_TOO_LARGE")):
            with self.subTest(path=path.name):
                command = [sys.executable, "-m", "eidolon_core", "--state", str(self.state),
                           "qualification-check", "--report", str(path)]
                run = subprocess.run(command, capture_output=True, text=True, timeout=5)
                self.assertEqual((run.returncode, run.stdout), (2, ""))
                self.assertEqual(json.loads(run.stderr)["message"], error)
        self.assertFalse(self.state.exists())

    def test_replacement_between_read_and_path_check_is_refused(self):
        original_stat = os.stat
        replacement = self.root / "replacement"
        replacement.write_bytes(self.report.read_bytes())  # even identical bytes, different inode

        def replacing_stat(path, **kwargs):
            replacement.replace(self.report)
            return original_stat(path, **kwargs)

        with patch("eidolon_core.qualification_io.os.stat", side_effect=replacing_stat):
            with self.assertRaisesRegex(QualificationCheckError, "^REPORT_CHANGED$"):
                read_report(self.report)

    def test_change_during_read_and_disappearing_path_are_refused(self):
        original_fstat = os.fstat
        calls = 0

        def changed_fstat(descriptor):
            nonlocal calls
            calls += 1
            if calls == 2:
                self.report.write_bytes(b"changed during read")
            return original_fstat(descriptor)

        with patch("eidolon_core.qualification_io.os.fstat", side_effect=changed_fstat):
            with self.assertRaisesRegex(QualificationCheckError, "^REPORT_CHANGED$"):
                read_report(self.report)
        with patch("eidolon_core.qualification_io.os.stat", side_effect=FileNotFoundError("private path")):
            with self.assertRaisesRegex(QualificationCheckError, "^REPORT_UNAVAILABLE$"):
                read_report(self.report)

    def test_growth_beyond_read_limit_is_refused(self):
        original_fstat = os.fstat
        calls = 0

        def grow_after_initial_stat(descriptor):
            nonlocal calls
            calls += 1
            info = original_fstat(descriptor)
            if calls == 1:
                with self.report.open("ab") as stream:
                    stream.write(b" " * MAX_BYTES)
            return info

        with patch("eidolon_core.qualification_io.os.fstat", side_effect=grow_after_initial_stat):
            with self.assertRaisesRegex(QualificationCheckError, "^REPORT_TOO_LARGE$"):
                read_report(self.report)

    def test_early_failures_close_descriptor_deterministically(self):
        original_open = os.open
        descriptors = []

        def remember_open(*args, **kwargs):
            descriptor = original_open(*args, **kwargs)
            descriptors.append(descriptor)
            return descriptor

        for fault in ("fstat", "fdopen"):
            with self.subTest(fault=fault), \
                 patch("eidolon_core.qualification_io.os.open", side_effect=remember_open), \
                 patch("eidolon_core.qualification_io.os." + fault, side_effect=OSError("private diagnostic")):
                with self.assertRaisesRegex(QualificationCheckError, "^REPORT_UNAVAILABLE$"):
                    read_report(self.report)
            with self.assertRaises(OSError):
                os.fstat(descriptors[-1])
        # The non-regular branch also closes before returning, without GC.
        with patch("eidolon_core.qualification_io.os.open", side_effect=remember_open):
            with self.assertRaises(QualificationCheckError):
                read_report(self.root)
        with self.assertRaises(OSError):
            os.fstat(descriptors[-1])

    def test_human_output_neutralizes_control_characters(self):
        report = base()
        report["scope"]["model"] = "model\x1b[2J\nspoofed-line"
        report["cases"]["results"][0]["violations"] = ["reason\r\x1b[31m"]
        self.report.write_text(json.dumps(report), encoding="utf-8")
        code, out, err = self.invoke("--format", "human", "qualification-check", "--report", str(self.report))
        self.assertEqual((code, err), (3, ""))
        self.assertIn("Eidolon Core Technologies (ECT)", out)
        self.assertIn("Authenticité des mesures non vérifiée", out)
        self.assertIn("\\u001b[2J\\u000aspoofed-line", out)
        self.assertNotIn("\x1b", out)
        self.assertNotIn("\r", out)
        self.assertNotIn("[OK]", out)

    def test_hardware_origin_does_not_authenticate_telemetry(self):
        report = base()
        report["run"]["origin"] = "hardware_reported"
        for row in report["cases"]["results"]:
            row["origin"] = "hardware_reported"
        for row in report["measurements"].values():
            row["origin"] = "hardware_reported"
        self.report.write_text(json.dumps(report), encoding="utf-8")
        result = check_report(self.report)
        self.assertEqual(result["status"], "PASSED_SCOPE")
        self.assertFalse(result["telemetry_authenticated"])
        self.assertFalse(result["authorizes_execution"])

    def test_execution_options_are_refused_before_loading(self):
        for options in (("--model-config", "missing-private-config"), ("--memory-root", "missing-memory"),
                        ("--profile", "action-sim"), ("--targets", "missing-catalog"),
                        ("--allow-target", "vm-test"), ("--research-scenario", "empty")):
            with self.subTest(options=options), \
                 patch("eidolon_core.model_config.load_model", side_effect=AssertionError("loaded model")), \
                 patch("eidolon_core.qualification_io.check_report", side_effect=AssertionError("loaded report")):
                code, out, err = self.invoke(*options, "qualification-check", "--report", str(self.report))
                self.assertEqual((code, out), (2, ""))
                self.assertTrue(json.loads(err)["message"].endswith("NOT_SUPPORTED"))
        self.assertFalse(self.state.exists())

    def test_real_cli_json_and_human_pass_are_bounded_to_report(self):
        for output_format in ("json", "human"):
            run = subprocess.run([sys.executable, "-m", "eidolon_core", "--state", str(self.state),
                                  "--format", output_format, "qualification-check", "--report", str(self.report)],
                                 capture_output=True, text=True, timeout=5)
            self.assertEqual((run.returncode, run.stderr), (0, ""))
            if output_format == "json":
                self.assertEqual(json.loads(run.stdout)["status"], "PASSED_SCOPE")
            else:
                self.assertIn("[OK] Rapport cohérent dans le périmètre déclaré.", run.stdout)
                self.assertIn("aucune qualification matérielle", run.stdout)
        self.assertFalse(self.state.exists())


if __name__ == "__main__":
    unittest.main()
