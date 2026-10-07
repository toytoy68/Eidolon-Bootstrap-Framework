#!/usr/bin/env python3
# Fake ssh for G046 (Linux only). Logs argv as JSON. With -L it listens like a tunnel.
# Otherwise it behaves like OpenSSH for the remote command: the words after the destination
# are JOINED WITH SPACES and run by "bash -c" with HOME=FAKE_REMOTE_HOME (a folder whose name
# contains a space). That is how a real ssh server receives the command string.
import json
import os
import socket
import subprocess
import sys
import time

args = sys.argv[1:]
with open(os.environ["FAKE_SSH_LOG"], "a") as log:
    log.write(json.dumps(args) + "\n")
if "-L" in args:
    port = int(args[args.index("-L") + 1].split(":")[1])
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("127.0.0.1", port))
    s.listen()
    time.sleep(300)
else:
    rest = args[args.index("--") + 2:]
    env = dict(os.environ, HOME=os.environ["FAKE_REMOTE_HOME"])
    done = subprocess.run(["bash", "-c", " ".join(rest)], cwd=env["HOME"], env=env, capture_output=True, text=True)
    sys.stdout.write(done.stdout[-600:])
    sys.stderr.write(done.stderr[-300:])
    sys.exit(done.returncode)
