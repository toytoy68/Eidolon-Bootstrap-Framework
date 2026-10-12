# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : comm_service.py
# Description : Service local eidolon-comm : voix, synthèse et image ponctuelle pour la page, clé appairée, boucle locale (G151)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

"""eidolon-comm: a SEPARATE loopback service (docs/COMMUNICATION.md §2). It does not touch the Core HTTP
server, the dialogue or the mission store: it only reads the paired conversation clients to check keys.

Routes (Authorization: Bearer <paired conversation key>; the read token is refused):
  GET    /v1/comm/status
  POST   /v1/comm/stt                       body audio/wav           -> transcript (text only)
  DELETE /v1/comm/stt                       stop this client's transcription
  POST   /v1/comm/tts                       {"text", "index", ...}   -> one sentence chunk (base64 WAV)
  DELETE /v1/comm/tts                       stop this client's synthesis
  POST   /v1/comm/vision/describe?purpose=presence|scene   body image/jpeg|png

The page is served by Core on another port: only the configured page origin gets CORS headers.
Engines not configured, or not installed, answer ENGINE_UNAVAILABLE; typed text keeps working in Core.
"""
import argparse
import base64
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import re
import stat
import sys
import urllib.parse

from .comm_contract import CommError, DeviceGate

PREFIX = "/v1/comm/"
MAX_BODY = 2 * 1024 * 1024 + 64 * 1024
CONFIG_SCHEMA = "eidolon-comm-config/1"
STATUS = {"INVALID_REQUEST": 400, "PAYLOAD_TOO_LARGE": 413, "AUDIO_FORMAT_UNSUPPORTED": 415, "DEVICE_BUSY": 409,
          "CANCELLED": 409, "COMM_DISABLED": 503, "ENGINE_UNAVAILABLE": 503, "TIMEOUT": 504, "UNAUTHORIZED": 401,
          "READ_TOKEN_NOT_ALLOWED": 403, "HOST_REFUSED": 403, "ORIGIN_REFUSED": 403, "NOT_FOUND": 404,
          "METHOD_NOT_ALLOWED": 405, "LENGTH_REQUIRED": 411}


class Refused(Exception):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


