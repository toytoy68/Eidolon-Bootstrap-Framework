# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : recipe_dashboard.py
# Description : Recette du dashboard : Core (relais /v1/comm) + eidolon-comm en processus séparés, Chromium à faux périphériques (C147)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""From eidolon-core/: PYTHONPATH=src python3 docs/validation/2026-10-12/claude-dashboard/recipe_dashboard.py [captures dir]

CONTAINER ONLY: simulated dialogue, simulated STT/TTS/vision, Chromium fake microphone and camera.
Same command lines as the VM units (separate processes, loopback). Does not qualify Windows or WebView2."""
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import tempfile
import time

HERE = Path(__file__).resolve().parent
CORE = HERE.parents[3]
sys.path.insert(0, str(CORE / "src"))
from eidolon_core.client_credentials import ClientCredentials      # noqa: E402
from eidolon_core.conversation_store import ConversationStore      # noqa: E402
from eidolon_core.store import Store                               # noqa: E402


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_port(port, seconds=20):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", port)) == 0:
                return True
        time.sleep(0.1)
    return False


def main():
    captures = sys.argv[1] if len(sys.argv) > 1 else None
    with tempfile.TemporaryDirectory(prefix="eidolon-dash-") as tmp:
        tmp = Path(tmp)
        store = Store(tmp / "state")
        ConversationStore(store, create=True)
        key = ClientCredentials(store, create=True).pair(client_id="pc-toytoy", actor="toytoy")["token"]
        read = secrets.token_urlsafe(32)
        (tmp / "read-token").write_text(read + "\n"); os.chmod(tmp / "read-token", 0o600)
        (tmp / "comm.json").write_text(json.dumps({"schema": "eidolon-comm-config/1", "stt": {"kind": "simulated"},
                                                   "tts": {"kind": "simulated"}, "vision": {"kind": "simulated"}}))
        os.chmod(tmp / "comm.json", 0o600)
        core_port, comm_port = free_port(), free_port()
        env = dict(os.environ, PYTHONPATH=str(CORE / "src"), PYTHONDONTWRITEBYTECODE="1")
        procs = [subprocess.Popen([sys.executable, "-m", "eidolon_core.comm_service", "--state", str(tmp / "state"),
                                   "--config", str(tmp / "comm.json"), "--port", str(comm_port),
                                   "--read-token-file", str(tmp / "read-token")], env=env,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL),
                 subprocess.Popen([sys.executable, "-m", "eidolon_core.http_api", "--state", str(tmp / "state"),
                                   "--token-file", str(tmp / "read-token"), "--port", str(core_port),
                                   "--web-root", str(CORE / "desktop" / "connected"), "--conversations", "simulated",
                                   "--comm-port", str(comm_port)], env=env,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)]
        try:
            ready = wait_port(comm_port) and wait_port(core_port)
            done = subprocess.run(["node", str(HERE / "browser_dashboard.js"), f"http://127.0.0.1:{core_port}/", key]
                                  + ([captures] if captures else []), capture_output=True, text=True, timeout=300,
                                  env=dict(os.environ, NODE_PATH=os.environ.get("NODE_PATH", "/opt/node22/lib/node_modules")))
            result = json.loads(done.stdout.strip().splitlines()[-1]) if done.stdout.strip() else {"checks": []}
        finally:
            for p in procs:
                p.terminate()
                try:
                    p.wait(10)
                except subprocess.TimeoutExpired:
                    p.kill()
        checks = [{"check": "services démarrés (Core :relais, eidolon-comm)", "ok": ready, "detail": ""}] + result["checks"]
        if done.stderr.strip() and not result["checks"]:
            checks.append({"check": "navigateur", "ok": False, "detail": done.stderr[-300:]})
    passed = sum(c["ok"] for c in checks)
    print(json.dumps({"passed": passed, "total": len(checks), "checks": checks}, ensure_ascii=False, indent=1))
    return 0 if passed == len(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
