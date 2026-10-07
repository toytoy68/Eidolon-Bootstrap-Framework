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

PROTOCOL = "eidolon-query-cleanup/2"
MAX_QUERY_CHARS = 1000

# Apply broad containers before their contents, so a URL/path is removed in
# full, instead of leaving a private path or token behind after email removal.
_PATH_START = (r"(?:[A-Za-z]:[\\/]|\\\\|/(?:home|Users|root|etc|var|mnt|media|tmp|opt|srv|data|usr|run)/|~/"
               r"|%[A-Za-z_]+%[\\/])")
_PATTERNS = (
    ("LOCAL_PATH", re.compile(r'["«“\']' + _PATH_START + r'[^"»”\'\r\n]*["»”\']')),
    # Any scheme (ssh, smb, sftp...), then a host with a TLD followed by a path or query.
    ("URL", re.compile(r"\b[a-z][a-z0-9+.-]{1,15}://[^\s<>\"«»]+", re.I)),
    # Without a scheme: "www." hosts, or a host with a TLD whose path carries a query string.
    ("URL", re.compile(r"(?<![\w@.-])www\.[^\s<>\"«»]+", re.I)),
    ("URL", re.compile(r"(?<![\w@.-])(?:[\w-]+\.)+[A-Za-z]{2,63}/?[^\s<>\"«»?]*\?[^\s<>\"«»]*")),
    ("LOCAL_PATH", re.compile(r"(?<!\w)" + _PATH_START + r"[^\s<>\"«»]+")),
    # Relative paths only with two levels ("./secrets/token.txt"), not "./configure".
    ("LOCAL_PATH", re.compile(r"(?<![\w.])\.{1,2}[\\/][^\s<>\"«»\\/]+[\\/][^\s<>\"«»]*")),
    ("EMAIL", re.compile(r"[\w.!#$%&'*+/=?^`{|}~-]+@[\w-]+(?:\.[\w-]+)+")),
    ("IBAN_SHAPE", re.compile(r"\b[A-Z]{2}\d{2}(?:[ -]?[A-Z0-9]{4}){3,7}(?:[ -]?[A-Z0-9]{1,3})?\b")),
    # Lower case only with a digit in every group, to keep ordinary words ("fr12 pour cela vous").
    ("IBAN_SHAPE", re.compile(r"\b[a-z]{2}\d{2}(?:[ -]?(?=[a-z0-9]*\d)[a-z0-9]{4}){3,7}(?:[ -]?[a-z0-9]{1,3})?\b")),
    ("PHONE_SHAPE", re.compile(r"(?<![\w.+-])(?:(?:\+|00)\d(?:[ .()\-]{0,2}\d){8,14}|0[1-9](?:[ .()\-]?\d){8})(?!\w|[.-]\d)")),
)
_IPV6_ENDPOINT = re.compile(r"\[[0-9A-Fa-f:.]+(?:%[\w.-]+)?\](?::[0-9]{1,5}(?!\w))?")
_IP_CANDIDATE = re.compile(r"(?<![\w.])(?:[0-9]{1,3}\.){3}[0-9]{1,3}(?!\w|\.\d)(?::[0-9]{1,5}(?!\w))?|(?<![\w:])[0-9A-Fa-f:]*:[0-9A-Fa-f:.]+(?:%[\w.-]+)?(?!\w)")


@dataclass(frozen=True)
class CleanedQuery:
    text: str
    original_sha256: str
    cleaned_sha256: str
    removed: tuple[tuple[str, int], ...]
    normalized: bool

    def receipt(self):
        """Metadata only; even the cleaned text can retain unknown secrets."""
        return {"protocol": PROTOCOL,
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
        value = match.group()
        address = value[1:value.index("]")] if value.startswith("[") else value
        if re.fullmatch(r"(?:[0-9]{1,3}\.){3}[0-9]{1,3}(?::[0-9]{1,5})?", value):
            # IPv4 with an optional port; leading zeros still designate an address.
            octets = value.split(":")[0].split(".")
            if any(int(o) > 255 for o in octets):
                return value
        else:
            try:
                ipaddress.ip_address(address)
            except ValueError:
                return value
        counts["NETWORK_ADDRESS"] = counts.get("NETWORK_ADDRESS", 0) + 1
        return " "

    text = _IPV6_ENDPOINT.sub(redact_address, text)
    text = " ".join(_IP_CANDIDATE.sub(redact_address, text).split())
    return CleanedQuery(text, hashlib.sha256(raw).hexdigest(),
                        hashlib.sha256(text.encode("utf-8")).hexdigest(),
                        tuple(sorted(counts.items())), normalized != query)
