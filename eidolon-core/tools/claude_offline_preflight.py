# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : tools/claude_offline_preflight.py
# Description : Préflight hors ligne opt-in de la recette VM/PC, lecture seule, arrêt sur inconnu (Claude, G236-9)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Read-only offline preflight for the VM/PC acceptance (runbook: docs/proposals/2026-10-15-claude-offline-acceptance-runbook.md).

Opt-in: nothing runs without --confirm-read-only. No service, installation, network, benchmark, model or private
corpus is touched; the credential file is only stat()-ed, never opened. Every check is PASS, FAIL or UNKNOWN, and
UNKNOWN stops the acceptance exactly like FAIL (exit 2; FAIL exits 1; all PASS exits 0).
"""
import argparse
import importlib.util
import json
import os
import re
from pathlib import Path
import shutil
import stat
import subprocess
import sys


def _git(path, *args):
    result = subprocess.run(["git", "-C", str(path), *args], capture_output=True, text=True, timeout=20,
                            env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"})
    if result.returncode != 0:
        raise RuntimeError("git failed")
    return result.stdout.strip()


def check_checkout(name, path, expected):
    if path is None:
        return {"check": f"{name}.checkout", "result": "UNKNOWN", "detail": "path not given"}
    try:
        head = _git(path, "rev-parse", "HEAD")
        dirty = bool(_git(path, "status", "--porcelain", "--untracked-files=all"))
    except (OSError, RuntimeError, subprocess.TimeoutExpired):
        return {"check": f"{name}.checkout", "result": "FAIL", "detail": "not a readable git checkout"}
    if dirty:
        return {"check": f"{name}.checkout", "result": "FAIL", "detail": f"{head} has local modifications"}
    if expected is None:
        return {"check": f"{name}.checkout", "result": "UNKNOWN", "detail": f"{head}; no expected SHA given"}
    ok = head == expected or (len(expected) >= 7 and head.startswith(expected))
    return {"check": f"{name}.checkout", "result": "PASS" if ok else "FAIL", "detail": head}


def check_python():
    ok = sys.version_info >= (3, 11)
    return {"check": "python", "result": "PASS" if ok else "FAIL", "detail": sys.version.split()[0]}


def check_module(name, required):
    found = importlib.util.find_spec(name) is not None                 # located, never imported
    result = "PASS" if found else ("FAIL" if required else "UNKNOWN")
    return {"check": f"module.{name}", "result": result, "detail": "found" if found else "missing"}


def check_disk(path, minimum_bytes):
    if path is None or minimum_bytes is None:
        return {"check": "disk", "result": "UNKNOWN", "detail": "path or minimum not given"}
    if type(minimum_bytes) is not int or minimum_bytes < 1:
        return {"check": "disk", "result": "FAIL", "detail": "invalid minimum byte policy"}
    try:
        free = shutil.disk_usage(path).free
    except OSError:
        return {"check": "disk", "result": "FAIL", "detail": "path unavailable"}
    return {"check": "disk", "result": "PASS" if free >= minimum_bytes else "FAIL", "detail": f"{free} bytes free"}


def check_credential(path):
    """stat() only: the secret is never opened, read or printed (its path is reported as given)."""
    if path is None:
        return {"check": "bridge.credential", "result": "UNKNOWN", "detail": "path not given"}
    try:
        path = Path(path).expanduser()
        if ".." in path.parts:
            raise ValueError("parent traversal")
        path = path.absolute()
        for ancestor in reversed(path.parents):
            if not stat.S_ISDIR(os.lstat(ancestor).st_mode):
                raise ValueError("unsafe ancestor")
        parent, leaf = os.lstat(path.parent), os.lstat(path)
    except (OSError, ValueError):
        return {"check": "bridge.credential", "result": "FAIL", "detail": "missing or unreadable metadata"}
    if not hasattr(os, "geteuid"):  # G258-7: no POSIX owner (Windows PC): unknown, never a pass or a crash
        return {"check": "bridge.credential", "result": "UNKNOWN", "detail": "POSIX ownership unavailable on this platform"}
    euid = os.geteuid()
    ok = (stat.S_ISDIR(parent.st_mode) and parent.st_uid == euid and stat.S_IMODE(parent.st_mode) == 0o700
          and stat.S_ISREG(leaf.st_mode) and leaf.st_uid == euid and stat.S_IMODE(leaf.st_mode) == 0o600
          and leaf.st_nlink == 1 and 32 <= leaf.st_size <= 4096)
    return {"check": "bridge.credential", "result": "PASS" if ok else "FAIL",
            "detail": "metadata only: private file and directory; content and live auth unverified" if ok else "permissions, type or size not as required"}


MEMORY_LAYOUT = ("memory/persistent", "memory/history")   # what the bridge's --root contains (G261 review)


def _lookup_account(name):
    try:
        import pwd
    except ImportError:
        return None, "no POSIX account database on this platform"
    try:
        return pwd.getpwnam(name).pw_uid, None
    except KeyError:
        return None, "service account not found"


RERANKER_REPO = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"
# Minimal set; the exact list must be taken from the real cache on the VM (G262-6), not invented here.
RERANKER_REQUIRED = ("config.json", "tokenizer_config.json", ("model.safetensors", "pytorch_model.bin"))


_DIRFLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
_BLOB_LINK = re.compile(r"\.\./\.\./blobs/([A-Za-z0-9._-]{1,128})")


class _Refused(Exception):
    def __init__(self, result, detail):
        super().__init__(detail)
        self.result, self.detail = result, detail


def _walk(path):
    """Open an absolute directory from '/' without following ANY link (G266-4)."""
    base = Path(path)
    if not base.is_absolute() or ".." in base.parts:
        raise _Refused("UNKNOWN", "cache path must be absolute, without '..'")
    fd = os.open("/", _DIRFLAGS)
    try:
        for part in base.parts[1:]:
            child = _open_child(fd, part, "cache path")
            os.close(fd)
            fd = child
        return fd
    except BaseException:
        os.close(fd)
        raise


def _open_child(fd, name, what):
    try:
        return os.open(name, _DIRFLAGS, dir_fd=fd)
    except FileNotFoundError:
        raise _Refused("FAIL", f"incomplete cache: {what} missing") from None
    except OSError as exc:
        if exc.errno in (40, 20):                    # ELOOP (a link) or ENOTDIR
            raise _Refused("FAIL", f"{what} is a link or not a directory") from None
        raise _Refused("UNKNOWN", "cache metadata unreadable") from None


def _regular(fd, name):
    try:
        return stat.S_ISREG(os.stat(name, dir_fd=fd, follow_symlinks=False).st_mode)
    except FileNotFoundError:
        return False


def check_reranker_cache(cache, *, repo=RERANKER_REPO, required=RERANKER_REQUIRED):
    """G262-6/G266-4, opt-in, metadata only. Every directory (cache, model, refs, snapshots, the commit,
    blobs) is opened by descriptor without following links; refs/main is read with a hard bound; snapshot
    links must be exactly ../../blobs/<name> and resolve to a regular blob of THIS model. A PASS states
    which metadata were checked: it does not certify that a model loads (nothing is loaded here)."""
    name = "reranker.cache"
    if cache is None:
        return {"check": name, "result": "UNKNOWN", "detail": "cache not given"}
    fds = []
    try:
        base = _walk(cache)
        fds.append(base)
        if not _regular(base, "version.txt"):
            return {"check": name, "result": "FAIL",
                    "detail": "cache not prepared: version.txt missing, transformers would try to write it"}
        model = _open_child(base, "models--" + repo.replace("/", "--"), "model directory")
        fds.append(model)
        refs = _open_child(model, "refs", "refs directory")
        fds.append(refs)
        try:
            ref = os.open("main", os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, dir_fd=refs)
        except OSError:
            return {"check": name, "result": "FAIL", "detail": "refs/main missing or malformed"}
        try:
            if not stat.S_ISREG(os.fstat(ref).st_mode):
                return {"check": name, "result": "FAIL", "detail": "refs/main missing or malformed"}
            commit = os.read(ref, 41)                    # bounded: never more than 41 bytes, whatever stat said
        finally:
            os.close(ref)
        if len(commit) != 40 or not all(c in b"0123456789abcdef" for c in commit):
            return {"check": name, "result": "FAIL", "detail": "refs/main missing or malformed"}
        snapshots = _open_child(model, "snapshots", "snapshots directory")
        fds.append(snapshots)
        snapshot = _open_child(snapshots, commit.decode("ascii"), "snapshot of refs/main")
        fds.append(snapshot)
        blobs = _open_child(model, "blobs", "blobs directory")
        fds.append(blobs)
        for item in required:
            names = item if isinstance(item, tuple) else (item,)
            if not any(_cached_file(snapshot, blobs, n) for n in names):
                return {"check": name, "result": "FAIL", "detail": "incomplete cache: missing " + " or ".join(names)}
    except _Refused as exc:
        return {"check": name, "result": exc.result, "detail": exc.detail}
    except OSError:
        return {"check": name, "result": "UNKNOWN", "detail": "cache metadata unreadable"}
    finally:
        for fd in reversed(fds):
            os.close(fd)
    return {"check": name, "result": "PASS",
            "detail": f"{repo}: prepared marker, refs/main and required snapshot entries present as regular "
                      f"blobs; metadata only, model NOT loaded"}


def _cached_file(snapshot, blobs, name):
    try:
        st = os.stat(name, dir_fd=snapshot, follow_symlinks=False)
    except FileNotFoundError:
        return False
    if stat.S_ISREG(st.st_mode):
        return True
    if not stat.S_ISLNK(st.st_mode):
        return False
    match = _BLOB_LINK.fullmatch(os.readlink(name, dir_fd=snapshot))
    return bool(match) and _regular(blobs, match.group(1))


def check_canonical_owner(root, account, *, max_entries=100_000, lookup=_lookup_account, lstat=None):
    """G262-1/G266-5, opt-in: every entry under --root/memory/{persistent,history} belongs to the EXPECTED
    service account (explicitly given, never inferred from who runs the acceptance; running the check AS
    that account is fine), is private and is no link. The tree is walked by descriptors without following
    any link; a directory replaced between its listing and its visit is a race, never followed. Nothing
    is opened for content, changed or chown-ed. `lstat(path)` may override owner/mode for simulations."""
    name = "memory.canonical_owner"
    if root is None or account is None:
        return {"check": name, "result": "UNKNOWN", "detail": "root or expected account not given"}
    if type(max_entries) is not int or max_entries < 1:
        return {"check": name, "result": "UNKNOWN", "detail": "invalid entry budget"}   # never a silent PASS
    if (type(account) is not str or not account or len(account) > 32
            or not all(c.isalnum() or c in "._-" for c in account)):
        return {"check": name, "result": "FAIL", "detail": "invalid account name"}
    uid, why = lookup(account)
    if uid is None:
        return {"check": name, "result": "UNKNOWN", "detail": why}
    if type(uid) is not int or uid < 0:
        return {"check": name, "result": "UNKNOWN", "detail": "invalid UID from the account database"}
    if uid == 0:
        return {"check": name, "result": "FAIL", "detail": "the service account must not be root"}

    def owner_mode(path, st):
        meta = lstat(path) if lstat is not None else st
        return meta.st_uid, stat.S_IMODE(meta.st_mode)

    def private(path, st):
        owner, mode = owner_mode(path, st)
        return owner == uid and not mode & 0o077

    fds = []
    try:
        base = _walk(root)
        fds.append(base)
        memory = _open_child(base, "memory", "memory/")
        fds.append(memory)
        if not private(Path(root) / "memory", os.fstat(memory)):
            return {"check": name, "result": "FAIL", "detail": "memory/ has another owner or is shared"}
        seen, pending = 0, []
        for part in ("persistent", "history"):
            fd = _open_child(memory, part, "memory/" + part)
            pending.append((Path(root) / "memory" / part, fd))
            fds.append(fd)
        while pending:
            path, dfd = pending.pop()
            if not private(path, os.fstat(dfd)):
                return {"check": name, "result": "FAIL", "detail": "a directory has another owner or is shared"}
            for entry in sorted(os.listdir(dfd)):
                seen += 1
                if seen > max_entries:
                    return {"check": name, "result": "UNKNOWN", "detail": "entry budget exceeded"}
                try:
                    st = os.stat(entry, dir_fd=dfd, follow_symlinks=False)
                except FileNotFoundError:
                    return {"check": name, "result": "UNKNOWN", "detail": "the tree changed during the check"}
                if stat.S_ISDIR(st.st_mode):
                    try:
                        child = os.open(entry, _DIRFLAGS, dir_fd=dfd)
                    except OSError:
                        return {"check": name, "result": "UNKNOWN", "detail": "the tree changed during the check"}
                    fds.append(child)
                    if (os.fstat(child).st_dev, os.fstat(child).st_ino) != (st.st_dev, st.st_ino):
                        return {"check": name, "result": "UNKNOWN", "detail": "the tree changed during the check"}
                    pending.append((path / entry, child))
                elif not stat.S_ISREG(st.st_mode):
                    return {"check": name, "result": "FAIL", "detail": "link or special file in the memory"}
                elif not private(path / entry, st):
                    return {"check": name, "result": "FAIL", "detail": "a file has another owner or is shared"}
    except _Refused as exc:
        detail = exc.detail.replace("cache path", "root").replace("incomplete cache: ", "")
        if exc.result == "FAIL" and "missing" in exc.detail:
            detail = "expected memory/persistent and memory/history"
        elif exc.result == "FAIL":
            detail = "root or an ancestor is a link or not a plain directory"
        return {"check": name, "result": exc.result, "detail": detail}
    except OSError:
        return {"check": name, "result": "UNKNOWN", "detail": "metadata unreadable"}
    finally:
        for fd in reversed(fds):
            os.close(fd)
    return {"check": name, "result": "PASS",
            "detail": f"{seen} entries owned by the expected account, private, no link; content not read"}


def run(args):
    checks = [check_python(),
              check_checkout("core", args.core, args.expect_core),
              check_checkout("memory", args.memory, args.expect_memory),
              check_module("qdrant_client", required=True),
              check_module("numpy", required=False),
              check_disk(args.data_dir, args.min_free_bytes),
              check_credential(args.credential)]
    if getattr(args, "reranker_cache", None) is not None:
        checks.append(check_reranker_cache(args.reranker_cache))
    if getattr(args, "service_account", None) is not None or getattr(args, "memory_root", None) is not None:
        checks.append(check_canonical_owner(args.memory_root, args.service_account))
    results = {c["result"] for c in checks}
    verdict = "FAIL" if "FAIL" in results else "UNKNOWN" if "UNKNOWN" in results else "PASS"
    return {"verdict": verdict, "checks": checks}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--confirm-read-only", action="store_true", required=True)
    parser.add_argument("--core")
    parser.add_argument("--memory")
    parser.add_argument("--expect-core")
    parser.add_argument("--expect-memory")
    parser.add_argument("--data-dir")
    parser.add_argument("--min-free-bytes", type=int)
    parser.add_argument("--credential")
    parser.add_argument("--memory-root", help="the bridge --root (contains memory/persistent and memory/history)")
    parser.add_argument("--service-account", help="expected owner of the memory, never inferred")
    parser.add_argument("--reranker-cache", help="offline reranker cache given to the bridge")
    report = run(parser.parse_args(argv))
    print(json.dumps(report, indent=1, ensure_ascii=False))
    return {"PASS": 0, "FAIL": 1, "UNKNOWN": 2}[report["verdict"]]


if __name__ == "__main__":
    sys.exit(main())
