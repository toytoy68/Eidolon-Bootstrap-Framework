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
from .objectives import DIAGNOSTIC, RESTART, TARGETED, bind, check_contract, check_plan, diagnostic_request, restart_parameters
from .store import Busy, TERMINAL
from .tools import Policy, default_registry
from .worker import CallFailure, _read_receipt, attempt_receipt_path, invoke


@dataclass(frozen=True)
class Limits:
    call_seconds: float = 10.0

    def __post_init__(self):
        if (type(self.call_seconds) not in (int, float) or not math.isfinite(self.call_seconds)
                or not 0 < self.call_seconds <= 300):
            raise ValueError("call timeout must be finite and within (0, 300] seconds")


class Runtime:
    def __init__(self, store, *, model=None, memory=None, registry=None, policy=None,
                 limits=None, checkpoint=None, catalog=None):
        self.catalog = catalog
        self.store = store
        self.model = model or DeterministicModel()
        self.memory = memory or SyntheticMemory()
        self.registry = registry or default_registry()
        self.policy = policy or Policy()
        self.limits = limits or Limits()
        self.checkpoint = checkpoint or (lambda _: None)

    def configuration(self):
        config = {"model": self.model.model_id, "memory": self.memory.provider_id,
                "memory_root": getattr(self.memory, "root", None),
                "policy": self.policy.manifest(), "tools": self.registry.manifest(),
                "call_seconds": self.limits.call_seconds}
        if self.catalog is not None:
            config["targets"] = self.catalog.manifest()
        return config

    def create(self, request):
        return self.store.create(request, self.configuration())

    def create_diagnostic(self, target_reference):
        if self.catalog is None or not isinstance(target_reference, str):
            raise ContractError("diagnostic requires a configured catalog and a target reference")
        return self.store.create(diagnostic_request(target_reference), self.configuration(),
                                 intent={"kind": DIAGNOSTIC, "target_reference": target_reference})

    def _save(self, m, kind, detail=None):
        self.store.save(m, kind, detail)
        self.checkpoint(kind)  # Fault injection only; no user/model-controlled hook.

    def _stop(self, m, status, code, message):
        m.update(status=status, error={"code": code, "message": message}, result=None)
        self._save(m, status, {"error": m["error"]})
        return m

    def _cancelled(self, m):
        return self.store.cancel_requested(m["id"])

    def _invoke(self, m, function, *args, call=None, verification=False):
        def spawned(worker):
            call["worker"] = worker
            self._save(m, "WORKER_SPAWNED", {"call_id": call["id"],
                                            "attempt": call["attempt"], **worker})
        lease = (self.store.worker_lease_path(m["id"], call["id"], call["attempt"])
                 if call is not None else None)
        return invoke(function, args, timeout=self.limits.call_seconds,
                      # Only the trusted, read-only verifier may finish after
                      # cancellation. It remains bounded by the call deadline.
                      cancelled=lambda: False if verification else self._cancelled(m), lease_path=lease,
                      on_started=spawned if call is not None else None)

    def _retain_receipt(self, m, call, receipt, *, late=False, recovered=False):
        key = "late_receipt" if late else ("recovered_receipt" if receipt["ok"] else "error_receipt")
        if call.get(key) == receipt:
            return
        call[key] = receipt
        call[key + "_sha256"] = digest(receipt)
        self._save(m, "RECOVERED_RECEIPT_SAVED" if recovered else key.upper() + "_SAVED",
                   {"call_id": call["id"], "attempt": call["attempt"],
                    "receipt_kind": key, "receipt_sha256": call[key + "_sha256"]})

    @staticmethod
    def _reset_attempt(call, detail):
        keys = ("attempt", "worker", "worker_protocol", "approval_sha256", "error_receipt", "error_receipt_sha256",
                "late_receipt", "late_receipt_sha256", "recovered_receipt", "recovered_receipt_sha256")
        prior = {key: call[key] for key in keys if key in call}
        prior["reconciliation"] = detail
        call.setdefault("attempt_history", []).append(prior)
        for key in keys:
            if key != "attempt":
                call.pop(key, None)
        call.update(status="PREPARED", attempt=call["attempt"] + 1, worker=None)

    def _prepare(self, m):
        """Optional trusted preparation before planning; return a stopped mission."""
        return None

    def _authorize_call(self, m, call):
        """Optional approval gate. Consumption is persisted with CALL_STARTED."""
        return None

    def _check_reconciliation(self, m, call, decision, output):
        """Optional provider-specific check while the worker lease is held."""
        return None

    def _preflight(self, m):
        # Validate ALL steps before any tool is run, and again after a restart.
        for step in m["plan"]["steps"]:
            tool = self.registry.get(step["tool"])
            if not self.policy.allows(tool):
                raise ContractError("POLICY_DENIED: " + step["tool"])
            tool.validate(step["parameters"], m["context"])
        check_plan(m)
        if m["objective"]["kind"] in TARGETED:
            objective = m["objective"]
            found = self.catalog.lookup(objective["target_id"], objective["capability"])
            tool = self.registry.get(objective["tool"])
            if found.status != "FOUND" or not self.policy.allows_target(tool, found.target, found.capability):
                raise ContractError("TARGET_POLICY_DENIED: explicit target/capability grant required")

    def run(self, identity):
        with self.store.lock(identity):
            m = self.store.get(identity)
            try:
                return self._run(m)
            except Busy:
                raise
            except Exception as exc:
                # Discard any partly mutated, possibly unserializable object.
                # Only the durable phase decides if another attempt is safe.
                m = self.store.get(identity)
                if m["status"] in TERMINAL:
                    raise
                m.update(status="REVIEW_REQUIRED" if m["phase"] == "EXECUTING" else "BLOCKED",
                         result=None, error={"code": "INTERNAL_ERROR", "message": type(exc).__name__})
                self.store.save(m, "INTERNAL_ERROR", {"error": m["error"]})
                return m

    def _run(self, m):
        if m["status"] in TERMINAL or m["status"] == "REVIEW_REQUIRED":
            return m
        if m["phase"] == "EXECUTING":
            return self._stop(m, "REVIEW_REQUIRED", "UNKNOWN_EFFECT",
                              "interrupted call: reconcile before any retry")
        pending_verification = (m['phase'] == 'VERIFY' and m['calls']
                                and m['calls'][-1]['status'] == 'RETURNED')
        if self._cancelled(m) and not pending_verification:
            return self._stop(m, "CANCELLED", "CANCELLED", "cancellation requested")
        if "objective" not in m:
            return self._stop(m, "BLOCKED", "MISSION_CONTRACT_REQUIRED",
                              "legacy mission: retain evidence and create a new contracted mission")
        try:
            check_contract(m)
        except ContractError as exc:
            return self._stop(m, "BLOCKED", "MISSION_CONTRACT_INVALID", str(exc))
        diagnostic = m["objective"]["kind"] in TARGETED
        if diagnostic and m["objective"]["selection_status"] != "FOUND":
            return self._stop(m, "BLOCKED", m["objective"]["selection_status"],
                              "select one configured target with the required capability")
        if m["objective"]["kind"] is None:
            return self._stop(m, "BLOCKED", "MISSION_UNSUPPORTED",
                              "clarification required: use a documented typed mission")
        if m["configuration"] != self.configuration():
            return self._stop(m, "BLOCKED", "CONFIGURATION_CHANGED",
                              "restore the mission configuration or create a new mission")
        # Explicit resume may retry an empty recall; no plan/tool existed.
        if (not diagnostic and m["context"] is not None and not m["context"]["items"]
                and m["plan"] is None and not m["calls"]):
            m["context"] = None
            m["objective"].update(required_references=None, context_sha256=None)
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
            m["objective"] = bind(m["objective"], m["context"])
            m["phase"] = "PLAN"
            self._save(m, "CONTEXT_SAVED", {"context_sha256": digest(m["context"])})
        if not diagnostic and not m["context"]["items"]:
            return self._stop(m, "BLOCKED", "MEMORY_EMPTY",
                              "no recalled evidence; explicit resume can retry recall")
        prepared = self._prepare(m)
        if prepared is not None:
            return prepared
        if m["plan"] is None:
            try:
                if m["model_output"] is None:
                    model_context = snapshot(m["context"])
                    if diagnostic:
                        # Overwrite any similarly named untrusted memory field.
                        model_context["_core_mission"] = snapshot(m["objective"])
                        if m["objective"]["kind"] == RESTART:
                            model_context["_core_action"] = restart_parameters(m)
                    m["model_output"] = self._invoke(m, self.model.propose, m["request"], model_context)
                    self._save(m, "MODEL_OUTPUT_SAVED")
                m["plan"] = parse_plan(m["model_output"])
            except CallFailure as exc:
                invalid = exc.code == "INVALID_RESPONSE"
                status = "CANCELLED" if self._cancelled(m) else ("FAILED" if invalid else "BLOCKED")
                return self._stop(m, status, "MODEL_INVALID" if invalid else "MODEL_UNAVAILABLE", str(exc))
            except ContractError as exc:
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
                if call.get("output_sha256") != digest(call["output"]):
                    return self._stop(m, "FAILED", "EVIDENCE_MISMATCH", "verified output fingerprint changed")
                continue
            if self._cancelled(m) and not (call and call['status'] == 'RETURNED'):
                return self._stop(m, "CANCELLED", "CANCELLED", "cancellation requested")
            if call is None:
                call = {"id": m["id"] + "/" + step["id"], "step": snapshot(step),
                        "tool_version": tool.version, "verifier": tool.verifier_id,
                        "attempt": 1, "status": "PREPARED", "output": None,
                        "context_sha256": digest(m["context"]), "receipt_origin": "worker"}
                if diagnostic:
                    call["target_binding"] = {key: m["objective"][key]
                                              for key in ("target_id", "capability", "catalog_sha256")}
                m["calls"].append(call)
            if call["status"] == "PREPARED":
                gated = self._authorize_call(m, call)
                if gated is not None:
                    return gated
                m["phase"] = "EXECUTING"
                call.update(status="STARTED", worker_protocol="lease-v2", worker=None)
                self._save(m, "CALL_STARTED", {"call_id": call["id"], "attempt": call["attempt"]})
                try:
                    output = self._invoke(m, tool.execute, step["parameters"], m["context"], call=call)
                except CallFailure as exc:
                    if exc.receipt is not None:
                        self._retain_receipt(m, call, exc.receipt, late=exc.code in {"TIMEOUT", "CANCELLED"})
                    if exc.authorized is False:
                        self._reset_attempt(call, {"decision": "not-authorized", "code": exc.code})
                        m["phase"] = "READY"
                        status = "CANCELLED" if self._cancelled(m) else "BLOCKED"
                        return self._stop(m, status, exc.code, str(exc) + "; tool was not authorized")
                    return self._stop(m, "REVIEW_REQUIRED", exc.code,
                                      str(exc) + "; effect unknown, no automatic retry")
                self.checkpoint("TOOL_RETURNED")
                call.update(output=output, status="RETURNED", output_sha256=digest(output))
                m["phase"] = "VERIFY"
                self._save(m, "RESULT_SAVED", {"call_id": call["id"], "output_sha256": call["output_sha256"]})
            if call["status"] != "RETURNED":
                return self._stop(m, "REVIEW_REQUIRED", "INVALID_CALL_STATE", "call needs review")
            try:
                verified = self._invoke(m, tool.verify, step["parameters"], m["context"], call["output"],
                                        verification=True)
            except CallFailure as exc:
                # A returned result still needs a verdict. Retain a resumable
                # verification even when an earlier stop request is present.
                return self._stop(m, "BLOCKED", "VERIFICATION_UNAVAILABLE", str(exc))
            if verified is not True:
                return self._stop(m, "FAILED", "VERIFICATION_FAILED", "output does not match expected result")
            if call.get("output_sha256") != digest(call["output"]):
                return self._stop(m, "FAILED", "EVIDENCE_MISMATCH", "output fingerprint changed")
            call["status"] = "VERIFIED"
            m["progress"]["completed"] = index + 1
            m["phase"] = "READY"
            self._save(m, "RESULT_VERIFIED", {"call_id": call["id"], "verifier": tool.verifier_id})
        if self._cancelled(m):
            return self._stop(m, "CANCELLED", "CANCELLED", "cancellation requested; received results verified")
        m.update(status="SUCCEEDED", phase="DONE", error=None,
                 result={"summary": "Statistiques vérifiées sur les extraits conservés.",
                         "evidence": [{"call_id": c["id"], "attempt": c["attempt"],
                                       "output_sha256": c["output_sha256"], "verifier": c["verifier"],
                                       "receipt_origin": c["receipt_origin"]}
                                      for c in m["calls"]],
                         "sources": snapshot(m["context"]),
                         "limits": ["Coverage is limited to the retained recall snapshot, not the whole memory corpus.",
                                    "Text statistics do not confirm source truth or semantic completeness.",
                                    "Source epistemic labels and review requirements remain unchanged."]})
        if m["objective"]["kind"] == RESTART:
            m["result"].update(summary="Redémarrage simulé vérifié : " + m["objective"]["target_id"],
                               simulation=snapshot(m["calls"][0]["output"]),
                               proposal_sha256=m["proposal"]["sha256"],
                               limits=["Local synthetic SQLite state only; no real service was contacted.",
                                       "Actor is an audit label, not an authenticated identity.",
                                       "Receipt proves a past transition; current health can change.",
                                       "Memory epistemic labels remain unchanged."])
        elif diagnostic:
            observation = m["calls"][0]["output"]
            m["result"]["summary"] = ("Diagnostic synthétique vérifié : "
                                      + observation["target_id"] + " = " + observation["state"])
            m["result"]["observation"] = snapshot(observation)
            m["result"]["target"] = snapshot(m["calls"][0]["target_binding"])
            m["result"]["limits"] = ["Synthetic fixture only; no machine was contacted.",
                                      "Observation is dated, not a guarantee of current service health.",
                                      "Memory epistemic labels remain unchanged."]
        self._save(m, "SUCCEEDED")
        return m

    def cancel(self, identity):
        self.store.request_cancel(identity)
        # Request is durable even if another process holds the execution lock.
        try:
            return self.run(identity)
        except Busy:
            return self.store.get(identity)

    def _abandon_unverified(self, m, *, decision, actor, reason, output):
        """Close a returned result whose verification stays unavailable; caller holds the lock.

        The RETURNED call, its output, fingerprint and origin are kept as they are:
        abandoning is neither a verification nor a claim that nothing happened.
        No model, memory, tool or verifier is called.
        """
        if decision != "abandon":
            raise ValueError("an unverified returned result is verified by run or explicitly abandoned")
        if output is not None:
            raise ValueError("abandon does not accept output")
        call = m["calls"][-1]
        detail = {"decision": "abandon", "actor": actor, "reason": reason,
                  "call_id": call["id"], "attempt": call["attempt"],
                  "result_state": "RETURNED_UNVERIFIED", "output_sha256": call.get("output_sha256")}
        m.update(status="ABANDONED", phase="DONE", result=None,
                 error={"code": "RESULT_UNVERIFIED", "message": "closed without verifying the returned result"})
        self._save(m, "ABANDONED", detail)
        return m

    def reconcile(self, identity, *, decision, actor, reason, output=None, confirm_no_effect=False):
        if (not isinstance(actor, str) or not actor.strip() or len(actor) > 200
                or not isinstance(reason, str) or not reason.strip() or len(reason) > 4000):
            raise ValueError("explicit reconciliation actor and reason required")
        snapshot({"actor": actor, "reason": reason})
        if type(confirm_no_effect) is not bool or (confirm_no_effect and decision != "no-effect"):
            raise ValueError("confirm_no_effect is only valid with no-effect")
        if decision not in {"no-effect", "observed-result", "use-receipt", "abandon"}:
            raise ValueError("unknown reconciliation decision")
        with self.store.lock(identity):
            m = self.store.get(identity)
            if (m["status"] == "BLOCKED" and m["phase"] == "VERIFY" and m["calls"]
                    and m["calls"][-1]["status"] == "RETURNED"):
                return self._abandon_unverified(m, decision=decision, actor=actor, reason=reason, output=output)
            if m["status"] != "REVIEW_REQUIRED" or not m["calls"]:
                raise ValueError("mission has no uncertain call to reconcile")
            call = m["calls"][-1]
            if call["status"] != "STARTED":
                raise ValueError("only an interrupted started call can be reconciled")
            detail = {"decision": decision, "actor": actor, "reason": reason,
                      "call_id": call["id"], "attempt": call["attempt"]}
            if decision == "abandon":
                if output is not None:
                    raise ValueError("abandon does not accept output")
                call.update(status="UNKNOWN", effect_unknown=True)
                m.update(status="ABANDONED", phase="DONE", result=None,
                         error={"code": "EFFECT_UNKNOWN", "message": "closed without resolving the effect"})
                self._save(m, "ABANDONED", detail)
                return m
            if m["configuration"] != self.configuration():
                raise ValueError("reconciliation requires the original configuration")
            with self.store.worker_quiescent(identity, call) as authorized:
                receipt = None
                saved = []
                for key in ("late_receipt", "error_receipt", "recovered_receipt"):
                    if key in call:
                        if call.get(key + "_sha256") != digest(call[key]):
                            raise ValueError("stored receipt fingerprint changed; review or abandon")
                        saved.append(call[key])
                if call.get("worker_protocol") == "lease-v2":
                    path = self.store.worker_lease_path(identity, call["id"], call["attempt"])
                    try:
                        receipt = _read_receipt(attempt_receipt_path(path))
                    except CallFailure as exc:
                        raise ContractError("stored attempt receipt invalid; review or abandon") from exc
                disk_receipt = receipt
                for item in saved:
                    if receipt is not None and digest(item) != digest(receipt):
                        raise ValueError("conflicting attempt receipts; review or abandon")
                    receipt = item
                if disk_receipt is not None:
                    self._retain_receipt(m, call, disk_receipt, recovered=True)
                detail["worker_authorized"] = authorized
                self._check_reconciliation(m, call, decision, output)
                if decision == "no-effect":
                    if output is not None:
                        raise ValueError("no-effect does not accept output")
                    if receipt is not None and receipt["ok"]:
                        raise ValueError("successful receipt exists: use-receipt or abandon")
                    if authorized is not False and not confirm_no_effect:
                        raise ValueError("execution authorized or unknown: explicit confirm_no_effect required after investigation")
                    detail["confirmed_no_effect"] = confirm_no_effect
                    self._reset_attempt(call, detail.copy())
                    m["phase"] = "READY"
                else:
                    if decision == "use-receipt":
                        if output is not None:
                            raise ValueError("use-receipt does not accept output")
                        if receipt is None or not receipt["ok"]:
                            raise ValueError("no successful stored receipt to verify")
                        output = receipt["value"]
                        origin = "worker_receipt_reconciliation"
                    else:
                        if receipt is not None and receipt["ok"] and digest(output) != digest(receipt["value"]):
                            raise ValueError("observed result conflicts with stored receipt; use-receipt or abandon")
                        origin = "human_reconciliation"
                    call.update(status="RETURNED", output=snapshot(output),
                                output_sha256=digest(output), receipt_origin=origin)
                    detail["output_sha256"] = call["output_sha256"]
                    detail["receipt_origin"] = origin
                    m["phase"] = "VERIFY"
                m.update(status="BLOCKED", error={"code": "RECONCILED", "message": "explicit resume required"})
                self._save(m, "RECONCILED", detail)
                return m
