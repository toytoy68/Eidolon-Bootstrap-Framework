# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_build_beta_bundle.py
# Description : Archive de sources bêta : reproductible, allow-list, aucun fichier non suivi ni secret (C-TASK-G044)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
import gzip
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest

TOOL = Path(__file__).resolve().parents[1] / "tools" / "build_beta_bundle.py"
spec = importlib.util.spec_from_file_location("build_beta_bundle", TOOL)
bundle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bundle)

SECRET = "SECRET-SYNTHETIQUE-G044-ne-doit-pas-sortir"


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                           "-c", "commit.gpgsign=false", *args], check=True, capture_output=True, text=True).stdout.strip()


class BundleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name) / "repo"
        self.repo.mkdir()
        git(self.repo, "init", "-q")
        for f in bundle.ALLOW_FILES:
            path = self.repo / f
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("contenu " + f + "\n")
        core = self.repo / "eidolon-core/src/eidolon_core"
        core.mkdir(parents=True)
        (core / "__init__.py").write_text("VERSION = 1\n")
        launchers = self.repo / "eidolon-core/desktop/connected/launchers"
        launchers.mkdir(parents=True)
        (launchers / "run.ps1").write_text("Write-Output 'x'\n")
        os.chmod(launchers / "run.ps1", 0o755)
        (self.repo / "01-system.sh").write_text("# bootstrap " + SECRET + "\n")      # tracked, outside the allow-list
        (self.repo / "eidolon-core/tests").mkdir()
        (self.repo / "eidolon-core/tests/test_x.py").write_text("# test\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "fixture")
        self.commit = git(self.repo, "rev-parse", "HEAD")
        # Untracked sentinels INSIDE allow-listed folders: must never be read.
        (core / "untracked.py").write_text(SECRET + "\n")
        (core / "read-token").write_text(SECRET + "\n")
        (self.repo / "eidolon-core/desktop/connected/app.js").write_text("// modifié localement " + SECRET + "\n")
        self.out = Path(self.tmp.name) / "out"
        self.out.mkdir()

    def names_and_blob(self, path):
        with tarfile.open(path, "r:gz") as tar:
            names = tar.getnames()
            blob = b"".join(tar.extractfile(m).read() for m in tar.getmembers() if m.isfile())
        return names, blob

    def test_two_builds_are_byte_identical_and_verify(self):
        a = bundle.build(self.repo, self.commit, self.out / "a.tar.gz")
        b = bundle.build(self.repo, self.commit, self.out / "b.tar.gz")
        self.assertEqual((self.out / "a.tar.gz").read_bytes(), (self.out / "b.tar.gz").read_bytes())
        self.assertEqual(a["sha256"], b["sha256"])
        self.assertEqual(bundle.verify(self.out / "a.tar.gz")["commit"], self.commit)

    def test_only_tracked_allow_listed_content_from_the_commit(self):
        bundle.build(self.repo, self.commit, self.out / "a.tar.gz")
        names, blob = self.names_and_blob(self.out / "a.tar.gz")
        self.assertNotIn(SECRET.encode(), blob, "no untracked file, no local modification, no Bootstrap file")
        self.assertFalse(any(n.endswith(("01-system.sh", "untracked.py", "read-token", "test_x.py")) for n in names))
        self.assertTrue(any(n.endswith("eidolon-core/src/eidolon_core/__init__.py") for n in names))
        with tarfile.open(self.out / "a.tar.gz", "r:gz") as tar:
            modes = {m.name.split("/", 1)[1]: (m.mode, m.uid, m.gid, m.uname, m.mtime) for m in tar.getmembers()}
        self.assertEqual(modes["eidolon-core/desktop/connected/launchers/run.ps1"][0], 0o755)
        self.assertEqual({v[1:4] for v in modes.values()}, {(0, 0, "")})
        self.assertEqual(len({v[4] for v in modes.values()}), 1, "one fixed mtime: the commit time")
        with gzip.open(self.out / "a.tar.gz") as g:
            g.read()
        self.assertEqual((self.out / "a.tar.gz").read_bytes()[4:8], b"\0\0\0\0", "gzip mtime is zero")

    def test_manifest_lists_every_file_with_its_hash(self):
        bundle.build(self.repo, self.commit, self.out / "a.tar.gz")
        with tarfile.open(self.out / "a.tar.gz", "r:gz") as tar:
            root = tar.getnames()[0].split("/")[0]
            manifest = json.loads(tar.extractfile(root + "/MANIFEST.json").read())
            for f in manifest["files"]:
                self.assertEqual(hashlib.sha256(tar.extractfile(root + "/" + f["path"]).read()).hexdigest(), f["sha256"])
        self.assertEqual(manifest["commit"], self.commit)
        self.assertFalse(manifest["qualifies_beta"])

    def test_commit_must_be_explicit_full_sha(self):
        for value in ("HEAD", "master", self.commit[:12], "", "0" * 40):
            with self.subTest(value=value), self.assertRaises(bundle.BundleError):
                bundle.build(self.repo, value, self.out / ("x-" + str(len(value)) + ".tar.gz"))
        self.assertEqual(list(self.out.iterdir()), [], "nothing written on refusal")

    def test_existing_destination_is_never_overwritten(self):
        target = self.out / "a.tar.gz"
        target.write_bytes(b"ancien")
        with self.assertRaises(FileExistsError):
            bundle.build(self.repo, self.commit, target)
        self.assertEqual(target.read_bytes(), b"ancien")

    def test_symlink_forbidden_name_and_missing_file_are_refused(self):
        core = self.repo / "eidolon-core/src/eidolon_core"
        for sentinel in ("untracked.py", "read-token"):      # keep this test about its own cases
            (core / sentinel).unlink()
        os.symlink("/etc/hostname", core / "link.py")
        git(self.repo, "add", "-A", "eidolon-core/src")
        git(self.repo, "commit", "-q", "-m", "symlink")
        with self.assertRaisesRegex(bundle.BundleError, "symlink"):
            bundle.build(self.repo, git(self.repo, "rev-parse", "HEAD"), self.out / "s.tar.gz")
        (core / "link.py").unlink()
        (core / "state.sqlite3").write_bytes(b"x")
        git(self.repo, "add", "-A", "eidolon-core/src")
        git(self.repo, "commit", "-q", "-m", "state")
        with self.assertRaisesRegex(bundle.BundleError, "forbidden"):
            bundle.build(self.repo, git(self.repo, "rev-parse", "HEAD"), self.out / "f.tar.gz")
        (core / "state.sqlite3").unlink()
        git(self.repo, "rm", "-q", "eidolon-core/docs/BETA-ACCEPTANCE.md")
        git(self.repo, "add", "-A", "eidolon-core/src")
        git(self.repo, "commit", "-q", "-m", "missing")
        with self.assertRaisesRegex(bundle.BundleError, "missing"):
            bundle.build(self.repo, git(self.repo, "rev-parse", "HEAD"), self.out / "m.tar.gz")

    def test_tampered_or_unsafe_archive_fails_verification(self):
        bundle.build(self.repo, self.commit, self.out / "a.tar.gz")
        with tarfile.open(self.out / "a.tar.gz", "r:gz") as tar:
            members = [(m, tar.extractfile(m).read()) for m in tar.getmembers()]
        for label, change in (("contenu modifié", lambda m, d: d + b"#" if m.name.endswith("__init__.py") else d),
                              ("fichier ajouté", None)):
            raw = io.BytesIO()
            with tarfile.open(fileobj=raw, mode="w:gz") as tar:
                for m, d in members:
                    d2 = change(m, d) if change else d
                    m.size = len(d2)
                    tar.addfile(m, io.BytesIO(d2))
                if change is None:
                    extra = tarfile.TarInfo(members[0][0].name.split("/")[0] + "/eidolon-core/src/eidolon_core/ajout.py")
                    extra.size = 1
                    tar.addfile(extra, io.BytesIO(b"x"))
            path = self.out / (label.replace(" ", "-") + ".tar.gz")
            path.write_bytes(raw.getvalue())
            with self.subTest(label=label), self.assertRaises(bundle.BundleError):
                bundle.verify(path)

    def test_cli_codes(self):
        def run(*a):
            return subprocess.run([sys.executable, str(TOOL), "--repo", str(self.repo), *a], capture_output=True, text=True)
        ok = run("--commit", self.commit, "--output", str(self.out / "c.tar.gz"))
        self.assertEqual(ok.returncode, 0, ok.stdout + ok.stderr)
        self.assertEqual(json.loads(ok.stdout)["status"], "OK")
        again = run("--commit", self.commit, "--output", str(self.out / "c.tar.gz"))
        self.assertEqual((again.returncode, json.loads(again.stdout)["status"]), (2, "REFUSED"))

    def test_empty_duplicate_and_structurally_forged_archives_are_refused(self):
        bundle.build(self.repo, self.commit, self.out / "original.tar.gz")
        with tarfile.open(self.out / "original.tar.gz", "r:gz") as tar:
            members = [(m, tar.extractfile(m).read()) for m in tar.getmembers()]
        for case in ("empty", "duplicate-member", "empty-manifest", "duplicate-manifest-entry",
                     "wrong-size", "wrong-mode", "changed-start"):
            target = self.out / (case + ".tar.gz")
            with tarfile.open(target, "w:gz") as tar:
                if case != "empty":
                    import copy
                    for original, data in members:
                        m = copy.copy(original)
                        if m.name.endswith("MANIFEST.json"):
                            manifest = json.loads(data)
                            if case == "empty-manifest": manifest["files"] = []
                            if case == "duplicate-manifest-entry": manifest["files"].append(manifest["files"][0])
                            if case == "wrong-size": manifest["files"][0]["size"] += 1
                            data = json.dumps(manifest).encode()
                        elif case == "wrong-mode":
                            m.mode = 0o777
                        elif case == "changed-start" and m.name.endswith("START-HERE.md"):
                            data = b"invented installation commands"
                        m.size = len(data)
                        tar.addfile(m, io.BytesIO(data))
                        if case == "duplicate-member":
                            tar.addfile(m, io.BytesIO(data))
            with self.subTest(case=case), self.assertRaises(bundle.BundleError):
                bundle.verify(target)


class RealRepositoryBundleTest(unittest.TestCase):
    """The archive of the current commit extracts and runs the beta fixture and diagnostic."""

    def test_current_commit_bundle_runs_fixture_and_preflight(self):
        repo = Path(__file__).resolve().parents[2]
        try:
            commit = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], check=True, capture_output=True, text=True).stdout.strip()
        except (OSError, subprocess.CalledProcessError):
            self.skipTest("git repository unavailable")
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "beta.tar.gz"
            bundle.build(repo, commit, out)
            names = tarfile.open(out, "r:gz").getnames()
            self.assertFalse(any(n.endswith((".sh", ".sqlite3")) or "/tests/" in n or "collaboration" in n for n in names))
            with tarfile.open(out, "r:gz") as tar:
                tar.extractall(tmp, filter="data")
            core = Path(tmp) / ("eidolon-beta-" + commit[:12]) / "eidolon-core"
            env = dict(os.environ, PYTHONPATH=str(core / "src"), PYTHONDONTWRITEBYTECODE="1")
            fixture = Path(tmp) / "fx"
            made = subprocess.run([sys.executable, "-m", "eidolon_core.beta_fixture", "--output", str(fixture)],
                                  cwd=core, env=env, capture_output=True, text=True)
            self.assertEqual(made.returncode, 0, made.stdout + made.stderr)
            check = subprocess.run([sys.executable, "-m", "eidolon_core.http_api", "--state", str(fixture / "state"),
                                    "--token-file", str(fixture / "read-token"), "--web-root", "desktop/connected",
                                    "--port", "8765", "--check"], cwd=core, env=env, capture_output=True, text=True)
            self.assertEqual(check.returncode, 0, check.stdout + check.stderr)
            self.assertEqual(json.loads(check.stdout)["status"], "PASS")


if __name__ == "__main__":
    unittest.main()
