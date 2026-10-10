# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_backup_encryption.py
# Description : Sauvegarde chiffrée des conversations avec age : aucun clair sur disque, déchiffrement vérifié, refus
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from eidolon_core import backup_encryption as be
from eidolon_core import conversation_storage as st
from eidolon_core import conversation_store as cs
from eidolon_core import personality as pe
from eidolon_core.contracts import ContractError, encode
from eidolon_core.diagnostics import synthetic_runtime
from eidolon_core.store import Store
from tests.test_conversation_storage import Base as V1Base

SRC = str(Path(__file__).resolve().parents[1] / "src")
ENV = dict(os.environ, PYTHONPATH=SRC, PYTHONDONTWRITEBYTECODE="1")
HAVE_AGE = (shutil.which("age") is not None and shutil.which("age-keygen") is not None
            and shutil.which("openssl") is not None)        # restoring now always checks a signature
SECRET_TEXT = "Diagnostique le serveur-secret-42."


def keypair(folder, name):
    identity = Path(folder) / f"{name}.key"
    subprocess.run(["age-keygen", "-o", str(identity)], check=True, capture_output=True)
    os.chmod(identity, 0o600)
    public = subprocess.run(["age-keygen", "-y", str(identity)], check=True, capture_output=True, text=True).stdout.strip()
    return identity, public


def signing_key(folder, name, algorithm="ed25519"):
    private, public = Path(folder) / f"{name}.pem", Path(folder) / f"{name}.pub.pem"
    options = ["-pkeyopt", "rsa_keygen_bits:1024"] if algorithm == "RSA" else []
    subprocess.run(["openssl", "genpkey", "-algorithm", algorithm, *options, "-out", str(private)],
                   check=True, capture_output=True)
    os.chmod(private, 0o600)
    subprocess.run(["openssl", "pkey", "-in", str(private), "-pubout", "-out", str(public)], check=True,
                   capture_output=True)
    return private, public


@unittest.skipUnless(HAVE_AGE, "age and openssl are not installed")
class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.runtime = synthetic_runtime(Store(self.root / "state"))
        self.conversations = cs.ConversationStore(self.runtime.store, create=True)
        cid = self.conversations.open(client_id="pc", client_key="k")["conversation_id"]
        self.conversations.append_turn(cid, client_id="pc", client_turn_key="t1", text=SECRET_TEXT)
        soul = self.root / "soul.json"
        soul.write_text(encode({"schema": pe.SCHEMA, "version": "0.2", "soul": "Sois curieux.", "evolving": []}))
        os.chmod(soul, 0o600)
        self.personality = pe.load("last-valid", str(soul), self.conversations).current
        self.database = self.conversations.path
        self.keys = self.root / "keys"; self.keys.mkdir()
        self.identity, self.public = keypair(self.keys, "toytoy")
        self.recipients = self.write_recipients(f"# clé publique de toytoy\n{self.public}\n")
        self.out = self.root / "out"; self.out.mkdir()
        self.sign_key, self.signer = signing_key(self.keys, "serveur")

    def write_recipients(self, text, mode=0o644, name="recipients.txt"):
        path = self.keys / name
        path.write_text(text)
        os.chmod(path, mode)
        return path


