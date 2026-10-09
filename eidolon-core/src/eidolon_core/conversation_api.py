# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : conversation_api.py
# Description : API de conversation et de soumission : client appairé, jeton de lecture refusé, reçus (C-TASK-G087)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

"""POST-only JSON routes under /v1/conversations/, served by ConversationAPI.handle().

handle() is transport-free so the read server (http_api, Codex) can mount it on the same origin;
ConversationServer is a minimal loopback host for tests and recipes. Every route needs a paired
conversation credential; the read token is refused explicitly. The client identity and actor come
from the credential, never from the request. A submission creates the mission it names and returns a
receipt; it does not run it. Cancellation records a request, never a confirmed stop.
"""
import argparse
import hmac
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pathlib import Path
import re
import sqlite3
import sys

from . import conversation as cv
from .client_credentials import ClientCredentials, CredentialError
from .commands import CancelCommands
from .contracts import ContractError
from . import conversation_storage
from .conversation_store import ConversationStore
from .dialogue import Dialogue

PROTOCOL = "eidolon-conversation-api/1"
PREFIX = "/v1/conversations/"
# An 8000-character turn in ANY valid JSON encoding: \uXXXX escapes of surrogate pairs take 12 bytes
# per character (96 000), plus the envelope.
MAX_BODY = 100_000
ROUTES = {"open", "recent", "turn", "page", "submit", "receipt", "resolve", "cancel"}
CONFLICTS = ("PROPOSAL_STALE", "PROPOSAL_CHANGED", "PROPOSAL_ALREADY_SUBMITTED", "COMMAND_KEY_REUSED",
             "TURN_KEY_REUSED", "REPLY_ALREADY_RECORDED", "STORE_CHANGED", "NOT_UNCERTAIN", "NOT_A_CANDIDATE",
             "TURN_OUT_OF_ORDER", "CONVERSATION_FULL")
SECURITY_HEADERS = (("Cache-Control", "no-store"), ("X-Content-Type-Options", "nosniff"),
                    ("Referrer-Policy", "no-referrer"),
                    ("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'"))


class APIError(ValueError):
    def __init__(self, status, code):
        super().__init__(code)
        self.status, self.code = status, code


def _decode(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate key")
            result[key] = value
        return result

    def nonfinite(_):
        raise ValueError("non-finite")

    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=unique, parse_constant=nonfinite)
        cv.snapshot(value)
    except (ValueError, UnicodeError, RecursionError, ContractError):
        raise APIError(400, "INVALID_JSON") from None
    if type(value) is not dict:
        raise APIError(400, "INVALID_JSON")
    return value


def _fields(data, required, optional=()):
    if not set(required) <= set(data) or set(data) - set(required) - set(optional):
        raise APIError(400, "INVALID_FIELDS")
    return data


