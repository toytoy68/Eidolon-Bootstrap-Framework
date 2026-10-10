# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : darme.py
# Description : Etat et evaluation passive des evenements de securite
# ==========================================================
"""DARME v0.1: deterministic, passive, dependency-free security event assessment.

No packet capture, firewall manipulation, privileged command or network call.
Events must originate from trusted collectors; caller supplies the trust boundary.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import ipaddress
import json


class Severity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class Badge(str, Enum):
    GOLD = "gold"
    RED = "red"
    BLUE = "blue"
    GREY = "grey"


@dataclass(frozen=True)
class SecurityEvent:
    event_id: str
    source: str
    category: str
    severity: Severity
    observed_at: str
    subject: str = ""

    def __post_init__(self):
        if not self.event_id or len(self.event_id) > 128:
            raise ValueError("invalid event id")
        if not self.source or len(self.source) > 128:
            raise ValueError("invalid source")
        if not self.category or len(self.category) > 128:
            raise ValueError("invalid category")
        if len(self.subject) > 256:
            raise ValueError("subject too long")
        try:
            stamp = datetime.fromisoformat(self.observed_at.replace("Z", "+00:00"))
        except ValueError:
            raise ValueError("invalid timestamp") from None
        if stamp.tzinfo is None:
            raise ValueError("timestamp must include timezone")


class DarmeMonitor:
    """In-memory projection of trusted events; no authority to enforce changes."""

    def __init__(self, sources):
        self.sources = frozenset(sources)
        if not self.sources or any(not isinstance(s, str) or not s for s in self.sources):
            raise ValueError("at least one named source required")
        self.healthy = {source: False for source in self.sources}
        self.events = {}
        self.acknowledged = set()
        self.intervention = False

    def health(self, source, healthy):
        if source not in self.sources or type(healthy) is not bool:
            raise ValueError("invalid source health")
        self.healthy[source] = healthy

    def ingest(self, event):
        if not isinstance(event, SecurityEvent) or event.source not in self.sources:
            raise ValueError("untrusted or invalid event")
        if event.event_id in self.events and self.events[event.event_id] != event:
            raise ValueError("event id collision")
        self.events[event.event_id] = event

    def acknowledge(self, event_id):
        if event_id not in self.events:
            raise ValueError("unknown event")
        self.acknowledged.add(event_id)

    def snapshot(self):
        active = [e for e in self.events.values()
                  if e.severity in (Severity.WARNING, Severity.CRITICAL)
                  and e.event_id not in self.acknowledged]
        badge = (Badge.GREY if not all(self.healthy.values()) else
                 Badge.RED if active else
                 Badge.BLUE if self.intervention else Badge.GOLD)
        return {
            "schema": "eidolon-darme-status/1",
            "badge": badge.value,
            "sources": dict(sorted(self.healthy.items())),
            "unacknowledged_alerts": len(active),
            "intervention": self.intervention,
            "events": [
                {"event_id": e.event_id, "source": e.source, "category": e.category,
                 "severity": e.severity.value, "observed_at": e.observed_at,
                 "subject": e.subject, "acknowledged": e.event_id in self.acknowledged}
                for e in sorted(self.events.values(), key=lambda e: (e.observed_at, e.event_id))
            ],
            "enforcement_enabled": False,
        }
