# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : g070_tools.py
# Description : Outil text.stats instrumenté pour le banc de courses G070 (journal d'appels hors processus)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Importable by the spawned tool workers (module-level functions only).

Every execute/verify appends one fsynced line to $G070_DIR/calls.log: the count of real
executions is read from there, never from the runtime's own records. Controls (files):
  hold          execute waits while it exists (bounded 20 s), to keep a worker in the tool;
  cancel-at-end execute requests cancellation of its own mission just before returning
                (a deterministic "late receipt": the result exists, cancellation wins)."""
import json
import os
from pathlib import Path
import time

from eidolon_core.runtime import Limits, Runtime
from eidolon_core.store import Store
from eidolon_core.tools import Policy, Registry, Tool, source_for, text_stats, verify_stats


def _dir():
    return Path(os.environ["G070_DIR"])


def _log(kind):
    fd = os.open(_dir() / "calls.log", os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
    try:
        os.write(fd, f"{kind} {os.getpid()} {time.monotonic():.3f}\n".encode())
        os.fsync(fd)
    finally:
        os.close(fd)


def counted_stats(parameters, context):
    _log("exec-start")
    deadline = time.monotonic() + 20
    while (_dir() / "hold").exists() and time.monotonic() < deadline:
        time.sleep(0.02)
    result = text_stats(parameters, context)
    trigger = _dir() / "cancel-at-end"
    if trigger.exists():
        state, mission = json.loads(trigger.read_text())
        Store(state).request_cancel(mission)
    _log("exec-end")
    return result


def counted_verify(parameters, context, result):
    _log("verify")
    return verify_stats(parameters, context, result)


def runtime(state, *, seconds=10.0, checkpoint=None):
    tool = Tool("text.stats", "1", "none", source_for, counted_stats, counted_verify, "text-stats-recompute/1")
    return Runtime(Store(state), registry=Registry([tool]), policy=Policy(),
                   limits=Limits(call_seconds=seconds), checkpoint=checkpoint)


def calls():
    path = _dir() / "calls.log"
    lines = path.read_text().split("\n") if path.exists() else []
    kinds = [line.split()[0] for line in lines if line]
    return {k: kinds.count(k) for k in ("exec-start", "exec-end", "verify")}