class ConversationAPI:
    def __init__(self, runtime, *, dialogue_model, read_token=None, allowed_hosts=None, attempt_seconds=None):
        """runtime: the mission Runtime whose Store, catalogue and configuration missions use."""
        self.runtime = runtime
        self.conversations = ConversationStore(runtime.store)
        self.credentials = ClientCredentials(runtime.store)
        # attempt_seconds=None: wall budget per attempt = the adapter's own timeout + 5 s, 120 s otherwise,
        # derived per turn from the model actually used (a profile may change between turns, G098).
        self.dialogue = Dialogue(self.conversations, dialogue_model, runtime.catalog, attempt_seconds=attempt_seconds)
        self.read_authorization = ("Bearer " + read_token).encode("ascii") if read_token else None
        self.allowed_hosts = allowed_hosts

    # -- transport-free entry point -----------------------------------------------------------

    def handle(self, method, path, headers, body):
        """headers: mapping name -> list of values. Returns (status, JSON-serializable object)."""
        try:
            return 200, self._route(method, path, headers, body)
        except APIError as exc:
            return exc.status, self._error(exc.code)
        except CredentialError as exc:
            return 503, self._error(str(exc).split(":")[0])
        except ContractError as exc:
            code = str(exc).split(":")[0]
            if code.endswith("_UNKNOWN") or code == "PROPOSAL_UNKNOWN":
                return 404, self._error(code)
            if code in CONFLICTS:
                return 409, self._error(code)
            if code.startswith("INVALID_"):
                return 400, self._error(code)
            if code in ("CONVERSATION_STORE_BUSY", "SERVER_STOPPING", "CONVERSATION_STORE_MIGRATION_REQUIRED"):
                return 503, self._error(code)
            return 503, self._error("CONVERSATION_UNAVAILABLE")
        except (KeyError, sqlite3.Error, OSError, ValueError, TypeError):
            return 503, self._error("CONVERSATION_UNAVAILABLE")

    def close(self):
        """Shutdown policy (G088-R2): in-flight model attempts are abandoned, nothing more is recorded."""
        self.dialogue.close()

    @staticmethod
    def _error(code):
        return {"protocol": PROTOCOL, "error": code, "authorizes_execution": False}

    @staticmethod
    def _one(headers, name):
        values = [v for k, vs in headers.items() if k.lower() == name.lower() for v in vs]
        if len(values) > 1:
            raise APIError(400, "DUPLICATE_HEADER")
        return values[0] if values else None

    def _client(self, headers):
        authorization = self._one(headers, "Authorization")
        if authorization is None or not authorization.startswith("Bearer "):
            raise APIError(401, "UNAUTHORIZED")
        if self.read_authorization is not None and hmac.compare_digest(
                authorization.encode("utf-8", "replace"), self.read_authorization):
            raise APIError(403, "READ_TOKEN_NOT_ALLOWED")     # reading never grants writing
        client = self.credentials.authenticate(authorization[len("Bearer "):])
        if client is None:
            raise APIError(401, "UNAUTHORIZED")
        return client

    def _route(self, method, path, headers, body):
        if self.allowed_hosts is not None:
            host = self._one(headers, "Host")
            if host not in self.allowed_hosts:
                raise APIError(403, "HOST_REFUSED")
            origin = self._one(headers, "Origin")
            if origin is not None and origin != "http://" + host:
                raise APIError(403, "ORIGIN_REFUSED")
        if not path.startswith(PREFIX) or path[len(PREFIX):] not in ROUTES:
            raise APIError(404, "NOT_FOUND")
        if method != "POST":
            raise APIError(405, "METHOD_NOT_ALLOWED")
        content_type = self._one(headers, "Content-Type")
        if content_type is None or content_type.lower() not in {"application/json", "application/json; charset=utf-8"}:
            raise APIError(415, "JSON_REQUIRED")
        if not isinstance(body, bytes) or len(body) > MAX_BODY:
            raise APIError(413, "REQUEST_TOO_LARGE")
        client = self._client(headers)
        data = _decode(body)
        return getattr(self, "_" + path[len(PREFIX):])(client, data)

    def _own(self, client, conversation_id):
        if not isinstance(conversation_id, str) or self.conversations.owner(conversation_id) != client["client_id"]:
            raise APIError(404, "CONVERSATION_UNKNOWN")       # same answer for absent and foreign

    # -- routes -----------------------------------------------------------------------------------

    def _open(self, client, data):
        _fields(data, {"client_key"})
        opened = self.conversations.open(client_id=client["client_id"], client_key=data["client_key"])
        # The client needs its own identity to build a submission; it is the credential's, never chosen.
        return {"protocol": PROTOCOL, **opened, "client_id": client["client_id"], "actor": client["actor"],
                "store_id": self.conversations.store_id}

    def _recent(self, client, data):
        _fields(data, set(), {"limit"})
        return {"protocol": PROTOCOL, "conversations": self.conversations.recent(client["client_id"],
                                                                                 limit=data.get("limit", 10))}

    def _turn(self, client, data):
        _fields(data, {"conversation_id", "client_turn_key", "text"})
        self._own(client, data["conversation_id"])
        result = self.dialogue.respond(data["conversation_id"], client_id=client["client_id"],
                                       client_turn_key=data["client_turn_key"], text=data["text"])
        # pending: another attempt for this very turn is still within its budget (G090-R1); ask again later.
        return {"protocol": PROTOCOL, "turn": result["turn"], "reply": result["reply"],
                "pending": bool(result.get("pending")), "replayed": result["replayed"],
                "model_called": result["model_called"]}

    def _page(self, client, data):
        _fields(data, {"conversation_id"}, {"after", "limit"})
        self._own(client, data["conversation_id"])
        return self.conversations.page(data["conversation_id"], after=data.get("after", 0),
                                       limit=data.get("limit", 20))

    def _submit(self, client, data):
        submission = cv.validate_submission(data)
        if submission["client_id"] != client["client_id"]:
            raise APIError(403, "CLIENT_MISMATCH")
        if submission["actor"] != client["actor"]:
            raise APIError(403, "ACTOR_MISMATCH")
        self._own(client, submission["conversation_id"])
        runtime = self.runtime
        receipt = self.conversations.submit(submission, create=lambda request, intent: runtime.store.create(
            request, runtime.configuration(), intent=intent))
        return {**receipt, "execution": "NOT_STARTED_BY_SUBMISSION"}

    def _receipt(self, client, data):
        _fields(data, {"command_key"})
        receipt = self.conversations.receipt(client_id=client["client_id"], command_key=data["command_key"])
        return {"protocol": PROTOCOL, "status": "FOUND" if receipt else "NOT_FOUND", "receipt": receipt,
                "authorizes_resend": False}

    def _resolve(self, client, data):
        _fields(data, {"command_key", "mission_id", "reason"})
        return self.conversations.resolve_uncertain(client_id=client["client_id"], command_key=data["command_key"],
                                                    mission_id=data["mission_id"], actor=client["actor"],
                                                    reason=data["reason"])

    def _cancel(self, client, data):
        _fields(data, {"command_key", "mission_id", "reason"})
        if not isinstance(data["mission_id"], str) or not self.conversations.submitted_by(client["client_id"],
                                                                                        data["mission_id"]):
            raise APIError(404, "MISSION_UNKNOWN")             # only missions this client submitted
        receipt = CancelCommands(self.runtime.store).submit({
            "protocol": "eidolon-cancel-command/1", "store_id": self.conversations.store_id,
            "client_id": client["client_id"], "command_key": data["command_key"],
            "mission_id": data["mission_id"], "actor": client["actor"], "reason": data["reason"]})
        return {**receipt, "meaning": "CANCELLATION_REQUESTED_NOT_CONFIRMED"}


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"
    server_version = "EidolonConversationAPI"
    sys_version = ""

    def log_message(self, *_):
        pass                                   # texts and tokens never reach access logs

    def _dispatch(self):
        try:
            length = self.headers.get("Content-Length", "0")
            if not re.fullmatch(r"[0-9]{1,9}", length) or int(length) > MAX_BODY:
                status, value = 413, ConversationAPI._error("REQUEST_TOO_LARGE")
            else:
                body = self.rfile.read(int(length))
                headers = {}
                for name, value in self.headers.items():
                    headers.setdefault(name, []).append(value)
                status, value = self.server.api.handle(self.command, self.path, headers, body)
            raw = json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            for name, header in SECURITY_HEADERS:
                self.send_header(name, header)
            self.end_headers()
            self.wfile.write(raw)
        except OSError:
            self.close_connection = True

    do_GET = do_POST = do_PUT = do_DELETE = do_PATCH = do_OPTIONS = do_HEAD = _dispatch


