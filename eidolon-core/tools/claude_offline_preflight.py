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
    euid = os.geteuid()
    ok = (stat.S_ISDIR(parent.st_mode) and parent.st_uid == euid and stat.S_IMODE(parent.st_mode) == 0o700
          and stat.S_ISREG(leaf.st_mode) and leaf.st_uid == euid and stat.S_IMODE(leaf.st_mode) == 0o600
          and leaf.st_nlink == 1 and 32 <= leaf.st_size <= 4096)
    return {"check": "bridge.credential", "result": "PASS" if ok else "FAIL",
            "detail": "metadata only: private file and directory; content and live auth unverified" if ok else "permissions, type or size not as required"}


def run(args):
    checks = [check_python(),
              check_checkout("core", args.core, args.expect_core),
              check_checkout("memory", args.memory, args.expect_memory),
              check_module("qdrant_client", required=True),
              check_module("numpy", required=False),
              check_disk(args.data_dir, args.min_free_bytes),
              check_credential(args.credential)]
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
    report = run(parser.parse_args(argv))
    print(json.dumps(report, indent=1, ensure_ascii=False))
    return {"PASS": 0, "FAIL": 1, "UNKNOWN": 2}[report["verdict"]]


if __name__ == "__main__":
    sys.exit(main())
