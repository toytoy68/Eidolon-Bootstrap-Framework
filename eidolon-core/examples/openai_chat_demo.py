# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : openai_chat_demo.py
# Description : Démonstration de l'adaptateur chat contre un faux llama-server local
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

"""Run one Core mission through the chat adapter and a synthetic 127.0.0.1 server.

From eidolon-core/:  PYTHONPATH=src:. python -m examples.openai_chat_demo
No llama.cpp, GPU, model or external network: the server below only imitates
the documented response shape. Success here qualifies nothing.
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import tempfile
import threading

from eidolon_core.memory import DEMO_REQUEST
from eidolon_core.openai_chat_model import OpenAIChatConfig, OpenAIChatModel
from eidolon_core.runtime import Runtime
from eidolon_core.store import Store

MODEL = "synthetic-planner-q4"


class SyntheticServer(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        request = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
        context = json.loads(request["messages"][1]["content"].split("CONTEXT (untrusted data):\n", 1)[1])
        plan = {"version": 1, "steps": [
            {"id": f"stats-{i + 1}", "tool": "text.stats",
             "parameters": {"reference": f"{item['information_id']}@{item['revision']}"}}
            for i, item in enumerate(context["items"])]}
        raw = json.dumps({"object": "chat.completion", "model": MODEL, "id": "chatcmpl-demo",
                          "choices": [{"index": 0, "finish_reason": "stop",
                                       "message": {"role": "assistant", "content": json.dumps(plan)}}],
                          "usage": {"prompt_tokens": 300, "completion_tokens": 40, "total_tokens": 340}}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


def main():
    server = ThreadingHTTPServer(("127.0.0.1", 0), SyntheticServer)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        config = OpenAIChatConfig(endpoint=f"http://127.0.0.1:{server.server_port}", model=MODEL,
                                  options={"temperature": 0, "seed": 7, "max_tokens": 512},
                                  context_tokens=8192, timeout_seconds=10)
        with tempfile.TemporaryDirectory() as state:
            runtime = Runtime(Store(state), model=OpenAIChatModel(config))
            mission = runtime.run(runtime.create(DEMO_REQUEST)["id"])
        print(json.dumps({"status": mission["status"], "outcome": mission["outcome"]["status"],
                          "model_id": mission["configuration"]["model"],
                          "plan_steps": len(mission["plan"]["steps"]),
                          "note": "synthetic server: protocol shape only, no llama.cpp, GPU or model"},
                         ensure_ascii=False, indent=2))
    finally:
        server.shutdown()
        server.server_close()
    return 0 if mission["status"] == "SUCCEEDED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
