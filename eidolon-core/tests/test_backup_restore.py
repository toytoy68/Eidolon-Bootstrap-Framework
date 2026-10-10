# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_backup_restore.py
# Description : Restauration des conversations : signature obligatoire, même Store, remplacement conservé, refus sans effet
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

import hashlib
import json
import os
import shutil
from pathlib import Path
import sqlite3
import subprocess
import sys
import unittest

from eidolon_core import conversation_storage as st
from eidolon_core import conversation_store as cs
from eidolon_core import personality as pe
from eidolon_core.contracts import ContractError
from eidolon_core.diagnostics import synthetic_runtime
from eidolon_core.store import Store
from tests.test_backup_encryption import ENV, HAVE_AGE, Base, signing_key


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


@unittest.skipUnless(HAVE_AGE, "age and openssl are required")
class RestoreTests(Base):
    def setUp(self):
        super().setUp()
        self.store = self.runtime.store
        self.folder = self.conversations.directory

    def leftovers(self):
        return sorted(p.name for p in self.folder.iterdir() if p.name.startswith(".restore-"))

    def add_conversation(self):
        return self.conversations.open(client_id="pc", client_key=os.urandom(4).hex())["conversation_id"]

    def assert_refused(self, code, source, **options):
        before = sha(self.database)
        with self.assertRaisesRegex(ContractError, code):
            st.restore_backup(self.store, source, **{"signer": self.signer, **options})
        self.assertEqual((sha(self.database), self.leftovers()), (before, []))          # untouched, no residue

    def test_a_signed_plain_backup_is_restored_and_the_replaced_database_kept(self):
        st.backup(self.database, self.out / "b.sqlite3", sign_with=self.sign_key)
        later = self.add_conversation()
        replaced = sha(self.database)
        result = st.restore_backup(self.store, self.out / "b.sqlite3", signer=self.signer)
        self.assertEqual((result["status"], result["signature"]), ("RESTORED", "VERIFIED"))
        kept = self.folder / result["replaced_kept_as"]
        self.assertEqual((sha(kept), os.stat(kept).st_mode & 0o777), (replaced, 0o600))
        reopened = cs.ConversationStore(self.store)
        with self.assertRaises(ContractError):
            reopened.page(later)                                                 # written after the backup
        self.assertEqual(pe.build(pe.read_copy(reopened)), self.personality)
        self.assertEqual(os.stat(self.database).st_mode & 0o777, 0o600)
        self.assertEqual(self.leftovers(), [])

    def test_a_signed_encrypted_backup_is_restored_with_the_identity(self):
        saved = st.backup(self.database, self.out / "b.age", encrypt_to=self.recipients, sign_with=self.sign_key)
        self.add_conversation()
        result = st.restore_backup(self.store, self.out / "b.age", signer=self.signer, identity=self.identity)
        self.assertEqual(result["logical_sha256"], saved["logical_sha256"])
        self.assertEqual(st.inspect(self.database)["logical_sha256"], saved["logical_sha256"])

    def test_an_unsigned_backup_is_never_restored(self):
        st.backup(self.database, self.out / "b.sqlite3", sign_with=self.sign_key)
        os.unlink(self.out / "b.sqlite3.sig")                                     # Core no longer makes one
        self.assert_refused("BACKUP_SIGNATURE_MISSING", self.out / "b.sqlite3")
        with self.assertRaisesRegex(ContractError, "BACKUP_SIGNER_REQUIRED"):
            st.restore_backup(self.store, self.out / "b.sqlite3", signer=None)
        with self.assertRaises(TypeError):
            st.restore_backup(self.store, self.out / "b.sqlite3")

    def test_another_signer_or_a_modified_backup_is_refused(self):
        st.backup(self.database, self.out / "b.sqlite3", sign_with=self.sign_key)
        _, other = signing_key(self.keys, "autre")
        self.assert_refused("BACKUP_SIGNATURE_WRONG_SIGNER", self.out / "b.sqlite3", signer=other)
        with open(self.out / "b.sqlite3", "ab") as handle:
            handle.write(b"\0")
        self.assert_refused("BACKUP_SIGNATURE_INVALID", self.out / "b.sqlite3")

    def test_a_backup_of_another_store_is_refused(self):
        other_runtime = synthetic_runtime(Store(self.root / "other-state"))
        other = cs.ConversationStore(other_runtime.store, create=True)
        st.backup(other.path, self.out / "other.sqlite3", sign_with=self.sign_key)
        self.assert_refused("RESTORE_REFUSED", self.out / "other.sqlite3")

    def test_an_encrypted_backup_needs_the_identity(self):
        st.backup(self.database, self.out / "b.age", encrypt_to=self.recipients, sign_with=self.sign_key)
        self.assert_refused("RESTORE_REFUSED", self.out / "b.age")

    def test_refused_while_another_process_holds_the_database(self):
        st.backup(self.database, self.out / "b.sqlite3", sign_with=self.sign_key)
        holder = sqlite3.connect(self.database, isolation_level=None)
        try:
            holder.execute("BEGIN IMMEDIATE")                                     # a running writer
            self.assert_refused("CONVERSATION_STORE_BUSY", self.out / "b.sqlite3")
        finally:
            holder.close()

    def test_a_server_left_running_cannot_write_into_the_replaced_file(self):
        st.backup(self.database, self.out / "b.sqlite3", sign_with=self.sign_key)
        st.restore_backup(self.store, self.out / "b.sqlite3", signer=self.signer)
        with self.assertRaisesRegex(ContractError, "STORE_CHANGED"):
            self.add_conversation()                    # self.conversations was opened before the restore

    def test_two_restores_in_the_same_second_keep_both_replaced_databases(self):
        st.backup(self.database, self.out / "b.sqlite3", sign_with=self.sign_key)
        first = st.restore_backup(self.store, self.out / "b.sqlite3", signer=self.signer)["replaced_kept_as"]
        second = st.restore_backup(self.store, self.out / "b.sqlite3", signer=self.signer)["replaced_kept_as"]
        self.assertNotEqual(first, second)
        self.assertTrue((self.folder / first).exists() and (self.folder / second).exists())

    def test_a_concurrent_restore_that_replaced_the_file_is_detected_under_the_lock(self):
        st.backup(self.database, self.out / "b.sqlite3", sign_with=self.sign_key)
        other = self.folder / "other.sqlite3"
        shutil.copy(self.database, other)
        os.chmod(other, 0o600)

        def concurrent(name):
            if name == "locked":                    # another restore swapped the file meanwhile
                os.replace(other, self.database)
        before = sha(other)
        with self.assertRaisesRegex(ContractError, "concurrent restore"):
            st.restore_backup(self.store, self.out / "b.sqlite3", signer=self.signer, checkpoint=concurrent)
        self.assertEqual((sha(self.database), self.leftovers()), (before, []))

    def test_a_process_killed_at_each_step_leaves_a_usable_database(self):
        st.backup(self.database, self.out / "b.sqlite3", sign_with=self.sign_key)
        backup_sha = st.inspect(self.out / "b.sqlite3")["logical_sha256"]
        for step in ("staged", "locked", "linked"):
            with self.subTest(step=step):
                self.add_conversation()
                current = st.inspect(self.database)["logical_sha256"]
                script = ("import os, sys; from pathlib import Path; from eidolon_core.store import Store; "
                          "from eidolon_core import conversation_storage as st; "
                          "st.restore_backup(Store(sys.argv[1]), sys.argv[2], signer=sys.argv[3], "
                          "checkpoint=lambda n: os._exit(9) if n == sys.argv[4] else None)")
                done = subprocess.run([sys.executable, "-c", script, str(self.root / "state"),
                                       str(self.out / "b.sqlite3"), str(self.signer), step],
                                      env=ENV, capture_output=True, timeout=60)
                self.assertEqual(done.returncode, 9)                              # really killed, no cleanup
                report = st.inspect(self.database)
                self.assertEqual((report["integrity"], report["state"]), ("ok", "CURRENT"))
                self.assertEqual(report["logical_sha256"], current)              # swap never reached
                self.assertEqual(len(self.leftovers()), 1)                        # staged copy left (0600)
                staged = self.folder / self.leftovers()[0]
                self.assertEqual((os.stat(staged).st_mode & 0o777, st.inspect(staged)["logical_sha256"]),
                                 (0o600, backup_sha))
                staged.unlink()
                for kept in self.folder.glob("conversations.sqlite3.before-restore-*"):
                    self.assertEqual(st.inspect(kept)["logical_sha256"], current)  # a link to the old one
                    kept.unlink()
        result = st.restore_backup(self.store, self.out / "b.sqlite3", signer=self.signer)  # rerun works
        self.assertEqual(result["status"], "RESTORED")

    def test_a_missing_database_is_restored(self):
        st.backup(self.database, self.out / "b.sqlite3", sign_with=self.sign_key)
        os.unlink(self.database)
        result = st.restore_backup(self.store, self.out / "b.sqlite3", signer=self.signer)
        self.assertEqual((result["status"], result["replaced_kept_as"]), ("RESTORED", None))
        cs.ConversationStore(self.store)

    def test_command_requires_the_signer(self):
        st.backup(self.database, self.out / "b.sqlite3", sign_with=self.sign_key)
        def cli(*args):
            return subprocess.run([sys.executable, "-m", "eidolon_core.conversation_api", "--state",
                                   str(self.root / "state"), "restore-backup", "--input", str(self.out / "b.sqlite3"),
                                   *args], env=ENV, capture_output=True, text=True, timeout=120)
        done = cli()
        self.assertEqual(done.returncode, 2)
        self.assertIn("--signer", done.stderr)
        done = cli("--signer", str(self.signer))
        self.assertEqual((done.returncode, json.loads(done.stdout)["status"]), (0, "RESTORED"), done.stderr)


if __name__ == "__main__":
    unittest.main()
