# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : tools/claude_hf_cache_audit.py
# Description : Audit EXPÉRIMENTAL des écritures et connexions au chargement du reranker hors ligne (Claude, G262-6)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Run it UNDER THE SERVICE ACCOUNT, with the service's environment, against the real offline cache:

  HF_HOME=<cache> HF_HUB_CACHE=<cache> HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
    <venv>/bin/python -I tools/claude_hf_cache_audit.py <cache> [--full]

Python audit hooks record every write-intent open/mkdir/rename/remove/chmod and every socket connect
while the model is loaded with local_files_only=True. Default: configuration only (no torch needed).
--full: the real CrossEncoder (torch and sentence-transformers required), exactly as services/memory_bridge.
Prints one JSON line; it never downloads (offline variables + local_files_only) and never prints content.
"""
import json
import os
import sys

REPO = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"


def main(argv):
    cache, full = argv[0], "--full" in argv[1:]
    writes, sockets = [], []

    def hook(event, args):
        if event == "open" and isinstance(args[0], (str, bytes, os.PathLike)):
            mode, flags = args[1], args[2]
            if (mode and any(c in mode for c in "wax+")) or (flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT)):
                writes.append(["open", os.fsdecode(args[0])])
        elif event in ("os.mkdir", "os.rename", "os.replace", "os.remove", "os.chmod", "os.symlink", "os.link"):
            writes.append([event, os.fsdecode(args[0])])
        elif event == "socket.connect":
            sockets.append(str(args[1]))
    sys.addaudithook(hook)
    result = "ok"
    try:
        if full:
            from sentence_transformers import CrossEncoder
            CrossEncoder(REPO, device="cpu", cache_folder=cache, max_length=512, local_files_only=True)
        else:
            from transformers import AutoConfig
            AutoConfig.from_pretrained(REPO, cache_dir=cache, local_files_only=True)
    except Exception as exc:  # reported, never hidden
        result = f"{type(exc).__name__}: {str(exc)[:200]}"
    print(json.dumps(dict(result=result, full=full, uid=os.geteuid(),
                          writes=[w for w in writes if not w[1].startswith(("/proc", "/dev"))], sockets=sockets)))
    return 0 if result == "ok" and not writes and not sockets else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