class ConversationServer(HTTPServer):
    """Loopback host for tests and synthetic recipes; production mounting goes through http_api."""

    def __init__(self, api, *, port=0):
        super().__init__(("127.0.0.1", port), _Handler)
        self.api = api
        if api.allowed_hosts is None:
            api.allowed_hosts = {f"127.0.0.1:{self.server_address[1]}", f"localhost:{self.server_address[1]}"}


def main(argv=None):
    """Operator commands, run on the server: pair or revoke a conversation client."""
    from .store import Store
    parser = argparse.ArgumentParser(prog="python -m eidolon_core.conversation_api",
                                     description="Appairage des clients de conversation (jeton affiché une fois)")
    parser.add_argument("--state", required=True)
    sub = parser.add_subparsers(dest="command", required=True)
    pair = sub.add_parser("pair")
    pair.add_argument("--client-id", required=True)
    pair.add_argument("--actor", required=True)
    revoke = sub.add_parser("revoke")
    revoke.add_argument("--client-id", required=True)
    migrate = sub.add_parser("migrate", help="Sauvegarde vérifiée puis migration explicite vers la version courante")
    migrate.add_argument("--backup", required=True, help="nouveau fichier de sauvegarde (jamais écrasé)")
    sub.add_parser("inspect-store", help="Inspection hors ligne en lecture seule ; ne migre jamais")
    save = sub.add_parser("backup", help="Sauvegarde vérifiable du dépôt des conversations")
    save.add_argument("--output", required=True)
    profile = sub.add_parser("profile", help="Choix explicite du profil de dialogue (aucun repli automatique)")
    profile.add_argument("action", choices=("select", "show"))
    profile.add_argument("--name")
    profile.add_argument("--actor")
    profile.add_argument("--profiles", help="fichier privé des profils : le nom doit y figurer")
    attach = sub.add_parser("attach", help="Lier un artefact média à une conversation de son propriétaire")
    attach.add_argument("--client-id", required=True)
    attach.add_argument("--conversation-id", required=True)
    attach.add_argument("--artifact-root", required=True)
    attach.add_argument("--reference", required=True, help="fichier JSON media-artifact-ref/1")
    args = parser.parse_args(argv)
    store = Store(args.state)
    database = Path(store.directory) / "conversations" / "conversations.sqlite3"
    try:
        if args.command == "pair":
            ConversationStore(store, create=True)
            print(json.dumps(ClientCredentials(store, create=True).pair(client_id=args.client_id, actor=args.actor)))
        elif args.command == "migrate":
            print(json.dumps(conversation_storage.migrate_with_backup(store, args.backup)))
        elif args.command == "inspect-store":
            report = conversation_storage.inspect(database)
            print(json.dumps(report))
            return 0 if report["integrity"] == "ok" and report["state"] == "CURRENT" else 3
        elif args.command == "backup":
            saved = conversation_storage.backup(database, args.output)
            print(json.dumps({key: saved[key] for key in ("version", "state", "logical_sha256", "file_sha256",
                                                           "bytes", "rows")}))
        elif args.command == "profile":
            print(json.dumps(_profile(store, args)))
        elif args.command == "attach":
            print(json.dumps(_attach(store, args)))
        else:
            ClientCredentials(store).revoke(args.client_id)
            print(json.dumps({"client_id": args.client_id, "status": "REVOKED"}))
    except ContractError as exc:
        print(json.dumps({"error": str(exc).split(":")[0]}))
        return 2
    return 0


