# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : conversation_media_results.py
# Description : Vue des résultats Image/Vidéo dans la conversation : liaison au bon travail, provenance, vérification (C-TASK-G101)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

"""What the conversation may show about a media job, built only from server records.

Inputs are Codex's structured records (media-job/1, media-collection/1) and the artifact store; never
a path or a reference written by a model or sent by a browser. Every output must come from THIS job
(same prepared request as the submitted proposal, same job id, same collection), each artifact is
re-read for its digest, and an analysis text stays an unverified observation. No state is a success.
"""
from . import conversation_media as cm
from .contracts import ContractError, digest
from .media_agents import MediaError, prepare
from .media_artifacts import validate_reference

PROTOCOL = "eidolon-media-result-view/1"


def _verification(artifact_store, reference):
    try:
        cm.check_artifact(artifact_store, reference)
    except ContractError as exc:
        return {"ARTIFACT_MODIFIED": "modified", "ARTIFACT_BUSY": "busy"}.get(str(exc).split(":")[0], "unavailable")
    return "hash_verified"


def result_view(proposal, job, *, conversations, artifact_store, viewer_client_id, collection=None):
    proposal = cm.validate_proposal(proposal)
    if (viewer_client_id != proposal["owner_client_id"]
            or conversations.owner(proposal["conversation_id"]) != viewer_client_id
            or proposal["store_id"] != conversations.store_id):
        raise ContractError("MEDIA_RESULT_UNKNOWN: no such result for this client")   # same answer as absent
    view = {"protocol": PROTOCOL, "proposal_sha256": digest(proposal), "agent": proposal["agent"],
            "operation": proposal["operation"], "job_id": None, "state_received": None, "stage": None,
            "binding": None, "source": None, "observation": None, "outputs": [], "excluded_outputs": 0,
            "collection": None, "open_action": "NOT_AVAILABLE", "success_claim": False,
            "authorizes_execution": False}
    if not isinstance(job, dict) or job.get("schema") != "media-job/1" or not isinstance(job.get("id"), str):
        return {**view, "binding": "UNREADABLE"}
    state = job.get("observed_state") or job.get("state")
    view.update(job_id=job["id"], state_received=state if isinstance(state, str) else None)
    view["stage"] = cm.stage(view["state_received"]) or "received_as_is"
    if "request" not in job:
        return {**view, "binding": "LEGACY_UNVERIFIABLE"}          # older record: state only, nothing listed
    try:
        expected = prepare(cm.media_request(proposal))
    except MediaError:
        return {**view, "binding": "UNVERIFIABLE"}
    if job["request"] != expected:
        return {**view, "binding": "WRONG_JOB"}                    # another job's result is never shown here
    view["binding"] = "MATCHED"
    if proposal["artifact"] is not None:
        view["source"] = {"artifact_id": proposal["artifact"]["artifact_id"],
                          "verification": _verification(artifact_store, proposal["artifact"])}
    result = job.get("result")
    if isinstance(result, dict) and result.get("state") == "RESULT_UNVERIFIED" and isinstance(result.get("text"), str):
        view["observation"] = {"text": result["text"][:20_000], "verified": False}
    if collection is not None:
        view.update(_collection(collection, job, artifact_store))
    return view


