# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : sd_notify.py
# Description : Signal « prêt » à systemd (Type=notify) une fois le port réellement ouvert (G167)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Minimal sd_notify(3) without dependency: one datagram on $NOTIFY_SOCKET. Outside systemd (no
variable) it does nothing. The variable is removed after use so child processes never inherit it."""
import os
import socket


def notify(message="READY=1"):
    path = os.environ.pop("NOTIFY_SOCKET", None)
    if not path or not (path.startswith("/") or path.startswith("@")):
        return False
    address = "\0" + path[1:] if path.startswith("@") else path
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as connection:
            connection.connect(address)
            connection.sendall(message.encode("ascii"))
    except OSError:
        return False
    return True
