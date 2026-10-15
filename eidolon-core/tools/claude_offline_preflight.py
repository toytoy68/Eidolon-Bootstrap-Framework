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


def check_canonical_owner(root, account, *, max_entries=100_000, lookup=_lookup_account, lstat=os.lstat,
                          scandir=os.scandir):
    """G262-1, opt-in: every entry under --root/memory/{persistent,history} belongs to the EXPECTED service
    account (explicitly given, never inferred from who runs the acceptance), is private and is no link.
    Metadata only: nothing is opened, changed or chown-ed. An unknown account or platform is UNKNOWN."""
    name = "memory.canonical_owner"
    if root is None or account is None:
        return {"check": name, "result": "UNKNOWN", "detail": "root or expected account not given"}
    if (type(account) is not str or not account or len(account) > 32
            or not all(c.isalnum() or c in "._-" for c in account)):
        return {"check": name, "result": "FAIL", "detail": "invalid account name"}
    uid, why = lookup(account)
    if uid is None:
        return {"check": name, "result": "UNKNOWN", "detail": why}
    if uid == 0:
        return {"check": name, "result": "FAIL", "detail": "the service account must not be root"}
    try:
        base = Path(root)
        if not base.is_absolute() or ".." in base.parts:
            raise ValueError("relative or traversing root")
        for ancestor in [*reversed(base.parents), base]:
            if not stat.S_ISDIR(lstat(ancestor).st_mode):
                return {"check": name, "result": "FAIL", "detail": "root or an ancestor is not a plain directory"}
        seen, pending = 0, [base / part for part in MEMORY_LAYOUT]
        for top in pending[:len(MEMORY_LAYOUT)]:
            if not stat.S_ISDIR(lstat(top).st_mode):
                return {"check": name, "result": "FAIL", "detail": "expected memory/persistent and memory/history"}
        parent = lstat(base / "memory")
        if parent.st_uid != uid or stat.S_IMODE(parent.st_mode) & 0o077:
            return {"check": name, "result": "FAIL", "detail": "memory/ has another owner or is shared"}
        while pending:
            directory = pending.pop()
            st = lstat(directory)
            if st.st_uid != uid or stat.S_IMODE(st.st_mode) & 0o077:
                return {"check": name, "result": "FAIL", "detail": "a directory has another owner or is shared"}
            with scandir(directory) as entries:
                for entry in entries:
                    seen += 1
                    if seen > max_entries:
                        return {"check": name, "result": "UNKNOWN", "detail": "entry budget exceeded"}
                    est = lstat(entry.path)
                    if stat.S_ISDIR(est.st_mode):
                        pending.append(Path(entry.path))
                    elif not stat.S_ISREG(est.st_mode):
                        return {"check": name, "result": "FAIL", "detail": "link or special file in the memory"}
                    elif est.st_uid != uid or stat.S_IMODE(est.st_mode) & 0o077:
                        return {"check": name, "result": "FAIL", "detail": "a file has another owner or is shared"}
    except FileNotFoundError:
        return {"check": name, "result": "FAIL", "detail": "expected memory/persistent and memory/history"}
    except (OSError, ValueError):
        return {"check": name, "result": "UNKNOWN", "detail": "metadata unreadable"}
    return {"check": name, "result": "PASS",
            "detail": f"{seen} entries owned by the expected account, private, no link; content not read"}


RERANKER_REPO = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"
# Minimal set; the exact list must be taken from the real cache on the VM (G262-6), not invented here.
RERANKER_REQUIRED = ("config.json", "tokenizer_config.json", ("model.safetensors", "pytorch_model.bin"))


def check_reranker_cache(cache, *, repo=RERANKER_REPO, required=RERANKER_REQUIRED, lstat=os.lstat):
    """G262-6, opt-in, metadata only: the offline cache is complete and PREPARED, so the service under a
    reduced account never writes into it nor reports a misleading "could not connect" error."""
    name = "reranker.cache"
    if cache is None:
        return {"check": name, "result": "UNKNOWN", "detail": "cache not given"}
    try:
        base = Path(cache)
        if not base.is_absolute() or ".." in base.parts:
            raise ValueError
        if not stat.S_ISDIR(lstat(base).st_mode):
            return {"check": name, "result": "FAIL", "detail": "cache is not a plain directory"}
        if not stat.S_ISREG(lstat(base / "version.txt").st_mode):
            raise FileNotFoundError
    except FileNotFoundError:
        return {"check": name, "result": "FAIL",
                "detail": "cache not prepared: version.txt missing, transformers would try to write it"}
    except (OSError, ValueError):
        return {"check": name, "result": "UNKNOWN", "detail": "cache metadata unreadable"}
    model = base / ("models--" + repo.replace("/", "--"))
    try:
        ref = (model / "refs" / "main")
        if not stat.S_ISREG(lstat(ref).st_mode) or lstat(ref).st_size != 40:
            return {"check": name, "result": "FAIL", "detail": "refs/main missing or malformed"}
        commit = ref.read_text(encoding="ascii")
        if not all(c in "0123456789abcdef" for c in commit):
            return {"check": name, "result": "FAIL", "detail": "refs/main missing or malformed"}
        snapshot = model / "snapshots" / commit
        for item in required:
            names = item if isinstance(item, tuple) else (item,)
            if not any(_cached_file(model, snapshot / n, lstat) for n in names):
                return {"check": name, "result": "FAIL", "detail": "incomplete cache: missing " + " or ".join(names)}
    except (OSError, UnicodeError):
        return {"check": name, "result": "FAIL", "detail": "incomplete cache: snapshot unreadable"}
    return {"check": name, "result": "PASS", "detail": f"{repo} snapshot complete and prepared; content not read"}


def _cached_file(model, path, lstat):
    """A snapshot entry is a regular file, or a RELATIVE link to a regular blob inside this model."""
    try:
        st = lstat(path)
    except FileNotFoundError:
        return False
    if stat.S_ISREG(st.st_mode):
        return True
    if not stat.S_ISLNK(st.st_mode):
        return False
    target = os.readlink(path)
    resolved = (path.parent / target).resolve()
    if os.path.isabs(target) or (model / "blobs").resolve() not in resolved.parents:
        return False
    return stat.S_ISREG(lstat(resolved).st_mode)


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
