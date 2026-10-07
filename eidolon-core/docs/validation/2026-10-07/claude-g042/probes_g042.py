# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : probes_g042.py
# Description : Contre-revue de la consultation des reçus C-009b sur cible figée (C-TASK-G042)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""PYTHONPATH=<frozen 37dc199>/eidolon-core/src python3 probes_g042.py
Synthetic states only, in temporary folders. Each alteration is applied to a fresh COPY of the
state with sqlite3, then read through receipt_lookup.lookup (and HTTP for the boundary cases)."""
import json
from pathlib import Path
import secrets
import shutil
import sqlite3
import tempfile
import threading
import time
import http.client

from eidolon_core.actions import ActionRuntime
from eidolon_core.client_sync import ClientSync
from eidolon_core.commands import CancelCommands, DecisionCommands
from eidolon_core.http_api import ReadOnlyStore, ReadServer
from eidolon_core.memory import DEMO_REQUEST
from eidolon_core.receipt_lookup import ReceiptLookupError, lookup
from eidolon_core.runtime import Runtime
from eidolon_core.store import Store

ACTOR, REASON = "Opérateur-secret-G042", "Motif privé G042 à ne jamais exporter"


def build(directory):
    store = Store(directory)
    runtime, actions = Runtime(store), ActionRuntime(store)
    m_req = runtime.create(DEMO_REQUEST)
    store_id = ClientSync(store).snapshot(m_req["id"])["store_id"]
    q = {}

    def cancel(key, mission_id):
        command = dict(protocol="eidolon-cancel-command/1", store_id=store_id, client_id="g042", command_key=key,
                       mission_id=mission_id, actor=ACTOR, reason=REASON)
        CancelCommands(store).submit(command)
        q[key] = {k: command[k] for k in ("store_id", "client_id", "command_key", "mission_id")}

    cancel("cancel-requested", m_req["id"])
    cancel("cancel-again", m_req["id"])                       # ALREADY_REQUESTED
    m_term = runtime.cancel(runtime.create(DEMO_REQUEST)["id"])
    cancel("cancel-terminal", m_term["id"])                    # ALREADY_TERMINAL
    m_dec = actions.run(actions.create_restart("nas")["id"])
    for decision in ("approve", "revoke"):
        cur = store.get(m_dec["id"])
        command = dict(protocol="eidolon-decision-command/1", store_id=store_id, client_id="g042",
                       command_key="decision-" + decision, mission_id=cur["id"], expected_revision=cur["revision"],
                       proposal_sha256=cur["proposal"]["sha256"], decision=decision, actor=ACTOR, reason=REASON)
        DecisionCommands(actions).submit(command)
        q["decision-" + decision] = {k: command[k] for k in ("store_id", "client_id", "command_key", "mission_id")}
    return q


def ask(directory, query):
    try:
        r = lookup(ReadOnlyStore(directory), query)
        return r["status"], r
    except ReceiptLookupError as exc:
        return f"{exc.status} {exc.code}", None


def altered(base, root, name, sql_fn):
    target = Path(root) / name
    shutil.copytree(base, target)
    db = sqlite3.connect(target / "missions.sqlite3")
    sql_fn(db)
    db.commit()
    db.close()
    return target


def body_edit(key, fn):
    def run(db):
        raw = db.execute("SELECT body FROM command_receipts WHERE command_key=?", (key,)).fetchone()[0]
        value = json.loads(raw)
        fn(value)
        db.execute("UPDATE command_receipts SET body=? WHERE command_key=?", (json.dumps(value, separators=(",", ":")), key))
    return run


def event_edit(key, fn):
    def run(db):
        seq = json.loads(db.execute("SELECT body FROM command_receipts WHERE command_key=?", (key,)).fetchone()[0])["event_sequence"]
        fn(db, seq)
    return run


def main():
    with tempfile.TemporaryDirectory(prefix="eidolon-g042-") as root:
        base = Path(root) / "base"
        q = build(base)
        print("== A. reçus authentiques")
        for key in q:
            status, r = ask(base, q[key])
            rec = r["receipt"] if r else {}
            print(f"A {key}: {status} {rec.get('protocol')} {rec.get('decision') or rec.get('cancel_outcome')} "
                  f"{rec.get('approval_status_at_recording') or rec.get('mission_status_at_recording')}")
        print("== B. données privées")
        blob = json.dumps([ask(base, q[k])[1] for k in q], ensure_ascii=False)
        print(f"B actor dans les réponses : {'PRÉSENT' if ACTOR in blob else 'absent'} ; reason : {'PRÉSENT' if REASON in blob else 'absent'}")
        print("== C. altérations isolées (une ligne) et cohérentes (plusieurs lignes)")
        cases = [
            ("C1 décision : approval_status_at_recording APPROVED→REVOKED", "decision-approve",
             body_edit("decision-approve", lambda v: v.update(approval_status_at_recording="REVOKED"))),
            ("C2 décision : decision approve→reject (statut assorti)", "decision-approve",
             body_edit("decision-approve", lambda v: v.update(decision="reject", approval_status_at_recording="REJECTED"))),
            ("C3 décision : recorded_at modifié", "decision-approve",
             body_edit("decision-approve", lambda v: v.update(recorded_at="2026-01-01T00:00:00+00:00"))),
            ("C4 décision : mission_revision +1", "decision-approve",
             body_edit("decision-approve", lambda v: v.update(mission_revision=v["mission_revision"] + 1))),
            ("C5 annulation : mission_status_at_recording NEW→RUNNING", "cancel-requested",
             body_edit("cancel-requested", lambda v: v.update(mission_status_at_recording="RUNNING"))),
            ("C6 annulation : mission_revision +5", "cancel-requested",
             body_edit("cancel-requested", lambda v: v.update(mission_revision=v["mission_revision"] + 5))),
            ("C7 annulation ALREADY_TERMINAL : cancel_requested_at_recording inversé", "cancel-terminal",
             body_edit("cancel-terminal", lambda v: v.update(cancel_requested_at_recording=not v["cancel_requested_at_recording"]))),
            ("C8 annulation ALREADY_TERMINAL : mission_status CANCELLED→SUCCEEDED", "cancel-terminal",
             body_edit("cancel-terminal", lambda v: v.update(mission_status_at_recording="SUCCEEDED"))),
            ("C9 événement : actor modifié", "decision-approve",
             event_edit("decision-approve", lambda db, s: db.execute(
                 "UPDATE events SET detail=json_set(detail,'$.actor','autre') WHERE sequence=?", (s,)))),
            ("C10 événement : kind modifié", "cancel-requested",
             event_edit("cancel-requested", lambda db, s: db.execute("UPDATE events SET kind='CANCELLED' WHERE sequence=?", (s,)))),
            ("C11 événement supprimé", "cancel-requested",
             event_edit("cancel-requested", lambda db, s: db.execute("DELETE FROM events WHERE sequence=?", (s,)))),
            ("C12 corps > 32 768 octets", "cancel-requested",
             lambda db: db.execute("UPDATE command_receipts SET body=body||? WHERE command_key='cancel-requested'", (" " * 40000,))),
            ("C13 clé JSON dupliquée", "cancel-requested",
             lambda db: db.execute("UPDATE command_receipts SET body=replace(body,'{\"','{\"status\":\"RECORDED\",\"') WHERE command_key='cancel-requested'")),
            ("C14 corps d'un autre reçu sous cette clé", "cancel-requested",
             lambda db: db.execute("UPDATE command_receipts SET body=(SELECT body FROM command_receipts WHERE command_key='cancel-again') "
                                   "WHERE command_key='cancel-requested'")),
            ("C15 store_id de la base modifié", "cancel-requested",
             lambda db: db.execute("UPDATE sync_metadata SET value='s-" + "0" * 32 + "' WHERE key='store_id'")),
            ("C16 COHÉRENT : recorded_at changé dans le reçu ET l'événement", "decision-approve",
             lambda db: (body_edit("decision-approve", lambda v: v.update(recorded_at="2026-01-01T00:00:00+00:00"))(db),
                         event_edit("decision-approve", lambda d, s: d.execute(
                             "UPDATE events SET at='2026-01-01T00:00:00+00:00' WHERE sequence=?", (s,)))(db))),
        ]
        for i, (label, key, fn) in enumerate(cases):
            status, r = ask(altered(base, root, f"c{i}", fn), q[key])
            shown = ""
            if r and r["receipt"]:
                rec = r["receipt"]
                shown = " → exporté : " + json.dumps({k: rec[k] for k in ("mission_status_at_recording", "mission_revision",
                    "cancel_requested_at_recording", "recorded_at", "approval_status_at_recording") if k in rec}, ensure_ascii=False)
            print(f"{label}: {status}{shown}")
        print("== D. absence ambiguë et concurrence")
        fresh = dict(q["cancel-requested"], command_key="cancel-late")
        print(f"D1 avant la commande : {ask(base, fresh)[0]}")
        CancelCommands(Store(base)).submit(dict(protocol="eidolon-cancel-command/1", **fresh, actor=ACTOR, reason=REASON))
        print(f"D1 après la commande (même clé) : {ask(base, fresh)[0]}  — NOT_FOUND puis FOUND sans aucun renvoi")
        token = secrets.token_urlsafe(32)
        server = ReadServer(base, token, port=0)
        threading.Thread(target=server.serve_forever, daemon=True).start()

        def http_lookup(body):
            c = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=10)
            t0 = time.perf_counter()
            c.request("POST", "/v1/command-receipt", body=json.dumps(body), headers={"Authorization": "Bearer " + token,
                                                                                     "Content-Type": "application/json"})
            resp = c.getresponse()
            raw = resp.read()
            c.close()
            return resp.status, raw, round((time.perf_counter() - t0) * 1000)
        for hold in (0.5, 3.0):
            db = sqlite3.connect(base / "missions.sqlite3", isolation_level=None, check_same_thread=False)
            db.execute("BEGIN EXCLUSIVE")
            timer = threading.Timer(hold, lambda d=db: (d.execute("ROLLBACK"), d.close()))
            timer.start()
            st, raw, ms = http_lookup(q["decision-approve"])
            timer.join()
            print(f"D2 verrou d'écriture {hold} s : HTTP {st} {json.loads(raw).get('status') or json.loads(raw).get('error')} en {ms} ms")
        print("== E. frontière HTTP")
        for label, body in (("champ en plus", dict(q["decision-approve"], extra=1)),
                            ("mission différente", dict(q["decision-approve"], mission_id=q["cancel-requested"]["mission_id"])),
                            ("autre store", dict(q["decision-approve"], store_id="s-" + "1" * 32)),
                            ("clé avec espace", dict(q["decision-approve"], command_key="a b"))):
            st, raw, _ = http_lookup(body)
            leaked = any(x in raw.decode() for x in ("proposal_sha256", "request_sha256", ACTOR, REASON))
            print(f"E {label}: HTTP {st} {json.loads(raw).get('error')} ; données du reçu dans l'erreur : {'OUI' if leaked else 'non'}")
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
