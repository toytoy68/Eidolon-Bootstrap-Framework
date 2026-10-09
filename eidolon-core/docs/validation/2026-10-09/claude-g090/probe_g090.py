# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : probe_g090.py
# Description : Contre-revue des doublons conversation/mission : double clic, clients concurrents, coupures (C-TASK-G090)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""python3 probe_g090.py <eidolon-core/src to test>   — prints one JSON report.

Independent of the unit tests: real loopback HTTP (ConversationServer), real processes for cuts,
synthetic state in temporary folders, a counting simulated model. Observations only: each scenario
records what happened (missions, model calls, receipts); the report says which guarantee held."""
import http.client
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading

SRC = str(Path(sys.argv[1]).resolve())
sys.path.insert(0, SRC)
sys.dont_write_bytecode = True
from eidolon_core import conversation_api as api  # noqa: E402
from eidolon_core.client_credentials import ClientCredentials  # noqa: E402
from eidolon_core.contracts import digest  # noqa: E402
from eidolon_core.conversation_store import ConversationStore  # noqa: E402
from eidolon_core.dialogue import SimulatedDialogueModel  # noqa: E402
from eidolon_core.diagnostics import synthetic_runtime  # noqa: E402
from eidolon_core.store import Store  # noqa: E402

ENV = dict(os.environ, PYTHONPATH=SRC, PYTHONDONTWRITEBYTECODE="1")


class Counting(SimulatedDialogueModel):
    """Counts calls; can hold every call until released (to make attempts overlap)."""
    def __init__(self, catalog, gate=None):
        super().__init__(catalog)
        self.calls, self.gate, self.lock = 0, gate, threading.Lock()

    def reply(self, text, history, memory):
        with self.lock:
            self.calls += 1
        if self.gate is not None:
            self.gate.wait(10)
        return super().reply(text, history, memory)


class Bench:
    def __init__(self, tmp, gate=None):
        self.state = os.path.join(tmp, "state")
        self.runtime = synthetic_runtime(Store(self.state))
        ConversationStore(self.runtime.store, create=True)
        credentials = ClientCredentials(self.runtime.store, create=True)
        self.keys = {name: credentials.pair(client_id=name, actor=name)["token"] for name in ("pc-a", "pc-b")}
        self.start(gate)

    def start(self, gate=None):
        self.model = Counting(self.runtime.catalog, gate)
        self.api = api.ConversationAPI(self.runtime, dialogue_model=self.model)
        self.server = api.ConversationServer(self.api)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def stop(self):
        self.server.shutdown()
        self.server.server_close()

    def post(self, route, body, client="pc-a"):
        c = http.client.HTTPConnection("127.0.0.1", self.server.server_address[1], timeout=20)
        c.request("POST", api.PREFIX + route, body=json.dumps(body).encode(),
                  headers={"Content-Type": "application/json", "Authorization": "Bearer " + self.keys[client],
                           "Host": f"127.0.0.1:{self.server.server_address[1]}"})
        r = c.getresponse()
        value = json.loads(r.read())
        c.close()
        return r.status, value

    def missions(self):
        with self.runtime.store.connection() as db:
            return db.execute("SELECT count(*) FROM missions").fetchone()[0]

    def conversation(self, client="pc-a"):
        return self.post("open", {"client_key": os.urandom(4).hex()}, client)[1]

    def proposal(self, opened, text="Diagnostique le nas.", key=None, client="pc-a"):
        return self.post("turn", {"conversation_id": opened["conversation_id"], "client_turn_key": key or os.urandom(4).hex(),
                                  "text": text}, client)[1]["reply"]["proposal"]

    @staticmethod
    def submission(opened, proposal, key, **changes):
        value = {"protocol": "eidolon-proposal-submission/1", "store_id": proposal["store_id"],
                 "client_id": opened.get("client_id", "pc-a"), "command_key": key,
                 "conversation_id": proposal["conversation_id"], "proposal_id": proposal["proposal_id"],
                 "proposal_version": proposal["version"], "proposal_sha256": digest(proposal),
                 "actor": opened.get("actor", "pc-a"), "reason": "sonde G090"}
        value.update(changes)
        return value


def parallel(n, fn):
    results, threads = [None] * n, []
    for i in range(n):
        threads.append(threading.Thread(target=lambda i=i: results.__setitem__(i, fn(i))))
    for t in threads:
        t.start()
    for t in threads:
        t.join(30)
    return results


def scenario(name, fn):
    with tempfile.TemporaryDirectory(prefix="eidolon-g090-") as tmp:
        try:
            return {"scenario": name, **fn(tmp)}
        except Exception as exc:  # noqa: BLE001 - an exception is an observation too
            return {"scenario": name, "error": f"{type(exc).__name__}: {str(exc)[:120]}"}


def double_click_same_key(tmp):
    b = Bench(tmp)
    o = b.conversation(); p = b.proposal(o)
    answers = parallel(5, lambda i: b.post("submit", b.submission(o, p, "same-key")))
    b.stop()
    return {"missions": b.missions(), "distinct_mission_ids": len({a[1].get("mission_id") for a in answers}),
            "statuses": sorted({a[0] for a in answers}), "held": b.missions() == 1}


def double_click_new_keys(tmp):
    b = Bench(tmp)
    o = b.conversation(); p = b.proposal(o)
    answers = parallel(5, lambda i: b.post("submit", b.submission(o, p, f"click-{i}")))
    b.stop()
    errors = sorted(a[1].get("error") or a[1].get("status") for a in answers)
    return {"missions": b.missions(), "answers": errors, "held": b.missions() == 1}


def two_clients(tmp):
    b = Bench(tmp)
    oa, ob = b.conversation("pc-a"), b.conversation("pc-b")
    pa, pb = b.proposal(oa, client="pc-a"), b.proposal(ob, "Diagnostique la mémoire.", client="pc-b")
    answers = parallel(2, lambda i: b.post("submit", b.submission(oa if i == 0 else ob, pa if i == 0 else pb, "k"),
                                           "pc-a" if i == 0 else "pc-b"))
    steal = b.post("submit", b.submission(ob, pb, "steal"), "pc-a")
    peek = b.post("page", {"conversation_id": oa["conversation_id"]}, "pc-b")
    b.stop()
    return {"missions": b.missions(), "own_submissions": [a[1].get("status") for a in answers],
            "cross_submit": steal[1].get("error"), "cross_read": peek[0],
            "held": b.missions() == 2 and steal[0] in (403, 404) and peek[0] == 404}


def lost_turn_response_then_resend(tmp):
    b = Bench(tmp)
    o = b.conversation()
    first = b.post("turn", {"conversation_id": o["conversation_id"], "client_turn_key": "t", "text": "Diagnostique le nas."})
    again = b.post("turn", {"conversation_id": o["conversation_id"], "client_turn_key": "t", "text": "Diagnostique le nas."})
    b.stop()
    return {"model_calls": b.model.calls, "same_reply": first[1]["reply"] == again[1]["reply"],
            "held": b.model.calls == 1 and first[1]["reply"] == again[1]["reply"]}


def same_turn_at_once(tmp):
    """Two attempts for the same turn overlap. ConversationServer serves one request at a time, so the
    handler is called from two threads, as the multi-threaded read server (http_api) does."""
    import time
    gate = threading.Event()
    b = Bench(tmp, gate)
    o = b.conversation()
    body = json.dumps({"conversation_id": o["conversation_id"], "client_turn_key": "t", "text": "Diagnostique le nas."}).encode()
    headers = {"Authorization": ["Bearer " + b.keys["pc-a"]], "Content-Type": ["application/json"],
               "Host": [f"127.0.0.1:{b.server.server_address[1]}"]}
    out = {}
    call = lambda name: out.__setitem__(name, b.api.handle("POST", api.PREFIX + "turn", headers, body))
    first = threading.Thread(target=call, args=("first",)); first.start()
    time.sleep(0.3)                                     # the first attempt is inside the model call
    second = threading.Thread(target=call, args=("second",)); second.start()
    second.join(2 if b.api.dialogue.__dict__.get("attempt_seconds") else 0.5)
    gate.set()
    first.join(20); second.join(20)
    b.stop()
    return {"model_calls": b.model.calls, "second_answer": "pending" if out["second"][1].get("pending") else
            (out["second"][1].get("reply") or {}).get("kind"), "held": b.model.calls == 1}


def restart_keeps_receipts(tmp):
    b = Bench(tmp)
    o = b.conversation(); p = b.proposal(o)
    receipt = b.post("submit", b.submission(o, p, "k"))[1]
    b.stop(); b.start()                                   # server restart, same state
    found = b.post("receipt", {"command_key": "k"})[1]
    again = b.post("submit", b.submission(o, p, "k"))[1]
    b.stop()
    return {"missions": b.missions(), "receipt_found": found.get("status"),
            "same_mission": again.get("mission_id") == receipt.get("mission_id"),
            "held": b.missions() == 1 and found.get("status") == "FOUND"}


def modified_proposal_old_agreement(tmp):
    b = Bench(tmp)
    o = b.conversation()
    v1 = b.proposal(o)
    first = b.post("submit", b.submission(o, v1, "k1"))[1]
    v2 = b.proposal(o, "Diagnostique plutôt la mémoire.")
    reuse_digest = b.post("submit", b.submission(o, v2, "k2", proposal_sha256=digest(v1)))
    replay_old = b.post("submit", b.submission(o, v1, "k1"))[1]
    stale_new_key = b.post("submit", b.submission(o, v1, "k3"))
    b.stop()
    return {"missions": b.missions(), "v2_with_v1_digest": reuse_digest[1].get("error"),
            "old_key_replays_v1_only": replay_old.get("mission_id") == first.get("mission_id"),
            "v1_new_key": stale_new_key[1].get("error"),
            "held": b.missions() == 1 and reuse_digest[0] == 409 and stale_new_key[0] == 409}


KILLED = r"""
import os, sys, json
sys.path.insert(0, sys.argv[1])
from eidolon_core import conversation_api as api
from eidolon_core.dialogue import SimulatedDialogueModel
from eidolon_core.diagnostics import synthetic_runtime
from eidolon_core.store import Store
class Dies(SimulatedDialogueModel):
    def reply(self, *a):
        open(sys.argv[3], "a").write("call\n")
        os._exit(9)                                  # process killed during the model call
