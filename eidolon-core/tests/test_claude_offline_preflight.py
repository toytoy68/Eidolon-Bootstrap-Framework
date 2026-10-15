# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_claude_offline_preflight.py
# Description : Tests du préflight hors ligne opt-in (Claude, G236-9)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
import contextlib
import importlib.util
import io
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "claude_offline_preflight", Path(__file__).resolve().parents[1] / "tools" / "claude_offline_preflight.py")
pre = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pre)


def repo(path):
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    (path / "f").write_text("x")
    subprocess.run(["git", "-C", str(path), "add", "f"], check=True)
    subprocess.run(["git", "-C", str(path), "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "x"],
                   check=True)
    return subprocess.run(["git", "-C", str(path), "rev-parse", "HEAD"], capture_output=True, text=True,
                          check=True).stdout.strip()


class Preflight(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.core, self.memory = self.tmp / "core", self.tmp / "memory"
        self.core_sha, self.memory_sha = repo(self.core), repo(self.memory)
        self.private = self.tmp / "private"
        self.private.mkdir(mode=0o700)
        self.secret = self.private / "token"
        self.secret.write_text("s" * 64)
        self.secret.chmod(0o600)

    def argv(self, **over):
        values = {"--core": self.core, "--memory": self.memory, "--expect-core": self.core_sha,
                  "--expect-memory": self.memory_sha[:12], "--data-dir": self.tmp, "--min-free-bytes": 1,
                  "--credential": self.secret}
        values.update(over)
        argv = ["--confirm-read-only"]
        for key, value in values.items():
            if value is not None:
                argv += [key, str(value)]
        return argv

    def run_main(self, argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = pre.main(argv)
        return code, out.getvalue()

    def test_nothing_runs_without_explicit_opt_in(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            pre.main(["--core", str(self.core)])

    def test_all_known_and_correct_passes_unless_a_required_module_is_missing(self):
        code, out = self.run_main(self.argv())
        expected = 0 if importlib.util.find_spec("qdrant_client") and importlib.util.find_spec("numpy") else None
        if expected == 0:
            self.assertEqual(code, 0, out)
        self.assertIn('"bridge.credential"', out)
        self.assertNotIn("s" * 32, out)                          # the secret is never read nor printed

    def test_unknown_stops_like_fail(self):
        code, out = self.run_main(self.argv(**{"--expect-core": None}))
        self.assertIn(code, (1, 2))
        self.assertIn('"UNKNOWN"', out)
        code, out = self.run_main(["--confirm-read-only"])                # nothing known at all
        self.assertEqual(code, 2 if '"FAIL"' not in out else 1)

    def test_wrong_sha_dirty_checkout_and_unsafe_credential_fail(self):
        self.assertEqual(pre.check_checkout("core", self.core, "0" * 40)["result"], "FAIL")
        (self.core / "f").write_text("modified")
        self.assertEqual(pre.check_checkout("core", self.core, self.core_sha)["result"], "FAIL")
        self.secret.chmod(0o644)
        self.assertEqual(pre.check_credential(str(self.secret))["result"], "FAIL")
        self.secret.chmod(0o600)
        os.link(self.secret, self.private / "hard")
        self.assertEqual(pre.check_credential(str(self.secret))["result"], "FAIL")

    def test_the_tool_never_writes_in_the_checkouts(self):
        before = {p: p.stat().st_mtime_ns for p in self.core.rglob("*") if ".git" not in p.parts}
        self.run_main(self.argv())
        after = {p: p.stat().st_mtime_ns for p in self.core.rglob("*") if ".git" not in p.parts}
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
