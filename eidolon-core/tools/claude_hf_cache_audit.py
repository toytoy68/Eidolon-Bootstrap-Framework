# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : tools/claude_hf_cache_audit.py
# Description : Audit EXPÉRIMENTAL des écritures et connexions au chargement du reranker hors ligne (Claude, G262-6, G266-10)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Run it UNDER THE SERVICE ACCOUNT, against the real offline cache:

  <venv>/bin/python -I tools/claude_hf_cache_audit.py --cache <cache> [--full]

What it IMPOSES (G266-10), whatever the caller's environment: HF_HUB_OFFLINE=1, TRANSFORMERS_OFFLINE=1,
HF_HOME and HF_HUB_CACHE = the cache, set before any library import, and no bytecode writing (__pycache__)
for the imported libraries. Network is BLOCKED: an audit hook
refuses socket connections and name resolution (recorded, then raised inside the library). Writes are
OBSERVED, not blocked: the report lists them and the exit code is non-zero.

Default: configuration only (transformers). --full: the real CrossEncoder (torch + sentence-transformers);
if those are absent the result says so, a load is never claimed. One JSON line, no file content; exception
messages are bounded and the cache path is redacted. Exit: 0 clean, 1 writes/network/failure, 2 usage.
"""
import argparse
import json
import os
import sys

REPO = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"
OFFLINE = ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE")


class NetworkBlocked(PermissionError):
    pass


def main(argv=None):
    parser = argparse.ArgumentParser(description="Offline reranker cache audit (writes observed, network blocked).")
    parser.add_argument("--cache", required=True, help="absolute path of the prepared offline cache")
    parser.add_argument("--full", action="store_true", help="load the real CrossEncoder (needs torch)")
    args = parser.parse_args(argv)
    cache = args.cache
    if not os.path.isabs(cache) or not os.path.isdir(cache) or os.path.islink(cache):
        parser.error("--cache must be an existing absolute directory, not a link")
    before = {k: os.environ.get(k) for k in (*OFFLINE, "HF_HOME", "HF_HUB_CACHE")}
    for key in OFFLINE:
        os.environ[key] = "1"
    os.environ["HF_HOME"] = os.environ["HF_HUB_CACHE"] = cache
    # Imports must not write __pycache__ either: under the service account the venv is root-owned.
    sys.dont_write_bytecode = True
    writes, network = [], []

    def hook(event, hook_args):
        if event == "open" and isinstance(hook_args[0], (str, bytes, os.PathLike)):
            mode, flags = hook_args[1], hook_args[2]
            if (mode and any(c in mode for c in "wax+")) or (flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT)):
                writes.append(["open", _redact(os.fsdecode(hook_args[0]), cache)])
        elif event in ("os.mkdir", "os.rename", "os.replace", "os.remove", "os.chmod", "os.symlink", "os.link"):
            writes.append([event, _redact(os.fsdecode(hook_args[0]), cache)])
        elif event in ("socket.connect", "socket.getaddrinfo"):
            network.append(event)
            raise NetworkBlocked("network blocked by the offline audit")
    sys.addaudithook(hook)
    loaded, result = None, "ok"
    try:
        if args.full:
            try:
                import torch  # noqa: F401
                from sentence_transformers import CrossEncoder
            except ImportError as exc:
                result = f"UNAVAILABLE: {type(exc).__name__} ({exc.name or 'module'} absent); nothing loaded"
            else:
                CrossEncoder(REPO, device="cpu", cache_folder=cache, max_length=512, local_files_only=True)
                loaded = "cross-encoder"
        else:
            try:
                from transformers import AutoConfig
            except ImportError as exc:
                result = f"UNAVAILABLE: {type(exc).__name__} ({exc.name or 'module'} absent); nothing loaded"
            else:
                AutoConfig.from_pretrained(REPO, cache_dir=cache, local_files_only=True)
                loaded = "configuration"
    except Exception as exc:  # reported, bounded, redacted; never hidden
        result = f"{type(exc).__name__}: {_redact(str(exc), cache)[:160]}"
    report = dict(result=result, loaded=loaded, full=args.full, uid=os.geteuid(),
                  imposed={k: os.environ[k] if k in OFFLINE else "<cache>" for k in before},
                  overridden=sorted(k for k, v in before.items() if v is not None and v != os.environ[k]),
                  writes=[w for w in writes if not w[1].startswith(("/proc", "/dev"))][:50],
                  writes_truncated=len(writes) > 50, network_blocked=sorted(set(network)))
    print(json.dumps(report, sort_keys=True))
    return 0 if result == "ok" and loaded and not report["writes"] and not network else 1


def _redact(text, cache):
    return text.replace(cache, "<cache>")


if __name__ == "__main__":
    sys.exit(main())
