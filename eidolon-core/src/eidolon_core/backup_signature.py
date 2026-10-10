# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : backup_signature.py
# Description : Signature Ed25519 des sauvegardes de conversations (openssl), vérifiée avant toute restauration
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

"""Ed25519 signature of a conversation backup, through the external `openssl` tool.

Core signs a small MANIFEST (canonical JSON) that names the backup file by its sha256 and size, and
what it holds (store, version, logical digest, encrypted or not). The signature file sits next to the
backup: <backup>.sig, schema eidolon-backup-signature/1.

- Signing key: an Ed25519 private key (PEM, 0600, owner), on the server, used unattended.
- Verification: the operator names the EXPECTED public key (PEM). The signer fingerprint, the
  signature, the purpose, then the file sha256 and size must all match; nothing is guessed.
- Keys and messages reach openssl as /dev/fd/N (opened or built by Core), with an empty environment
  and a time limit; openssl's messages are never relayed.
"""
import base64
import binascii
import hashlib
import json
import os
import subprocess

from .backup_encryption import EncryptionError, _open_owned, find_tool
from .contracts import encode

SCHEMA = "eidolon-backup-signature/1"
PURPOSE = "eidolon-conversation-backup"
SPKI_PREFIX = bytes.fromhex("302a300506032b6570032100")      # SubjectPublicKeyInfo of an Ed25519 key
MAX_FILE_BYTES = 8 * 1024
TIMEOUT_SECONDS = 120
MANIFEST_FIELDS = {"purpose", "file_sha256", "bytes", "encrypted", "store_id", "version", "logical_sha256",
                   "plaintext_sha256", "signed_at"}


class SignatureError(EncryptionError):
    pass


def fingerprint(public_der):
    return "ed25519:" + hashlib.sha256(public_der[len(SPKI_PREFIX):]).hexdigest()


def _ed25519(der):
    return isinstance(der, bytes) and len(der) == 44 and der.startswith(SPKI_PREFIX)


def read_public_key(path):
    """The expected signer: one PEM Ed25519 public key, in a file only its owner can modify."""
    fd = _open_owned(path, "SIGNER_KEY_REFUSED", private=False)
    try:
        raw = os.read(fd, MAX_FILE_BYTES + 1)
    finally:
        os.close(fd)
    try:
        lines = raw.decode("ascii").strip().splitlines()
        if lines[0] != "-----BEGIN PUBLIC KEY-----" or lines[-1] != "-----END PUBLIC KEY-----":
            raise ValueError
        der = base64.b64decode("".join(lines[1:-1]), validate=True)
    except (UnicodeError, ValueError, IndexError, binascii.Error):
        raise SignatureError("SIGNER_KEY_REFUSED: a PEM public key is required") from None
    if not _ed25519(der):
        raise SignatureError("SIGNER_KEY_REFUSED: an Ed25519 public key is required")
    return der


def _memory(data):
    fd = os.memfd_create("eidolon-signature")
    os.write(fd, data)
    os.lseek(fd, 0, os.SEEK_SET)
    return fd


def _openssl(arguments, fds):
    try:
        return subprocess.run([find_tool("openssl", "OPENSSL_UNAVAILABLE"), *arguments], capture_output=True,
                              env={}, pass_fds=tuple(fds), timeout=TIMEOUT_SECONDS, check=False)
    except (OSError, subprocess.TimeoutExpired):
        raise SignatureError("BACKUP_SIGNING_FAILED: openssl did not complete") from None


def _verify(message, signature, public_der):
    fds = [_memory(public_der), _memory(signature), _memory(message)]
    try:
        done = _openssl(["pkeyutl", "-verify", "-rawin", "-pubin", "-keyform", "DER", "-inkey", f"/dev/fd/{fds[0]}",
                         "-sigfile", f"/dev/fd/{fds[1]}", "-in", f"/dev/fd/{fds[2]}"], fds)
    finally:
        for fd in fds:
            os.close(fd)
    return done.returncode == 0 and done.stdout.strip() == b"Signature Verified Successfully"


def sign(manifest, key_path):
    """The signature document of this manifest, checked against the key's own public half."""
    if set(manifest) != MANIFEST_FIELDS or manifest["purpose"] != PURPOSE:
        raise SignatureError("BACKUP_SIGNING_FAILED: invalid manifest")
    message = encode(manifest).encode("utf-8")
    key = _open_owned(key_path, "SIGNING_KEY_REFUSED", private=True)
    data = _memory(message)
    try:
        public = _openssl(["pkey", "-in", f"/dev/fd/{key}", "-pubout", "-outform", "DER"], [key])
        if public.returncode != 0 or not _ed25519(public.stdout):
            raise SignatureError("SIGNING_KEY_REFUSED: an Ed25519 private key (PEM) is required")
        signed = _openssl(["pkeyutl", "-sign", "-rawin", "-inkey", f"/dev/fd/{key}", "-in", f"/dev/fd/{data}"],
                          [key, data])
    finally:
        os.close(key)
        os.close(data)
    if signed.returncode != 0 or len(signed.stdout) != 64 or not _verify(message, signed.stdout, public.stdout):
        raise SignatureError("BACKUP_SIGNING_FAILED: openssl did not produce a valid signature")
    return {"schema": SCHEMA, "manifest": manifest, "signer": fingerprint(public.stdout),
            "signature": base64.b64encode(signed.stdout).decode("ascii")}