class CommAPI:
    """Transport-free handler: (method, path, headers, body) -> (status, JSON-serializable, extra headers)."""

    def __init__(self, credentials, *, stt=None, tts=None, vision=None, read_token=None, allowed_hosts=None,
                 allowed_origin=None):
        self.credentials, self.stt, self.tts, self.vision = credentials, stt, tts, vision
        self.read_authorization = ("Bearer " + read_token).encode("ascii") if read_token else None
        self.allowed_hosts, self.allowed_origin = allowed_hosts, allowed_origin

    def _one(self, headers, name):
        values = [v for k, vs in headers.items() if k.lower() == name.lower() for v in vs]
        if len(values) > 1:
            raise CommError("INVALID_REQUEST", "duplicate header")
        return values[0] if values else None

    def _cors(self, headers):
        origin = self._one(headers, "Origin")
        if origin is None:
            return {}
        if origin != self.allowed_origin:
            raise Refused("ORIGIN_REFUSED")
        return {"Access-Control-Allow-Origin": origin, "Vary": "Origin",
                "Access-Control-Allow-Headers": "Authorization, Content-Type",
                "Access-Control-Allow-Methods": "GET, POST, DELETE"}

    def _client(self, headers):
        auth = self._one(headers, "Authorization")
        if auth is None or not auth.startswith("Bearer "):
            raise Refused("UNAUTHORIZED")
        if self.read_authorization is not None and hmac.compare_digest(auth.encode("utf-8", "replace"),
                                                                       self.read_authorization):
            raise Refused("READ_TOKEN_NOT_ALLOWED")
        client = self.credentials.authenticate(auth[len("Bearer "):])
        if client is None:
            raise Refused("UNAUTHORIZED")
        return client["client_id"]

    def status(self):
        def part(service):
            return service.status() if service is not None else {"state": "unavailable"}
        return {"protocol": "eidolon-comm/1", "capture_default": "off", "stt": part(self.stt), "tts": part(self.tts),
                "vision": part(self.vision), "authorizes_execution": False}

    def handle(self, method, path, headers, body):
        extra = {}
        try:
            if self.allowed_hosts is not None and self._one(headers, "Host") not in self.allowed_hosts:
                raise Refused("HOST_REFUSED")
            extra = self._cors(headers)
            if method == "OPTIONS":
                return 204, None, extra
            url = urllib.parse.urlsplit(path)
            if not url.path.startswith(PREFIX):
                raise Refused("NOT_FOUND")
            route = url.path[len(PREFIX):]
            client = self._client(headers)
            result = self._route(method, route, url.query, client, body)
            if method == "POST" and self._client(headers) != client:
                raise Refused("UNAUTHORIZED")       # G167: key revoked while processing: result discarded
            return 200, result, extra
        except Refused as exc:
            return STATUS[exc.code], self._error(exc.code), extra
        except CommError as exc:
            return STATUS.get(exc.code, 503), self._error(exc.code), extra

    @staticmethod
    def _error(code):
        return {"protocol": "eidolon-comm/1", "error": code, "authorizes_execution": False}

    def _route(self, method, route, query, client, body):
        if route == "status" and method == "GET":
            return self.status()
        if route == "stt":
            service = self._need(self.stt)
            if method == "DELETE":
                return {"stopped": service.cancel(client)}
            if method == "POST":
                return service.transcribe(client, body)
        if route == "tts":
            service = self._need(self.tts)
            if method == "DELETE":
                return {"stopped": service.stop(client)}
            if method == "POST":
                request = self._json(body)
                if not set(request) <= {"text", "index", "voice", "rate", "volume"} or "text" not in request:
                    raise CommError("INVALID_REQUEST", "text, index, voice, rate, volume only")
                result = service.synthesize(client, request["text"], index=request.get("index", 0),
                                            voice=request.get("voice"), rate=request.get("rate", 0.9),
                                            volume=request.get("volume", 1.0))
                wav = result.pop("wav")
                return {**result, "wav_base64": base64.b64encode(wav).decode("ascii")}
        if route == "vision/describe" and method == "POST":
            purpose = urllib.parse.parse_qs(query).get("purpose", ["presence"])
            if len(purpose) != 1:
                raise CommError("INVALID_REQUEST", "one purpose")
            return self._need(self.vision).describe(client, body, purpose[0])
        if route in ("status", "stt", "tts", "vision/describe"):
            raise Refused("METHOD_NOT_ALLOWED")
        raise Refused("NOT_FOUND")

    @staticmethod
    def _need(service):
        if service is None:
            raise CommError("ENGINE_UNAVAILABLE", "not configured on this server")
        return service

    @staticmethod
    def _json(body):
        try:
            value = json.loads(body.decode("utf-8"))
        except (ValueError, UnicodeError, AttributeError):
            raise CommError("INVALID_REQUEST", "JSON body required") from None
        if not isinstance(value, dict):
            raise CommError("INVALID_REQUEST", "JSON object required")
        return value


class _Handler(BaseHTTPRequestHandler):
    server_version = "eidolon-comm"
    sys_version = ""

    def log_message(self, *args):
        pass                                      # never log content, paths with queries, or keys

    def _serve(self, method):
        self.connection.settimeout(15)
        headers = {}
        for name, value in self.headers.items():
            headers.setdefault(name, []).append(value)
        body = b""
        if method in ("POST",):
            length = self.headers.get("Content-Length")
            if length is None or not length.isdigit():
                return self._send(411, CommAPI._error("LENGTH_REQUIRED"), {})
            if int(length) > MAX_BODY:
                return self._send(413, CommAPI._error("PAYLOAD_TOO_LARGE"), {})
            body = self.rfile.read(int(length))
        status, value, extra = self.server.api.handle(method, self.path, headers, body)
        self._send(status, value, extra)

    def _send(self, status, value, extra):
        raw = b"" if value is None else json.dumps(value, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        for name, val in {**extra, "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"}.items():
            self.send_header(name, val)
        if value is not None:
            self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        self._serve("GET")

    def do_POST(self):
        self._serve("POST")

    def do_DELETE(self):
        self._serve("DELETE")

    def do_OPTIONS(self):
        self._serve("OPTIONS")


class CommServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, api, *, port=8766):
        super().__init__(("127.0.0.1", port), _Handler)
        self.api = api
        if api.allowed_hosts is None:
            api.allowed_hosts = {f"127.0.0.1:{self.server_port}", f"localhost:{self.server_port}"}


