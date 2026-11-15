#!/usr/bin/python3
import datetime, json, os, pathlib, signal, subprocess, time
ROOT = pathlib.Path(__file__).parent
def now(): return datetime.datetime.now().astimezone().isoformat()
def capture(args):
    p = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=20)
    return p.stdout
start = time.monotonic()
started = now()
deadline = start + 10800
workers = []
outputs = []
interrupted = False
def stop(signum, frame):
    global interrupted
    interrupted = True
signal.signal(signal.SIGTERM, stop)
signal.signal(signal.SIGINT, stop)
for i in range(8):
    f = open(ROOT / ("worker-%02d.log" % (i+1)), "wb")
    p = subprocess.Popen(["/usr/bin/stdbuf","-oL","-eL","/usr/sbin/memtester","12G","0"], stdout=f, stderr=subprocess.STDOUT)
    workers.append(p)
    outputs.append(f)
def save_status(state):
    status = dict(state=state, started=started, updated=now(), elapsed_seconds=round(time.monotonic()-start), requested_gib=96, workers=[dict(pid=p.pid,exit_code=p.poll()) for p in workers])
    tmp = ROOT / "status.tmp"
    tmp.write_text(json.dumps(status, indent=2))
    tmp.replace(ROOT / "status.json")
save_status("running")
try:
    with open(ROOT / "telemetry.log", "a") as telemetry:
        while time.monotonic() < deadline and not interrupted and any(p.poll() is None for p in workers):
            telemetry.write("\n" + now() + "\n")
            telemetry.write(capture(["/usr/bin/free","-m"]))
            telemetry.write(capture(["/usr/bin/sensors"]))
            telemetry.flush()
            save_status("running")
            time.sleep(min(60,max(0,deadline-time.monotonic())))
finally:
    for p in workers:
        if p.poll() is None: p.terminate()
    for p in workers:
        try: p.wait(timeout=10)
        except subprocess.TimeoutExpired:
            p.kill()
            p.wait()
    for f in outputs: f.close()
    (ROOT / "kernel-final.log").write_text(capture(["/usr/bin/journalctl","-k","-b","--no-pager"]))
    counts = {}
    for path in ROOT.glob("worker-*.log"):
        with path.open("rb") as f:
            counts[path.name] = sum(line.count(b"FAILURE") for line in f)
    (ROOT / "failure-counts.json").write_text(json.dumps(counts, indent=2))
    save_status("time_limit_reached" if time.monotonic() >= deadline else "interrupted" if interrupted else "workers_exited")