def read_document(path):
    """A signature file: regular, no symlink, bounded, exact JSON fields. Never repaired."""
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        raise SignatureError("BACKUP_SIGNATURE_MISSING: no signature next to the backup") from None
    except OSError:
        raise SignatureError("BACKUP_SIGNATURE_INVALID: signature unreadable") from None
    try:
        raw = os.read(fd, MAX_FILE_BYTES + 1)
    finally:
        os.close(fd)

    def unique(pairs):
        result = {}
        for key, item in pairs:
            if key in result:
                raise ValueError("duplicate key")
            result[key] = item
        return result
    try:
        if len(raw) > MAX_FILE_BYTES:
            raise ValueError
        document = json.loads(raw.decode("utf-8"), object_pairs_hook=unique)
    except (ValueError, UnicodeError, RecursionError):
        raise SignatureError("BACKUP_SIGNATURE_INVALID: unreadable signature file") from None
    if (not isinstance(document, dict) or set(document) != {"schema", "manifest", "signer", "signature"}
            or document["schema"] != SCHEMA or not isinstance(document["manifest"], dict)
            or set(document["manifest"]) != MANIFEST_FIELDS or document["manifest"]["purpose"] != PURPOSE
            or not isinstance(document["signer"], str) or not isinstance(document["signature"], str)):
        raise SignatureError("BACKUP_SIGNATURE_INVALID: exact fields required")
    return document


def verify(document, public_der):
    """The signed manifest, if this exact expected key signed it."""
    if document["signer"] != fingerprint(public_der):
        raise SignatureError("BACKUP_SIGNATURE_WRONG_SIGNER: signed by another key than the expected one")
    try:
        signature = base64.b64decode(document["signature"], validate=True)
    except (ValueError, binascii.Error):
        raise SignatureError("BACKUP_SIGNATURE_INVALID: invalid encoding") from None
    if len(signature) != 64 or not _verify(encode(document["manifest"]).encode("utf-8"), signature, public_der):
        raise SignatureError("BACKUP_SIGNATURE_INVALID: the signature does not match")
    return document["manifest"]


SERVER_KEY = "backup-signing.pem"
SERVER_PUBLIC_KEY = "backup-signing.pub.pem"


def server_key(directory, *, create=True):
    """The server's own signing key (every backup is signed): (private path, "EXISTING" | "CREATED").

    Created ONCE, at the first backup, next to the conversation store: private 0600, public 0644 to copy
    off the server. If the private key later disappears while its public half is still there, nothing
    is regenerated silently: SIGNING_KEY_LOST, the operator restores the key or removes the public file.
    """
    directory = os.fspath(directory)
    private, public = os.path.join(directory, SERVER_KEY), os.path.join(directory, SERVER_PUBLIC_KEY)
    if os.path.lexists(private):
        return private, "EXISTING"
    if os.path.lexists(public):
        raise SignatureError("SIGNING_KEY_LOST: the server signing key is missing; restore it, or remove "
                             "its public file explicitly to create a new one")
    if not create:
        return None, "TO_CREATE"                # checked before a backup; created only once it succeeded
    generated = _openssl(["genpkey", "-algorithm", "ed25519"], [])
    if generated.returncode != 0 or not generated.stdout.startswith(b"-----BEGIN PRIVATE KEY-----"):
        raise SignatureError("BACKUP_SIGNING_FAILED: openssl could not create the signing key")
    pem = _memory(generated.stdout)
    try:
        derived = _openssl(["pkey", "-in", f"/dev/fd/{pem}", "-pubout"], [pem])
    finally:
        os.close(pem)
    if derived.returncode != 0 or not derived.stdout.startswith(b"-----BEGIN PUBLIC KEY-----"):
        raise SignatureError("BACKUP_SIGNING_FAILED: openssl could not derive the public key")
    written = []
    try:
        for path, data, mode in ((private, generated.stdout, 0o600), (public, derived.stdout, 0o644)):
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
            written.append(path)
            try:
                os.write(fd, data)
                os.fsync(fd)
            finally:
                os.close(fd)
    except OSError:
        for path in written:
            os.unlink(path)
        raise SignatureError("BACKUP_SIGNING_FAILED: the signing key could not be written") from None
    return private, "CREATED"
