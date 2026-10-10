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
        st.backup(self.database, self.out / "b.sqlite3")
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
