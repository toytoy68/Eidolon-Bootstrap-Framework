# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : media_workspace.py
# Description : Espace média privé, initialisation explicite sans moteur
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Create a NEW coherent local media workspace; never install/start an engine.

An existing Core/conversation store is required. Initialization is journalled,
not rolled back by deletion: a partial workspace remains for operator review.
No overwrite, repair, migration, download, model choice or automatic resumption.
The parent is owned/private; hostile same-UID processes are outside this contract.
"""
import os
from pathlib import Path
import re
import uuid

from .contracts import ContractError
from .conversation_store import ConversationStore
from .http_api import ReadOnlyStore
from .media_agents import MediaError, parse_json
from .media_artifacts import ArtifactStore, initialize as artifact_init, _directory, _read, _write, _encoded
from .media_resources import ResourcePool, initialize as pool_init
from .media_worker import MediaWorker, initialize as worker_init
from .media_setup import check_configuration
from .presentation import header, message, section, safe_text

SCHEMA = "media-workspace/1"
COMPONENTS = {"artifacts": ("mas-", "store_id"), "resources": ("mrp-", "pool_id"), "worker": ("mw-", "worker_id")}


def _save(fd, value, *, initial=False):
    name = "workspace.json" if initial else ".workspace-" + uuid.uuid4().hex
    try:
        _write(name, _encoded(value), fd)
        if not initial:
            os.replace(name, "workspace.json", src_dir_fd=fd, dst_dir_fd=fd)
        os.fsync(fd)
    finally:
        if not initial:
            try: os.unlink(name, dir_fd=fd)
            except FileNotFoundError: pass


def _id(value, prefix):
    return isinstance(value, str) and re.fullmatch(re.escape(prefix) + r"[0-9a-f]{32}", value) is not None


def initialize(path, *, state, checkpoint=None):
    """Operator action; state must already exist. Partial creation is retained on failure."""
    conversations = ConversationStore(ReadOnlyStore(state))
    target = Path(path).absolute()
    parent = _directory(target.parent)
    fd = None
    checkpoint = checkpoint or (lambda stage: None)
    try:
        os.mkdir(target.name, mode=0o700, dir_fd=parent)
        fd = _directory(target.name, parent)
        record = {"schema": SCHEMA, "workspace_id": "mws-" + uuid.uuid4().hex,
                  "store_id": conversations.store_id, "state": "INITIALIZING", "components": {}}
        _save(fd, record, initial=True)
        os.fsync(parent)
        checkpoint("intent")
        for name, create in (("artifacts", lambda: artifact_init(target / "artifacts")),
                             ("resources", lambda: pool_init(target / "resources")),
                             ("worker", lambda: worker_init(target / "worker", store_id=conversations.store_id))):
            created = create()
            record["components"][name] = created[COMPONENTS[name][1]]
            _save(fd, record)
            checkpoint(name)
        config = {"artifact_store": {"root": str(target / "artifacts"), "store_id": record["components"]["artifacts"]},
                  "resource_pool": {"root": str(target / "resources"), "pool_id": record["components"]["resources"]},
                  "workflows": {}}
        _write("media.json", _encoded(config) + b"\n", fd)
        os.fsync(fd)
        checkpoint("configuration")
        record["state"] = "LOCAL_WORKSPACE_READY"
        _save(fd, record)
        return {**record, "configuration_file": str(target / "media.json"),
                "engine_state": "NOT_CONFIGURED", "engine_contacted": False, "hardware_qualified": False,
                "authorizes_execution": False}
    finally:
        if fd is not None: os.close(fd)
        os.close(parent)


def inspect(path, *, workspace_id):
    target = Path(path).absolute()
    fd = _directory(target)
    try:
        record = parse_json(_read("workspace.json", fd, 8192))
        if (type(record) is not dict or set(record) != {"schema", "workspace_id", "store_id", "state", "components"}
                or record["schema"] != SCHEMA or not _id(record["workspace_id"], "mws-")
                or not _id(record["store_id"], "s-") or type(record["state"]) is not str or record["state"] not in {"INITIALIZING", "LOCAL_WORKSPACE_READY"}
                or type(record["components"]) is not dict or set(record["components"]) - set(COMPONENTS)
                or any(not _id(value, COMPONENTS[name][0]) for name, value in record["components"].items())):
            raise MediaError("INVALID_MEDIA_WORKSPACE")
        if record["workspace_id"] != workspace_id:
            raise MediaError("MEDIA_WORKSPACE_IDENTITY_MISMATCH")
        components, resource_state = {}, None
        for name in COMPONENTS:
            identity = record["components"].get(name)
            if identity is None:
                components[name] = "NOT_RECORDED"
                continue
            try:
                if name == "artifacts":
                    ArtifactStore(target / name, expected_store_id=identity)
                elif name == "resources":
                    resource_state = ResourcePool(target / name, identity).inspect()["state"]
                else:
                    MediaWorker(target / name, worker_id=identity, store_id=record["store_id"])
                components[name] = "IDENTITY_OBSERVED"
            except (OSError, MediaError, ContractError):
                components[name] = "UNAVAILABLE_OR_CHANGED"
        config_state = "UNAVAILABLE_OR_CHANGED"
        try:
            config = parse_json(_read("media.json", fd, 1_000_000))
            if (config.get("artifact_store") != {"root": str(target / "artifacts"), "store_id": record["components"].get("artifacts")}
                    or config.get("resource_pool") != {"root": str(target / "resources"), "pool_id": record["components"].get("resources")}):
                config_state = "WORKSPACE_CONFIG_MISMATCH"
            else:
                config_state = check_configuration(config)["state"]
        except (OSError, MediaError, AttributeError, TypeError):
            pass
        coherent = (all(v == "IDENTITY_OBSERVED" for v in components.values())
                    and config_state in {"CONFIGURED_SCOPE", "INCOMPLETE"})
        return {"schema": "media-workspace-inspection/1", "workspace_id": record["workspace_id"],
                "store_id": record["store_id"], "recorded_state": record["state"],
                "state": "LOCAL_WORKSPACE_READY" if coherent and record["state"] == "LOCAL_WORKSPACE_READY" else "REVIEW_REQUIRED",
                "components": components, "resource_state": resource_state,
                "configuration_state": config_state, "engine_contacted": False, "hardware_qualified": False,
                "authorizes_execution": False}
    finally:
        os.close(fd)


def render(value):
    lines = [header(title="Installation locale des agents média"),
             message("INFO", "État : " + value["state"]),
             message("INFO", "Espace : " + value["workspace_id"]),
             message("INFO", "Magasin Core : " + value["store_id"]), section("Composants locaux")]
    for name, observed in value["components"].items():
        lines.append(message("INFO", name + " : " + observed))
    if "configuration_file" in value:
        lines.append(message("INFO", "Configuration à compléter : " + safe_text(value["configuration_file"])))
    if "configuration_state" in value:
        lines.append(message("INFO", "Configuration : " + value["configuration_state"]))
    lines.append(message("ATTENTION", "Aucun moteur installé, téléchargé ou démarré ; aucun modèle qualifié."))
    return "\n".join(lines)
