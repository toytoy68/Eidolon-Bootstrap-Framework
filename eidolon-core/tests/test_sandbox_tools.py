# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : tests/test_sandbox_tools.py
# Description : Real OS isolation, Core receipts and Darme delivery
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
from datetime import datetime, timezone, timedelta
import hashlib
import http.server
import json
import os
from pathlib import Path
import subprocess
import threading
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
from eidolon_core import sandbox_tools as sandbox
from eidolon_core.contracts import reference
from eidolon_core.memory import DEMO_REQUEST, SyntheticMemory
from eidolon_core.runtime import Runtime
from eidolon_core.store import Store
from eidolon_core.worker import attempt_receipt_path

real = pytest.mark.skipif(os.environ.get("EIDOLON_SANDBOX_INTEGRATION")!="1",
                         reason="explicit Linux bubblewrap integration")


class DeniedModel:
    model_id="synthetic-denied/1"
    def propose(self,request,context):
        return json.dumps({"version":1,"steps":[{"id":"blocked","tool":"network.upload",
            "parameters":{"data":"PRIVATE_SENTINEL"}}]})


def test_budget_is_checked_before_launch(monkeypatch):
    context=SyntheticMemory().recall(DEMO_REQUEST)
    context["items"][0]["content"]="é"*32769
    monkeypatch.setattr(subprocess,"run",lambda *a,**kw:pytest.fail("must not launch"))
    with pytest.raises(ValueError,match="budget"):
        sandbox.execute({"reference":reference(context["items"][0])},context)


def test_missing_sandbox_has_no_fallback(monkeypatch):
    context=SyntheticMemory().recall(DEMO_REQUEST)
    monkeypatch.setattr(sandbox,"BWRAP","/nonexistent/eidolon-bwrap")
    with pytest.raises(RuntimeError,match="no unisolated fallback"):
        sandbox.execute({"reference":reference(context["items"][0])},context)


@real
def test_real_runtime_saves_verified_worker_receipt(tmp_path):
    store=Store(tmp_path/"core")
    runtime=Runtime(store,registry=sandbox.sandbox_registry())
    mission=runtime.run(runtime.create(DEMO_REQUEST)["id"])
    assert mission["status"]=="SUCCEEDED",mission.get("error")
    call=mission["calls"][0]
    receipt=attempt_receipt_path(store.worker_lease_path(mission["id"],call["id"],call["attempt"]))
    assert json.loads(receipt.read_text())=={"ok":True,"value":call["output"]}
    assert call["status"]=="VERIFIED"
    assert Runtime(store,registry=sandbox.sandbox_registry()).run(mission["id"])["calls"]==mission["calls"]


@real
def test_interrupted_after_return_keeps_receipt_and_never_reexecutes(tmp_path):
    class Stop(BaseException): pass
    def checkpoint(phase):
        if phase=="TOOL_RETURNED":raise Stop()
    store=Store(tmp_path/"core")
    runtime=Runtime(store,registry=sandbox.sandbox_registry(),checkpoint=checkpoint)
    identity=runtime.create(DEMO_REQUEST)["id"]
    with pytest.raises(Stop):runtime.run(identity)
    before=store.get(identity);call=before["calls"][0]
    receipt=attempt_receipt_path(store.worker_lease_path(identity,call["id"],call["attempt"]))
    old=receipt.read_bytes()
    resumed=Runtime(store,registry=sandbox.sandbox_registry()).run(identity)
    assert resumed["status"]=="REVIEW_REQUIRED"
    assert resumed["error"]["code"]=="UNKNOWN_EFFECT"
    assert receipt.read_bytes()==old
    assert resumed["calls"][0]["attempt"]==1