class EncryptedBackupTests(Base):
    def test_only_the_encrypted_form_is_written_and_it_decrypts_to_the_verified_copy(self):
        saved = st.backup(self.database, self.out / "b.age", encrypt_to=self.recipients, sign_with=self.sign_key)
        raw = (self.out / "b.age").read_bytes()
        self.assertTrue(raw.startswith(be.HEADER))
        for clear in (SECRET_TEXT.encode(), b"SQLite format 3", b"Sois curieux"):
            self.assertNotIn(clear, raw)
        self.assertEqual(sorted(p.name for p in self.out.iterdir()), ["b.age", "b.age.sig"])   # no plaintext
        self.assertEqual(os.stat(self.out / "b.age").st_mode & 0o777, 0o600)
        self.assertEqual((saved["encrypted"], saved["recipients"], saved["personality"]),
                         (True, 1, self.personality.identity()))
        self.assertEqual(saved["logical_sha256"], st.inspect(self.database)["logical_sha256"])
        plain = st.decrypt_backup(self.out / "b.age", self.identity, self.out / "plain.sqlite3", signer=self.signer)
        self.assertEqual((plain["logical_sha256"], plain["personality"], plain["file_sha256"]),
                         (saved["logical_sha256"], saved["personality"], saved["plaintext_sha256"]))
        self.assertEqual(os.stat(self.out / "plain.sqlite3").st_mode & 0o777, 0o600)

    def test_restore_from_an_encrypted_backup(self):
        st.backup(self.database, self.out / "b.age", encrypt_to=self.recipients, sign_with=self.sign_key)
        cid = self.conversations.open(client_id="pc", client_key="after")["conversation_id"]   # lost by restore
        st.decrypt_backup(self.out / "b.age", self.identity, self.out / "plain.sqlite3", signer=self.signer)
        os.replace(self.out / "plain.sqlite3", self.database)                               # server stopped
        for extra in ("-wal", "-shm"):
            Path(str(self.database) + extra).unlink(missing_ok=True)
        reopened = cs.ConversationStore(self.runtime.store)
        self.assertEqual(pe.build(pe.read_copy(reopened)), self.personality)
        with self.assertRaises(ContractError):
            reopened.page(cid)

    def test_several_recipients_each_can_decrypt(self):
        other_identity, other_public = keypair(self.keys, "secours")
        recipients = self.write_recipients(f"{self.public}\n\n{other_public}\n", name="two.txt")
        saved = st.backup(self.database, self.out / "b.age", encrypt_to=recipients, sign_with=self.sign_key)
        self.assertEqual(saved["recipients"], 2)
        for n, identity in enumerate((self.identity, other_identity)):
            plain = st.decrypt_backup(self.out / "b.age", identity, self.out / f"p{n}.sqlite3", signer=self.signer)
            self.assertEqual(plain["logical_sha256"], saved["logical_sha256"])

    def test_an_encrypted_backup_is_never_read_as_a_plain_one(self):
        st.backup(self.database, self.out / "b.age", encrypt_to=self.recipients, sign_with=self.sign_key)
        with self.assertRaisesRegex(ContractError, "BACKUP_ENCRYPTED"):
            st.verify_backup(self.out / "b.age")


