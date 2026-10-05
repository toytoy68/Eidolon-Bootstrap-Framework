# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : web_reader.py
# Description : Adaptateur de lecture HTTP contrôlée pour la recherche candidate
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

"""Transport-to-research adapter; no provider, mission capability or HTML extractor.

Injected connector/resolver are trusted code. Keep their semantics stable under
transport_id; use a new reader/coordinator when changing transport configuration.
"""
from dataclasses import asdict, dataclass, field
import re
import time

from .contracts import ContractError, digest
from .research import AccessFailure, Page
from .web_transport import TransportLimits, WebTransportError, fetch


@dataclass(frozen=True)
class WebReader:
    resolver: object
    connector: object = None
    limits: TransportLimits = field(default_factory=lambda: TransportLimits(max_body_bytes=128_000))
    transport_id: str = "stdlib-http/3"
    clock: object = time.monotonic

    def __post_init__(self):
        if (not callable(self.resolver) or not callable(self.clock)
                or not isinstance(self.limits, TransportLimits) or self.limits.max_body_bytes > 128_000
                or type(self.transport_id) is not str
                or not re.fullmatch(r"[A-Za-z0-9._/-]{1,100}", self.transport_id)):
            raise ContractError("invalid WebReader configuration")

    @property
    def reader_id(self):
        return "web-reader/2/" + digest({"transport": self.transport_id, "limits": asdict(self.limits)})[:24]

    def read(self, url, policy):
        return self.read_guarded(url, policy, None)

    def read_guarded(self, url, policy, before_hop):
        try:
            result = fetch(url, policy=policy, resolver=self.resolver, connector=self.connector,
                           limits=self.limits, clock=self.clock, before_hop=before_hop)
        except WebTransportError as exc:
            if exc.code == "HTTP_STATUS" and exc.observation is not None:
                observed = exc.observation
                return Page(observed["final_url"], observed["status"], "", b"", policy.policy_id,
                            retry_after=observed["retry_after"],
                            retry_review_required=observed["retry_review_required"], retrieval=observed)
            code = {"DESTINATION_REFUSED": "POLICY_REFUSED", "BODY_TOO_LARGE": "TOO_LARGE",
                    "TRUNCATED": "TRUNCATED", "ENCODED_CONTENT": "UNSUPPORTED_CONTENT",
                    "TIMEOUT": "TIMEOUT", "DEADLINE_EXCEEDED": "TIMEOUT",
                    "TLS_CERTIFICATE": "TLS_ERROR", "TLS_ERROR": "TLS_ERROR",
                    "AMBIGUOUS_HEADER": "INVALID_RESPONSE", "BAD_HTTP_RESPONSE": "INVALID_RESPONSE",
                    "HEADERS_TOO_LARGE": "INVALID_RESPONSE", "REDIRECT_LOOP": "INVALID_RESPONSE"}.get(exc.code, "UNAVAILABLE")
            raise AccessFailure(code) from exc
        return Page(result.final_url, result.status, result.content_type or "", result.body,
                    result.policy_id, deadline_exceeded=result.deadline_exceeded, retrieval=result.evidence())
