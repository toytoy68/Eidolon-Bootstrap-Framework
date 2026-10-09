# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_conversation_storage.py
# Description : Évolution du stockage des conversations : inspection, version future, sauvegarde, migration, pannes (C-TASK-G099)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from eidolon_core import conversation as cv
from eidolon_core import conversation_storage as st
from eidolon_core import conversation_store as cs
from eidolon_core.contracts import ContractError
from eidolon_core.diagnostics import synthetic_runtime
from eidolon_core.store import Store

SRC = str(Path(__file__).resolve().parents[1] / "src")
ENV = dict(os.environ, PYTHONPATH=SRC, PYTHONDONTWRITEBYTECODE="1")


class Crash(BaseException):
    pass


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class Base(unittest.TestCase):
    """A v3 store with turns, a proposal, a submitted mission, then rewritten as an exact v1 store."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.state = self.base / "state"
        self.runtime = synthetic_runtime(Store(self.state))
        conv = cs.ConversationStore(self.runtime.store, create=True)
        self.cid = conv.open(client_id="pc", client_key="k")["conversation_id"]
        for n, text in enumerate(["Bonjour", "Diagnostique le nas."]):
            turn = conv.append_turn(self.cid, client_id="pc", client_turn_key=f"t{n}", text=text)["turn"]
            output = json.dumps({"version": 1, "kind": "proposal", "text": "Diagnostic proposé.",
                                 "proposal": {"template": cv.DIAGNOSTIC, "parameters": {"target_reference": "nas"}}})
            conv.record_reply(cv.decide_reply(turn, output, self.runtime.catalog,
                                              previous_proposal=conv.current_proposal(self.cid)))
        proposal = conv.current_proposal(self.cid)
        self.receipt = conv.submit(
            {"protocol": cv.SUBMISSION_PROTOCOL, "store_id": conv.store_id, "client_id": "pc", "command_key": "s1",
             "conversation_id": self.cid, "proposal_id": proposal["proposal_id"], "proposal_version": proposal["version"],
             "proposal_sha256": cv.proposal_sha256(proposal), "actor": "toytoy", "reason": "validé"},
            create=lambda request, intent: self.runtime.store.create(request, self.runtime.configuration(), intent=intent))
        self.path = conv.path
        self.missions_db = Path(self.runtime.store.directory) / "missions.sqlite3"
        with sqlite3.connect(self.path) as db:
            db.executescript("DROP TABLE media_proposals; DROP TABLE media_links; DROP TABLE attempts; DROP TABLE attachments; UPDATE meta SET value='%s' "
                             "WHERE key='schema'; PRAGMA user_version=1;" % cs.SCHEMA_V1)
        self.core_before = self.core()

    def core(self):
        with sqlite3.connect(self.path) as db:
            return {t: db.execute(f"SELECT * FROM {t} ORDER BY {o}").fetchall() for t, o in st.CORE_TABLES.items()}

    def version(self):
        with sqlite3.connect(self.path) as db:
            return db.execute("PRAGMA user_version").fetchone()[0]

    def missions(self):
        with self.runtime.store.connection() as db:
            return (db.execute("SELECT id, revision, body FROM missions ORDER BY id").fetchall(),
                    db.execute("SELECT count(*) FROM events").fetchone()[0])


class InspectionTests(Base):
    def test_old_version_is_reported_and_never_migrated_by_reading(self):
        before = sha(self.path)
        report = st.inspect(self.path)
        self.assertEqual((report["state"], report["version"], report["integrity"], report["migrated"]),
                         ("MIGRATION_REQUIRED", 1, "ok", False))
        self.assertEqual(report["rows"]["turns"], 2)
        with self.assertRaisesRegex(ContractError, "CONVERSATION_STORE_MIGRATION_REQUIRED"):
            cs.ConversationStore(self.runtime.store)
        self.assertEqual(sha(self.path), before)

    def test_future_version_is_refused_everywhere_and_nothing_is_written(self):
        with sqlite3.connect(self.path) as db:
            db.execute("PRAGMA user_version=9")
        before = sha(self.path)
        self.assertEqual(st.inspect(self.path)["state"], "FUTURE_VERSION")
        with self.assertRaisesRegex(ContractError, "CONVERSATION_STORE_UNAVAILABLE"):
            st.migrate_with_backup(self.runtime.store, self.base / "backup.sqlite3")
        with self.assertRaisesRegex(ContractError, "CONVERSATION_STORE_UNAVAILABLE"):
            cs.ConversationStore(self.runtime.store, migrate=True)
        self.assertFalse((self.base / "backup.sqlite3").exists())
        self.assertEqual(sha(self.path), before)


class MigrationTests(Base):
    def test_backup_then_migration_keeps_ids_order_references_and_replays_no_mission(self):
        missions, missions_sha = self.missions(), sha(self.missions_db)
        result = st.migrate_with_backup(self.runtime.store, self.base / "backup.sqlite3")
        self.assertEqual((result["status"], result["from_version"], result["version"]), ("MIGRATED", 1, cs.VERSION))
        self.assertEqual(self.core(), self.core_before)                            # same rows, same order
        self.assertEqual((self.missions(), sha(self.missions_db)), (missions, missions_sha))
        backup = self.base / "backup.sqlite3"
        self.assertEqual(backup.stat().st_mode & 0o777, 0o600)
        saved = st.verify_backup(backup)
        self.assertEqual((saved["version"], saved["file_sha256"]), (1, result["backup"]["file_sha256"]))
        conv = cs.ConversationStore(self.runtime.store)
        self.assertEqual(conv.receipt(client_id="pc", command_key="s1"), self.receipt)
        self.assertEqual(len(conv.page(self.cid)["items"]), 2)
        again = st.migrate_with_backup(self.runtime.store, self.base / "other.sqlite3")
        self.assertEqual(again["status"], "ALREADY_CURRENT")

    def test_rollback_is_putting_the_backup_back(self):
        st.migrate_with_backup(self.runtime.store, self.base / "backup.sqlite3")
        os.replace(self.base / "backup.sqlite3", self.path)                        # server stopped
        self.assertEqual((self.version(), self.core()), (1, self.core_before))

    def test_interrupted_migration_leaves_a_valid_intermediate_version_and_resumes(self):
        def crash(name):
            if name == "MIGRATION_STEP_2":
                raise Crash()
        with self.assertRaises(Crash):
            st.migrate_with_backup(self.runtime.store, self.base / "b1.sqlite3", checkpoint=crash)
        self.assertEqual((self.version(), st.inspect(self.path)["state"]), (2, "MIGRATION_REQUIRED"))
        self.assertEqual(self.core(), self.core_before)
        result = st.migrate_with_backup(self.runtime.store, self.base / "b2.sqlite3")
        self.assertEqual((result["from_version"], result["version"]), (2, cs.VERSION))
        self.assertEqual(self.core(), self.core_before)

    def test_disk_error_during_a_step_rolls_it_back(self):
        def disk(name):
            raise sqlite3.OperationalError("disk I/O error")
        with self.assertRaisesRegex(ContractError, "CONVERSATION_STORE_UNAVAILABLE"):
            st.migrate_with_backup(self.runtime.store, self.base / "b.sqlite3", checkpoint=disk)
        self.assertEqual((self.version(), self.core()), (1, self.core_before))

    def test_backup_failure_migrates_nothing_and_leaves_no_partial_file(self):
        before = sha(self.path)
        with patch("eidolon_core.conversation_storage.os.fsync", side_effect=OSError(28, "No space left on device")):
            with self.assertRaisesRegex(ContractError, "BACKUP_FAILED"):
                st.migrate_with_backup(self.runtime.store, self.base / "full.sqlite3")
        self.assertFalse((self.base / "full.sqlite3").exists())
        with self.assertRaisesRegex(ContractError, "BACKUP_PATH_REFUSED"):
            st.migrate_with_backup(self.runtime.store, self.base / "absent-folder" / "b.sqlite3")
        (self.base / "taken.sqlite3").write_bytes(b"keep me")
        with self.assertRaisesRegex(ContractError, "BACKUP_PATH_REFUSED"):
            st.migrate_with_backup(self.runtime.store, self.base / "taken.sqlite3")
        self.assertEqual((self.base / "taken.sqlite3").read_bytes(), b"keep me")
        self.assertEqual((sha(self.path), self.version()), (before, 1))

    def test_a_write_after_the_backup_stops_the_migration(self):
        original = st.backup

        def backup_then_write(source, output):
            report = original(source, output)
            with sqlite3.connect(self.path) as db:
                db.execute("INSERT INTO conversations VALUES ('c-%s', 'pc', 'late', 'x', 0, NULL)" % ("9" * 32))
            return report
        with patch.object(st, "backup", backup_then_write):
            with self.assertRaisesRegex(ContractError, "BACKUP_STALE"):
                st.migrate_with_backup(self.runtime.store, self.base / "b.sqlite3")
        self.assertEqual(self.version(), 1)

    def test_a_damaged_backup_is_detected(self):
        st.backup(self.path, self.base / "b.sqlite3")
        raw = bytearray((self.base / "b.sqlite3").read_bytes()); raw[0:16] = b"not a database!!"
        (self.base / "b.sqlite3").write_bytes(bytes(raw))
        with self.assertRaises(ContractError):
            st.verify_backup(self.base / "b.sqlite3")


class CommandTests(Base):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, "-m", "eidolon_core.conversation_api", "--state", str(self.state), *args],
                              env=ENV, capture_output=True, text=True, timeout=60)

    def test_inspect_backup_and_migrate_commands(self):
        before = sha(self.path)
        done = self.run_cli("inspect-store")
        self.assertEqual((done.returncode, json.loads(done.stdout)["state"]), (3, "MIGRATION_REQUIRED"))
        self.assertEqual(self.run_cli("migrate").returncode, 2)                    # a backup is mandatory
        self.assertEqual(sha(self.path), before)
        saved = self.run_cli("backup", "--output", str(self.base / "manual.sqlite3"))
        self.assertEqual(json.loads(saved.stdout)["version"], 1)
        missions = self.missions()
        migrated = self.run_cli("migrate", "--backup", str(self.base / "pre.sqlite3"))
        self.assertEqual(json.loads(migrated.stdout)["status"], "MIGRATED", migrated.stdout + migrated.stderr)
        done = self.run_cli("inspect-store")
        self.assertEqual((done.returncode, json.loads(done.stdout)["state"]), (0, "CURRENT"))
        self.assertEqual((self.core(), self.missions()), (self.core_before, missions))


if __name__ == "__main__":
    unittest.main()