runtime = synthetic_runtime(Store(sys.argv[2]))
try:
    a = api.ConversationAPI(runtime, dialogue_model=Dies(runtime.catalog), attempt_seconds=1)
except TypeError:                                    # versions without an attempt budget
    a = api.ConversationAPI(runtime, dialogue_model=Dies(runtime.catalog))
token = sys.argv[4]
a.handle("POST", api.PREFIX + "turn", {"Authorization": ["Bearer " + token], "Content-Type": ["application/json"]},
         json.dumps({"conversation_id": sys.argv[5], "client_turn_key": "t", "text": "Diagnostique le nas."}).encode())
"""


def killed_during_model_call(tmp):
    b = Bench(tmp)
    o = b.conversation()
    b.stop()
    calls = os.path.join(tmp, "calls.txt")
    p = subprocess.run([sys.executable, "-c", KILLED, SRC, b.state, calls, b.keys["pc-a"], o["conversation_id"]],
                       env=ENV, capture_output=True, text=True, timeout=60)
    b.start()
    turn = {"conversation_id": o["conversation_id"], "client_turn_key": "t", "text": "Diagnostique le nas."}
    right_after = b.post("turn", turn)[1]               # the dead attempt's deadline (1 s + 5 s margin) not yet over
    import time
    time.sleep(6.5)
    later = b.post("turn", turn)[1]
    b.stop()
    first_process_calls = len(open(calls).read().splitlines()) if os.path.exists(calls) else 0
    state = lambda v: "pending" if v.get("pending") else (v.get("reply") or {}).get("core_note") or (v.get("reply") or {}).get("kind")
    return {"killed_exit": p.returncode, "first_process_model_calls": first_process_calls,
            "right_after_restart": state(right_after), "after_deadline": state(later),
            "model_calls_after_restart": b.model.calls, "held": b.model.calls == 0}


def main():
    report = [scenario(name, fn) for name, fn in (
        ("double clic, même clé (5 envois simultanés)", double_click_same_key),
        ("double clic, nouvelle clé à chaque clic", double_click_new_keys),
        ("deux clients concurrents", two_clients),
        ("réponse de tour perdue puis renvoi", lost_turn_response_then_resend),
        ("même tour envoyé deux fois en même temps", same_turn_at_once),
        ("redémarrage du serveur : reçus retrouvables", restart_keeps_receipts),
        ("proposition modifiée : ancien accord réutilisé", modified_proposal_old_agreement),
        ("processus tué pendant l'appel modèle, puis renvoi", killed_during_model_call))]
    print(json.dumps({"source": SRC, "held": sum(1 for r in report if r.get("held")), "total": len(report),
                      "scenarios": report}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
