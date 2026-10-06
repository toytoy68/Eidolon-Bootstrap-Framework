# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_access_token.py
# Description : Publication exclusive et pannes du jeton de lecture
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

from eidolon_core import access_token
from eidolon_core.http_api import read_token


class AccessTokenTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.target = self.root / "read-token"

    def assert_clean(self, expected):
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), expected)

    def test_creates_private_compatible_secret_without_exporting_it(self):
        with patch("socket.socket", side_effect=AssertionError("no network")):
            report = access_token.create(self.target)
        self.assertEqual(report["status"], "CREATED")
        self.assertTrue(report["destination_created"])
        self.assertTrue(report["durability_confirmed"])
        self.assertTrue(report["cleanup_complete"])
        self.assertFalse(report["authorizes_execution"])
        self.assertFalse(report["existing_servers_updated"])
        token = read_token(self.target)
        self.assertEqual(len(token), 43)
        self.assertEqual(stat.S_IMODE(self.target.stat().st_mode), 0o600)
        self.assertEqual(self.target.stat().st_uid, os.getuid())
        for fmt in ("json", "human"):
            text = access_token.render(report, fmt)
            self.assertNotIn(token, text)
            self.assertNotIn(str(self.root), text)
        self.assert_clean(["read-token"])

    def test_new_files_have_distinct_tokens(self):
        access_token.create(self.target)
        other = self.root / "other"
        access_token.create(other)
        self.assertNotEqual(read_token(self.target), read_token(other))

    def test_existing_file_is_unchanged_even_on_repeat(self):
        self.target.write_text("existing data")
        before = self.target.stat()
        for _ in range(2):
            report = access_token.create(self.target)
            self.assertEqual(report["status"], "NOT_CREATED")
            self.assertEqual(report["code"], "DESTINATION_EXISTS")
            self.assertFalse(report["destination_created"])
        self.assertEqual(self.target.read_text(), "existing data")
        self.assertEqual(self.target.stat().st_ino, before.st_ino)
        self.assertEqual(self.target.stat().st_mode, before.st_mode)
        self.assert_clean(["read-token"])

    def test_symlink_directory_and_fifo_destinations_are_never_replaced(self):
        referent = self.root / "referent"
        referent.write_text("keep me")
        for kind in ("symlink", "directory", "fifo", "dangling"):
            with self.subTest(kind=kind):
                if kind == "directory":
                    self.target.mkdir()
                elif kind == "fifo":
                    os.mkfifo(self.target)
                else:
                    self.target.symlink_to(referent if kind == "symlink" else self.root / "absent")
                before = self.target.lstat()
                self.assertEqual(access_token.create(self.target)["code"], "DESTINATION_EXISTS")
                self.assertEqual(self.target.lstat().st_ino, before.st_ino)
                self.assertEqual(referent.read_text(), "keep me")
                self.assertFalse((self.root / "absent").exists())
                if kind == "directory":
                    self.target.rmdir()
                else:
                    self.target.unlink()

    def test_missing_or_symlink_parent_is_not_created_or_followed(self):
        missing = self.root / "missing"
        self.assertEqual(access_token.create(missing / "token")["code"], "PARENT_UNAVAILABLE")
        self.assertFalse(missing.exists())
        link = self.root / "link"
        link.symlink_to(self.root, target_is_directory=True)
        self.assertEqual(access_token.create(link / "token")["code"], "PARENT_UNAVAILABLE")
        self.assertFalse((self.root / "token").exists())

    def test_concurrent_creators_publish_exactly_one_complete_token(self):
        barrier = threading.Barrier(2)

        def worker():
            barrier.wait(timeout=3)
            return access_token.create(self.target)

        with ThreadPoolExecutor(max_workers=2) as pool:
            reports = list(pool.map(lambda _: worker(), range(2)))
        self.assertEqual(sorted(r["status"] for r in reports), ["CREATED", "NOT_CREATED"])
        self.assertEqual(len(read_token(self.target)), 43)
        self.assert_clean(["read-token"])

    def test_publication_exposes_complete_written_inode_only(self):
        real_link = os.link
        seen = []

        def inspect_link(source, target, **kwargs):
            fd = os.open(source, os.O_RDONLY, dir_fd=kwargs["src_dir_fd"])
            try:
                data = os.read(fd, 100)
                self.assertRegex(data, rb"^[A-Za-z0-9_-]{43}\n$")
                self.assertFalse(self.target.exists())
                seen.append(data)
            finally:
                os.close(fd)
            return real_link(source, target, **kwargs)

        with patch.object(access_token.os, "link", side_effect=inspect_link):
            self.assertEqual(access_token.create(self.target)["status"], "CREATED")
        self.assertEqual(self.target.read_bytes(), seen[0])

    def test_partial_writes_are_completed(self):
        real_write = os.write
        with patch.object(access_token.os, "write", side_effect=lambda fd, b: real_write(fd, b[:3])):
            self.assertEqual(access_token.create(self.target)["status"], "CREATED")
        self.assertEqual(len(read_token(self.target)), 43)

    def test_write_zero_or_exception_leaves_no_destination_or_staging(self):
        for failure in (0, OSError("secret error text")):
            mock = patch.object(access_token.os, "write", **(
                {"side_effect": failure} if isinstance(failure, Exception) else {"return_value": failure}))
            with mock:
                report = access_token.create(self.target)
            self.assertEqual(report["code"], "TOKEN_WRITE_FAILED")
            self.assertEqual(report["status"], "NOT_CREATED")
            self.assertNotIn("secret error text", json.dumps(report))
            self.assert_clean([])

    def test_file_sync_failure_never_publishes(self):
        with patch.object(access_token.os, "fsync", side_effect=OSError("disk fault")):
            report = access_token.create(self.target)
        self.assertEqual(report["code"], "TOKEN_WRITE_FAILED")
        self.assertFalse(report["destination_created"])
        self.assert_clean([])

    def test_link_failure_never_changes_destination(self):
        with patch.object(access_token.os, "link", side_effect=OSError("unsupported filesystem")):
            report = access_token.create(self.target)
        self.assertEqual(report["code"], "TOKEN_PUBLISH_FAILED")
        self.assertFalse(report["destination_created"])
        self.assert_clean([])

    def test_directory_sync_failure_keeps_published_token_and_reports_uncertainty(self):
        real_sync = os.fsync

        def fail_directory(fd):
            if stat.S_ISDIR(os.fstat(fd).st_mode):
                raise OSError("directory sync failed")
            real_sync(fd)

        with patch.object(access_token.os, "fsync", side_effect=fail_directory):
            report = access_token.create(self.target)
        self.assertEqual(report["status"], "CREATED_REVIEW_REQUIRED")
        self.assertEqual(report["code"], "TOKEN_DIRECTORY_SYNC_FAILED")
        self.assertTrue(report["destination_created"])
        self.assertFalse(report["durability_confirmed"])
        self.assertEqual(len(read_token(self.target)), 43)
        self.assert_clean(["read-token"])

    def test_cleanup_failure_does_not_erase_published_token(self):
        with patch.object(access_token.os, "unlink", side_effect=OSError("cleanup failed")):
            report = access_token.create(self.target)
        self.assertEqual(report["status"], "CREATED_REVIEW_REQUIRED")
        self.assertEqual(report["code"], "TOKEN_CLEANUP_FAILED")
        self.assertFalse(report["cleanup_complete"])
        self.assertTrue(report["destination_created"])
        self.assertEqual(len(read_token(self.target)), 43)
        staged = list(self.root.glob(".eidolon-read-token-*"))
        self.assertEqual(len(staged), 1)
        self.assertEqual(staged[0].stat().st_ino, self.target.stat().st_ino)

    def test_restrictive_umask_still_creates_private_readable_file(self):
        previous = os.umask(0o777)
        try:
            self.assertEqual(access_token.create(self.target)["status"], "CREATED")
        finally:
            os.umask(previous)
        self.assertEqual(stat.S_IMODE(self.target.stat().st_mode), 0o600)
        self.assertEqual(len(read_token(self.target)), 43)

    def test_actual_cli_reports_success_and_collision_without_secret(self):
        args = [sys.executable, "-m", "eidolon_core.access_token", "--output", str(self.target)]
        env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1] / "src"))
        for code in (0, 2):
            result = subprocess.run(args, env=env, text=True, capture_output=True, timeout=5)
            self.assertEqual(result.returncode, code, result.stderr)
            self.assertEqual(result.stderr, "")
            report = json.loads(result.stdout)
            self.assertEqual(report["status"], "CREATED" if code == 0 else "NOT_CREATED")
            self.assertNotIn(read_token(self.target), result.stdout)
            self.assertNotIn(str(self.root), result.stdout)


if __name__ == "__main__":
    unittest.main()
