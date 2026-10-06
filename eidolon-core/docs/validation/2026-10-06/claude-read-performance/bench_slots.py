# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : bench_slots.py
# Description : Refus de connexion selon le nombre de clients simultanés, 4 places serveur (C-TASK-G039)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""From eidolon-core/: PYTHONPATH=src python3 docs/validation/2026-10-06/claude-read-performance/bench_slots.py
1, 2, 3, 4 and 5 clients, each sending 100 sequential snapshot requests (new connection each time,
like the client G031). Counts answers that are not HTTP 200 (connection dropped by the server)."""
import concurrent.futures
import json
from pathlib import Path
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).parent))
from bench_read import ENV, request, start  # noqa: E402


def main():
    with tempfile.TemporaryDirectory(prefix="eidolon-g039-slots-") as root:
        out = Path(root) / "fx"
        subprocess.run([sys.executable, "-m", "eidolon_core.beta_fixture", "--output", str(out)], check=True, env=ENV, capture_output=True)
        manifest = json.loads((out / "manifest.json").read_text())
        token = (out / "read-token").read_text().strip()
        mission = manifest["scenarios"][0]["mission_id"]
        proc, port = start(out / "state", out / "read-token")
        try:
            for clients in (1, 2, 3, 4, 5):
                def worker(_):
                    return [request(port, token, "GET", f"/v1/missions/{mission}")[0] for _ in range(100)]
                with concurrent.futures.ThreadPoolExecutor(clients) as pool:
                    statuses = [s for batch in pool.map(worker, range(clients)) for s in batch]
                refused = [s for s in statuses if s != 200]
                print(json.dumps({"clients": clients, "requests": len(statuses), "not_200": len(refused),
                                  "kinds": sorted(set(map(str, refused)))}))
        finally:
            proc.terminate()
            proc.wait(timeout=10)


if __name__ == "__main__":
    main()
