# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : probes_g048.py
# Description : Contre-revue de la liaison reçu/événement C-012 sur cible figée (C-TASK-G048)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""python3 probes_g048.py <frozen 0fdf18e>/eidolon-core/src <frozen b5f0093>/eidolon-core/src

Synthetic states only, in temporary folders. Each alteration is applied to a fresh COPY of the
state with sqlite3, then read through receipt_lookup.lookup (and once over loopback HTTP).
The old source (before C-012) builds a legacy state in a subprocess; nothing is migrated."""
import hashlib
import http.client
import json
import os
from pathlib import Path
import secrets
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import threading

NEW_SRC, OLD_SRC = (str(Path(p).resolve()) for p in sys.argv[1:3])
sys.path.insert(0, NEW_SRC)

from eidolon_core.contracts import digest  # noqa: E402
from eidolon_core.http_api import ReadOnlyStore, ReadServer  # noqa: E402
from eidolon_core.receipt_lookup import ReceiptLookupError, lookup  # noqa: E402

ACTOR, REASON = "Opérateur-secret-G048", "Motif privé G048 à ne jamais exporter"
KEYS = ("cancel-requested", "cancel-again", "cancel-terminal", "decision-approve", "decision-revoke")

# Runs in a subprocess with PYTHONPATH=<src>; prints the lookup queries as JSON.
BUILD = r"""
import json, sys
from eidolon_core.actions import ActionRuntime
from eidolon_core.client_sync import ClientSync
from eidolon_core.commands import CancelCommands, DecisionCommands
from eidolon_core.memory import DEMO_REQUEST
from eidolon_core.runtime import Runtime
from eidolon_core.store import Store
ACTOR, REASON = sys.argv[2], sys.argv[3]
store = Store(sys.argv[1])
runtime, actions = Runtime(store), ActionRuntime(store)
m_req = runtime.create(DEMO_REQUEST)
store_id = ClientSync(store).snapshot(m_req["id"])["store_id"]
q = {}
def cancel(key, mission_id):
    command = dict(protocol="eidolon-cancel-command/1", store_id=store_id, client_id="g048", command_key=key,
                   mission_id=mission_id, actor=ACTOR, reason=REASON)
    CancelCommands(store).submit(command)
    q[key] = {k: command[k] for k in ("store_id", "client_id", "command_key", "mission_id")}
cancel("cancel-requested", m_req["id"])
cancel("cancel-again", m_req["id"])
m_term = runtime.cancel(runtime.create(DEMO_REQUEST)["id"])
cancel("cancel-terminal", m_term["id"])
m_dec = actions.run(actions.create_restart("nas")["id"])
for decision in ("approve", "revoke"):
    cur = store.get(m_dec["id"])
    command = dict(protocol="eidolon-decision-command/1", store_id=store_id, client_id="g048",
                   command_key="decision-" + decision, mission_id=cur["id"], expected_revision=cur["revision"],
                   proposal_sha256=cur["proposal"]["sha256"], decision=decision, actor=ACTOR, reason=REASON)
    DecisionCommands(actions).submit(command)
    q["decision-" + decision] = {k: command[k] for k in ("store_id", "client_id", "command_key", "mission_id")}
print(json.dumps(q))
"""

# Submits one cancel command; a SQL function registered on every Store connection
# kills the process (os._exit) when a trigger installed in the copy calls it.
SUBMIT = r"""
import json, os, sqlite3, sys
import eidolon_core.store as store_mod
from eidolon_core.commands import CancelCommands
from eidolon_core.store import Store
real = sqlite3.connect
def connect(*a, **k):
    db = real(*a, **k)
    db.create_function("g048_crash", 0, lambda: os._exit(9))
    return db
store_mod.sqlite3.connect = connect
command = json.loads(sys.argv[2])
try:
    print(json.dumps(CancelCommands(Store(sys.argv[1])).submit(command)))
