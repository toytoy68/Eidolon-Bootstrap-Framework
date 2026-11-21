# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : sandbox_tools.py
# Description : Opt-in isolated text statistics; no arbitrary command API
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Linux/bubblewrap executor for the single pure text.stats capability.

Core validates the reference, a separate interpreter validates the fixed message,
and the kernel isolates network, mounts, IPC, PID and credentials. No host home,
credentials, writable host directory, model-supplied code or executable is exposed.
The existing worker persists receipts and retains uncertain interrupted calls.
This is NOT a sandbox for arbitrary callbacks, GPU servers or service mutations.
"""
import json
import subprocess

from .contracts import ContractError
from .tools import Registry, Tool, source_for, verify_stats

BWRAP = "/usr/bin/bwrap"
MAX_TEXT_BYTES = 65536
_PROGRAM = """
import hashlib,json,resource,sys
resource.setrlimit(resource.RLIMIT_CORE,(0,0))
resource.setrlimit(resource.RLIMIT_CPU,(2,2))
resource.setrlimit(resource.RLIMIT_AS,(134217728,134217728))
resource.setrlimit(resource.RLIMIT_FSIZE,(1048576,1048576))
raw=sys.stdin.buffer.read(524289)
if len(raw)>524288: raise ValueError("input budget")
value=json.loads(raw)
if (type(value) is not dict or set(value)!={"tool","text"}
    or value["tool"]!="text.stats" or type(value["text"]) is not str
    or len(value["text"].encode("utf-8"))>65536):
    raise ValueError("independent tool policy refused")
text=value["text"]
print(json.dumps({"characters":len(text),"utf8_bytes":len(text.encode("utf-8")),
                  "sha256":hashlib.sha256(text.encode("utf-8")).hexdigest()}))
"""


def _command(program):
    # program is trusted source code, never supplied by a model or a tool argument.
    return [BWRAP, "--unshare-all", "--new-session", "--die-with-parent",
        "--cap-drop", "ALL", "--ro-bind", "/usr", "/usr",
        "--symlink", "usr/bin", "/bin", "--symlink", "usr/lib", "/lib",
        "--symlink", "usr/lib64", "/lib64", "--proc", "/proc", "--dev", "/dev",
        "--tmpfs", "/tmp", "--chdir", "/tmp", "--clearenv",
        "--setenv", "PATH", "/usr/bin:/bin",
        "/usr/bin/python3", "-I", "-S", "-c", program]


def validate(parameters, context):
    item = source_for(parameters, context)
    if len(item["content"].encode("utf-8")) > MAX_TEXT_BYTES:
        raise ContractError("sandbox text budget exceeded")
    return item


def execute(parameters, context):
    text = validate(parameters, context)["content"]
    message = json.dumps({"tool": "text.stats", "text": text}, ensure_ascii=True).encode()
    try:
        result = subprocess.run(_command(_PROGRAM), input=message,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, close_fds=True,
            env={"PATH":"/usr/bin:/bin", "LANG":"C.UTF-8"},
            timeout=5, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError("sandbox unavailable; no unisolated fallback") from exc
    if result.returncode != 0 or len(result.stdout) > 1024:
        raise RuntimeError("sandbox refused or incomplete")
    value = json.loads(result.stdout)
    if not verify_stats(parameters, context, value):
        raise RuntimeError("sandbox evidence mismatch")
    return value


def sandbox_registry():
    """Explicitly selected by a trusted host; default runtime remains unchanged."""
    return Registry([Tool("text.stats", "sandbox-1", "none", validate, execute,
                          verify_stats, "text-stats-recompute/1")])
