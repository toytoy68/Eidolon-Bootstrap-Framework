# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : p5_sigterm.py
# Description : SIGTERM sur beta_check pendant que son serveur de recette tourne (C-TASK-G047)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""python3 p5_sigterm.py <frozen eidolon-core>. Targets only the direct children of its own beta_check."""
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time

core = Path(sys.argv[1])


def children(pid):
    out = subprocess.run(["pgrep", "-P", str(pid)], capture_output=True, text=True).stdout.split()
    result = []
    for c in out:
        try:
            result.append((int(c), Path(f"/proc/{c}/cmdline").read_bytes().replace(b"\0", b" ").decode()))
        except OSError:
            pass
    return result


with tempfile.TemporaryDirectory() as t:
    env = dict(os.environ, TMPDIR=t, PYTHONPATH=str(core / "src"), PYTHONDONTWRITEBYTECODE="1")
    p = subprocess.Popen([sys.executable, "-m", "eidolon_core.beta_check", "--web-root", str(core / "desktop/connected")],
                         cwd=core, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    server = None
    for _ in range(500):
        server = next((pid for pid, cmd in children(p.pid) if "--web-root" in cmd and "--check" not in cmd), None)
        if server:
            break
        time.sleep(0.01)
    print("serveur de recette vu :", bool(server))
    p.send_signal(signal.SIGTERM)
    p.wait()
    time.sleep(1)
    alive = server is not None and Path(f"/proc/{server}").exists() and \
        "Z" not in Path(f"/proc/{server}/status").read_text().split("State:")[1][:4]
    print("serveur orphelin encore actif après SIGTERM :", alive)
    for f in sorted(Path(t).rglob("*")):
        if f.suffix not in (".lock",) and "worker" not in f.name:
            print("reste :", str(f).replace(t, "<TMPDIR>"), oct(f.stat().st_mode & 0o777))
    if alive:
        os.kill(server, signal.SIGKILL)