def _profile(store, args):
    """Record or show the explicit profile selection. No model is contacted, nothing is downloaded."""
    conversations = ConversationStore(store)
    if args.action == "show":
        return {"selected": conversations.selected_profile()}
    if not args.name or not args.actor:
        raise ContractError("INVALID_CONVERSATION: --name and --actor are required")
    if args.profiles is not None:
        from .dialogue_profiles import DialogueProfiles
        from .diagnostics import demo_catalog
        if args.name not in DialogueProfiles.load(args.profiles, demo_catalog()).names():
            raise ContractError("DIALOGUE_PROFILE_UNAVAILABLE: profile not configured")
    return {"status": "SELECTED", "selected": conversations.select_profile(args.name, actor=args.actor),
            "applies_to": "turns whose model attempt starts after this selection"}


def _attach(store, args):
    """Operator attachment: the reference must name an artifact readable unchanged in this artifact store."""
    from .conversation_media import check_artifact
    from .media_agents import MediaError
    from .media_artifacts import ArtifactStore
    try:
        with open(args.reference, "rb") as handle:
            reference = json.loads(handle.read(4096).decode("utf-8"))
        artifacts = ArtifactStore(args.artifact_root)
    except (OSError, ValueError, MediaError):
        raise ContractError("ARTIFACT_UNAVAILABLE: reference or artifact store unreadable") from None
    record = ConversationStore(store).attach(owner_client_id=args.client_id, conversation_id=args.conversation_id,
                                            reference=reference, verify=lambda ref: check_artifact(artifacts, ref))
    return {"status": "ATTACHED", "conversation_id": record["conversation_id"],
            "artifact_id": record["reference"]["artifact_id"]}


if __name__ == "__main__":
    sys.exit(main())
