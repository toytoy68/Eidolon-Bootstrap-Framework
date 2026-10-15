# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : beta_runtime.py
# Description : Authenticated profile services, explicit actions and durable receipts
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Optional server wiring. Profiles are operator bindings of paired client IDs.

Browser and model cannot choose a profile, path root, bridge credential or actor.
Each preview freezes the complete user-visible action. An exact digest authorizes
one execution. Internet attempts are reserved durably before I/O and never retried
implicitly; remembering may explicitly replay its identical journaled command.
"""
from contextlib import contextmanager, closing
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import uuid

from .contracts import digest, encode, validate_context
from .runtime_json import read_json_snapshot, _open_directory
from .bridge_credentials import read_bridge_token
from .activity import Activity
from . import memory_bridge_client, profile_files


class ServiceError(ValueError):
    def __init__(self, code, status=400):
        self.code, self.status = code, status
        super().__init__(code)


def identifier(value):
    return type(value) is str and re.fullmatch(r"[A-Za-z0-9_-]{1,80}", value) is not None


def absolute(value):
    return type(value) is str and Path(value).is_absolute() and not any(p in (".", "..") for p in value.split("/"))


def validate_config(raw):
    fields = {"schema", "state_directory", "activity_source", "clients", "profiles", "searxng_url"}
    if (type(raw) is not dict or set(raw) != fields or raw["schema"] != "eidolon-beta-runtime/1"
            or not absolute(raw["state_directory"]) or (type(raw["activity_source"]) is not str or not re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", raw["activity_source"]))
            or type(raw["profiles"]) is not dict or not 1 <= len(raw["profiles"]) <= 16
            or type(raw["clients"]) is not dict or not 1 <= len(raw["clients"]) <= 100):
        raise ValueError("invalid beta runtime")
    seen = set()
    for name, p in raw["profiles"].items():
        if (not identifier(name) or type(p) is not dict or set(p) != {
                "memory_port", "read_token_file", "write_token_file", "web_enabled", "daily_web_limit", "file_roots"}
                or type(p["memory_port"]) is not int or not 1024 <= p["memory_port"] <= 65535
                or not absolute(p["read_token_file"])
                or p["write_token_file"] is not None and not absolute(p["write_token_file"])
                or type(p["web_enabled"]) is not bool or type(p["daily_web_limit"]) is not int
                or not 1 <= p["daily_web_limit"] <= 1000 or type(p["file_roots"]) is not dict
                or len(p["file_roots"]) > 16
                or any(not identifier(k) or not absolute(v) for k, v in p["file_roots"].items())):
            raise ValueError("invalid profile service configuration")
        # Distinct endpoints and credentials: sharing is not inferred from names.
        identities = [p["memory_port"], p["read_token_file"]]
        if p["write_token_file"] is not None:
            identities.append(p["write_token_file"])
        if len(set(identities)) != len(identities) or any(v in seen for v in identities):
            raise ValueError("profile endpoints and credentials must be isolated")
        seen.update(identities)
    if any(not identifier(c) or type(p) is not str or p not in raw["profiles"] for c, p in raw["clients"].items()):
        raise ValueError("invalid client profile binding")
    from .web_search import SearxngProvider
    if raw["searxng_url"] is not None:
        SearxngProvider(raw["searxng_url"])  # validation only, no network
    if any(p["web_enabled"] for p in raw["profiles"].values()) and raw["searxng_url"] is None:
        raise ValueError("web permission requires an explicit provider")
    return json.loads(encode(raw))


class BetaRuntime:
    @classmethod
    def load(cls, filename):
        path = Path(filename).absolute()
        fd = _open_directory(str(path.parent))
        try:
            info = os.stat(path.name, dir_fd=fd, follow_symlinks=False)
            if info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o600:
                raise ValueError("private operator configuration required")
        finally:
            os.close(fd)
        return cls(read_json_snapshot(str(path.parent), path.name, max_bytes=65536, max_depth=6))

    def __init__(self, config, *, bridge=None, provider=None, reader=None, clock=None):
        self.config = validate_config(config)
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.path = Path(config["state_directory"]) / "actions.sqlite3"
        self.bridge = bridge or memory_bridge_client.request
        self.activity = Activity(config["state_directory"], config["activity_source"], clock=self.clock)
        try:
            with self._db() as db:
                db.execute("CREATE TABLE IF NOT EXISTS binding (id INTEGER PRIMARY KEY, fingerprint TEXT NOT NULL)")
                fingerprint = digest(self.config)
                old = db.execute("SELECT fingerprint FROM binding WHERE id=1").fetchone()
                if old is not None and old[0] != fingerprint:
                    raise ValueError("profile bindings changed; explicit migration required")
                db.execute("INSERT OR IGNORE INTO binding VALUES (1,?)", (fingerprint,))
                db.execute("CREATE TABLE IF NOT EXISTS actions (id TEXT PRIMARY KEY, client TEXT NOT NULL, request_key TEXT NOT NULL, profile TEXT NOT NULL, action TEXT NOT NULL, proposal TEXT NOT NULL, state TEXT NOT NULL, result TEXT, day TEXT, UNIQUE(client,request_key))")
                db.execute("CREATE TABLE IF NOT EXISTS turn_sources (client TEXT NOT NULL, conversation TEXT NOT NULL, turn_key TEXT NOT NULL, action_id TEXT, text_sha TEXT NOT NULL, PRIMARY KEY(client,conversation,turn_key))")
                # Sole exporter lock also excludes a second service instance using this state.
                db.execute("UPDATE actions SET state='UNKNOWN' WHERE state='INFLIGHT'")
            from .web_search import SearxngProvider
            from .web_reader import WebReader
            from .egress import system_resolver
            from .html_extract import ExtractLimits
            self.provider = provider or (SearxngProvider(config["searxng_url"]) if config["searxng_url"] else None)
            self.reader = reader or WebReader(system_resolver, html_limits=ExtractLimits())
        except BaseException:
            self.activity.close()
            raise

    @contextmanager
    def _db(self):
        fd = _open_directory(str(self.path.parent))
        try:
            info = os.fstat(fd)
            if info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o700:
                raise ValueError("private state required")
            leaf = os.open(self.path.name, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK,
                           0o600, dir_fd=fd)
            try:
                info = os.fstat(leaf)
                if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_mode & 0o077:
                    raise ValueError("private regular state required")
            finally:
                os.close(leaf)
            with closing(sqlite3.connect(f"/proc/self/fd/{fd}/{self.path.name}", timeout=10)) as db:
                db.row_factory = sqlite3.Row
                db.execute("PRAGMA synchronous=FULL")
                with db:
                    db.execute("BEGIN IMMEDIATE")
                    yield db
        finally:
            os.close(fd)

    def close(self):
        self.activity.close()

    def profile(self, client):
        name = self.config["clients"].get(client)
        if name is None:
            raise ServiceError("PROFILE_NOT_BOUND", 403)
        return name, self.config["profiles"][name]

    def capabilities(self, client):
        name, p = self.profile(client)
        return {"profile_id": name, "remember": p["write_token_file"] is not None,
                "web": p["web_enabled"], "daily_web_limit": p["daily_web_limit"],
                "file_roots": sorted(p["file_roots"])}

    def recall_for(self, client, text):
        name, p = self.profile(client)
        payload = {"query": text, "mode": "operational", "max_items": 5, "max_chars": 4000, "max_item_chars": 800}
        result = self.bridge("/v1/recall", payload, token=read_bridge_token(p["read_token_file"]),
            port=p["memory_port"], schema="eidolon-memory-recall/1", expected_profile=name)
        return validate_context(result)

    def _parameters(self, p, action, parameters):
        if type(parameters) is not dict:
            raise ServiceError("INVALID_PARAMETERS")
        if action == "remember":
            if not p["write_token_file"]:
                raise ServiceError("REMEMBER_NOT_ALLOWED", 403)
            if (set(parameters) != {"text"} or type(parameters["text"]) is not str
                    or not parameters["text"].strip() or len(parameters["text"]) > 16000 or "\0" in parameters["text"]):
                raise ServiceError("INVALID_REMEMBER_TEXT")
        elif action in ("web.search", "web.fetch"):
            key, maximum = ("query", 400) if action == "web.search" else ("url", 2000)
            if not p["web_enabled"]:
                raise ServiceError("WEB_NOT_ALLOWED", 403)
            if (set(parameters) != {key} or type(parameters[key]) is not str
                    or not parameters[key].strip() or len(parameters[key]) > maximum
                    or any(ord(c) < 32 for c in parameters[key])):
                raise ServiceError("INVALID_WEB_REQUEST")
            if action == "web.fetch":
                from urllib.parse import urlsplit
                u = urlsplit(parameters[key])
                if u.scheme != "https" or not u.hostname or u.username or u.password or u.fragment:
                    raise ServiceError("HTTPS_URL_REQUIRED")
        elif action == "file.read":
            if set(parameters) != {"root", "path"} or parameters["root"] not in p["file_roots"]:
                raise ServiceError("FILE_ROOT_NOT_ALLOWED", 403)
            observed = profile_files.read(p["file_roots"][parameters["root"]], parameters["path"])
            parameters = dict(parameters, sha256=observed["sha256"], bytes=observed["bytes"])
        else:
            raise ServiceError("ACTION_NOT_ALLOWED", 403)
        return parameters

    def preview(self, client, actor, key, action, parameters):
        if not identifier(key):
            raise ServiceError("INVALID_REQUEST_KEY")
        name, p = self.profile(client)
        with self._db() as db:
            old = db.execute("SELECT * FROM actions WHERE client=? AND request_key=?", (client, key)).fetchone()
            if old is not None:
                proposal = json.loads(old["proposal"])
                old_parameters = dict(proposal["parameters"])
                if action == "file.read":
                    old_parameters.pop("sha256", None); old_parameters.pop("bytes", None)
                if proposal["action"] != action or old_parameters != parameters or proposal["actor"] != actor:
                    raise ServiceError("ACTION_KEY_REUSED", 409)
                return self._view(old)
            parameters = self._parameters(p, action, parameters)
            proposal = {"id": uuid.uuid4().hex, "profile_id": name, "client_id": client, "actor": actor,
                        "action": action, "parameters": parameters, "created_at": self.clock().isoformat()}
            db.execute("INSERT INTO actions VALUES (?,?,?,?,?,?,'PREVIEW',NULL,NULL)",
                       (proposal["id"], client, key, name, action, encode(proposal)))
            return {"proposal": proposal, "sha256": digest(proposal), "state": "PREVIEW", "result": None}

    @staticmethod
    def _view(row):
        proposal = json.loads(row["proposal"])
        return {"proposal": proposal, "sha256": digest(proposal),
                "state": "UNKNOWN" if row["state"] == "INFLIGHT" else row["state"],
                "result": json.loads(row["result"]) if row["result"] else None}

    def receipts(self, client):
        self.profile(client)
        with self._db() as db:
            return [self._view(r) for r in db.execute(
                "SELECT * FROM actions WHERE client=? ORDER BY rowid DESC LIMIT 20", (client,))]

    def commit(self, client, identity, approved):
        name, p = self.profile(client)
        with self._db() as db:
            row = db.execute("SELECT * FROM actions WHERE id=? AND client=?", (identity, client)).fetchone()
            if row is None:
                raise ServiceError("ACTION_NOT_FOUND", 404)
            view = self._view(row)
            if type(approved) is not str or approved != view["sha256"]:
                raise ServiceError("APPROVAL_MISMATCH", 409)
            if row["state"] != "PREVIEW" and not (row["state"] == "UNKNOWN" and row["action"] == "remember"):
                return view
            if row["action"].startswith("web."):
                day = self.clock().date().isoformat()
                used = db.execute("SELECT count(*) FROM actions WHERE profile=? AND day=?", (name, day)).fetchone()[0]
                if used >= p["daily_web_limit"]:
                    raise ServiceError("WEB_DAILY_QUOTA", 429)
                # A backwards clock never opens an older day's budget again.
                latest = db.execute("SELECT max(day) FROM actions WHERE profile=?", (name,)).fetchone()[0]
                if latest is not None and day < latest:
                    raise ServiceError("WEB_CLOCK_REVERSED", 503)
            else:
                day = None
            db.execute("UPDATE actions SET state='INFLIGHT',day=? WHERE id=?", (day, identity))
        try:
            result = dict(self._execute(p, view["proposal"]), observed_at=self.clock().isoformat())
            state = "COMMITTED"
        except Exception:
            # No guesses about whether remote I/O happened; no provider exceptions/private paths leak.
            result, state = {"error": "ACTION_UNAVAILABLE", "effects": "UNKNOWN"}, "UNKNOWN"
        with self._db() as db:
            db.execute("UPDATE actions SET state=?,result=? WHERE id=?", (state, encode(result), identity))
            return self._view(db.execute("SELECT * FROM actions WHERE id=?", (identity,)).fetchone())

    def _execute(self, p, proposal):
        action, parameters = proposal["action"], proposal["parameters"]
        if action == "remember":
            command = {"schema": "eidolon-remember/1", "request_id": proposal["id"],
                       "actor": proposal["profile_id"], "timestamp": proposal["created_at"], "text": parameters["text"]}
            expected = digest(command)
            result = self.bridge("/v1/remember", {"command": command, "approved_sha256": expected},
                token=read_bridge_token(p["write_token_file"]), port=p["memory_port"],
                schema="eidolon-memory-write/1", expected_profile=proposal["profile_id"])
            if (result.get("state") != "COMMITTED" or result.get("sha256") != expected
                    or type(result.get("receipt")) is not dict
                    or result["receipt"].get("information_id") != "remember-" + proposal["id"]
                    or result["receipt"].get("revision") != 1):
                raise ValueError("remember receipt mismatch")
            return result
        if action == "web.search":
            results, unavailable = self.provider.query(parameters["query"], 5)
            return {"status": "OK" if results else "EMPTY", "results": results,
                    "unresponsive_engines": unavailable, "provider": self.provider.provider_id,
                    "fetched_at": self.clock().isoformat(), "untrusted": True, "quota_scope": "profile_UTC_day_durable"}
        if action == "web.fetch":
            from .egress import WebPolicy
            from .research import _classify_page, ResearchLimits
            page = self.reader.read(parameters["url"], WebPolicy())
            status, text, details = _classify_page(page, ResearchLimits())
            return {"status": status, "text": text, "url": page.url, "http_status": page.status,
                    "retrieval": page.retrieval, "untrusted": True, "extraction": details}
        observed = profile_files.read(p["file_roots"][parameters["root"]], parameters["path"])
        if observed["sha256"] != parameters["sha256"]:
            raise ValueError("file changed after preview")
        return dict(observed, untrusted=True)

    def turn_observations(self, client, conversation, turn_key, text, action_id=None):
        """Freeze a selected receipt with the turn; retries retain its original source.

        No network, filesystem reread, automatic remembering or new approval.
        A model cannot select another person's receipt or reinterpret a changed
        source as a retry of the original turn.
        """
        from . import conversation as cv
        cv._text(text, cv.MAX_TURN_TEXT, "text")
        cv._text(turn_key, 200, "client_turn_key")
        self.profile(client)
        if action_id is not None and (type(action_id) is not str or not re.fullmatch(r"[0-9a-f]{32}", action_id)):
            raise ServiceError("INVALID_SOURCE_ACTION")
        with self._db() as db:
            old = db.execute("SELECT action_id,text_sha FROM turn_sources WHERE client=? AND conversation=? AND turn_key=?",
                             (client, conversation, turn_key)).fetchone()
            if old is not None:
                if old["text_sha"] != digest(text) or action_id is not None and old["action_id"] != action_id:
                    raise ServiceError("TURN_SOURCE_CHANGED", 409)
                action_id = old["action_id"]
            observation = None
            if action_id is not None:
                row = db.execute("SELECT * FROM actions WHERE id=? AND client=?", (action_id, client)).fetchone()
                if row is None or row["state"] != "COMMITTED" or row["action"] not in ("web.search", "web.fetch", "file.read"):
                    raise ServiceError("SOURCE_ACTION_UNAVAILABLE", 404)
                view = self._view(row); result = view["result"]
                content = encode({"action": row["action"], "parameters": view["proposal"]["parameters"], "result": result})
                observation = {"source": row["action"], "reference": "action-"+action_id,
                    "state": "UNVERIFIED", "observed_at": result.get("observed_at", view["proposal"]["created_at"]),
                    "text": "Source externe non vérifiée.\n"+content[:3600]+("\n[EXTRAIT TRONQUÉ]" if len(content)>3600 else "")}
            if old is None:
                db.execute("INSERT INTO turn_sources VALUES (?,?,?,?,?)", (client, conversation, turn_key, action_id, digest(text)))
            return [observation] if observation else None

    def files(self, client, root, path):
        _, p = self.profile(client)
        if type(root) is not str or root not in p["file_roots"]:
            raise ServiceError("FILE_ROOT_NOT_ALLOWED", 403)
        return profile_files.listing(p["file_roots"][root], path)