class DecryptionRefusalTests(Base):
    def setUp(self):
        super().setUp()
        st.backup(self.database, self.out / "b.age", encrypt_to=self.recipients, sign_with=self.sign_key)

    def assert_refused(self, code, source=None, identity=None):
        with self.assertRaisesRegex(ContractError, code):
            st.decrypt_backup(source or self.out / "b.age", identity or self.identity, self.out / "plain.sqlite3",
                              signer=self.signer)
        self.assertFalse((self.out / "plain.sqlite3").exists())                     # nothing partial kept

    def test_wrong_identity(self):
        other, _ = keypair(self.keys, "autre")
        self.assert_refused("BACKUP_DECRYPTION_FAILED", identity=other)

    def test_modified_or_truncated_backup(self):
        raw = bytearray((self.out / "b.age").read_bytes())
        raw[-5] ^= 0x01
        modified, short = self.out / "modified.age", self.out / "short.age"
        modified.write_bytes(bytes(raw))
        short.write_bytes(bytes(raw[: len(raw) // 2]))
        for source in (modified, short):
            shutil.copy(self.out / "b.age.sig", str(source) + ".sig")
            self.assert_refused("BACKUP_SIGNATURE_INVALID", source=source)      # the signature stops it first
            # and age itself authenticates the content, should a file ever reach it:
            fd = os.memfd_create("plain")
            try:
                with self.assertRaisesRegex(ContractError, "BACKUP_DECRYPTION_FAILED"):
                    be.decrypt(source, self.identity, fd)
            finally:
                os.close(fd)

    def test_the_signer_is_mandatory(self):
        with self.assertRaisesRegex(ContractError, "BACKUP_SIGNER_REQUIRED"):
            st.decrypt_backup(self.out / "b.age", self.identity, self.out / "plain.sqlite3", signer=None)
        with self.assertRaises(TypeError):
            st.decrypt_backup(self.out / "b.age", self.identity, self.out / "plain.sqlite3")
        self.assertFalse((self.out / "plain.sqlite3").exists())

    def test_identity_must_be_private(self):
        os.chmod(self.identity, 0o644)
        self.assert_refused("AGE_IDENTITY_REFUSED")
        os.chmod(self.identity, 0o600)
        link = self.keys / "link.key"
        link.symlink_to(self.identity)
        self.assert_refused("AGE_IDENTITY_REFUSED", identity=link)

    def test_existing_output_is_never_overwritten(self):
        (self.out / "plain.sqlite3").write_bytes(b"garder")
        with self.assertRaisesRegex(ContractError, "BACKUP_PATH_REFUSED"):
            st.decrypt_backup(self.out / "b.age", self.identity, self.out / "plain.sqlite3", signer=self.signer)
        self.assertEqual((self.out / "plain.sqlite3").read_bytes(), b"garder")


class RecipientRefusalTests(Base):
    def assert_refused(self, code, recipients):
        with self.assertRaisesRegex(ContractError, code):
            st.backup(self.database, self.out / "b.age", encrypt_to=recipients)
        self.assertEqual(list(self.out.iterdir()), [])                              # nothing written

    def test_invalid_recipient_files(self):
        cases = {"empty": ("# rien\n", 0o644), "not a key": ("ssh-ed25519 AAAA test\n", 0o644),
                 "secret key": ("AGE-SECRET-KEY-1QQQQ\n", 0o644), "duplicate": (f"{self.public}\n{self.public}\n", 0o644),
                 "group writable": (f"{self.public}\n", 0o664), "binary": ("é\n", 0o644)}
        for name, (text, mode) in cases.items():
            with self.subTest(name):
                self.assert_refused("AGE_RECIPIENTS_REFUSED", self.write_recipients(text, mode, name=name))
        link = self.keys / "link.txt"
        link.symlink_to(self.recipients)
        self.assert_refused("AGE_RECIPIENTS_REFUSED", link)

    def test_too_large_for_an_in_memory_copy_is_refused_before_writing(self):
        with patch.object(st, "MAX_IN_MEMORY_BACKUP", 1024):
            self.assert_refused("BACKUP_TOO_LARGE_FOR_MEMORY", self.recipients)

    def test_age_missing_writes_nothing(self):
        with patch("eidolon_core.backup_encryption.shutil.which", return_value=None):
            self.assert_refused("AGE_UNAVAILABLE", self.recipients)

    def test_age_failure_leaves_no_file(self):
        with patch("eidolon_core.backup_encryption.subprocess.run",
                   return_value=subprocess.CompletedProcess([], 1)):
            self.assert_refused("BACKUP_ENCRYPTION_FAILED", self.recipients)


@unittest.skipUnless(HAVE_AGE, "age and openssl are not installed")
class EncryptedMigrationTests(V1Base):
    def test_migration_after_an_encrypted_backup_and_rollback_from_it(self):
        identity, public = keypair(self.base, "toytoy")
        recipients = self.base / "recipients.txt"
        recipients.write_text(public + "\n")
        key, signer = signing_key(self.base, "serveur")
        result = st.migrate_with_backup(self.runtime.store, self.base / "pre.age", encrypt_to=recipients,
                                        sign_with=key)
        self.assertEqual((result["status"], result["from_version"]), ("MIGRATED", 1))
        self.assertTrue((self.base / "pre.age").read_bytes().startswith(be.HEADER))
        plain = st.decrypt_backup(self.base / "pre.age", identity, self.base / "pre.sqlite3", signer=signer)
        self.assertEqual((plain["version"], plain["logical_sha256"]), (1, result["backup"]["logical_sha256"]))
        os.replace(self.base / "pre.sqlite3", self.path)                              # rollback
        self.assertEqual((self.version(), self.core()), (1, self.core_before))


@unittest.skipUnless(HAVE_AGE, "age and openssl are not installed")
class CommandTests(Base):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, "-m", "eidolon_core.conversation_api", "--state",
                               str(self.root / "state"), *args], env=ENV, capture_output=True, text=True, timeout=120)

    def test_backup_and_decrypt_commands(self):
        done = self.run_cli("backup", "--output", str(self.out / "b.age"), "--encrypt-to", str(self.recipients),
                            "--sign-with", str(self.sign_key))
        saved = json.loads(done.stdout)
        self.assertEqual((done.returncode, saved["encrypted"], saved["recipients"]), (0, True, 1), done.stderr)
        done = self.run_cli("decrypt-backup", "--input", str(self.out / "b.age"), "--identity", str(self.identity),
                            "--output", str(self.out / "plain.sqlite3"))
        self.assertEqual(done.returncode, 2)                                  # --signer is mandatory
        self.assertIn("--signer", done.stderr)
        done = self.run_cli("decrypt-backup", "--input", str(self.out / "b.age"), "--identity", str(self.identity),
                            "--output", str(self.out / "plain.sqlite3"), "--signer", str(self.signer))
        plain = json.loads(done.stdout)
        self.assertEqual((done.returncode, plain["logical_sha256"]), (0, saved["logical_sha256"]))
        self.assertNotIn(str(self.identity), done.stdout + done.stderr)
        done = self.run_cli("decrypt-backup", "--input", str(self.out / "b.age"), "--identity", str(self.recipients),
                            "--output", str(self.out / "again.sqlite3"), "--signer", str(self.signer))
        self.assertEqual((done.returncode, json.loads(done.stdout)["error"]), (2, "AGE_IDENTITY_REFUSED"))


if __name__ == "__main__":
    unittest.main()
