# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : openai_chat_model.py
# Description : Adaptateur candidat du contrat Model vers l'API chat de llama-server
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

"""Optional planner for llama.cpp's ``POST /v1/chat/completions``. Not a default.

Written against llama.cpp release b11418 (commit 9871df5); see
docs/OPENAI-CHAT-ADAPTER.md for what the server documents, what its code does
and what this adapter decides. No universal compatibility with every
"OpenAI-compatible" server is claimed. Core still parses, pre-checks and
authorizes every step; nothing here runs a tool.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
import json
from http.client import HTTPException
from .model_http import CompleteHeaderHandler, IncompleteHeaders
import math
import os
import re
import urllib.error
import urllib.parse
import urllib.request

from .contracts import ContractError, digest, encode, snapshot
from .ollama_model import PLAN_SCHEMA
from .planner_prompt import SYSTEM_PROMPT, messages as planner_messages, prompt_fingerprint

LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1"}
OPTION_KEYS = {"temperature", "seed", "max_tokens", "top_p", "top_k"}
ENV_NAME = re.compile(r"[A-Z_][A-Z0-9_]{0,63}")


class OpenAIChatError(RuntimeError):
    """Adapter failure. Never converted to an empty or default plan."""

    def __init__(self, code, message):
        super().__init__(f"{code}: {message}")
        self.code = code


@dataclass(frozen=True)
class _Options(Mapping):
    """Immutable scalar options that survive a multiprocessing spawn."""
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
class OpenAIChatConfig:
    endpoint: str                       # base URL, e.g. http://127.0.0.1:8080 (no default)
    model: str                          # name the server reports (its alias); no default model
    options: Mapping = field(default_factory=dict)
    context_tokens: int | None = None   # server context declared by the operator, if known
    timeout_seconds: float = 60.0
    max_prompt_bytes: int = 64_000
    max_response_bytes: int = 256_000
    max_output_bytes: int = 64_000      # same bound as contracts.parse_plan
    allow_non_loopback: bool = False    # operator decision, see the adapter documentation
    api_key_env: str | None = None      # NAME of an environment variable, never the key

    def __post_init__(self):
        if (not isinstance(self.endpoint, str) or not 1 <= len(self.endpoint) <= 2000
                or any(c.isspace() or ord(c) < 32 for c in self.endpoint)):
            raise ContractError("endpoint must be bounded text without whitespace or controls")
        try:
            url = urllib.parse.urlsplit(self.endpoint)
            if url.port is not None and not 1 <= url.port <= 65535:
                raise ValueError("invalid port")
            encode(self.endpoint)
        except ValueError as exc:
            raise ContractError("invalid endpoint") from exc
        if (url is None or url.scheme not in {"http", "https"} or not url.hostname
                or url.username or url.password or url.query or url.fragment
                or url.path not in {"", "/"}):
            raise ContractError("endpoint must be an http(s) base URL without credentials, path or query")
        loopback = url.hostname in LOOPBACK_HOSTS
        if not loopback and self.allow_non_loopback is not True:
            raise ContractError("non-loopback endpoint requires an approved operator configuration")
        if type(self.allow_non_loopback) is not bool:
            raise ContractError("allow_non_loopback must be a boolean")
        if not isinstance(self.model, str) or not 1 <= len(self.model) <= 200 or any(
                c.isspace() or ord(c) < 32 for c in self.model):
            raise ContractError("model must be a non-empty name without whitespace")
        if not isinstance(self.options, (dict, _Options)) or set(self.options) - OPTION_KEYS:
            raise ContractError(f"options limited to {sorted(OPTION_KEYS)}")
        bounds = {"temperature": (0, 10), "seed": (-1, 2**32 - 1),
                  "max_tokens": (1, 1_000_000), "top_p": (0, 1), "top_k": (0, 1_000_000)}
        for key, value in self.options.items():
            try:
                finite = type(value) in (int, float) and math.isfinite(value)
            except OverflowError:
                finite = False
            low, high = bounds[key]
            if (not finite or not low <= value <= high
                    or (key in {"seed", "max_tokens", "top_k"} and type(value) is not int)):
                raise ContractError(f"option {key} is outside the adapter's bounded domain")
        encode(self.model)
        object.__setattr__(self, "options", _Options(tuple(sorted(self.options.items()))))
        if self.context_tokens is not None and (type(self.context_tokens) is not int
                                                or not 1 <= self.context_tokens <= 10_000_000):
            raise ContractError("context_tokens must be a positive integer or None")
        if (type(self.timeout_seconds) not in (int, float) or not 0 < self.timeout_seconds <= 600):
            raise ContractError("timeout must be within (0, 600] seconds")
        for name in ("max_prompt_bytes", "max_response_bytes", "max_output_bytes"):
            value = getattr(self, name)
            if type(value) is not int or not 1 <= value <= 4_000_000:
                raise ContractError(f"{name} must be a positive bounded integer")
        if self.api_key_env is not None:
            if not isinstance(self.api_key_env, str) or not ENV_NAME.fullmatch(self.api_key_env):
                raise ContractError("api_key_env must be an environment variable NAME, never a key")
            if not loopback and url.scheme != "https":
                # A bearer key over clear HTTP is readable by anyone on the network path.
                raise ContractError("an API key outside loopback requires https")

    def url(self):
        return self.endpoint.rstrip("/") + "/v1/chat/completions"

    def manifest(self):
        """Canonical, secret-free description that identifies this controller."""
        return {"adapter": "openai-chat-llamacpp/4", "server_contract": "llama.cpp b11418",
                "endpoint": self.endpoint.rstrip("/"), "model": self.model,
                "options": dict(self.options), "response_format": digest(PLAN_SCHEMA),
                "system_prompt": prompt_fingerprint(), "context_tokens": self.context_tokens,
                "allow_non_loopback": self.allow_non_loopback, "api_key_env": self.api_key_env,
                "timeout_seconds": self.timeout_seconds,
                "budgets": {"prompt_bytes": self.max_prompt_bytes,
                            "response_bytes": self.max_response_bytes,
                            "output_bytes": self.max_output_bytes,
                            "output_tokens": self.options.get("max_tokens")}}


class UrllibChatTransport:
    """Stdlib HTTP transport. Module-level and stateless so spawn can pickle it."""

    def post(self, url, body, *, headers, timeout, max_bytes):
        request = urllib.request.Request(url, data=body, method="POST", headers=dict(headers))
        # No proxy and no redirect: the configured endpoint is the only destination.
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), CompleteHeaderHandler(), _NoRedirect())
        try:
            try:
                response = opener.open(request, timeout=timeout)
            except urllib.error.HTTPError as exc:
                response = exc
            with response:
                return response.status, (response.headers or {}).get("Content-Type", ""), _bounded(response, max_bytes)
        except IncompleteHeaders:
            raise OpenAIChatError("INCOMPLETE_HTTP", "response ended inside HTTP headers") from None
        except (urllib.error.URLError, OSError, ValueError, HTTPException) as exc:
            reason = getattr(exc, "reason", exc)
            raise OpenAIChatError("TRANSPORT", type(reason).__name__) from None


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None  # A 3xx surfaces as an HTTP status, never as a new destination.


def _bounded(stream, max_bytes):
    from .model_http import read_body
    return read_body(stream, max_bytes, OpenAIChatError)


def _reject_constant(name):
    raise ValueError(f"non-finite JSON constant {name}")


class OpenAIChatModel:
    """``contracts.Model`` over a configured llama-server chat endpoint."""

    def __init__(self, config, transport=None):
        if not isinstance(config, OpenAIChatConfig):
            raise ContractError("OpenAIChatConfig required")
        self.config = config
        self.transport = transport or UrllibChatTransport()

    @property
    def model_id(self):
        # Replacing the config must also change Runtime.configuration().
        return f"openai-chat/{self.config.model}@{digest(self.config.manifest())[:16]}"

    def messages(self, request, context):
        return planner_messages(request, context)

    def body(self, request, context):
        return {"model": self.config.model, "messages": self.messages(request, context), "stream": False,
                # llama-server b11418 reads "schema" directly for json_object (server-common.cpp).
                "response_format": {"type": "json_object", "schema": snapshot(PLAN_SCHEMA)},
                **dict(self.config.options)}

    def headers(self):
        headers = {"Content-Type": "application/json"}
        if self.config.api_key_env is not None:
            key = os.environ.get(self.config.api_key_env)
            if not key:
                raise OpenAIChatError("MISSING_SECRET", f"environment variable {self.config.api_key_env} is not set")
            if len(key) > 8192 or any(not 33 <= ord(c) <= 126 for c in key):
                raise OpenAIChatError("INVALID_SECRET", "API key must be bounded printable ASCII without whitespace")
            headers["Authorization"] = "Bearer " + key
        return headers

    def propose(self, request, context):
        body = encode(self.body(request, context)).encode("utf-8")
        if len(body) > self.config.max_prompt_bytes:
            raise OpenAIChatError("PROMPT_TOO_LARGE", f"{len(body)} > {self.config.max_prompt_bytes} bytes")
        headers = self.headers()
        status, content_type, raw = self.transport.post(
            self.config.url(), body, headers=headers, timeout=self.config.timeout_seconds,
            max_bytes=self.config.max_response_bytes)
        secret = headers.get("Authorization", "").removeprefix("Bearer ") or None
        return self.read_response(status, content_type, raw, _secret=secret)

    def read_response(self, status, content_type, raw, *, _secret=None):
        if type(status) is not int or not 100 <= status <= 599:
            raise OpenAIChatError("BAD_RESPONSE", "transport returned an invalid HTTP status")
        if not isinstance(raw, bytes):
            raise OpenAIChatError("BAD_RESPONSE", "transport returned no bytes")
        if len(raw) > self.config.max_response_bytes:
            raise OpenAIChatError("RESPONSE_TOO_LARGE", "transport response exceeds configured budget")
        def unique(pairs):
            value = {}
            for key, item in pairs:
                if key in value:
                    raise ValueError("duplicate response key")
                value[key] = item
            return value
        try:
            payload = json.loads(raw.decode("utf-8"), parse_constant=_reject_constant, object_pairs_hook=unique)
            encode(payload)  # Finite values and UTF-8, including escaped lone surrogates.
        except (UnicodeDecodeError, ValueError, RecursionError) as exc:
            if status != 200:
                raise OpenAIChatError("HTTP_STATUS", f"status {status}") from exc
            raise OpenAIChatError("BAD_RESPONSE", "body is not JSON") from exc
        if status != 200:
            error = payload.get("error") if isinstance(payload, dict) else None
            kind = error.get("type") if isinstance(error, dict) else None
            code = "CONTEXT_EXCEEDED" if kind == "exceed_context_size_error" else (
                "AUTHENTICATION" if status == 401 else "HTTP_STATUS")
            # A server/proxy can reflect Authorization in arbitrary fields. Do not
            # copy remote error text into the durable mission or its journal.
            raise OpenAIChatError(code, f"status {status}; remote error details omitted")
        if str(content_type).split(";")[0].strip().lower() != "application/json":
            raise OpenAIChatError("BAD_RESPONSE", "non-streaming answer must be application/json")
        if not isinstance(payload, dict) or payload.get("object") != "chat.completion":
            raise OpenAIChatError("BAD_RESPONSE", "answer is not a chat.completion object")
        if "error" in payload:
            raise OpenAIChatError("MODEL_ERROR", "server returned an error envelope")
        if payload.get("model") != self.config.model:
            raise OpenAIChatError("MODEL_MISMATCH", "answer does not come from the configured model")
        choices = payload.get("choices")
        if not isinstance(choices, list) or len(choices) != 1 or not isinstance(choices[0], dict):
            raise OpenAIChatError("BAD_RESPONSE", "exactly one choice expected")
        choice = choices[0]
        message = choice.get("message")
        if not isinstance(message, dict) or message.get("role") != "assistant":
            raise OpenAIChatError("BAD_RESPONSE", "missing assistant message")
        if message.get("tool_calls") is not None and not isinstance(message["tool_calls"], list):
            raise OpenAIChatError("BAD_RESPONSE", "tool_calls must be null or a list")
        if message.get("refusal") is not None and not isinstance(message["refusal"], str):
            raise OpenAIChatError("BAD_RESPONSE", "refusal must be null or text")
        if message.get("tool_calls") or choice.get("finish_reason") == "tool_calls":
            raise OpenAIChatError("TOOL_CALL_REFUSED", "the adapter never executes or relays tool calls")
        if message.get("refusal"):
            raise OpenAIChatError("REFUSED", "the model refused to propose a plan")
        reason = choice.get("finish_reason")
        if reason == "length":
            raise OpenAIChatError("INCOMPLETE", "generation stopped on a length limit")
        if reason != "stop":
            raise OpenAIChatError("BAD_RESPONSE", "unexpected finish_reason")
        self._check_usage(payload.get("usage"))
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            # reasoning_content alone is not a plan.
            raise OpenAIChatError("EMPTY_OUTPUT", "assistant content is absent or not text")
        if len(content.encode("utf-8")) > self.config.max_output_bytes:
            raise OpenAIChatError("OUTPUT_TOO_LARGE", f"more than {self.config.max_output_bytes} bytes")
        if _secret:
            # Check both the text and JSON-decoded strings before Core can
            # persist a plan containing an escaped reflection of the key.
            values = [content]
            try:
                values.append(json.loads(content))
            except (ValueError, RecursionError):
                pass  # Core will classify a malformed plan, without executing it.
            while values:
                value = values.pop()
                if isinstance(value, str) and _secret in value:
                    raise OpenAIChatError("SECRET_IN_RESPONSE", "response reflected the transport credential; output withheld")
                if isinstance(value, dict):
                    values.extend(value.keys())
                    values.extend(value.values())
                elif isinstance(value, list):
                    values.extend(value)
        return content

    def _check_usage(self, usage):
        counts = [usage.get(k) for k in ("prompt_tokens", "completion_tokens", "total_tokens")] \
            if isinstance(usage, dict) else [None]
        if any(type(c) is not int or c < 0 for c in counts):
            raise OpenAIChatError("BAD_RESPONSE", "usage counters must be non-negative integers")
        prompt, completion, total = counts
        if total != prompt + completion:
            raise OpenAIChatError("BAD_RESPONSE", "usage counters are inconsistent")
        if self.config.context_tokens is not None and total > self.config.context_tokens:
            raise OpenAIChatError("BAD_RESPONSE", "usage exceeds the declared context")
        limit = self.config.options.get("max_tokens")
        if limit is not None and completion > limit:
            raise OpenAIChatError("BAD_RESPONSE", "completion exceeds the requested max_tokens")
