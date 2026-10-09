# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : recipe_g127.py
# Description : Recette intégrée accueil conversation → agents média depuis le paquet installé (C-TASK-G127)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Run with the INSTALLED package (env -u PYTHONPATH <venv>/bin/python, from /):
    python recipe_g127.py <archive>/eidolon-core/desktop/connected <browser script>

Flow, per mode: the human writes in the conversation (real server, simulated dialogue model) → Core
freezes a media proposal → the human validates (paired key) → a durable queue ticket, nothing run →
the operator runs it explicitly (eidolon-media-worker run --execute-local) → poll/collect → the page
reads the result. Engines are SIMULATED over loopback HTTP (ComfyUI/Ollama shapes, adapted from Codex's
installed_media_worker.py); FFmpeg/FFprobe are real. No model, GPU, VM or Windows. Prints one JSON report."""
from email import policy
from email.parser import BytesParser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import http.client
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tempfile
import threading
import time
from urllib.parse import parse_qs, urlsplit

WEB, BROWSER = sys.argv[1], sys.argv[2]
BIN = Path(sys.executable).parent
CHECKS = []
ENV = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}


def check(step, name, ok, detail=""):
    CHECKS.append({"step": step, "check": name, "ok": bool(ok), "detail": str(detail)[:300]})


class Engine:
    """Loopback stand-in for ComfyUI + Ollama. Counts every engine call; can hang or drop an output."""
    def __init__(self, media):
        self.media, self.calls, self.uploaded, self.histories, self.outputs = media, [], {}, {}, {}
        self.hang = threading.Event()        # set: the next /prompt never answers (process will be killed)
        self.two_outputs = False             # next job reports two outputs, the second one unreadable
        engine = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                engine.calls.append("POST " + self.path)
                raw = self.rfile.read(int(self.headers["Content-Length"]))
                if self.path == "/upload/image":
                    msg = BytesParser(policy=policy.default).parsebytes(
                        ("Content-Type: " + self.headers["Content-Type"] + "\r\n\r\n").encode() + raw)
                    parts = {p.get_param("name", header="content-disposition"): p for p in msg.iter_parts()}
                    name = parts["image"].get_filename()
                    engine.uploaded[name] = parts["image"].get_payload(decode=True)
                    return self.reply({"name": name, "subfolder": "", "type": "input"})
                body = json.loads(raw)
                if self.path == "/api/show":
                    return self.reply({"capabilities": ["completion", "vision"]})
                if self.path == "/api/generate":
                    return self.reply({"model": body["model"], "done": True, "done_reason": "stop",
                                       "response": "Observation synthétique <b>non vérifiée</b>."})
                if engine.hang.is_set():
                    engine.hang.clear()
                    time.sleep(120)              # the worker process is killed meanwhile
                    return
                flow = body["prompt"]
                kind = "video" if "duration" in flow["1"]["inputs"] else "image"
                pid = "g127-" + str(len(engine.histories) + 1)
                ext = ".mp4" if kind == "video" else ".png"
                files = [{"filename": pid + ext, "subfolder": "", "type": "output"}]
                if engine.two_outputs:
                    engine.two_outputs = False
                    files.append({"filename": pid + "-perdu" + ext, "subfolder": "", "type": "output"})
                engine.histories[pid] = {"prompt": [1, pid, flow, {}, ["1"]],
                                         "status": {"completed": True, "status_str": "success"},
                                         "outputs": {"1": {"videos" if kind == "video" else "images": files}}}
                engine.outputs[pid + ext] = engine.media[kind]
                self.reply({"prompt_id": pid})

            def do_GET(self):
                engine.calls.append("GET " + self.path.split("?")[0])
                u = urlsplit(self.path)
                if u.path == "/object_info/SyntheticFixture":
                    return self.reply({"SyntheticFixture": {"name": "SyntheticFixture", "input": {
                        "required": {"text": ["STRING", {}], "width": ["INT", {}], "height": ["INT", {}]},
                        "optional": {"duration": ["INT", {}], "source": [["x.png"], {}]}}}})
                if u.path.startswith("/history/"):
                    pid = u.path.rsplit("/", 1)[-1]
                    return self.reply({pid: engine.histories[pid]})
                name = parse_qs(u.query)["filename"][0]
                store = engine.uploaded if parse_qs(u.query)["type"] == ["input"] else engine.outputs
                if name not in store:
                    self.send_response(404); self.send_header("Content-Length", "0"); self.end_headers(); return
                self.reply(store[name], "video/mp4" if name.endswith(".mp4") else "image/png")

            def reply(self, value, kind="application/json"):
                body = value if type(value) is bytes else json.dumps(value).encode()
                self.send_response(200); self.send_header("Content-Type", kind)
                self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)

            def log_message(self, *args):
                pass
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.url = "http://127.0.0.1:" + str(self.server.server_port)

    def posts(self):
        return [c for c in self.calls if c in ("POST /prompt", "POST /api/generate")]


def run(cmd, code=0, **kw):
    p = subprocess.run([str(c) for c in cmd], env=ENV, capture_output=True, text=True, timeout=kw.get("timeout", 60))
    if code is not None and p.returncode != code:
        raise SystemExit(f"{cmd[:3]} → {p.returncode}: {p.stdout[-300:]} {p.stderr[-300:]}")
    return p


def as_json(p):
    return json.loads(p.stdout)


class Api:
    def __init__(self, port, key, token):
        self.port, self.key, self.token = port, key, token

    def call(self, route, body, token=None):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=30)
        c.request("POST", "/v1/conversations/" + route, body=json.dumps(body).encode(),
                  headers={"Host": f"127.0.0.1:{self.port}", "Authorization": "Bearer " + (token or self.key),
                           "Content-Type": "application/json"})
        r = c.getresponse(); value = json.loads(r.read()); c.close()
        return r.status, value


def main():
    with tempfile.TemporaryDirectory(prefix="eidolon-g127-") as tmp:
        root = Path(tmp)
        # Real FFmpeg fixtures (64×64, 2 s).
        run(["/usr/bin/ffmpeg", "-nostdin", "-v", "error", "-f", "lavfi", "-i", "color=c=blue:s=64x64:r=2", "-t", "2",
             "-threads", "1", "-c:v", "mpeg4", root / "fixture.mp4"])
        run(["/usr/bin/ffmpeg", "-nostdin", "-v", "error", "-i", root / "fixture.mp4", "-frames:v", "1", "-threads", "1",
             root / "fixture.png"])
        engine = Engine({"image": (root / "fixture.png").read_bytes(), "video": (root / "fixture.mp4").read_bytes()})
        state, token_file = root / "state", root / "read-token"
        run([sys.executable, "-m", "eidolon_core", "--state", state, "demo"])
        run([sys.executable, "-m", "eidolon_core.access_token", "--output", token_file])
        token = token_file.read_text().strip()
        key = as_json(run([sys.executable, "-m", "eidolon_core.conversation_api", "--state", state, "pair",
                           "--client-id", "pc-toytoy", "--actor", "toytoy"]))["token"]
        # Operator: the media workspace (C-067), completed with the simulated engines' configuration.
        ws = as_json(run([BIN / "eidolon-media", "workspace-init", "--root", root / "media", "--state", state]))
        cfg_file = root / "media" / "media.json"
        cfg = json.loads(cfg_file.read_text())
        cfg.update({"comfy_endpoint": engine.url, "ollama_endpoint": engine.url, "vision_model": "fixture:local",
                    "ffmpeg": "/usr/bin/ffmpeg", "source_transfer": "upload-verified", "workflows": {}})
        for kind in ("image", "video"):
            for op in ("create", "edit"):
                fields = {"prompt": "text", "width": "width", "height": "height"}
                if kind == "video":
                    fields["duration_seconds"] = "duration"
                if op == "edit":
                    fields["source"] = "source"
                cfg["workflows"][kind + "." + op] = {
                    "prompt": {"1": {"class_type": "SyntheticFixture", "inputs": {v: "" for v in fields.values()}}},
                    "bindings": {k: ["1", v] for k, v in fields.items()}}
        cfg_file.write_text(json.dumps(cfg)); os.chmod(cfg_file, 0o600)
        inspected = run([BIN / "eidolon-media", "workspace-inspect", "--root", root / "media", "--workspace-id",
                         ws["workspace_id"]], code=None)
        check("S", "espace média cohérent après configuration", inspected.returncode == 0
              and as_json(inspected)["state"] == "LOCAL_WORKSPACE_READY", as_json(inspected).get("configuration_state"))
        store_args = ["--root", root / "media" / "artifacts", "--store-id", cfg["artifact_store"]["store_id"]]
        pool_args = ["--root", root / "media" / "resources", "--pool-id", cfg["resource_pool"]["pool_id"]]
        worker = [BIN / "eidolon-media-worker", "--root", root / "media" / "worker", "--state", state, "--worker-id",
                  json.loads((root / "media" / "workspace.json").read_text())["components"]["worker"]]

        server = subprocess.Popen([sys.executable, "-m", "eidolon_core.http_api", "--state", state, "--token-file",
                                   token_file, "--port", "0", "--web-root", WEB, "--conversations", "simulated",
                                   "--media-workspace", root / "media", "--media-workspace-id", ws["workspace_id"]],
                                  env=ENV, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        port = None
        deadline = time.monotonic() + 15
        while port is None and time.monotonic() < deadline:
            m = re.search(r"http://127\.0\.0\.1:(\d+)", server.stdout.readline())
            port = int(m.group(1)) if m else None
        api = Api(port, key, token)
        try:
            status, refused = api.call("open", {"client_key": "x"}, token=token)
            check("S", "jeton de lecture refusé sur la conversation", status == 403, refused.get("error"))
            cid = api.call("open", {"client_key": "g127"})[1]["conversation_id"]
            n = [0]

            def say(text):
                n[0] += 1
                return api.call("turn", {"conversation_id": cid, "client_turn_key": f"t{n[0]}", "text": text})[1]["reply"]

            def attach(kind):
                suffix = "png" if kind == "image" else "mp4"
                ref = as_json(run([BIN / "eidolon-media", "artifact-import", *store_args, "--source",
                                   root / ("fixture." + suffix)]))["reference"]
                (root / (kind + "-ref.json")).write_text(json.dumps(ref))
                run([sys.executable, "-m", "eidolon_core.conversation_api", "--state", state, "attach", "--client-id",
                     "pc-toytoy", "--conversation-id", cid, "--artifact-root", root / "media" / "artifacts",
                     "--reference", root / (kind + "-ref.json")])

            def submit(reply, key_name):
                p = reply["proposal"]
                return api.call("submit", {"protocol": "eidolon-proposal-submission/1", "store_id": p["store_id"],
                                           "client_id": "pc-toytoy", "command_key": key_name, "conversation_id": cid,
                                           "proposal_id": p["proposal_id"], "proposal_version": p["version"],
                                           "proposal_sha256": reply["proposal_sha256"], "actor": "toytoy",
                                           "reason": "Accord humain synthétique"})

            def release():
                held = as_json(run([BIN / "eidolon-media", "resource-inspect", *pool_args]))
                if held["state"] == "RESERVED":
                    run([BIN / "eidolon-media", "resource-release", *pool_args, "--lease-id", held["current"]["lease_id"],
                         "--reviewed-idle", "--reason", "Moteur simulé observé au repos"])

            own = lambda t: ["--client-id", "pc-toytoy", "--ticket", t["ticket_id"]]
            modes = [("image", "create", "Crée une image : un phare au crépuscule"),
                     ("image", "edit", "Retouche la photo : ajoute un ciel étoilé"),
                     ("image", "analyze", "Analyse la photo : décris-la"),
                     ("video", "create", "Crée une vidéo : la mer au loin"),
                     ("video", "edit", "Retouche la vidéo : plus lumineuse"),
                     ("video", "analyze", "Analyse la vidéo : décris-la")]
            attach("image")
            stages = {}
            for kind, op, text in modes:
                name = f"{kind}.{op}"
                if name == "video.create":
                    attach("video")
                reply = say(text)
                p = reply.get("proposal") or {}
                check("M", f"{name} : proposition figée par Core", reply["kind"] == "PROPOSAL"
                      and (p.get("agent"), p.get("operation")) == (kind, op), reply["kind"])
                before = len(engine.posts())
                status, ticket = submit(reply, "valider-" + name)
                check("M", f"{name} : accord → ticket, aucun appel moteur", status == 200 and ticket["state"] == "ACCEPTED"
                      and len(engine.posts()) == before, ticket.get("state", ticket))
                done = as_json(run([*worker, "run", *own(ticket), "--config", cfg_file, "--execute-local"], timeout=120))
                again = as_json(run([*worker, "run", *own(ticket), "--config", cfg_file, "--execute-local"]))
                check("M", f"{name} : lancement explicite, un seul appel", done["state"] == "RETURNED"
                      and again == done and len(engine.posts()) == before + 1, done["state"])
                if op != "analyze":
                    run([*worker, "poll", *own(ticket)])
                    run([*worker, "collect", *own(ticket), "--artifact-root", root / "media" / "artifacts",
                         "--artifact-store-id", cfg["artifact_store"]["store_id"], "--collect-local"])
                release()
                body = api.call("media_results", {"conversation_id": cid})[1]
                mine = next(t for t in body["tickets"] if t["receipt"]["ticket_id"] == ticket["ticket_id"])
                result = mine["result"]
                ok = result and result["binding"] == "MATCHED" and result["success_claim"] is False
                if op == "analyze":
                    ok = ok and result["observation"]["verified"] is False
                else:
                    ok = ok and result["outputs"] and result["outputs"][0]["verification"] == "hash_verified"
                check("M", f"{name} : résultat lu par la route, non vérifié", ok, result and result.get("stage"))
                stages[name] = result and result.get("stage")

            # Cut: the worker process is killed while the engine holds the request.
            reply = say("Crée une image : coupure pendant l'appel")
            ticket = submit(reply, "valider-coupure")[1]
            engine.hang.set()
            proc = subprocess.Popen([str(c) for c in [*worker, "run", *own(ticket), "--config", cfg_file, "--execute-local"]],
                                    env=ENV, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            limit = time.monotonic() + 20
            while engine.hang.is_set() and time.monotonic() < limit:
                time.sleep(0.05)
            time.sleep(0.3)
            proc.send_signal(signal.SIGKILL); proc.wait(10)
            posts = len(engine.posts())
            resumed = as_json(run([*worker, "run", *own(ticket), "--config", cfg_file, "--execute-local"]))
            body = api.call("media_results", {"conversation_id": cid})[1]
            cut = next(t for t in body["tickets"] if t["receipt"]["ticket_id"] == ticket["ticket_id"])
            check("C", "coupure : tentative durable, aucun second appel moteur", resumed["state"] == "ATTEMPTED"
                  and len(engine.posts()) == posts, resumed["state"])
            check("C", "coupure : effet inconnu affiché, rien de relancé", cut["receipt"]["state"] == "ATTEMPTED",
                  cut["observation"])
            held = as_json(run([BIN / "eidolon-media", "resource-inspect", *pool_args]))
            check("C", "coupure : réservation conservée pour revue", held["state"] == "RESERVED")
            release()

            # Partial: two outputs announced, the second one cannot be read.
            reply = say("Crée une image : deux variantes")
            ticket = submit(reply, "valider-partiel")[1]
            engine.two_outputs = True
            run([*worker, "run", *own(ticket), "--config", cfg_file, "--execute-local"])
            collected = run([*worker, "collect", *own(ticket), "--artifact-root", root / "media" / "artifacts",
                             "--artifact-store-id", cfg["artifact_store"]["store_id"], "--collect-local"], code=None)
            release()
            body = api.call("media_results", {"conversation_id": cid})[1]
            part = next(t for t in body["tickets"] if t["receipt"]["ticket_id"] == ticket["ticket_id"])["result"]
            check("P", "collecte partielle annoncée, import conservé", collected.returncode != 0 and part
                  and part["collection"]["partial"] is True and part["collection"]["imported"] == 1
                  and part["collection"]["expected"] == 2, part and part["collection"])
            text = json.dumps(body)
            check("P", "aucun chemin privé ni secret dans la route", tmp not in text and key not in text and token not in text)

            # Browser: the page reads it all back after a reload, at 1280 and 360 px.
            browser = run(["node", BROWSER, f"http://127.0.0.1:{port}/", key, tmp], code=None, timeout=240)
            try:
                seen = json.loads(browser.stdout.strip().splitlines()[-1])
            except (ValueError, IndexError):
                seen = {"ok": False, "error": browser.stderr[-300:]}
            check("B", "Chromium 1280 et 360 : demandes et résultats lus, sans chemin ni débordement", seen.get("ok"), seen)
        finally:
            server.send_signal(signal.SIGTERM); server.wait(10)
            engine.server.shutdown()
        check("Z", "huit tickets durables, six modes", len(stages) == 6, stages)
    passed = sum(c["ok"] for c in CHECKS)
    print(json.dumps({"passed": passed, "total": len(CHECKS), "engine": "SIMULATED_HTTP", "ffmpeg": "REAL",
                      "model": "SIMULATED_DIALOGUE", "checks": CHECKS}, ensure_ascii=False, indent=1))
    return 0 if passed == len(CHECKS) else 1


if __name__ == "__main__":
    sys.exit(main())
