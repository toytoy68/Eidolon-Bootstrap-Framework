# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : media_worker.py
# Description : File média durable, accord lié et essai explicite unique
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""A private, bounded queue between authenticated conversation submission and engines.

Only trusted server code calls enqueue(): it supplies identity from a paired
credential, not request fields. The current proposal is read from ConversationStore.
Enqueue does no engine work; run_once is an explicit operator action. The attempt
is durable BEFORE any engine effect. A crash never grants another attempt, even
if no job was written. Inspect/replay are offline. No daemon or automatic retry.

POSIX cooperative flock, private owned parent, no hostile same-user process.
One queue per conversation store. No deletion/expiry or implicit initialization.
"""
from contextlib import contextmanager
import fcntl
import os
from pathlib import Path
import re
import uuid

from . import conversation as cv
from . import conversation_media as cm
from .contracts import ContractError, digest, snapshot
from .media_agents import MediaError, execute, parse_json, prepare, read_source
from .media_artifacts import ArtifactStore, _directory, _private, _read, _write, _encoded

MAX_TICKETS = 128
MAX_BYTES = 8 * 1024 * 1024
STATES = {"ACCEPTED", "ATTEMPTED", "RETURNED", "REVIEW_REQUIRED"}


def _matches(value, pattern):
    return isinstance(value, str) and re.fullmatch(pattern, value) is not None


def _ticket_id(submission):
    return "mt-" + digest([submission["client_id"], submission["command_key"]])[:32]


def _save(fd, value, *, initial=False):
    raw = _encoded(value)
    if len(raw) > MAX_BYTES:
        raise MediaError("WORKER_CAPACITY")
    name = "queue.json" if initial else ".queue-" + uuid.uuid4().hex
    try:
        _write(name, raw, fd)
        if not initial:
            os.replace(name, "queue.json", src_dir_fd=fd, dst_dir_fd=fd)
        os.fsync(fd)
    finally:
        if not initial:
            try:
                os.unlink(name, dir_fd=fd)
            except FileNotFoundError:
                pass


def _load(fd):
    value = parse_json(_read("queue.json", fd, MAX_BYTES))
    if (type(value) is not dict or set(value) != {"schema", "worker_id", "store_id", "tickets"}
            or value["schema"] != "media-worker/1" or not _matches(value["worker_id"], r"mw-[0-9a-f]{32}")
            or not _matches(value["store_id"], r"s-[0-9a-f]{32}")
            or type(value["tickets"]) is not dict or len(value["tickets"]) > MAX_TICKETS):
        raise MediaError("INVALID_WORKER")
    for key, row in value["tickets"].items():
        try:
            if (type(row) is not dict or set(row) != {"ticket_id", "proposal", "submission", "job_id", "state",
                    "configuration_sha256", "failure_code", "collection_attempted"}
                    or key != row["ticket_id"] or not _matches(key, r"mt-[0-9a-f]{32}")
                    or not _matches(row["job_id"], r"media-[0-9a-f]{32}") or row["state"] not in STATES
                    or type(row["collection_attempted"]) is not bool
                    or row["configuration_sha256"] is not None and not _matches(row["configuration_sha256"], r"[0-9a-f]{64}")
                    or row["failure_code"] is not None and not _matches(row["failure_code"], r"[A-Z_]{1,80}")):
                raise ValueError()
            cm.check_submission(row["submission"], row["proposal"])
            if key != _ticket_id(row["submission"]) or row["proposal"]["store_id"] != value["store_id"]:
                raise ValueError()
            if row["state"] == "ACCEPTED" and (row["configuration_sha256"] is not None
                    or row["failure_code"] is not None or row["collection_attempted"]):
                raise ValueError()
        except (ContractError, MediaError, ValueError, KeyError, TypeError):
            raise MediaError("INVALID_WORKER_TICKET") from None
    return value


def initialize(path, *, store_id):
    cv._id(store_id, "s", "store_id")
    target = Path(path)
    parent = _directory(target.parent)
    fd = None
    try:
        os.mkdir(target.name, mode=0o700, dir_fd=parent)
        fd = _directory(target.name, parent)
        _write("writer.lock", b"", fd)
        value = {"schema": "media-worker/1", "worker_id": "mw-" + uuid.uuid4().hex,
                 "store_id": store_id, "tickets": {}}
        _save(fd, value, initial=True)
        os.fsync(parent)
        return {k: v for k, v in value.items() if k != "tickets"}
    finally:
        if fd is not None:
            os.close(fd)
        os.close(parent)


class MediaWorker:
    def __init__(self, path, *, worker_id, store_id):
        self.path = Path(path).absolute()
        self.worker_id, self.store_id = worker_id, store_id
        fd = _directory(self.path)
        try:
            info = os.fstat(fd)
            self.identity = info.st_dev, info.st_ino
            self._identity(_load(fd))
        finally:
            os.close(fd)

    def _identity(self, value):
        if value["worker_id"] != self.worker_id or value["store_id"] != self.store_id:
            raise MediaError("WORKER_IDENTITY_MISMATCH")

    @contextmanager
    def _locked(self):
        fd = _directory(self.path)
        lock = None
        try:
            info = os.fstat(fd)
            if (info.st_dev, info.st_ino) != self.identity:
                raise MediaError("WORKER_REPLACED")
            lock = os.open("writer.lock", os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
            _private(os.fstat(lock))
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise MediaError("WORKER_BUSY") from None
            value = _load(fd)
            self._identity(value)
            yield fd, value
        finally:
            if lock is not None:
                os.close(lock)
            os.close(fd)

    def _scope(self, conversations):
        if conversations.store_id != self.store_id:
            raise MediaError("WORKER_IDENTITY_MISMATCH")

    @staticmethod
    def _row(value, ticket_id, client_id):
        row = value["tickets"].get(ticket_id) if isinstance(ticket_id, str) else None
        if row is None or row["submission"]["client_id"] != client_id:
            raise MediaError("MEDIA_TICKET_UNKNOWN")
        return row

    @staticmethod
    def _receipt(row):
        return {"schema": "media-ticket/1", "ticket_id": row["ticket_id"], "job_id": row["job_id"],
                "proposal_sha256": row["submission"]["proposal_sha256"], "state": row["state"],
                "execution": "NOT_STARTED" if row["state"] == "ACCEPTED" else "ATTEMPT_RECORDED",
                "failure_code": row["failure_code"], "collection_attempted": row["collection_attempted"],
                "automatic_retry": False, "authorizes_execution": False, "success_claim": False}

    def enqueue(self, submission, *, conversations, authenticated_client_id, authenticated_actor):
        """Server-only: authenticated identity, CURRENT stored proposal, durable receipt; no engine IO.

        Exact replay returns the same ticket even after a later proposal. A new
        command key cannot execute an already accepted proposal again.
        """
        self._scope(conversations)
        submission = cv.validate_submission(submission)
        if submission["client_id"] != authenticated_client_id or submission["actor"] != authenticated_actor:
            raise MediaError("MEDIA_CLIENT_MISMATCH")
        if submission["store_id"] != self.store_id or conversations.owner(submission["conversation_id"]) != authenticated_client_id:
            raise MediaError("MEDIA_TICKET_UNKNOWN")
        key = _ticket_id(submission)
        with self._locked() as (fd, value):
            existing = value["tickets"].get(key)
            if existing is not None:
                if existing["submission"] != submission:
                    raise MediaError("MEDIA_COMMAND_KEY_REUSED")
                return self._receipt(existing)
            current = conversations.current_proposal(submission["conversation_id"])
            cm.check_submission(submission, current)
            if any(r["submission"]["proposal_sha256"] == submission["proposal_sha256"] for r in value["tickets"].values()):
                raise MediaError("MEDIA_PROPOSAL_ALREADY_SUBMITTED")
            if len(value["tickets"]) >= MAX_TICKETS:
                raise MediaError("WORKER_CAPACITY")
            row = {"ticket_id": key, "proposal": snapshot(current), "submission": submission,
                   "job_id": "media-" + uuid.uuid4().hex, "state": "ACCEPTED", "configuration_sha256": None,
                   "failure_code": None, "collection_attempted": False}
            value["tickets"][key] = row
            _save(fd, value)
            return self._receipt(row)

    def receipt(self, *, client_id, command_key):
        """Offline receipt lookup by the authenticated client's id and their original command key."""
        cv.validate_scope(self.store_id, client_id, command_key)
        with self._locked() as (_, value):
            row = value["tickets"].get(_ticket_id({"client_id": client_id, "command_key": command_key}))
            return self._receipt(row) if row is not None else None

    def tickets(self, *, client_id):
        """Offline bounded receipt list; no prompts, paths, configuration, or other clients."""
        with self._locked() as (_, value):
            return [self._receipt(r) for r in value["tickets"].values() if r["submission"]["client_id"] == client_id]

    def _job(self, fd, row):
        child = _directory(row["ticket_id"], fd)
        try:
            job = parse_json(_read("job.json", child, 2_000_000))
        finally:
            os.close(child)
        if (type(job) is not dict or job.get("schema") != "media-job/1" or job.get("id") != row["job_id"]
                or job.get("request") != prepare(cm.media_request(row["proposal"]))):
            raise MediaError("MEDIA_JOB_BINDING_MISMATCH")
        if job.get("state") == "INTENT":
            job["observed_state"] = "REVIEW_REQUIRED"
        return job

    def _inputs(self, row, conversations, config, backend=None):
        """Offline local checks only. An invalid config or a held pool consumes no attempt."""
        from .media_backends import LocalMediaBackend
        from .media_resources import configured
        pool = configured(config)
        if pool is None:
            raise MediaError("WORKER_RESOURCE_POOL_REQUIRED")
        resources = pool.inspect()
        artifact_store = None
        if row["proposal"]["artifact"] is not None:
            storage = config.get("artifact_store") if isinstance(config, dict) else None
            if type(storage) is not dict or set(storage) != {"root", "store_id"}:
                raise MediaError("ARTIFACT_STORE_NOT_CONFIGURED")
            artifact_store = ArtifactStore(storage["root"], expected_store_id=storage["store_id"])
        request = cm.verify_for_execution(row["proposal"], conversations, artifact_store)
        runner = backend or LocalMediaBackend(config)
        source, evidence = read_source(prepare(request), config)
        del source
        runner.plan(prepare(request), evidence)  # no inference, upload, FFmpeg or HTTP
        return request, runner, resources

    def check(self, ticket_id, *, client_id, conversations, config):
        """Offline readiness of one ticket. No admission, mutation, HTTP or inference."""
        self._scope(conversations)
        config = snapshot(config)
        with self._locked() as (_, value):
            row = self._row(value, ticket_id, client_id)
            receipt = self._receipt(row)
            if row["state"] != "ACCEPTED":
                return {"receipt": receipt, "state": "ATTEMPT_ALREADY_RECORDED", "ready": False,
                        "authorizes_execution": False, "hardware_qualified": False}
            _, _, resources = self._inputs(row, conversations, config)
            return {"receipt": receipt, "state": "LOCAL_INPUTS_VALID", "resource_state": resources["state"],
                    "ready": resources["state"] == "AVAILABLE", "authorizes_execution": False,
                    "hardware_qualified": False}

    def run_once(self, ticket_id, *, client_id, conversations, config, execute_local=False, backend=None):
        """Explicit one-shot worker, NEVER called just because a proposal was submitted.

        Before an attempt: recheck the owner, attachment and content. After claim,
        every failure is conservatively uncertain. An accepted new proposal (with
        fresh human submission) is required for any later attempt, not a new key.
        """
        if execute_local is not True:
            raise MediaError("MEDIA_EXECUTION_NOT_ENABLED")
        self._scope(conversations)
        config = snapshot(config)
        with self._locked() as (fd, value):
            row = self._row(value, ticket_id, client_id)
            if row["state"] != "ACCEPTED":
                return self._receipt(row)  # no re-read/upload/resubmit or engine query
            request, runner, resources = self._inputs(row, conversations, config, backend)
            if resources["state"] != "AVAILABLE":
                raise MediaError("RESOURCE_RESERVED")
            row["state"] = "ATTEMPTED"
            row["configuration_sha256"] = digest(config)
            _save(fd, value)  # durable before execute (including resource-pool reservation)
            frozen = snapshot(row)
        try:
            execute(request, config, self.path / ticket_id, backend=runner, job_id=frozen["job_id"])
        except Exception:
            # Do not copy engine text, prompts, paths, exceptions or config into the receipt.
            self._finish(ticket_id, "REVIEW_REQUIRED", "MEDIA_ATTEMPT_UNCERTAIN")
            raise MediaError("MEDIA_ATTEMPT_UNCERTAIN") from None
        return self._finish(ticket_id, "RETURNED", None)

    def _finish(self, ticket_id, state, failure_code):
        with self._locked() as (fd, value):
            row = value["tickets"][ticket_id]
            if row["state"] != "ATTEMPTED":
                raise MediaError("INVALID_WORKER_TICKET")
            if state == "RETURNED":
                self._job(fd, row)  # verify the exact preassigned job, not merely an equal request
            row["state"], row["failure_code"] = state, failure_code
            _save(fd, value)
            return self._receipt(row)

    def result(self, ticket_id, *, client_id, conversations, artifact_store):
        """Offline owner-scoped receipt and G101 view of the EXACT linked job/collection.

        Missing journal after a recorded attempt means unknown effect, never
        permission to repeat. This method does not poll any engine.
        """
        from .conversation_media_results import result_view
        self._scope(conversations)
        with self._locked() as (fd, value):
            row = self._row(value, ticket_id, client_id)
            if conversations.owner(row["proposal"]["conversation_id"]) != client_id:
                raise MediaError("MEDIA_TICKET_UNKNOWN")
            receipt = self._receipt(row)
            if row["state"] == "ACCEPTED":
                return {"receipt": receipt, "result": None, "observation": "NOT_STARTED"}
            try:
                job = self._job(fd, row)
            except (OSError, MediaError):
                return {"receipt": receipt, "result": None, "observation": "JOB_UNAVAILABLE_OR_CHANGED"}
            collection = None
            if row["collection_attempted"]:
                try:
                    child = _directory(ticket_id + "-collection", fd)
                    try:
                        collection = parse_json(_read("job.json", child, 2_000_000))
                    finally:
                        os.close(child)
                except (OSError, MediaError):
                    return {"receipt": receipt, "result": None, "observation": "COLLECTION_UNAVAILABLE_OR_CHANGED"}
            view = result_view(row["proposal"], job, conversations=conversations, artifact_store=artifact_store,
                               viewer_client_id=client_id, collection=collection)
            return {"receipt": receipt, "result": view, "observation": "RECORDED_UNVERIFIED"}

    def poll_once(self, ticket_id, *, client_id, transport=None):
        """Explicit history GET; bounded public state only, no raw remote paths or outputs."""
        from .media_backends import poll_job
        with self._locked() as (fd, value):
            row = self._row(value, ticket_id, client_id)
            if row["state"] == "ACCEPTED":
                raise MediaError("MEDIA_JOB_NOT_STARTED")
            job = self._job(fd, row)
        observed = poll_job(job, transport=transport)
        return {"ticket_id": ticket_id, "job_id": job["id"], "state": observed["state"],
                "automatic_retry": False, "success_claim": False, "authorizes_execution": False}

    def collect_once(self, ticket_id, *, client_id, artifact_store, transport=None, binary_transport=None):
        """Explicit single collection attempt; partial imports survive, never imported twice.

        Call poll_once first and inspect its state. Even a failed history GET
        consumes this collection attempt: review the existing journal afterwards.
        """
        from .media_outputs import collect, _receipt
        with self._locked() as (fd, value):
            row = self._row(value, ticket_id, client_id)
            if row["state"] == "ACCEPTED":
                raise MediaError("MEDIA_JOB_NOT_STARTED")
            if row["collection_attempted"]:
                return self._receipt(row)
            job = self._job(fd, row)
            _receipt(job)  # only a recorded exact queue acknowledgement can be collected
            row["collection_attempted"] = True
            _save(fd, value)  # before the history GET, target creation, and artifact imports
            receipt = self._receipt(row)
        try:
            collect(self.path / ticket_id, artifact_store.path, artifact_store.store_id,
                    self.path / (ticket_id + "-collection"), transport=transport, binary_transport=binary_transport)
        except Exception:
            raise MediaError("MEDIA_COLLECTION_REVIEW_REQUIRED") from None
        return receipt
