# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : bench_read.py
# Description : Coût de la consultation HTTP bêta à 10, 100 et 1000 missions synthétiques (C-TASK-G039)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""From eidolon-core/: PYTHONPATH=src python3 docs/validation/2026-10-06/claude-read-performance/bench_read.py

For each size N: the C-009g beta fixture (6 missions, 3 receipts) plus N-6 NEW missions created
in one process with Runtime.create; the real http_api runs as a SEPARATE process on 127.0.0.1:0.
Each measure is 3 repetitions of 10 sequential requests (median and max per request, in ms).
Everything is created in a temporary folder and removed at the end. No other host is contacted."""
import concurrent.futures
import http.client
import json
import os
from pathlib import Path
import platform
import re
import sqlite3
import statistics
import subprocess
import sys
import tempfile
import threading
import time

from eidolon_core.runtime import Runtime
from eidolon_core.store import Store

SIZES = (10, 100, 1000)
REPS, CALLS = 3, 10
ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")


def start(state, token_file):
    proc = subprocess.Popen([sys.executable, "-m", "eidolon_core.http_api", "--state", str(state), "--token-file", str(token_file),
                             "--port", "0"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, env=ENV)
    line = ""
    while "127.0.0.1:" not in line:
        line += proc.stdout.readline()
    return proc, int(re.search(r"127\.0\.0\.1:(\d+)", line).group(1))


def request(port, token, method, path, body=None, timeout=10):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=timeout)
    headers = {"Authorization": "Bearer " + token}
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    t0 = time.perf_counter()
    try:
        conn.request(method, path, body=data, headers=headers)
        resp = conn.getresponse()
        raw = resp.read()
        return resp.status, raw, (time.perf_counter() - t0) * 1000
    except (ConnectionError, OSError) as exc:
        return type(exc).__name__, b"", (time.perf_counter() - t0) * 1000
    finally:
        conn.close()


def measure(fn):
    """3 repetitions x 10 calls: median and max of the per-call latency, last body size."""
    times, size, status = [], 0, None
    for _ in range(REPS):
        for _ in range(CALLS):
            status, raw, ms = fn()
            times.append(ms)
            size = len(raw)
    return {"median_ms": round(statistics.median(times), 2), "max_ms": round(max(times), 2), "bytes": size, "status": status}


def full_listing(port, token, limit):
    cursor, pages, total_bytes, t0 = None, 0, 0, time.perf_counter()
    while True:
        status, raw, _ = request(port, token, "POST", "/v1/missions", {"limit": limit} if cursor is None else {"limit": limit, "cursor": cursor})
        pages += 1
        total_bytes += len(raw)
        page = json.loads(raw)
        if not page["has_more"]:
            return pages, total_bytes, (time.perf_counter() - t0) * 1000, len(page["items"])
        cursor = page["next_cursor"]


def cpu_rss(pid):
    with open(f"/proc/{pid}/stat") as f:
        fields = f.read().rsplit(")", 1)[1].split()
    ticks = int(fields[11]) + int(fields[12])
    with open(f"/proc/{pid}/status") as f:
        rss = int(next(line for line in f if line.startswith("VmRSS")).split()[1])
    return ticks / os.sysconf("SC_CLK_TCK"), rss


def bench(size, root):
    out = Path(root) / f"n{size}"
    subprocess.run([sys.executable, "-m", "eidolon_core.beta_fixture", "--output", str(out)], check=True, env=ENV, capture_output=True)
    manifest = json.loads((out / "manifest.json").read_text())
    t0 = time.perf_counter()
    runtime = Runtime(Store(out / "state"))
    for i in range(size - len(manifest["scenarios"])):
        runtime.create("mission synthétique de banc %04d" % i)
    build_s = time.perf_counter() - t0
    token = (out / "read-token").read_text().strip()
    db_bytes = (out / "state" / "missions.sqlite3").stat().st_size
    proc, port = start(out / "state", out / "read-token")
    try:
        mission = manifest["scenarios"][0]["mission_id"]
        _, raw, _ = request(port, token, "GET", f"/v1/missions/{mission}")
        cursor = json.loads(raw)["cursor"]
        receipt = manifest["receipt_queries"][1]
        absent = dict(receipt, command_key="absente-g039")
        r = {"missions": size, "build_s": round(build_s, 2), "db_kib": db_bytes // 1024}
        r["health"] = measure(lambda: request(port, token, "GET", "/v1/health"))
        r["page20"] = measure(lambda: request(port, token, "POST", "/v1/missions", {"limit": 20}))
        r["page100"] = measure(lambda: request(port, token, "POST", "/v1/missions", {"limit": 100}))
        r["snapshot"] = measure(lambda: request(port, token, "GET", f"/v1/missions/{mission}"))
        r["poll"] = measure(lambda: request(port, token, "POST", f"/v1/missions/{mission}/poll", {"cursor": cursor}))
        r["receipt_found"] = measure(lambda: request(port, token, "POST", "/v1/command-receipt", receipt))
        r["receipt_absent"] = measure(lambda: request(port, token, "POST", "/v1/command-receipt", absent))
        listings = [full_listing(port, token, 100) for _ in range(REPS)]
        r["full_list_100"] = {"pages": listings[0][0], "bytes": listings[0][1], "items_last_page": listings[0][3],
                              "ms": [round(x[2], 1) for x in listings]}
        listings20 = [full_listing(port, token, 20) for _ in range(REPS)]
        r["full_list_20"] = {"pages": listings20[0][0], "bytes": listings20[0][1], "ms": [round(x[2], 1) for x in listings20]}
        # Idle: no client request for 10 s.
        cpu0, rss0 = cpu_rss(proc.pid)
        time.sleep(10)
        cpu1, rss1 = cpu_rss(proc.pid)
        r["idle_10s"] = {"cpu_s": round(cpu1 - cpu0, 3), "rss_kib": rss1}
        # Parallel clients (4 connection slots): 1, 4 and 8 clients, 5 snapshots each.
        conc = {}
        for clients in (1, 4, 8):
            def worker(_):
                return [request(port, token, "GET", f"/v1/missions/{mission}")[::2] for _ in range(5)]
            t0 = time.perf_counter()
            with concurrent.futures.ThreadPoolExecutor(clients) as pool:
                results = [x for batch in pool.map(worker, range(clients)) for x in batch]
            elapsed = (time.perf_counter() - t0) * 1000
            ok = [ms for st, ms in results if st == 200]
            conc[clients] = {"ok": len(ok), "refused": len(results) - len(ok), "median_ms": round(statistics.median(ok), 2) if ok else None,
                             "wall_ms": round(elapsed, 1)}
        r["parallel"] = conc
        # SQLite write lock held by another connection (rollback journal: readers wait, timeout 2 s).
        locks = {}
        for hold in (0.5, 3.0):
            db = sqlite3.connect(out / "state" / "missions.sqlite3", isolation_level=None, check_same_thread=False)
            db.execute("BEGIN EXCLUSIVE")
            timer = threading.Timer(hold, lambda d=db: (d.execute("ROLLBACK"), d.close()))
            timer.start()
            status, raw, ms = request(port, token, "POST", "/v1/missions", {"limit": 20})
            timer.join()
            code = json.loads(raw).get("error") if raw and status != 200 else None
            locks[hold] = {"status": status, "error": code, "ms": round(ms, 1)}
            _, _, after = request(port, token, "GET", "/v1/health")
            locks[hold]["health_after_ms"] = round(after, 1)
        r["write_lock"] = locks
        return r
    finally:
        proc.terminate()
        proc.wait(timeout=10)


def machine():
    fs = subprocess.run(["stat", "-f", "-c", "%T", tempfile.gettempdir()], capture_output=True, text=True).stdout.strip()
    return {"python": platform.python_version(), "sqlite": sqlite3.sqlite_version, "kernel": platform.release(),
            "cpus": os.cpu_count(), "tmp_fs": fs, "machine": platform.machine()}


def main():
    print(json.dumps({"machine": machine()}, ensure_ascii=False))
    with tempfile.TemporaryDirectory(prefix="eidolon-g039-") as root:
        for size in SIZES:
            print(json.dumps(bench(size, root), ensure_ascii=False))
    print(json.dumps({"cleaned": not Path(root).exists()}))


if __name__ == "__main__":
    main()
