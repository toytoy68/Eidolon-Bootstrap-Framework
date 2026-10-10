"""Tests for DARME journal file permissions (POSIX)."""
import os
import stat
import tempfile
import unittest
from pathlib import Path

from eidolon_core.darme_store import DarmeJournal


@unittest.skipUnless(os.name == "posix", "POSIX file modes required")
class DarmeJournalPermissionTests(unittest.TestCase):
    def test_new_file_is_private(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "events.sqlite3"
            journal = DarmeJournal(path)
            journal.close()
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)

    def test_existing_world_readable_file_refused(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "events.sqlite3"
            path.touch(mode=0o600)
            path.chmod(0o644)
            with self.assertRaises(ValueError):
                DarmeJournal(path)

    def test_symlink_refused(self):
        with tempfile.TemporaryDirectory() as root:
            target = Path(root) / "real.sqlite3"
            target.touch()
            alias = Path(root) / "alias.sqlite3"
            alias.symlink_to(target)
            with self.assertRaises(ValueError):
                DarmeJournal(alias)


if __name__ == "__main__":
    unittest.main()