def load_config(path):
    """Private operator file (0600, no symlink): which engines are REALLY installed, and where."""
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as handle:
        info = os.fstat(handle.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise ValueError("COMM_CONFIG_NOT_PRIVATE")
        value = json.loads(handle.read(64 * 1024).decode("utf-8"))
    if (not isinstance(value, dict) or value.get("schema") != CONFIG_SCHEMA
            or not set(value) <= {"schema", "stt", "tts", "vision", "allowed_origin"}):
        raise ValueError("COMM_CONFIG_INVALID")
    origin = value.get("allowed_origin")
    if origin is not None and not re.fullmatch(r"http://(127\.0\.0\.1|localhost):[0-9]{1,5}", origin):
        raise ValueError("COMM_CONFIG_INVALID: allowed_origin must be the local Core page")
    return value


def build_engines(config):
    """(stt, tts, vision) services from the configuration; a missing section means unavailable."""
    from .comm_stt import DEFAULT_VOCABULARY, SILENCE_RMS, FasterWhisperSTT, SimulatedSTT, SpeechToText, Vocabulary
    from .comm_tts import PiperTTS, SimulatedTTS, TextToSpeech
    from .comm_vision import OllamaVision, SimulatedVision, Vision
    gate = DeviceGate()
    stt = tts = vision = None
    if config.get("stt"):
        s = config["stt"]
        words = s.get("vocabulary")                   # G164: optional; "default" = DEFAULT_VOCABULARY
        if words == "default":
            words = DEFAULT_VOCABULARY
        if words is not None and (not isinstance(words, dict) or not set(words) <= {"terms", "replacements"}):
            raise CommError("INVALID_REQUEST", "stt.vocabulary: terms and replacements only")
        vocabulary = Vocabulary(words.get("terms", ()), words.get("replacements")) if words is not None else None
        engine = SimulatedSTT() if s.get("kind") == "simulated" else FasterWhisperSTT(
            s["model_dir"], threads=s.get("threads", 2), beam_size=s.get("beam_size", 1), vad=s.get("vad", False),
            bias=s.get("bias", "none"), vocabulary=vocabulary)
        stt = SpeechToText(engine, gate=gate, vocabulary=vocabulary, silence_rms=s.get("silence_rms", SILENCE_RMS))
    if config.get("tts"):
        t = config["tts"]
        engine = SimulatedTTS() if t.get("kind") == "simulated" else PiperTTS(t["executable"], t["voice_dir"])
        tts = TextToSpeech(engine, default_voice=t.get("default_voice"), gate=gate)
    if config.get("vision"):
        v = config["vision"]
        engine = SimulatedVision() if v.get("kind") == "simulated" else OllamaVision(v["endpoint"], v["model"])
        vision = Vision(engine, gate=gate)
    return stt, tts, vision


def main(argv=None):
    from .comm_credentials import ReadOnlyClientCredentials, ReadOnlyCredentialStore
    from .http_api import read_token
    from .presentation import message
    parser = argparse.ArgumentParser(prog="python -m eidolon_core.comm_service",
                                     description="Eidolon — service local voix, synthèse et image ponctuelle")
    parser.add_argument("--state", required=True, help="état Core (clés appairées de la conversation, lecture)")
    parser.add_argument("--config", required=True, help="fichier privé eidolon-comm-config/1 (0600)")
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--read-token-file", help="jeton de lecture de Core, refusé ici comme sur la conversation")
    parser.add_argument("--check", action="store_true", help="vérifier la configuration et les moteurs, sans ouvrir de port")
    args = parser.parse_args(argv)
    try:
        config = load_config(args.config)
        stt, tts, vision = build_engines(config)
        api = CommAPI(ReadOnlyClientCredentials(ReadOnlyCredentialStore(args.state)), stt=stt, tts=tts, vision=vision,
                      read_token=read_token(args.read_token_file) if args.read_token_file else None,
                      allowed_origin=config.get("allowed_origin"))
    except (OSError, ValueError, KeyError, TypeError, CommError) as exc:
        code = getattr(exc, "code", None) or str(exc).split(":")[0][:60] or type(exc).__name__
        print(message("ERREUR", f"COMM_STARTUP_REFUSED : {code}"), file=sys.stderr)
        return 2
    status = api.status()
    if args.check:
        print(json.dumps(status, ensure_ascii=False))
        return 0
    with CommServer(api, port=args.port) as server:
        engines = ", ".join(f"{k} {status[k].get('engine', 'indisponible')}" for k in ("stt", "tts", "vision"))
        print(message("INFO", f"eidolon-comm sur http://127.0.0.1:{server.server_port} — {engines} ; capture désactivée par défaut."), flush=True)
        try:
            from .sd_notify import notify
            notify()                                # G167: Type=notify, ready only once the port is open
            server.serve_forever()
        except KeyboardInterrupt:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
