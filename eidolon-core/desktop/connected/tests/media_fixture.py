# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : media_fixture.py
# Description : Prépare côté serveur un vrai travail média lié à une conversation, pour les tests de la page (C-TASK-G101)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""python media_fixture.py <state> <client_id> <conversation_id|latest> <private work folder>

Synthetic only: a private artifact store, one attached PNG, a frozen media proposal, a media-job/1 record
whose request is that proposal's, a collection with one imported output, and the operator link. No
engine is contacted. Prints the artifact id of the output."""
import json
from pathlib import Path
import sys

from eidolon_core import conversation_media as cm
from eidolon_core.conversation_media_results import link_job
from eidolon_core.conversation_store import ConversationStore
from eidolon_core.media_agents import prepare, write_record
from eidolon_core.media_artifacts import ArtifactStore, initialize
from eidolon_core.store import Store

state, client, conversation, work = sys.argv[1], sys.argv[2], sys.argv[3], Path(sys.argv[4])
PNG = b"\x89PNG\r\n\x1a\nsynthetic page fixture"
conv = ConversationStore(Store(state))
if conversation == "latest":                                 # the conversation the page just used
    conversation = conv.recent(client, limit=1)[0]["conversation_id"]
root = work / "artifacts"
initialize(root)
artifacts = ArtifactStore(root)
source = artifacts.import_bytes(PNG, display_name="phare.png")["reference"]
conv.attach(owner_client_id=client, conversation_id=conversation, reference=source,
            verify=lambda r: cm.check_artifact(artifacts, r))
turn = conv.append_turn(conversation, client_id=client, client_turn_key="media-fixture", text="Retouche la photo")["turn"]
kind, proposal = cm.propose(conv, turn, {"template": "media.image.edit", "parameters": {
    "prompt": "Ajoute un ciel étoilé", "format": "square", "artifact_id": source["artifact_id"]}}, owner_client_id=client)
assert kind == "PROPOSAL", proposal
job = {"schema": "media-job/1", "id": "media-" + "1" * 32, "state": "OUTPUTS_IMPORTED_UNVERIFIED",
       "request": prepare(cm.media_request(proposal)), "automatic_retry": False}
job_dir = work / "job"; job_dir.mkdir(mode=0o700); write_record(job_dir, job)
collection_id = "mc-" + "2" * 32
out = artifacts.import_bytes(PNG + b"!", display_name="sortie-1.png", provenance={
    "kind": "comfy-output", "job_id": job["id"], "prompt_id": "p1", "node_id": "9", "output_index": 0,
    "collection_id": collection_id})
coll_dir = work / "collecte"; coll_dir.mkdir(mode=0o700)
write_record(coll_dir, {"schema": "media-collection/1", "id": collection_id, "job_id": job["id"],
                        "state": "OUTPUTS_IMPORTED_UNVERIFIED", "store_id": artifacts.store_id, "artifacts": [out],
                        "expected_outputs": [{}]})
link_job(conv, owner_client_id=client, conversation_id=conversation, proposal=proposal, job_dir=str(job_dir),
         artifact_root=str(root), collection_dir=str(coll_dir))
print(json.dumps({"output": out["reference"]["artifact_id"]}))
