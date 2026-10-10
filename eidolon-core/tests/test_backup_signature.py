# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_backup_signature.py
# Description : Signature Ed25519 des sauvegardes : vérifiée avant restauration, fichier altéré ou forgé refusé
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import unittest
from unittest.mock import patch

from eidolon_core import backup_signature as bs
from eidolon_core import conversation_storage as st
from eidolon_core.contracts import ContractError, encode
from tests.test_backup_encryption import ENV, HAVE_AGE, Base as EncryptionBase, keypair
from tests.test_conversation_storage import Base as V1Base

HAVE_OPENSSL = shutil.which("openssl") is not None


def signing_key(folder, name, algorithm="ed25519"):
    private, public = Path(folder) / f"{name}.pem", Path(folder) / f"{name}.pub.pem"
    options = ["-pkeyopt", "rsa_keygen_bits:1024"] if algorithm == "RSA" else []
    subprocess.run(["openssl", "genpkey", "-algorithm", algorithm, *options, "-out", str(private)],
                   check=True, capture_output=True)
    os.chmod(private, 0o600)
    subprocess.run(["openssl", "pkey", "-in", str(private), "-pubout", "-out", str(public)], check=True,
                   capture_output=True)
    return private, public


@unittest.skipUnless(HAVE_OPENSSL and HAVE_AGE, "openssl and age are required")
class Base(EncryptionBase):
    def setUp(self):
        super().setUp()
        self.sign_key, self.signer = signing_key(self.keys, "serveur")

    def signed(self, name="b.age", encrypted=True):
        options = {"encrypt_to": self.recipients} if encrypted else {}
        return st.backup(self.database, self.out / name, sign_with=self.sign_key, **options)


class SigningTests(Base):
    def test_a_plain_signed_backup_verifies(self):
        saved = self.signed("b.sqlite3", encrypted=False)
        sig = self.out / "b.sqlite3.sig"
        self.assertEqual(os.stat(sig).st_mode & 0o777, 0o600)
        checked = st.verify_signed_backup(self.out / "b.sqlite3", self.signer)
        self.assertEqual((checked["signature"]["signature"], checked["signature"]["signer"], saved["signer"]),
                         ("VERIFIED", saved["signer"], bs.fingerprint(bs.read_public_key(self.signer))))
        self.assertEqual(checked["backup"]["logical_sha256"], saved["logical_sha256"])
        self.assertNotIn(b"PRIVATE", sig.read_bytes())

    def test_an_encrypted_signed_backup_is_checked_before_decryption(self):
        saved = self.signed()
        self.assertEqual(sorted(p.name for p in self.out.iterdir()), ["b.age", "b.age.sig"])
        manifest = json.loads((self.out / "b.age.sig").read_text())["manifest"]
        self.assertEqual((manifest["encrypted"], manifest["plaintext_sha256"]), (True, saved["plaintext_sha256"]))
        plain = st.decrypt_backup(self.out / "b.age", self.identity, self.out / "plain.sqlite3", signer=self.signer)
        self.assertEqual((plain["signature"], plain["logical_sha256"]), ("VERIFIED", saved["logical_sha256"]))
        self.assertIsNone(st.verify_signed_backup(self.out / "b.age", self.signer)["backup"])


class RefusalTests(Base):
    def setUp(self):
        super().setUp()
        self.signed()

    def assert_no_restore(self, code, source=None, signer=None):
        with self.assertRaisesRegex(ContractError, code):
            st.decrypt_backup(source or self.out / "b.age", self.identity, self.out / "plain.sqlite3",
                              signer=signer or self.signer)
        self.assertFalse((self.out / "plain.sqlite3").exists())                  # nothing decrypted

    def test_a_modified_backup_is_refused_before_decrypting(self):
        raw = bytearray((self.out / "b.age").read_bytes()); raw[-3] ^= 1
        (self.out / "b.age").write_bytes(bytes(raw))
        self.assert_no_restore("BACKUP_SIGNATURE_INVALID")

    def test_a_backup_forged_with_the_public_recipient_is_refused(self):
        os.unlink(self.out / "b.age")
        st.backup(self.database, self.out / "b.age", encrypt_to=self.recipients)   # valid age file, not signed by us
        self.assert_no_restore("BACKUP_SIGNATURE_INVALID")
        forger_key, forger_public = signing_key(self.keys, "intrus")
        os.unlink(self.out / "b.age"); os.unlink(self.out / "b.age.sig")
        st.backup(self.database, self.out / "b.age", encrypt_to=self.recipients, sign_with=forger_key)
        self.assert_no_restore("BACKUP_SIGNATURE_WRONG_SIGNER")

    def test_a_modified_manifest_is_refused(self):
        document = json.loads((self.out / "b.age.sig").read_text())
        document["manifest"]["store_id"] = "s-" + "0" * 32
        (self.out / "b.age.sig").write_text(encode(document))
        self.assert_no_restore("BACKUP_SIGNATURE_INVALID")

    def test_a_signature_from_another_backup_is_refused(self):
        self.signed("other.age")
        shutil.copy(self.out / "other.age.sig", self.out / "b.age.sig")
        self.assert_no_restore("BACKUP_SIGNATURE_INVALID")

    def test_a_missing_or_unreadable_signature_is_refused(self):
        os.rename(self.out / "b.age.sig", self.out / "kept.sig")
        self.assert_no_restore("BACKUP_SIGNATURE_MISSING")
        (self.out / "b.age.sig").write_text("{pas du json")
        self.assert_no_restore("BACKUP_SIGNATURE_INVALID")

    def test_the_expected_signer_key_is_checked(self):
        _, rsa_public = signing_key(self.keys, "rsa", "RSA")
        self.assert_no_restore("SIGNER_KEY_REFUSED", signer=rsa_public)
        (self.keys / "bad.pem").write_text("pas une clé"); os.chmod(self.keys / "bad.pem", 0o644)
        self.assert_no_restore("SIGNER_KEY_REFUSED", signer=self.keys / "bad.pem")
        os.chmod(self.signer, 0o664)
        self.assert_no_restore("SIGNER_KEY_REFUSED")


