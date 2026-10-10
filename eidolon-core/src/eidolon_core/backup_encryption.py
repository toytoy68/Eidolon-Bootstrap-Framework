# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : backup_encryption.py
# Description : Chiffrement des sauvegardes de conversations avec l'outil age (destinataires publics, clé privée hors serveur)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

"""Encryption of conversation backups with the external `age` tool (age-encryption.org/v1).

Core never implements cryptography: it hands bytes to `age` and checks what comes back.

- Encrypting needs only PUBLIC recipients (age1…), read from an operator file that only its owner can
  modify. The private identity can stay off the server; only decryption needs it.
- The validated recipients are passed on the command line (-r), so the file is never re-read by age
  after Core checked it. The identity is opened once by Core (no symlink, owner, 0600) and handed to
  age as /dev/fd/N, for the same reason.
- age runs with an empty environment, a time limit, and its output goes into a file Core created
  itself (O_EXCL, 0600). Its messages are never relayed: they may name paths.
"""
import os
import re
import shutil
import stat
import subprocess

from .contracts import ContractError

HEADER = b"age-encryption.org/v1\n"
RECIPIENT = re.compile(r"age1[ac-hj-np-z02-9]{58}")
MAX_RECIPIENTS = 20
MAX_KEY_FILE_BYTES = 8 * 1024
TIMEOUT_SECONDS = 600


class EncryptionError(ContractError):
    pass


def find_age():
    """The age executable found on PATH, if it is a regular file that only root or this user can change."""
    found = shutil.which("age")
    if found is None:
        raise EncryptionError("AGE_UNAVAILABLE: the age tool is not installed")
    path = os.path.realpath(found)
    try:
        info = os.stat(path)
    except OSError:
        raise EncryptionError("AGE_UNAVAILABLE: the age tool is unreadable") from None
    if (not stat.S_ISREG(info.st_mode) or info.st_mode & 0o022 or info.st_uid not in (0, os.getuid())
            or not os.access(path, os.X_OK)):
        raise EncryptionError("AGE_UNAVAILABLE: the age tool is not safely installed")
    return path


def _open_owned(path, error, *, private):
    """Open a small regular file of this user: no symlink; private=True also forbids any group/other access."""
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError:
        raise EncryptionError(f"{error}: unreadable") from None
    info = os.fstat(fd)
    forbidden = 0o077 if private else 0o022
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & forbidden
            or info.st_size > MAX_KEY_FILE_BYTES):
        os.close(fd)
        raise EncryptionError(f"{error}: a small regular file owned by this user is required"
                              + (" (0600)" if private else ", not writable by others"))
    return fd


def read_recipients(path):
    """Public age recipients, one per line; blank lines and # comments allowed. Never repaired."""
    fd = _open_owned(path, "AGE_RECIPIENTS_REFUSED", private=False)
    try:
        raw = os.read(fd, MAX_KEY_FILE_BYTES + 1)
    finally:
        os.close(fd)
    try:
        lines = raw.decode("utf-8").splitlines()       # comments may be in French; keys are ASCII
    except UnicodeError:
        raise EncryptionError("AGE_RECIPIENTS_REFUSED: UTF-8 text required") from None
    recipients = [line.strip() for line in lines if line.strip() and not line.strip().startswith("#")]
    if (not 1 <= len(recipients) <= MAX_RECIPIENTS or len(set(recipients)) != len(recipients)
            or any(not RECIPIENT.fullmatch(r) for r in recipients)):
        raise EncryptionError("AGE_RECIPIENTS_REFUSED: 1 to 20 distinct age1… recipients required")
    return recipients


def encrypt(data, recipients, output_fd):
    """Encrypt bytes for these recipients into an open file; returns the number of recipient stanzas."""
    age = find_age()
    arguments = [age, "--encrypt"]
    for recipient in recipients:
        arguments += ["-r", recipient]
    try:
        done = subprocess.run(arguments, input=data, stdout=output_fd, stderr=subprocess.DEVNULL, env={},
                              timeout=TIMEOUT_SECONDS, check=False)
    except (OSError, subprocess.TimeoutExpired):
        raise EncryptionError("BACKUP_ENCRYPTION_FAILED: age did not complete") from None
    if done.returncode != 0:
        raise EncryptionError("BACKUP_ENCRYPTION_FAILED: age refused to encrypt")
    os.fsync(output_fd)
    os.lseek(output_fd, 0, os.SEEK_SET)
    head = os.read(output_fd, 64 * 1024)
    stanzas = head.split(b"\n---", 1)[0].count(b"\n-> X25519 ")
    if not head.startswith(HEADER) or stanzas != len(recipients) or os.fstat(output_fd).st_size <= len(data):
        raise EncryptionError("BACKUP_ENCRYPTION_FAILED: the encrypted file is not as expected")
    return stanzas


def is_encrypted(path):
    with open(path, "rb") as handle:
        return handle.read(len(HEADER)) == HEADER


def decrypt(input_path, identity_path, output_fd):
    """Decrypt an age file with a private identity (0600) into an open file."""
    age = find_age()
    identity = _open_owned(identity_path, "AGE_IDENTITY_REFUSED", private=True)
    try:
        try:
            source = os.open(input_path, os.O_RDONLY | os.O_NOFOLLOW)
        except OSError:
            raise EncryptionError("BACKUP_DECRYPTION_FAILED: encrypted backup unreadable") from None
        try:
            if not stat.S_ISREG(os.fstat(source).st_mode):
                raise EncryptionError("BACKUP_DECRYPTION_FAILED: a regular file is required")
            try:
                done = subprocess.run([age, "--decrypt", "-i", f"/dev/fd/{identity}"], stdin=source,
                                      stdout=output_fd, stderr=subprocess.DEVNULL, env={}, pass_fds=(identity,),
                                      timeout=TIMEOUT_SECONDS, check=False)
            except (OSError, subprocess.TimeoutExpired):
                raise EncryptionError("BACKUP_DECRYPTION_FAILED: age did not complete") from None
        finally:
            os.close(source)
    finally:
        os.close(identity)
    if done.returncode != 0:
        # Wrong key, damaged or modified file: age authenticates the content, nothing partial is used.
        raise EncryptionError("BACKUP_DECRYPTION_FAILED: wrong identity, or damaged or modified backup")
    os.fsync(output_fd)