@pytest.mark.parametrize("crash_after_feed_unlink",[False,True])
def test_denial_to_signed_darme_receipt(tmp_path,monkeypatch,crash_after_feed_unlink):
    from eidolon_core.darme_core_outbox import export_once,acknowledge
    from eidolon_core.darme_core_receiver import CoreFeedReceiver
    from eidolon_core.darme_core_receipt import sign_receipt
    from eidolon_core.darme_core_feed import canonical
    from eidolon_core.darme_store import DarmeJournal
    store=Store(tmp_path/"core")
    runtime=Runtime(store,model=DeniedModel(),registry=sandbox.sandbox_registry())
    mission=runtime.run(runtime.create(DEMO_REQUEST)["id"])
    assert mission["status"]=="BLOCKED" and mission["calls"]==[]
    sender,receiver=Ed25519PrivateKey.generate(),Ed25519PrivateKey.generate()
    pub=lambda k:k.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)
    feed,state=tmp_path/"feed.json",tmp_path/"sender.json"
    assert export_once(store.path,state,feed,sender)==1
    assert b"PRIVATE_SENTINEL" not in feed.read_bytes()
    journal=DarmeJournal(tmp_path/"darme.sqlite")
    try:
        target=CoreFeedReceiver(pub(sender),tmp_path/"receiver.json",journal)
        assert target.accept(feed.read_bytes())==1
        # Restart before acknowledgement: same event, no duplicate.
        later=lambda:datetime.now(timezone.utc)+timedelta(hours=1)
        target=CoreFeedReceiver(pub(sender),tmp_path/"receiver.json",journal,now=later)
        assert target.accept(feed.read_bytes())==0
        fresh=CoreFeedReceiver(pub(sender),tmp_path/"unseen.json",journal,now=later)
        with pytest.raises(ValueError,match="stale feed"):
            fresh.accept(feed.read_bytes())
        payload=json.loads(feed.read_bytes())["payload"]
        digest=hashlib.sha256(canonical(payload)).hexdigest()
        receipt=sign_receipt(receiver,payload["sequence"],digest)
        if crash_after_feed_unlink:
            original=Path.unlink
            def interrupt(path,*a,**kw):
                if path==feed.with_suffix(".pending"):raise OSError("synthetic crash")
                return original(path,*a,**kw)
            with monkeypatch.context() as patch:
                patch.setattr(Path,"unlink",interrupt)
                with pytest.raises(OSError,match="synthetic crash"):
                    acknowledge(feed,state,feed.with_suffix(".pending"),receipt,pub(receiver))
            assert not feed.exists() and feed.with_suffix(".pending").exists()
        else:
            acknowledge(feed,state,feed.with_suffix(".pending"),receipt,pub(receiver))
        assert export_once(store.path,state,feed,sender)==0
        assert journal.db.execute("SELECT count(*) FROM events").fetchone()[0]==1
    finally:journal.close()


@real
def test_same_os_boundary_blocks_private_files_post_put_dns(tmp_path):
    secret=tmp_path/"synthetic-private";secret.write_text("SYNTHETIC")
    received=[]
    class Sink(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            received.append(self.path);self.send_response(200);self.end_headers()
        do_PUT=do_POST
        def log_message(self,*a):pass
    server=http.server.HTTPServer(("127.0.0.1",0),Sink)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    program="""import json,pathlib,socket,urllib.request
r={"private_visible":pathlib.Path(SECRET).exists()}
pathlib.Path("/tmp/allowed").write_text("synthetic")
r["temp_write"]=pathlib.Path("/tmp/allowed").read_text()=="synthetic"
for method in ["POST","PUT"]:
 try:
  urllib.request.urlopen(urllib.request.Request(URL,data=b"SYNTHETIC",method=method),timeout=1)
  r[method]="escaped"
 except Exception:r[method]="blocked"
try:socket.getaddrinfo("synthetic.invalid",80);r["DNS"]="escaped"
except Exception:r["DNS"]="blocked"
r["cap"]=[s for s in pathlib.Path("/proc/self/status").read_text().splitlines() if s.startswith("CapEff:")][0].split()[1]
print(json.dumps(r))
""".replace("SECRET",repr(str(secret))).replace("URL",repr("http://127.0.0.1:"+str(server.server_port)+"/sink"))
    try:
        result=subprocess.run(sandbox._command(program),capture_output=True,timeout=10)
        assert result.returncode==0,result.stderr
        observed=json.loads(result.stdout)
        assert observed==dict(private_visible=False,temp_write=True,POST="blocked",PUT="blocked",DNS="blocked",cap="0000000000000000")
        assert received==[]
    finally:server.shutdown();thread.join();server.server_close()


@real
def test_independent_worker_refuses_unknown_action():
    result=subprocess.run(sandbox._command(sandbox._PROGRAM),
        input=b'{"tool":"shell.execute","text":"echo forbidden"}',
        capture_output=True,timeout=10)
    assert result.returncode!=0 and result.stdout==b""


@real
def test_model_text_is_data_only():
    context=SyntheticMemory().recall(DEMO_REQUEST)
    text="__import__('os').system('curl https://synthetic.invalid'); $HOME; $(id)"
    context["items"][0]["content"]=text
    value=sandbox.execute({"reference":reference(context["items"][0])},context)
    assert value["sha256"]==hashlib.sha256(text.encode()).hexdigest()
