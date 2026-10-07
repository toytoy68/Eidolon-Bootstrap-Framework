# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : query_cleanup.py
# Description : Retrait local borné de motifs sensibles dans une requête
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Deterministic cleanup candidate, not anonymization or permission to transmit.

No network, model, logging or persistence. Names, quoted private prose, spelled
addresses and arbitrary secrets are outside this pattern-based mechanism.
False positives are possible (product numbers, public URLs and paths).
"""
from dataclasses import dataclass
import hashlib
import ipaddress
import re
import unicodedata

from .contracts import ContractError

PROTOCOL = "eidolon-query-cleanup/1"
MAX_QUERY_CHARS = 1000

# Apply broad containers before their contents, so a URL/path is removed in
# full, instead of leaving a private path or token behind after email removal.
_PATH_START = r"(?:[A-Za-z]:[\\/]|\\\\|/(?:home|Users|root|etc|var|mnt|media|tmp)/|~/)"
_PATTERNS = (
    ("LOCAL_PATH", re.compile(r'["«“]' + _PATH_START + r'[^"»”\r\n]*["»”]')),
    ("URL", re.compile(r"\b(?:https?|ftp|file)://[^\s<>\"«»]+", re.I)),
    ("LOCAL_PATH", re.compile(r"(?<!\w)" + _PATH_START + r"[^\s<>\"«»]+")),
    ("EMAIL", re.compile(r"[\w.!#$%&'*+/=?^`{|}~-]+@[\w-]+(?:\.[\w-]+)+")),
    ("IBAN_SHAPE", re.compile(r"\b[A-Z]{2}\d{2}(?: ?[A-Z0-9]{4}){3,7}(?: ?[A-Z0-9]{1,3})?\b")),
    ("PHONE_SHAPE", re.compile(r"(?<![\w.+-])(?:\+(?:\d[ .()\-]?){9,14}\d|0[1-9](?:[ .()\-]?\d){8})(?!\w|[.-]\d)")),
)
_IP_CANDIDATE = re.compile(r"(?<![\w.:])(?:[0-9]{1,3}\.){3}[0-9]{1,3}(?![\w.])|(?<![\w:])[0-9A-Fa-f:]*:[0-9A-Fa-f:.]+(?:%[\w.-]+)?(?!\w)")


@dataclass(frozen=True)
class CleanedQuery:
    text: str
    original_sha256: str
    cleaned_sha256: str
    removed: tuple[tuple[str, int], ...]
    normalized: bool

    def receipt(self):
        """Metadata only; even the cleaned text can retain unknown secrets."""
        return {"protocol": PROTOCOL, "original_sha256": self.original_sha256,
                "cleaned_sha256": self.cleaned_sha256,
                "removed": dict(self.removed), "normalized": self.normalized,
                "empty": not bool(self.text), "anonymity_guaranteed": False,
                "authorizes_transmission": False}


def clean_query(query):
    """Remove recognized spans; reject invalid input without echoing its value."""
    if type(query) is not str or not query.strip() or len(query) > MAX_QUERY_CHARS:
        raise ContractError("INVALID_CLEANUP_QUERY")
    try:
        raw = query.encode("utf-8")
    except UnicodeError as exc:
        raise ContractError("INVALID_CLEANUP_QUERY") from exc
    if any(unicodedata.category(c) == "Cc" and c not in "\t\r\n" for c in query):
        raise ContractError("INVALID_CLEANUP_QUERY")
    normalized = unicodedata.normalize("NFKC", query)
    normalized = "".join(c for c in normalized if unicodedata.category(c) != "Cf")
    normalized = " ".join(normalized.split())
    if len(normalized) > MAX_QUERY_CHARS:
        raise ContractError("NORMALIZED_QUERY_TOO_LARGE")
    text, counts = normalized, {}
    for kind, pattern in _PATTERNS:
        text, count = pattern.subn(" ", text)
        if count:
            counts[kind] = counts.get(kind, 0) + count

    def redact_address(match):
        try:
            ipaddress.ip_address(match.group())
        except ValueError:
            return match.group()
        counts["NETWORK_ADDRESS"] = counts.get("NETWORK_ADDRESS", 0) + 1
        return " "

    text = " ".join(_IP_CANDIDATE.sub(redact_address, text).split())
    return CleanedQuery(text, hashlib.sha256(raw).hexdigest(),
                        hashlib.sha256(text.encode("utf-8")).hexdigest(),
                        tuple(sorted(counts.items())), normalized != query)
