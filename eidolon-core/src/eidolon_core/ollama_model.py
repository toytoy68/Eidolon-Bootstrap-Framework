# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : ollama_model.py
# Description : Adaptateur optionnel du contrat Model vers l'API chat d'Ollama
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

"""Optional Ollama planner behind ``contracts.Model``. Not the demo default.

The adapter only turns (request, context) into bounded plan TEXT. Core still
parses, pre-checks and authorizes every step; nothing here runs a tool.
Protocol: POST {endpoint}/api/chat, non-streaming, as documented in
ollama/ollama docs/api.md (commit 42e911b, read 2026-10-05). See
docs/OLLAMA-ADAPTER.md for what is documented versus tested.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from collections.abc import Mapping
from http.client import HTTPException
import json
import urllib.error
import urllib.parse
import urllib.request

from .contracts import ContractError, digest, encode
from .planner_prompt import SYSTEM_PROMPT, messages as planner_messages, prompt_fingerprint

LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1"}
OPTION_KEYS = {"temperature", "seed", "num_predict", "num_ctx", "top_k", "top_p"}

# Structured-output schema sent as "format". It narrows the model's output;
# Core's parse_plan remains the only authority on what a valid plan is.
PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "version": {"type": "integer", "enum": [1]},
        "steps": {"type": "array", "minItems": 1, "maxItems": 5, "items": {
            "type": "object",
            "properties": {"id": {"type": "string"}, "tool": {"type": "string"},
                           "parameters": {"type": "object"}},
            "required": ["id", "tool", "parameters"]}},
    },
    "required": ["version", "steps"],
}


class OllamaError(RuntimeError):
    """Adapter failure. Never converted to an empty or default plan."""

    def __init__(self, code, message):
        super().__init__(f"{code}: {message}")
        self.code = code


@dataclass(frozen=True)
class _Options(Mapping):
    """Immutable scalar options, including across a multiprocessing spawn."""
    entries: tuple

    def __getitem__(self, key):
        for name, value in self.entries:
            if name == key:
                return value
        raise KeyError(key)

    def __iter__(self):
        return (name for name, _ in self.entries)

    def __len__(self):
        return len(self.entries)


@dataclass(frozen=True)
class OllamaConfig:
    endpoint: str                     # base URL, e.g. http://127.0.0.1:11434 (no default)
    model: str                        # e.g. "name:tag" (no default model is chosen)
    options: Mapping = field(default_factory=dict)
    timeout_seconds: float = 60.0
    max_prompt_bytes: int = 64_000
    max_response_bytes: int = 256_000
    max_output_bytes: int = 64_000    # same bound as contracts.parse_plan
    allow_non_loopback: bool = False  # operator decision, see OLLAMA-ADAPTER.md

    def __post_init__(self):
        if (not isinstance(self.endpoint, str) or not 1 <= len(self.endpoint) <= 2000
                or any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in self.endpoint)):
            raise ContractError("endpoint must be bounded text without whitespace or controls")
        try:
            url = urllib.parse.urlsplit(self.endpoint)
            if url.port is not None and not 1 <= url.port <= 65535:
                raise ValueError("invalid port")
            encode(self.endpoint)
        except ValueError:
            raise ContractError("invalid endpoint") from None
        if (url is None or url.scheme not in {"http", "https"} or not url.hostname
                or url.username is not None or url.password is not None
                or "?" in self.endpoint or "#" in self.endpoint
                or url.path not in {"", "/"}):
            raise ContractError("endpoint must be an http(s) base URL without credentials, path or query")
        if url.hostname not in LOOPBACK_HOSTS and not self.allow_non_loopback:
            raise ContractError("non-loopback endpoint requires an approved operator configuration")
        if not isinstance(self.model, str) or not 1 <= len(self.model) <= 200 or any(
                c.isspace() or ord(c) < 32 or ord(c) == 127 for c in self.model):
            raise ContractError("model must be a non-empty name without whitespace")
        encode(self.model)
        if not isinstance(self.options, (dict, _Options)) or set(self.options) - OPTION_KEYS:
            raise ContractError(f"options limited to {sorted(OPTION_KEYS)}")
        bounds = {"temperature": (0, 2), "seed": (0, 2**31 - 1),
                  "num_predict": (1, 8192), "num_ctx": (256, 262144),
                  "top_k": (0, 2**31 - 1), "top_p": (0, 1)}
        for key, value in self.options.items():
            low, high = bounds[key]
            if (type(value) not in (int, float) or not low <= value <= high
                    or (key in {"seed", "num_predict", "num_ctx", "top_k"} and type(value) is not int)
                    or (key == "top_p" and value == 0)):
                raise ContractError(f"option {key} is outside the adapter's bounded domain")
        object.__setattr__(self, "options", _Options(tuple(sorted(self.options.items()))))
        if (type(self.timeout_seconds) not in (int, float) or not 0 < self.timeout_seconds <= 600):
            raise ContractError("timeout must be within (0, 600] seconds")
        for name in ("max_prompt_bytes", "max_response_bytes", "max_output_bytes"):
            value = getattr(self, name)
            if type(value) is not int or not 1 <= value <= 4_000_000:
                raise ContractError(f"{name} must be a positive bounded integer")
        if type(self.allow_non_loopback) is not bool:
            raise ContractError("allow_non_loopback must be a boolean")

    def url(self):
        return self.endpoint.rstrip("/") + "/api/chat"

    def manifest(self):
        """Canonical, secret-free description that identifies this controller."""
        return {"adapter": "ollama-chat/4", "endpoint": self.endpoint.rstrip("/"), "model": self.model,
                "options": dict(sorted(self.options.items())), "format": digest(PLAN_SCHEMA),
                "allow_non_loopback": self.allow_non_loopback,
                "system_prompt": prompt_fingerprint(), "timeout_seconds": self.timeout_seconds,
                "budgets": {"prompt_bytes": self.max_prompt_bytes,
                            "response_bytes": self.max_response_bytes,
                            "output_bytes": self.max_output_bytes,
                            "output_tokens": self.options.get("num_predict")}}


class UrllibTransport:
    """Stdlib HTTP transport. Module-level and stateless so spawn can pickle it."""

    def post(self, url, body, *, timeout, max_bytes):
        request = urllib.request.Request(url, data=body, method="POST",
                                         headers={"Content-Type": "application/json"})
        # No proxy and no redirect: the configured endpoint is the only destination.
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())
        try:
            try:
                response = opener.open(request, timeout=timeout)
            except urllib.error.HTTPError as exc:
                response = exc
            with response:
                return response.status, (response.headers or {}).get("Content-Type", ""), _bounded(response, max_bytes)
        except (urllib.error.URLError, OSError, ValueError, HTTPException) as exc:
            reason = getattr(exc, "reason", exc)
            raise OllamaError("TRANSPORT", type(reason).__name__) from None


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None  # A 3xx then surfaces as an HTTP status, never as a new destination.


def _bounded(stream, max_bytes):
    from .model_http import read_body
    return read_body(stream, max_bytes, OllamaError)


def _same_model(configured, reported):
    def full(name):
        return name if ":" in name.rsplit("/", 1)[-1] else name + ":latest"
    return full(configured) == full(reported)


class OllamaModel:
    """``contracts.Model`` over a configured Ollama endpoint."""

    def __init__(self, config, transport=None):
        if not isinstance(config, OllamaConfig):
            raise ContractError("OllamaConfig required")
        self.config = config
        self.transport = transport or UrllibTransport()

    @property
    def model_id(self):
        # Replacing the config must also change Runtime.configuration().
        return f"ollama/{self.config.model}@{digest(self.config.manifest())[:16]}"

    def messages(self, request, context):
        return planner_messages(request, context)

    def propose(self, request, context):
        body = encode({"model": self.config.model, "messages": self.messages(request, context),
                       "stream": False, "format": PLAN_SCHEMA,
                       "options": dict(sorted(self.config.options.items()))}).encode("utf-8")
        if len(body) > self.config.max_prompt_bytes:
            raise OllamaError("PROMPT_TOO_LARGE", f"{len(body)} > {self.config.max_prompt_bytes} bytes")
        status, content_type, raw = self.transport.post(
            self.config.url(), body, timeout=self.config.timeout_seconds,
            max_bytes=self.config.max_response_bytes)
        return self.read_response(status, content_type, raw)

    def read_response(self, status, content_type, raw):
        if type(status) is not int or not 100 <= status <= 599:
            raise OllamaError("BAD_RESPONSE", "transport returned an invalid HTTP status")
        if not isinstance(raw, bytes):
            raise OllamaError("BAD_RESPONSE", "transport returned no bytes")
        if len(raw) > self.config.max_response_bytes:
            raise OllamaError("RESPONSE_TOO_LARGE", "transport response exceeds configured budget")
        def unique(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError("duplicate response key")
                result[key] = value
            return result
        try:
            payload = json.loads(raw.decode("utf-8"), parse_constant=_reject_constant, object_pairs_hook=unique)
            encode(payload)  # Reject overflowed floats and escaped unpaired surrogates too.
        except (UnicodeDecodeError, ValueError, RecursionError):
            if status != 200:
                raise OllamaError("HTTP_STATUS", f"status {status}") from None
            raise OllamaError("BAD_RESPONSE", "body is not finite, unambiguous UTF-8 JSON") from None
        if status != 200:
            # Remote errors may reflect the request/context. Keep them out of
            # durable mission records just like the llama-server adapter does.
            raise OllamaError("HTTP_STATUS", f"status {status}; remote error details omitted")
        if not str(content_type).split(";")[0].strip().lower() == "application/json":
            raise OllamaError("BAD_RESPONSE", "non-streaming answer must be application/json")
        if not isinstance(payload, dict):
            raise OllamaError("BAD_RESPONSE", "answer must be a JSON object")
        if "error" in payload:
            raise OllamaError("MODEL_ERROR", "server returned an error envelope")
        if payload.get("done") is not True:
            raise OllamaError("BAD_RESPONSE", "answer is not a completed, non-streaming response")
        if payload.get("done_reason", "stop") != "stop":
            # e.g. a length cut: a truncated plan must never reach the parser as if complete.
            raise OllamaError("INCOMPLETE", "answer did not finish with stop")
        reported = payload.get("model")
        if not isinstance(reported, str) or not _same_model(self.config.model, reported):
            raise OllamaError("MODEL_MISMATCH", "answer does not come from the configured model")
        message = payload.get("message")
        if not isinstance(message, dict) or message.get("role") != "assistant":
            raise OllamaError("BAD_RESPONSE", "missing assistant message")
        if message.get("tool_calls") is not None and not isinstance(message["tool_calls"], list):
            raise OllamaError("BAD_RESPONSE", "tool_calls must be null or a list")
        if message.get("tool_calls"):
            raise OllamaError("TOOL_CALL_REFUSED", "the adapter never executes or relays tool calls")
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise OllamaError("EMPTY_OUTPUT", "assistant content is absent or not text")
        if len(content.encode("utf-8", errors="surrogatepass")) > self.config.max_output_bytes:
            raise OllamaError("OUTPUT_TOO_LARGE", f"more than {self.config.max_output_bytes} bytes")
        return content


def _reject_constant(name):
    raise ValueError(f"non-finite JSON constant {name}")
