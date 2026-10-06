# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : actions.py
# Description : Approbation et orchestration des actions purement simulées
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

"""C-005a local simulation. Never enables a connector to real machines."""
from dataclasses import dataclass

from . import approvals
from .contracts import ContractError, digest, encode, snapshot
from .diagnostics import demo_catalog, FIXTURES
from .objectives import RESTART, check_contract, restart_request
from .runtime import Runtime
from .simulation import RESTART_TOOL, SimulatedServices
from .store import TERMINAL
from .targets import Catalog
from .tools import Policy, Registry
from .worker import CallFailure


def action_catalog():
    raw = demo_catalog().manifest()
    for target in raw["targets"]:
        target["capabilities"] = [{"name": "service.observe", "effect": "local_read"},
                                  {"name": RESTART_TOOL, "effect": "mutation"}]
    return Catalog.from_config(raw)


@dataclass(frozen=True)
class SimulationPolicy(Policy):
    policy_id: str = "local-synthetic-action-only/1"

    def allows(self, tool):
        return (tool is not None and tool.name == RESTART_TOOL and tool.name in self.allowed_tools
                and tool.effect == "mutation")

    def allows_target(self, tool, target, capability):
        return (self.allows(tool) and capability is not None and capability.name == RESTART_TOOL
                and capability.effect == "mutation" and (target.id, capability.name) in self.target_grants)

    def allows_observation(self, target):
        capability = target.capability("service.observe")
        return (capability is not None and capability.effect == "local_read"
                and (target.id, capability.name) in self.target_grants)

    def manifest(self):
        return {"id": self.policy_id, "allowed_tools": sorted(self.allowed_tools),
                "target_grants": sorted([list(g) for g in self.target_grants]),
                "scope": "synthetic-local-database-only", "requires_approval": [RESTART_TOOL]}


@dataclass(frozen=True)
class ActionModel:
    model_id: str = "deterministic-synthetic-action/1"

    def propose(self, request, context):
        return encode({"version": 1, "steps": [{"id": "restart", "tool": RESTART_TOOL,
                                                "parameters": context["_core_action"]}]})


class ActionRuntime(Runtime):
    def __init__(self, store, *, world=None, catalog=None, allowed_targets=None, model=None,
                 policy=None, registry=None, **kwargs):
        self.world = world or SimulatedServices.initialize(store.directory / "simulation.sqlite3")
        allowed = [identity for identity, _ in FIXTURES] if allowed_targets is None else list(allowed_targets)
        super().__init__(store, catalog=catalog or action_catalog(), model=model or ActionModel(),
                         registry=registry or Registry([self.world.tool()]),
                         policy=policy or SimulationPolicy(allowed_tools=(RESTART_TOOL,),
                             target_grants=tuple((identity, capability) for identity in allowed
                                                 for capability in ("service.observe", RESTART_TOOL))), **kwargs)

    def configuration(self):
        return {**super().configuration(), "action_simulation": self.world.manifest()}

    def create_restart(self, target_reference):
        if not isinstance(target_reference, str):
            raise ContractError("synthetic restart requires a target reference")
        return self.store.create(restart_request(target_reference), self.configuration(),
                                 intent={"kind": RESTART, "target_reference": target_reference})

    @staticmethod
    def condition(observation):
        return {k: observation[k] for k in ("target_id", "world_id", "state", "revision")}

    def _observe(self, m):
        target = self.catalog.get(m["objective"]["target_id"])
        if target is None or not self.policy.allows_observation(target):
            raise ContractError("OBSERVATION_POLICY_DENIED: synthetic target read permission required")
        observation = self._invoke(m, self.world.observe, target.id)
        if self._invoke(m, self.world.verify_observation, target.id, observation) is not True:
            raise ContractError("synthetic observation is malformed, stale or changed")
        return observation

    def _prepare(self, m):
        if m["objective"]["kind"] != RESTART or m.get("action_condition") is not None:
            return None
        try:
            observation = self._observe(m)
        except (ContractError, CallFailure) as exc:
            return self._stop(m, "CANCELLED" if self._cancelled(m) else "BLOCKED", "ACTION_OBSERVATION_UNAVAILABLE", str(exc))
        if observation["state"] != "DOWN":
            return self._stop(m, "BLOCKED", "ACTION_CONDITION_NOT_MET", "synthetic restart requires an observed DOWN service")
        m["action_condition"] = self.condition(observation)
        m["action_observation"] = snapshot(observation)
        self._save(m, "ACTION_CONDITION_SAVED", {"observation_sha256": digest(observation)})
        return None

    def _authorize_call(self, m, call):
        if m["objective"]["kind"] != RESTART:
            return None
        previous_sha = (m.get("proposal") or {}).get("sha256")
        try:
            proposal = approvals.prepare(m, call)
        except ContractError as exc:
            return self._stop(m, "BLOCKED", "APPROVAL_INVALID", str(exc))
        if proposal["sha256"] != previous_sha:
            self._save(m, "ACTION_PROPOSED", {"proposal_sha256": proposal["sha256"], "attempt": call["attempt"]})
        if proposal["status"] != "APPROVED":
            return self._stop(m, "BLOCKED", "APPROVAL_" + ("REQUIRED" if proposal["status"] == "PENDING" else proposal["status"]),
                              "inspect proposal; explicit decision and resume required")
        try:
            observation = self._observe(m)
        except (ContractError, CallFailure) as exc:
            return self._stop(m, "CANCELLED" if self._cancelled(m) else "BLOCKED", "ACTION_OBSERVATION_UNAVAILABLE", str(exc))
        m["last_condition_check"] = snapshot(observation)
        self._save(m, "ACTION_CONDITION_CHECKED", {"observation_sha256": digest(observation)})
        if self.condition(observation) != m["action_condition"]:
            return self._stop(m, "BLOCKED", "ACTION_PRECONDITION_CHANGED",
                              "synthetic state or revision changed; proposal retained, create a new mission after review")
        if self._cancelled(m):
            return self._stop(m, "CANCELLED", "CANCELLED", "cancellation requested before action")
        approvals.consume(m, call)
        return None

    def _check_reconciliation(self, m, call, decision, output):
        if m["objective"]["kind"] == RESTART and decision == "no-effect" and self.world.receipt(m["id"]) is not None:
            raise ContractError("simulation has a committed effect receipt; reconcile its result or abandon")

    def _prepare_decision(self, m, *, expected_sha256, decision, actor, reason):
        """Validate and change an in-memory copy; caller holds the mission lock."""
        if (m["status"] in TERMINAL | {"REVIEW_REQUIRED"} or self._cancelled(m)
                or m["objective"]["kind"] != RESTART or len(m["calls"]) != 1
                or m["calls"][0]["status"] != "PREPARED"):
            raise ContractError("mission is not awaiting an action decision")
        if m["configuration"] != self.configuration():
            raise ContractError("decision requires the original configuration")
        check_contract(m)
        self._preflight(m)
        entry = approvals.decide(m, m["calls"][0], expected_sha256=expected_sha256,
                                 decision=decision, actor=actor, reason=reason)
        m.update(status="BLOCKED", error={"code": "APPROVAL_" + m["proposal"]["status"],
                                          "message": "decision recorded; no tool executed"})
        return entry

    def decide(self, identity, *, expected_sha256, decision, actor, reason):
        with self.store.lock(identity):
            m = self.store.get(identity)
            entry = self._prepare_decision(m, expected_sha256=expected_sha256,
                                           decision=decision, actor=actor, reason=reason)
            self._save(m, "ACTION_DECISION", entry)
            return m
