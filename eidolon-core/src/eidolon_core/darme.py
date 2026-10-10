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
from collections import OrderedDict
from datetime import datetime, timezone
from enum import Enum
MAX_EVENTS = 10000

def _safe(value, limit, allow_empty=False):
    if (not isinstance(value, str) or len(value) > limit or (not value and not allow_empty)
            or any(ord(c) < 32 or ord(c) == 127 or 0x80 <= ord(c) <= 0x9f for c in value)):
        raise ValueError('invalid event text')

def _instant(value):
    _safe(value, 64)
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        raise ValueError('invalid timestamp') from None
    if parsed.tzinfo is None:
        raise ValueError('timestamp must include timezone')
    return parsed.astimezone(timezone.utc)



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
        for value, limit, empty in ((self.event_id, 128, False), (self.source, 128, False),
                                    (self.category, 128, False), (self.subject, 256, True)):
            _safe(value, limit, empty)
        if not isinstance(self.severity, Severity):
            raise ValueError("severity must be Severity")
        _instant(self.observed_at)


class DarmeMonitor:
    """In-memory projection of trusted events; no authority to enforce changes."""

    def __init__(self, sources, max_events=MAX_EVENTS):
        sources = list(sources)
        if not sources or len(set(sources)) != len(sources):
            raise ValueError("unique named sources required")
        for source in sources:
            _safe(source, 128)
        if type(max_events) is not int or not 1 <= max_events <= MAX_EVENTS:
            raise ValueError("invalid event capacity")
        self.sources = frozenset(sources)
        self.max_events = max_events
        self.healthy = {source: False for source in self.sources}
        self.events = OrderedDict()
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
        if event.event_id not in self.events and len(self.events) >= self.max_events:
            raise OverflowError("DARME_EVENT_CAPACITY: ingest paused; storage required")
        self.events[event.event_id] = event

    def acknowledge(self, event_id):
        if event_id not in self.events:
            raise ValueError("unknown event")
        self.acknowledged.add(event_id)

    def snapshot(self):
        active = [e for e in self.events.values()
                  if e.severity in (Severity.WARNING, Severity.CRITICAL)
                  and e.event_id not in self.acknowledged]
        visibility = "complete" if all(self.healthy.values()) else "partial"
        badge = (Badge.RED if active else Badge.BLUE if self.intervention else
                 Badge.GREY if visibility == "partial" else Badge.GOLD)
        return {
            "schema": "eidolon-darme-status/1",
            "badge": badge.value,
            "visibility": visibility,
            "sources": dict(sorted(self.healthy.items())),
            "unacknowledged_alerts": len(active),
            "intervention": self.intervention,
            "events": [
                {"event_id": e.event_id, "source": e.source, "category": e.category,
                 "severity": e.severity.value, "observed_at": e.observed_at,
                 "subject": e.subject, "acknowledged": e.event_id in self.acknowledged}
                for e in sorted(self.events.values(), key=lambda e: (_instant(e.observed_at), e.event_id))
            ],
            "enforcement_enabled": False,
            "authorizes_execution": False,
        }
