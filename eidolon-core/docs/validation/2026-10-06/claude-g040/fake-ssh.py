#!/usr/bin/env python3
# Fake "ssh.exe" for the Linux run of eidolon-tunnel.ps1 (C-TASK-G040). Logs its arguments.
# With -L 127.0.0.1:P:127.0.0.1:P it listens on 127.0.0.1:P like a tunnel; otherwise it is the
# remote diagnostic and exits with FAKE_CHECK_CODE (default 0). Never contacts anything.
import os
import socket
import sys
import time

with open(os.environ["FAKE_SSH_LOG"], "a") as log:
    log.write(" ".join(sys.argv[1:]) + "\n")
if "-L" in sys.argv:
    port = int(sys.argv[sys.argv.index("-L") + 1].split(":")[1])
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("127.0.0.1", port))
    s.listen()
    time.sleep(300)
else:
    print("[OK] diagnostic simulé")
    sys.exit(int(os.environ.get("FAKE_CHECK_CODE", "0")))
