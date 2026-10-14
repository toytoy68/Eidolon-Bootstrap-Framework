# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : monitor_remote.py
# Description : Lecture du statut DARME d'une autre VM par SSH à commande forcée, arguments fixes, hôte épinglé (G166)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Remote DARME status for the dashboard (docs/MEMORY-CHANNEL.md).

Core's eidolon-monitor runs ONE fixed ssh command line; Memory's sshd forces the read-only feed
command for that key (deployment/memory-feed/), whatever the client asks. Nothing in the argv comes
from the browser: host, user, port, key and known_hosts come from the private operator configuration
and are validated here. The host key is pinned (StrictHostKeyChecking=yes on a dedicated
known_hosts), no agent, no forwarding, no config file, no remote command. Output is bounded in size
and time; failures are generic codes, never ssh's stderr (it may contain addresses).
"""
import json
import os
import re
import select
import signal
import stat
import subprocess
import time

SSH = "/usr/bin/ssh"
MAX_REPLY = 64 * 1024
TIMEOUT = 6.0
HOST = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9.-]{0,251}[A-Za-z0-9])?|[0-9a-fA-F:]{2,39}")
USER = re.compile(r"[a-z_][a-z0-9_-]{0,31}")


def _private_file(path, *, secret):
    """Absolute regular file, no symlink, owned by us; a key must be 0600-like, known_hosts not writable by others."""
    if not isinstance(path, str) or not path.startswith("/") or ".." in path or len(path) > 200:
        return False
    try:
        info = os.lstat(path)
    except OSError:
        return False
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid():
        return False
    return not info.st_mode & (0o077 if secret else 0o022)


def validate(spec):
    """Checked copy of an ssh machine specification, or ValueError (configuration refused at startup)."""
    if not isinstance(spec, dict) or set(spec) - {"host", "user", "port", "key", "known_hosts"} \
            or not {"host", "user", "key", "known_hosts"} <= set(spec):
        raise ValueError("MONITOR_CONFIG_INVALID: ssh host, user, key, known_hosts (port optional)")
    host, user, port = spec["host"], spec["user"], spec.get("port", 22)
    if not isinstance(host, str) or not HOST.fullmatch(host) or host.startswith("-"):
        raise ValueError("MONITOR_CONFIG_INVALID: ssh host")
    if not isinstance(user, str) or not USER.fullmatch(user):
        raise ValueError("MONITOR_CONFIG_INVALID: ssh user")
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError("MONITOR_CONFIG_INVALID: ssh port")
    if not _private_file(spec["key"], secret=True):
        raise ValueError("MONITOR_CONFIG_NOT_PRIVATE: ssh key (0600, owner, no link)")
    if not _private_file(spec["known_hosts"], secret=False):
        raise ValueError("MONITOR_CONFIG_INVALID: pinned known_hosts (owner, not writable by others)")
    return {"host": host, "user": user, "port": port, "key": spec["key"], "known_hosts": spec["known_hosts"]}


def command(spec, ssh=SSH):
    """The ONLY command line ever run (argv list, no shell)."""
    return [ssh, "-F", "/dev/null", "-T", "-n",
            "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes",
            "-o", "UserKnownHostsFile=" + spec["known_hosts"], "-o", "GlobalKnownHostsFile=/dev/null",
            "-o", "IdentitiesOnly=yes", "-o", "IdentityAgent=none", "-o", "PasswordAuthentication=no",
            "-o", "KbdInteractiveAuthentication=no", "-o", "ForwardAgent=no", "-o", "ForwardX11=no",
            "-o", "ClearAllForwardings=yes", "-o", "PermitLocalCommand=no", "-o", "ControlMaster=no",
            "-o", "ControlPath=none", "-o", "ConnectTimeout=3", "-o", "ServerAliveInterval=2",
            "-o", "ServerAliveCountMax=1", "-o", "LogLevel=ERROR",
            "-i", spec["key"], "-p", str(spec["port"]), "-l", spec["user"], "--", spec["host"]]


def read_ssh(spec, *, ssh=SSH, timeout=TIMEOUT, **_):
    """(JSON object, None) or (None, generic error code)."""
    try:
        process = subprocess.Popen(command(spec, ssh), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                   stderr=subprocess.DEVNULL, env={"PATH": "/usr/bin:/bin", "HOME": "/nonexistent"},
                                   close_fds=True, start_new_session=True)
    except OSError:
        return None, "UNAVAILABLE"
    deadline, raw, error = time.monotonic() + timeout, b"", None
    try:
        while True:
            left = deadline - time.monotonic()
            if left <= 0:
                error = "TIMEOUT"
                break
            ready, _, _ = select.select([process.stdout], [], [], left)
            if not ready:
                continue
            chunk = os.read(process.stdout.fileno(), 16384)
            if not chunk:
                break
            raw += chunk
            if len(raw) > MAX_REPLY:
                error = "REPLY_TOO_LARGE"
                break
    finally:
        if process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except OSError:
                pass
        process.stdout.close()
        code = process.wait()
    if error:
        return None, error
    if code != 0:
        return None, "UNAVAILABLE"                      # refused key, unknown host key, network, feed error
    try:
        value = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeError):
        return None, "INVALID_REPLY"
    return (value, None) if isinstance(value, dict) else (None, "INVALID_REPLY")
