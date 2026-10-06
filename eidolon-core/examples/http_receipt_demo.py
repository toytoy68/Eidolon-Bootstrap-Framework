# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : http_receipt_demo.py
# Description : Reçu retrouvé via HTTP loopback, état entièrement synthétique
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Run from eidolon-core: PYTHONPATH=src:. python -m examples.http_receipt_demo."""
from http.client import HTTPConnection
import json
import secrets
import tempfile
import threading

from eidolon_core.client_sync import ClientSync
from eidolon_core.commands import CancelCommands
from eidolon_core.http_api import ReadServer
from eidolon_core.memory import DEMO_REQUEST
from eidolon_core.runtime import Runtime
from eidolon_core.store import Store


def demo():
    with tempfile.TemporaryDirectory(prefix="eidolon-receipt-demo-") as directory:
        store = Store(directory)
        mission = Runtime(store).create(DEMO_REQUEST)
        query = dict(store_id=ClientSync(store).snapshot(mission["id"])["store_id"],
                     client_id="demo-client", command_key="cancel-001", mission_id=mission["id"])
        token = secrets.token_urlsafe(32)
        with ReadServer(directory, token, port=0) as server:
            thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": .01})
            thread.start()

            def read_receipt():
                connection = HTTPConnection("127.0.0.1", server.server_port, timeout=5)
                try:
                    connection.request("POST", "/v1/command-receipt", body=json.dumps(query),
                                       headers={"Authorization": "Bearer " + token,
                                                "Content-Type": "application/json"})
                    response = connection.getresponse()
                    data = json.loads(response.read())
                    if response.status != 200:
                        raise RuntimeError("unexpected receipt HTTP status")
                    return data
                finally:
                    connection.close()

            try:
                absent = read_receipt()
                # A trusted local writer records a synthetic stop request. Discard
                # its response, then query through HTTP; never repeat submit.
                CancelCommands(store).submit({"protocol": "eidolon-cancel-command/1", **query,
                                               "actor": "demo", "reason": "synthetic local request"})
                before = store.path.read_bytes()
                found, repeated = read_receipt(), read_receipt()
                unchanged = before == store.path.read_bytes()
                current = store.get(mission["id"])
                checked = (absent["status"] == "NOT_FOUND" and found["status"] == "FOUND"
                           and found == repeated and unchanged and not found["authorizes_resend"]
                           and current["status"] == "NEW" and current["cancel_requested"])
                if not checked:
                    raise RuntimeError("receipt demonstration invariant failed")
                return {"synthetic": True, "transport": "HTTP_LOOPBACK", "query": query,
                        "before_recording": absent, "after_recording": found,
                        "same_receipt_on_repeat": True, "database_unchanged_by_reads": unchanged,
                        "mission_status_now": current["status"], "stop_confirmed": False,
                        "tool_executed": False, "checks_passed": checked}
            finally:
                server.shutdown()
                thread.join(5)


if __name__ == "__main__":
    print(json.dumps(demo(), ensure_ascii=False, indent=2))
