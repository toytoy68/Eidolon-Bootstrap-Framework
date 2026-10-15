# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : maintenance_observations.py
# Description : Normalisation pure des observations hôte pour les ticks explicites de maintenance (Claude, G236-8)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Pure normalisation of host observations into the keyword arguments of Memory ``IndexMaintenance.tick``.

No sensor, no service, no runner wiring: the host passes what it measured, with provenance and dates. The
output is conservative by construction. An unknown activity or boot time counts as "just now", which defers
the work. An unknown or stale load is never ``load_ok``. A date without a time zone, in the future beyond
the skew, or not finite is refused, never guessed.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import math
import re

MAX_SKEW = timedelta(seconds=60)
_SOURCE = re.compile(r"[a-z][a-z0-9._-]{0,63}\Z")


class ObservationRefused(ValueError):
    """The host observation cannot be trusted; no tick should run."""


@dataclass(frozen=True)
class TickObservation:
    at: datetime
    last_activity: datetime
    boot_at: datetime
    load_ok: bool
    notes: tuple

    def tick_kwargs(self):
        return dict(at=self.at, last_activity=self.last_activity, boot_at=self.boot_at, load_ok=self.load_ok)


def _aware(value, name):
    if isinstance(value, str):
        if not 20 <= len(value) <= 40:
            raise ObservationRefused(f"invalid {name}")
        try:
            value = datetime.fromisoformat(value)
        except ValueError:
            raise ObservationRefused(f"invalid {name}") from None
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ObservationRefused(f"{name} needs a time zone")
    return value.astimezone(timezone.utc)


def _optional_past(value, name, at, notes):
    if value is None:
        notes.append(f"{name.upper()}_UNKNOWN")
        return at                                          # unknown = just now: the window will defer
    moment = _aware(value, name)
    if moment > at + MAX_SKEW:
        raise ObservationRefused(f"{name} is in the future")
    return min(moment, at)


def normalize_host_observation(raw, *, max_load_age=timedelta(seconds=120)):
    """raw: {"source", "at", "last_activity"?, "boot_at"?, "load"?: {"observed_at", "ratio", "limit"}}.

    ``load.ratio`` is the host's own load measure (for example 1-minute load / CPU count) and ``limit`` its
    accepted ceiling; both are host policy, none is invented here.
    """
    if not isinstance(raw, dict) or not raw.keys() <= {"source", "at", "last_activity", "boot_at", "load"}:
        raise ObservationRefused("invalid host observation")
    source = raw.get("source")
    if type(source) is not str or _SOURCE.fullmatch(source) is None:
        raise ObservationRefused("invalid observation source")
    if not isinstance(max_load_age, timedelta) or max_load_age <= timedelta(0):
        raise ObservationRefused("invalid load freshness limit")
    at = _aware(raw.get("at"), "at")
    notes = []
    last_activity = _optional_past(raw.get("last_activity"), "last_activity", at, notes)
    boot_at = _optional_past(raw.get("boot_at"), "boot_at", at, notes)
    load = raw.get("load")
    load_ok = False
    if load is None:
        notes.append("LOAD_UNKNOWN")
    else:
        if not isinstance(load, dict) or load.keys() != {"observed_at", "ratio", "limit"}:
            raise ObservationRefused("invalid load observation")
        observed = _aware(load["observed_at"], "load.observed_at")
        ratio, limit = load["ratio"], load["limit"]
        if any(type(v) not in (int, float) or not math.isfinite(v) or v < 0 for v in (ratio, limit)) or limit == 0:
            raise ObservationRefused("invalid load values")
        if observed > at + MAX_SKEW:
            raise ObservationRefused("load observation is in the future")
        if at - observed > max_load_age:
            notes.append("LOAD_STALE")
        else:
            load_ok = ratio <= limit
            if not load_ok:
                notes.append("LOAD_HIGH")
    return TickObservation(at, last_activity, boot_at, load_ok, tuple(notes))