def _collection(collection, job, artifact_store):
    if (not isinstance(collection, dict) or collection.get("schema") != "media-collection/1"
            or collection.get("job_id") != job["id"]):
        return {"collection": {"state": "WRONG_JOB", "expected": None, "imported": 0, "partial": True}}
    state = collection.get("observed_state") or collection.get("state")
    expected = collection.get("expected_outputs")
    outputs, excluded = [], 0
    for manifest in collection.get("artifacts") or []:
        try:
            reference = validate_reference(manifest["reference"])
            provenance = manifest["provenance"]
            same = (provenance.get("job_id") == job["id"] and provenance.get("collection_id") == collection.get("id")
                    and reference["store_id"] == collection.get("store_id"))
        except (MediaError, KeyError, TypeError, AttributeError):
            same = False
        if not same:
            excluded += 1                                           # copied or foreign reference: not shown
            continue
        outputs.append({"artifact_id": reference["artifact_id"], "display_name": manifest.get("display_name"),
                        "media_type": manifest.get("media_type"), "size": manifest.get("size"),
                        "provenance": {k: provenance.get(k) for k in ("job_id", "node_id", "output_index",
                                                                       "collection_id")},
                        "verification": _verification(artifact_store, reference), "content_verified": False})
    imported = len(outputs)
    total = len(expected) if isinstance(expected, list) else None
    return {"outputs": outputs, "excluded_outputs": excluded, "stage": cm.stage(state) or "received_as_is",
            "collection": {"state": state if isinstance(state, str) else None, "expected": total, "imported": imported,
                           "partial": state != "OUTPUTS_IMPORTED_UNVERIFIED" or (total is not None and imported < total)}}


class _UnavailableStore:
    """Stands for an artifact store that cannot be opened: every file reads as unavailable."""
    store_id = None

    def read(self, reference):
        raise MediaError("ARTIFACT_STORE_CHANGED")


def link_job(conversations, *, owner_client_id, conversation_id, proposal, job_dir, artifact_root, collection_dir=None):
    """Operator (or media worker) records which job serves this submitted proposal; refused unless the
    job's structured request is exactly the proposal's (binding MATCHED). Paths stay on the server."""
    from .media_agents import inspect as inspect_job
    from .media_artifacts import ArtifactStore
    try:
        job = inspect_job(job_dir)
        store = ArtifactStore(artifact_root)
    except (MediaError, OSError, ValueError):
        raise ContractError("MEDIA_JOB_UNAVAILABLE: job record or artifact store unreadable") from None
    view = result_view(proposal, job, conversations=conversations, artifact_store=store,
                       viewer_client_id=owner_client_id)
    if view["binding"] != "MATCHED":
        raise ContractError("MEDIA_JOB_MISMATCH: this job does not serve this proposal")
    # G123-R1: the link names the EXACT job id read now; another job with the same request is refused later.
    return conversations.link_media(owner_client_id=owner_client_id, conversation_id=conversation_id,
                                    proposal=proposal, job_dir=job_dir, artifact_root=artifact_root,
                                    collection_dir=collection_dir, job_id=job["id"])


def views_for(conversations, *, owner_client_id, conversation_id):
    """Fresh views of every job linked to this owner's conversation, read from the records now."""
    from .media_agents import inspect as inspect_job
    from .media_artifacts import ArtifactStore
    from .media_outputs import inspect_collection
    views = []
    for link in conversations.media_links(owner_client_id=owner_client_id, conversation_id=conversation_id):
        try:
            job = inspect_job(link["job_dir"])
        except (MediaError, OSError, ValueError):
            job = None                                  # → binding UNREADABLE, nothing listed
        if job is not None and (link["job_id"] is None or job.get("id") != link["job_id"]):
            # G123-R1: an equal request is not the same job. A v4 link without job id must be redone.
            view = result_view(link["proposal"], None, conversations=conversations, artifact_store=_UnavailableStore(),
                               viewer_client_id=owner_client_id)
            views.append({**view, "binding": "WRONG_JOB" if link["job_id"] else "UNVERIFIABLE"})
            continue
        collection = None
        if link["collection_dir"] is not None:
            try:
                collection = inspect_collection(link["collection_dir"])
            except (MediaError, OSError, ValueError):
                collection = {"schema": "unreadable"}   # → shown as a collection of another job: ignored
        try:
            store = ArtifactStore(link["artifact_root"])
        except (MediaError, OSError, ValueError):
            store = _UnavailableStore()
        views.append(result_view(link["proposal"], job, conversations=conversations, artifact_store=store,
                                 viewer_client_id=owner_client_id, collection=collection))
    return views