except Exception as exc:
    print("ERROR", type(exc).__name__, exc)
"""


def run(src, code, *args):
    env = dict(os.environ, PYTHONPATH=src, PYTHONDONTWRITEBYTECODE="1")
    return subprocess.run([sys.executable, "-c", code, *args], env=env, capture_output=True, text=True, timeout=120)


def build(src, directory):
    proc = run(src, BUILD, str(directory), ACTOR, REASON)
    if proc.returncode:
        raise SystemExit(proc.stderr)
    return json.loads(proc.stdout)


def ask(directory, query):
    try:
        r = lookup(ReadOnlyStore(directory), query)
        return r["status"], r
    except ReceiptLookupError as exc:
        return f"{exc.status} {exc.code}", None


def label(status, r):
    if r and r["receipt"]:
        return f"{status} binding={r.get('receipt_binding', '(absent)')}"
    return status


def copy(base, root, name, sql_fn=None):
    target = Path(root) / name
    shutil.copytree(base, target)
    if sql_fn:
        db = sqlite3.connect(target / "missions.sqlite3")
        sql_fn(db)
        db.commit()
        db.close()
    return target


def body_edit(key, fn):
    def apply(db):
        raw = db.execute("SELECT body FROM command_receipts WHERE command_key=?", (key,)).fetchone()[0]
        value = json.loads(raw)
        fn(value)
        db.execute("UPDATE command_receipts SET body=? WHERE command_key=?",
                   (json.dumps(value, separators=(",", ":"), ensure_ascii=False), key))
    return apply


def event_detail_edit(key, fn):
    def apply(db):
        seq = json.loads(db.execute("SELECT body FROM command_receipts WHERE command_key=?", (key,)).fetchone()[0])["event_sequence"]
        raw = db.execute("SELECT detail FROM events WHERE sequence=?", (seq,)).fetchone()[0]
        db.execute("UPDATE events SET detail=? WHERE sequence=?", (fn(raw), seq))
    return apply


def json_fn(fn):
    def edit(raw):
        value = json.loads(raw)
        fn(value)
        return json.dumps(value, separators=(",", ":"), ensure_ascii=False)
    return edit


def drop_hash(value):
    value.pop("receipt_sha256", None)


def both(*fns):
    return lambda db: [fn(db) for fn in fns]


def rehash(key):
    """Coherent rewrite: recompute the event hash from the (altered) receipt body."""
    def apply(db):
        body = json.loads(db.execute("SELECT body FROM command_receipts WHERE command_key=?", (key,)).fetchone()[0])
        event_detail_edit(key, json_fn(lambda v: v.update(receipt_sha256=digest(body))))(db)
    return apply


def state_digest(directory):
    db = sqlite3.connect(Path(directory) / "missions.sqlite3")
    rows = {t: db.execute(f"SELECT * FROM {t} ORDER BY rowid").fetchall() for t in ("events", "command_receipts", "missions")}
    db.close()
    return hashlib.sha256(repr(rows).encode()).hexdigest()[:16], {t: len(v) for t, v in rows.items()}


def exported(r):
    rec = r["receipt"]
    return json.dumps({k: rec[k] for k in ("mission_status_at_recording", "mission_revision", "cancel_requested_at_recording",
                                          "approval_status_at_recording", "decision", "recorded_at") if k in rec},
                      ensure_ascii=False)


ALTERATIONS = [
    ("C5 annulation : mission_status_at_recording NEW→RUNNING", "cancel-requested",
     lambda v: v.update(mission_status_at_recording="RUNNING")),
    ("C6 annulation : mission_revision +5", "cancel-requested",
     lambda v: v.update(mission_revision=v["mission_revision"] + 5)),
    ("C7 ALREADY_TERMINAL : cancel_requested_at_recording inversé", "cancel-terminal",
     lambda v: v.update(cancel_requested_at_recording=not v["cancel_requested_at_recording"])),
    ("C8 ALREADY_TERMINAL : CANCELLED→SUCCEEDED", "cancel-terminal",
     lambda v: v.update(mission_status_at_recording="SUCCEEDED")),
    ("C1 décision : APPROVED→REVOKED", "decision-approve",
     lambda v: v.update(approval_status_at_recording="REVOKED")),
    ("C4 décision : mission_revision +1", "decision-approve",
     lambda v: v.update(mission_revision=v["mission_revision"] + 1)),
]


def main():
    with tempfile.TemporaryDirectory(prefix="eidolon-g048-") as root:
        base = Path(root) / "base"
        q = build(NEW_SRC, base)

        print("== A. reçus authentiques (source 0fdf18e)")
        for key in KEYS:
            print(f"A {key}: {label(*ask(base, q[key]))}")
        blob = json.dumps([ask(base, q[k])[1] for k in KEYS], ensure_ascii=False)
        print(f"A actor/reason/receipt_sha256 de l'événement dans les réponses : "
              f"{'PRÉSENT' if ACTOR in blob or REASON in blob else 'absents'}")

        print("== B. altérations isolées du reçu (G042 C1-C8), hash présent")
        for i, (name, key, fn) in enumerate(ALTERATIONS):
            print(f"B {name}: {label(*ask(copy(base, root, f'b{i}', body_edit(key, fn)), q[key]))}")

        print("== C. hash présent mais invalide (reçu intact)")
        invalid = [("majuscules", lambda v: v.update(receipt_sha256=v["receipt_sha256"].upper())),
                   ("tronqué à 63", lambda v: v.update(receipt_sha256=v["receipt_sha256"][:63])),
                   ("non hexadécimal", lambda v: v.update(receipt_sha256="z" * 64)),
                   ("hash d'un autre reçu", None),
                   ("nombre", lambda v: v.update(receipt_sha256=123)),
                   ("null", lambda v: v.update(receipt_sha256=None)),
                   ("chaîne vide", lambda v: v.update(receipt_sha256="")),
                   ("objet", lambda v: v.update(receipt_sha256={"sha256": v["receipt_sha256"]})),
                   ("espace final", lambda v: v.update(receipt_sha256=v["receipt_sha256"] + " "))]
        other = json.loads(sqlite3.connect(base / "missions.sqlite3").execute(
            "SELECT body FROM command_receipts WHERE command_key='cancel-again'").fetchone()[0])
        for i, (name, fn) in enumerate(invalid):
            fn = fn or (lambda v: v.update(receipt_sha256=digest(other)))
            d = copy(base, root, f"c{i}", event_detail_edit("cancel-requested", json_fn(fn)))
            print(f"C {name}: {label(*ask(d, q['cancel-requested']))}")
        # Duplicate JSON key in the event detail: valid hash then invalid, and the reverse.
        good = digest(json.loads(sqlite3.connect(base / "missions.sqlite3").execute(
            "SELECT body FROM command_receipts WHERE command_key='cancel-requested'").fetchone()[0]))
        for i, pair in enumerate(((good, "0" * 64), ("0" * 64, good))):
            def dup(raw, pair=pair):
                value = json.loads(raw)
                value.pop("receipt_sha256")
                inner = json.dumps(value, separators=(",", ":"), ensure_ascii=False)[1:-1]
                return '{"receipt_sha256":"%s","receipt_sha256":"%s",%s}' % (pair[0], pair[1], inner)
            d = copy(base, root, f"cdup{i}", event_detail_edit("cancel-requested", dup))
            print(f"C clé receipt_sha256 dupliquée ({'valide puis fausse' if i == 0 else 'fausse puis valide'}): "
                  f"{label(*ask(d, q['cancel-requested']))}")

        print("== D. hash absent : ancien format et rétrogradation")
        for key in ("cancel-requested", "decision-approve"):
            d = copy(base, root, f"d-{key}", event_detail_edit(key, json_fn(drop_hash)))
            print(f"D hash retiré seul, {key}: {label(*ask(d, q[key]))}")
        for i, (name, key, fn) in enumerate(ALTERATIONS):
            d = copy(base, root, f"dd{i}", both(body_edit(key, fn), event_detail_edit(key, json_fn(drop_hash))))
            status, r = ask(d, q[key])
            print(f"D hash retiré + {name}: {label(status, r)}" + (f" → exporté : {exported(r)}" if r else ""))

        print("== E. réécriture cohérente reçu + hash (hors détection annoncée)")
        for i, (name, key, fn) in enumerate(ALTERATIONS[:4]):
            d = copy(base, root, f"e{i}", both(body_edit(key, fn), rehash(key)))
            status, r = ask(d, q[key])
            print(f"E {name} + hash recalculé: {label(status, r)}" + (f" → exporté : {exported(r)}" if r else ""))

        print("== F. ancien état (source b5f0093, avant C-012) lu par 0fdf18e : non-migration")
        legacy = Path(root) / "legacy"
        ql = build(OLD_SRC, legacy)
        before = state_digest(legacy)
        print(f"F hash dans les événements de l'ancien état : "
              f"{sqlite3.connect(legacy / 'missions.sqlite3').execute(chr(32).join(('SELECT count(*) FROM events', 'WHERE detail LIKE', chr(39) + '%receipt_sha256%' + chr(39)))).fetchone()[0]}")
        for key in KEYS:
            print(f"F {key}: {label(*ask(legacy, ql[key]))}")
        print(f"F état inchangé après lectures : {state_digest(legacy) == before}")
        # A new command written by the new source into the old state.
        cmd = dict(protocol="eidolon-cancel-command/1", **dict(ql["cancel-requested"], command_key="after-upgrade"),
                   actor=ACTOR, reason=REASON)
        proc = run(NEW_SRC, SUBMIT, str(legacy), json.dumps(cmd))
        after = state_digest(legacy)
        print(f"F nouvelle commande par 0fdf18e : {proc.stdout.strip()[:60]}… ; lignes {before[1]} → {after[1]}")
        db = sqlite3.connect(legacy / "missions.sqlite3")
        old_rows_same = db.execute("SELECT count(*) FROM events WHERE detail LIKE '%receipt_sha256%'").fetchone()[0]
        db.close()
        print(f"F événements avec hash ensuite : {old_rows_same} (seulement le nouveau) ; "
              f"nouveau reçu : {label(*ask(legacy, ql['cancel-requested'] | {'command_key': 'after-upgrade'}))} ; "
              f"ancien : {label(*ask(legacy, ql['cancel-requested']))}")
        for i, (name, key, fn) in enumerate(ALTERATIONS[:4]):
            d = copy(legacy, root, f"f{i}", body_edit(key, fn))
            status, r = ask(d, ql[key])
            print(f"F ancien reçu + {name}: {label(status, r)}" + (f" → exporté : {exported(r)}" if r else ""))

        print("== G. transaction : panne pendant l'écriture (processus tué par os._exit)")
        points = [
            ("après la mise à jour du hash, avant l'insertion du reçu",
             "CREATE TRIGGER g048 AFTER UPDATE ON events WHEN json_extract(NEW.detail,'$.receipt_sha256') IS NOT NULL "
             "BEGIN SELECT g048_crash(); END"),
            ("après l'insertion du reçu, avant le commit",
             "CREATE TRIGGER g048 AFTER INSERT ON command_receipts BEGIN SELECT g048_crash(); END"),
            ("refus SQL à l'insertion du reçu (sans tuer)",
             "CREATE TRIGGER g048 BEFORE INSERT ON command_receipts BEGIN SELECT RAISE(ABORT,'g048'); END"),
        ]
        for i, (name, ddl) in enumerate(points):
            d = copy(base, root, f"g{i}", lambda db, ddl=ddl: db.execute(ddl))
            before = state_digest(d)
            cmd = dict(protocol="eidolon-cancel-command/1", **dict(q["cancel-requested"], command_key=f"crash-{i}"),
                       actor=ACTOR, reason=REASON)
            proc = run(NEW_SRC, SUBMIT, str(d), json.dumps(cmd))
            sqlite3.connect(d / "missions.sqlite3").execute("DROP TRIGGER g048").connection.commit()
            after = state_digest(d)
            query = dict(q["cancel-requested"], command_key=f"crash-{i}")
            print(f"G {name}: code {proc.returncode} {proc.stdout.strip()[:40]!r} ; état identique : {before == after} ; "
                  f"consultation : {label(*ask(d, query))}")
            again = run(NEW_SRC, SUBMIT, str(d), json.dumps(cmd))
            print(f"G   même clé renvoyée ensuite : code {again.returncode} ; consultation : {label(*ask(d, query))}")

        print("== H. doublons de clé")
        d = copy(base, root, "h")
        before = state_digest(d)
        cmd = dict(protocol="eidolon-cancel-command/1", **q["cancel-requested"], actor=ACTOR, reason=REASON)
        proc = run(NEW_SRC, SUBMIT, str(d), json.dumps(cmd))
        print(f"H même clé, même contenu : {proc.stdout.strip()[:48]}… ; état identique : {state_digest(d) == before} ; "
              f"{label(*ask(d, q['cancel-requested']))}")
        proc = run(NEW_SRC, SUBMIT, str(d), json.dumps(dict(cmd, reason="autre motif")))
        print(f"H même clé, autre contenu : {proc.stdout.strip()[:60]} ; état identique : {state_digest(d) == before}")
        par = dict(cmd, command_key="parallel")
        procs = [subprocess.Popen([sys.executable, "-c", SUBMIT, str(d), json.dumps(par)], text=True,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  env=dict(os.environ, PYTHONPATH=NEW_SRC, PYTHONDONTWRITEBYTECODE="1")) for _ in range(4)]
        outs = [p.communicate(timeout=120)[0].strip() for p in procs]
        db = sqlite3.connect(d / "missions.sqlite3")
        n_rec = db.execute("SELECT count(*) FROM command_receipts WHERE command_key='parallel'").fetchone()[0]
        seq = json.loads(db.execute("SELECT body FROM command_receipts WHERE command_key='parallel'").fetchone()[0])["event_sequence"]
        n_ev = db.execute("SELECT count(*) FROM events WHERE detail LIKE '%\"command_key\":\"parallel\"%'").fetchone()[0]
        db.close()
        kinds = sorted({o if o.startswith("ERROR") else "reçu " + json.loads(o)["recorded_at"] for o in outs})
        print(f"H 4 processus, même clé en parallèle : réponses distinctes : {kinds} ; reçus : {n_rec} ; "
              f"événements portant la clé : {n_ev} (séquence {seq}) ; {label(*ask(d, dict(q['cancel-requested'], command_key='parallel')))}")

        print("== I. frontière HTTP (loopback, jeton synthétique)")
        token = secrets.token_urlsafe(32)
        legacy_copy = copy(legacy, root, "i")
        for name, directory, query in (("nouveau", base, q["decision-approve"]), ("ancien", legacy_copy, ql["decision-approve"])):
            server = ReadServer(directory, token, port=0)
            threading.Thread(target=server.serve_forever, daemon=True).start()
            c = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=10)
            c.request("POST", "/v1/command-receipt", body=json.dumps(query),
                      headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"})
            resp = c.getresponse()
            body = json.loads(resp.read())
            c.close()
            server.shutdown()
            server.server_close()
            print(f"I {name}: HTTP {resp.status} {body.get('status')} receipt_binding={body.get('receipt_binding')} ; "
                  f"champs : {sorted(set(body) - {'receipt'})}")


if __name__ == "__main__":
    main()