class SigningRefusalTests(Base):
    def assert_nothing_written(self, code, **options):
        with self.assertRaisesRegex(ContractError, code):
            st.backup(self.database, self.out / "b.age", encrypt_to=self.recipients, **options)
        return sorted(p.name for p in self.out.iterdir())

    def test_signing_key_must_be_private_ed25519(self):
        os.chmod(self.sign_key, 0o644)
        self.assertEqual(self.assert_nothing_written("SIGNING_KEY_REFUSED", sign_with=self.sign_key), [])
        rsa_key, _ = signing_key(self.keys, "rsa", "RSA")
        self.assertEqual(self.assert_nothing_written("SIGNING_KEY_REFUSED", sign_with=rsa_key), [])

    def test_an_existing_signature_is_never_overwritten(self):
        (self.out / "b.age.sig").write_text("garder")
        self.assertEqual(self.assert_nothing_written("BACKUP_PATH_REFUSED", sign_with=self.sign_key), ["b.age.sig"])
        self.assertEqual((self.out / "b.age.sig").read_text(), "garder")

    def test_openssl_missing_leaves_nothing(self):
        real = shutil.which
        with patch("eidolon_core.backup_encryption.shutil.which",
                   side_effect=lambda name: None if name == "openssl" else real(name)):
            self.assertEqual(self.assert_nothing_written("OPENSSL_UNAVAILABLE", sign_with=self.sign_key), [])


@unittest.skipUnless(HAVE_OPENSSL and HAVE_AGE, "openssl and age are required")
class SignedMigrationTests(V1Base):
    def test_signed_encrypted_migration_backup_and_verified_rollback(self):
        identity, public = keypair(self.base, "toytoy")
        (self.base / "recipients.txt").write_text(public + "\n")
        key, signer = signing_key(self.base, "serveur")
        result = st.migrate_with_backup(self.runtime.store, self.base / "pre.age",
                                        encrypt_to=self.base / "recipients.txt", sign_with=key)
        self.assertEqual(result["status"], "MIGRATED")
        st.decrypt_backup(self.base / "pre.age", identity, self.base / "pre.sqlite3", signer=signer)
        os.replace(self.base / "pre.sqlite3", self.path)
        self.assertEqual((self.version(), self.core()), (1, self.core_before))


@unittest.skipUnless(HAVE_OPENSSL and HAVE_AGE, "openssl and age are required")
class CommandTests(Base):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, "-m", "eidolon_core.conversation_api", "--state",
                               str(self.root / "state"), *args], env=ENV, capture_output=True, text=True, timeout=120)

    def test_backup_verify_and_decrypt_commands(self):
        done = self.run_cli("backup", "--output", str(self.out / "b.age"), "--encrypt-to", str(self.recipients),
                            "--sign-with", str(self.sign_key))
        saved = json.loads(done.stdout)
        self.assertEqual((done.returncode, saved["signed"]), (0, True), done.stderr)
        done = self.run_cli("verify-backup", "--input", str(self.out / "b.age"), "--signer", str(self.signer))
        self.assertEqual((done.returncode, json.loads(done.stdout)["signature"]["signature"]), (0, "VERIFIED"))
        done = self.run_cli("decrypt-backup", "--input", str(self.out / "b.age"), "--identity", str(self.identity),
                            "--output", str(self.out / "plain.sqlite3"), "--signer", str(self.signer))
        self.assertEqual((done.returncode, json.loads(done.stdout)["signature"]), (0, "VERIFIED"))
        _, other = signing_key(self.keys, "autre")
        done = self.run_cli("verify-backup", "--input", str(self.out / "b.age"), "--signer", str(other))
        self.assertEqual((done.returncode, json.loads(done.stdout)["error"]), (2, "BACKUP_SIGNATURE_WRONG_SIGNER"))


if __name__ == "__main__":
    unittest.main()
