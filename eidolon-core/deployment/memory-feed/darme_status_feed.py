# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : darme_status_feed.py
# Description : Commande forcée SSH sur Memory : une ligne de statut DARME, lecture seule, aucune entrée acceptée (G166)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Installed root-owned as /usr/local/lib/eidolon/darme-status-feed (0755), run by sshd as the
`eidolon-monitor-feed` account (ForceCommand). It ignores nothing silently: any command the client
tries to send is REFUSED (exit 2). It sends only STATUS\\n to the local DARME socket, checks that the
socket is served by `eidolon-darme` (SO_PEERCRED), bounds the answer (64 KiB, 2 s) and prints exactly
one JSON object line. No argument, no environment value and no file path comes from the client."""
import json
import os
import pwd
import socket
import struct
import sys
import time

SOCKET = "/run/eidolon-darme/status.sock"
SERVER = "eidolon-darme"
MAX_REPLY = 64 * 1024


def feed(path=SOCKET, expected_uid=None, timeout=2.0):
    connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    connection.settimeout(timeout)
    deadline = time.monotonic() + timeout
    try:
        connection.connect(path)
        _, uid, _ = struct.unpack("3i", connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
        if uid != expected_uid:
            raise ValueError("unexpected socket owner")
        connection.sendall(b"STATUS\n")
        raw = b""
        while not raw.endswith(b"\n"):
            if time.monotonic() > deadline:
                raise ValueError("deadline")
            part = connection.recv(16384)
            if not part:
                break
            raw += part
            if len(raw) > MAX_REPLY:
                raise ValueError("too large")
    finally:
        connection.close()
    value = json.loads(raw.decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError("not an object")
    return json.dumps(value, separators=(",", ":"), sort_keys=True)


def main():
    if os.environ.get("SSH_ORIGINAL_COMMAND") or len(sys.argv) > 1:
        print('{"error":"FEED_TAKES_NO_COMMAND"}')
        return 2
    try:
        line = feed(expected_uid=pwd.getpwnam(SERVER).pw_uid)
    except (OSError, ValueError, KeyError, struct.error):
        print('{"error":"DARME_UNAVAILABLE"}')
        return 1
    sys.stdout.write(line + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
