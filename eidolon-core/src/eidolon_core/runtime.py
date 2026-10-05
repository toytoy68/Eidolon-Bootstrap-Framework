# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : runtime.py
# Description : Exécution séquentielle, vérification et reprise des missions
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

"""One agent, sequential execution, explicit uncertain-effect reconciliation."""
from dataclasses import dataclass
import math

from .contracts import ContractError, digest, parse_plan, snapshot, validate_context
from .memory import SyntheticMemory
from .model import DeterministicModel
from .store import TERMINAL
from .tools import Policy, default_registry
from .worker import CallFailure, invoke


@dataclass(frozen=True)
class Limits:
    call_seconds: float = 10.0

    def __post_init__(self):
        if (type(self.call_seconds) not in (int, float) or not math.isfinite(self.call_seconds)
                or not 0 < self.call_seconds <= 300):
            raise ValueError("call timeout must be finite and within (0, 300] seconds")


class Runtime:
    def __init__(self, store, *, model=None, memory=None, registry=None, policy=None,
                 limits=None, checkpoint=None):
        self.store = store
        self.model = model or DeterministicModel()
        self.memory = memory or SyntheticMemory()
        self.registry = registry or default_registry()
        self.policy = policy or Policy()
        self.limits = limits or Limits()
        self.checkpoint = checkpoint or (lambda _: None)

    def configuration(self):
        return {"model": self.model.model_id, "memory": self.memory.provider_id,
                "memory_root": getattr(self.memory, "root", None),
                "policy": self.policy.manifest(), "tools": self.registry.manifest(),
                "call_seconds": self.limits.call_seconds}

    def create(self, request):
        return self.store.create(request, self.configuration())

    def _save(self, m, kind, detail=None):
        self.store.save(m, kind, detail)
        self.checkpoint(kind)  # Fault injection only; no user/model-controlled hook.

    def _stop(self, m, status, code, message):
        m.update(status=status, error={"code": code, "message": message}, result=None)
        self._save(m, status, {"error": m["error"]})
        return m

    def _cancelled(self, m):
        return self.store.get(m["id"])["cancel_requested"]

    def _invoke(self, m, function, *args):
        return invoke(function, args, timeout=self.limits.call_seconds,
                      cancelled=lambda: self._cancelled(m))

    def _preflight(self, m):
        # Validate ALL steps before any tool is run, and again after a restart.
        for step in m["plan"]["steps"]:
            tool = self.registry.get(step["tool"])
            if not self.policy.allows(tool):
                raise ContractError("POLICY_DENIED: " + step["tool"])
            tool.validate(step["parameters"], m["context"])

    def run(self, identity):
        with self.store.lock(identity):
            m = self.store.get(identity)
            if m["status"] in TERMINAL or m["status"] == "REVIEW_REQUIRED":
                return m
            if m["phase"] == "EXECUTING":
                return self._stop(m, "REVIEW_REQUIRED", "UNKNOWN_EFFECT",
                                  "interrupted call: reconcile before any retry")
            if self._cancelled(m):
                return self._stop(m, "CANCELLED", "CANCELLED", "cancellation requested")
            if m["configuration"] != self.configuration():
                return self._stop(m, "BLOCKED", "CONFIGURATION_CHANGED",
                                  "restore the mission configuration or create a new mission")
            m.update(status="RUNNING", error=None)
            self._save(m, "RESUMED")
            if m["context"] is None:
                m["phase"] = "RECALL"
                self._save(m, "RECALL_STARTED")
                try:
                    m["context"] = validate_context(self._invoke(m, self.memory.recall, m["request"]))
                except (CallFailure, ContractError, TypeError, ValueError) as exc:
                    status = "CANCELLED" if self._cancelled(m) else "BLOCKED"
                    return self._stop(m, status, "MEMORY_UNAVAILABLE", str(exc))
                m["phase"] = "PLAN"
                self._save(m, "CONTEXT_SAVED", {"context_sha256": digest(m["context"])})
            if m["plan"] is None:
                try:
                    if m["model_output"] is None:
                        m["model_output"] = self._invoke(m, self.model.propose, m["request"], m["context"])
                        self._save(m, "MODEL_OUTPUT_SAVED")
                    m["plan"] = parse_plan(m["model_output"])
                except (CallFailure, ContractError) as exc:
                    status = "CANCELLED" if self._cancelled(m) else "FAILED"
                    return self._stop(m, status, "MODEL_INVALID", str(exc))
                m["progress"]["total"] = len(m["plan"]["steps"])
                m["phase"] = "READY"
                self._save(m, "PLAN_SAVED")
            try:
                self._preflight(m)
            except (ContractError, ValueError, TypeError) as exc:
                return self._stop(m, "BLOCKED", "PREFLIGHT_REFUSED", str(exc))
            for index, step in enumerate(m["plan"]["steps"]):
                tool = self.registry.get(step["tool"])
                call = m["calls"][index] if index < len(m["calls"]) else None
                if call and call["status"] == "VERIFIED":
                    continue
                if self._cancelled(m):
                    return self._stop(m, "CANCELLED", "CANCELLED", "cancellation requested")
                if call is None:
                    call = {"id": m["id"] + "/" + step["id"], "step": snapshot(step),
                            "tool_version": tool.version, "verifier": tool.verifier_id,
                            "attempt": 1, "status": "PREPARED", "output": None,
                            "context_sha256": digest(m["context"]), "receipt_origin": "worker"}
                    m["calls"].append(call)
                if call["status"] == "PREPARED":
                    m["phase"] = "EXECUTING"
                    call["status"] = "STARTED"
                    self._save(m, "CALL_STARTED", {"call_id": call["id"], "attempt": call["attempt"]})
                    try:
                        output = self._invoke(m, tool.execute, step["parameters"], m["context"])
                    except CallFailure as exc:
                        return self._stop(m, "REVIEW_REQUIRED", exc.code,
                                          str(exc) + "; effect unknown, no automatic retry")
                    self.checkpoint("TOOL_RETURNED")
                    call.update(output=output, status="RETURNED", output_sha256=digest(output))
                    m["phase"] = "VERIFY"
                    self._save(m, "RESULT_SAVED", {"call_id": call["id"], "output_sha256": call["output_sha256"]})
                if call["status"] != "RETURNED":
                    return self._stop(m, "REVIEW_REQUIRED", "INVALID_CALL_STATE", "call needs review")
                try:
                    verified = self._invoke(m, tool.verify, step["parameters"], m["context"], call["output"])
                except CallFailure as exc:
                    status = "CANCELLED" if self._cancelled(m) else "BLOCKED"
                    return self._stop(m, status, "VERIFICATION_UNAVAILABLE", str(exc))
                if verified is not True:
                    return self._stop(m, "FAILED", "VERIFICATION_FAILED", "output does not match expected result")
                call["status"] = "VERIFIED"
                m["progress"]["completed"] = index + 1
                m["phase"] = "READY"
                self._save(m, "RESULT_VERIFIED", {"call_id": call["id"], "verifier": tool.verifier_id})
            m.update(status="SUCCEEDED", phase="DONE", error=None,
                     result={"summary": "Statistiques vérifiées sur les extraits conservés.",
                             "evidence": snapshot(m["calls"]), "sources": snapshot(m["context"]),
                             "limits": ["Text statistics do not confirm source truth or semantic completeness.",
                                        "Source epistemic labels and review requirements remain unchanged."]})
            self._save(m, "SUCCEEDED")
            return m

    def cancel(self, identity):
        self.store.request_cancel(identity)
        # Request is durable even if another process holds the execution lock.
        from .store import Busy
        try:
            return self.run(identity)
        except Busy:
            return self.store.get(identity)

    def reconcile(self, identity, *, decision, actor, reason, output=None):
        if (not isinstance(actor, str) or not actor.strip() or len(actor) > 200
                or not isinstance(reason, str) or not reason.strip() or len(reason) > 4000):
            raise ValueError("explicit reconciliation actor and reason required")
        if decision not in {"no-effect", "observed-result"}:
            raise ValueError("unknown reconciliation decision")
        with self.store.lock(identity):
            m = self.store.get(identity)
            if m["status"] != "REVIEW_REQUIRED" or not m["calls"]:
                raise ValueError("mission has no uncertain call to reconcile")
            if m["configuration"] != self.configuration():
                raise ValueError("reconciliation requires the original configuration")
            call = m["calls"][-1]
            if call["status"] != "STARTED":
                raise ValueError("only an interrupted started call can be reconciled")
            detail = {"decision": decision, "actor": actor, "reason": reason,
                      "call_id": call["id"], "attempt": call["attempt"]}
            if decision == "no-effect":
                if output is not None:
                    raise ValueError("no-effect does not accept output")
                call.update(status="PREPARED", attempt=call["attempt"] + 1)
                m["phase"] = "READY"
            else:
                call.update(status="RETURNED", output=snapshot(output),
                            output_sha256=digest(output), receipt_origin="human_reconciliation")
                detail["output_sha256"] = call["output_sha256"]
                m["phase"] = "VERIFY"
            m.update(status="BLOCKED", error={"code": "RECONCILED", "message": "explicit resume required"})
            self._save(m, "RECONCILED", detail)
            return m
