# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : diagnostics.py
# Description : Services synthétiques observés et vérifiés sans réseau
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

"""A pure fixture provider, never a connector to user machines."""
from dataclasses import dataclass
from datetime import datetime, timezone
import uuid

from .contracts import ContractError, digest
from .targets import Catalog
from .tools import Policy, Registry, Tool

SERVICE_TOOL = "service.observe.synthetic"
SERVICE_CAPABILITY = "service.observe"
FIXTURES = (("sim-memory", "UP"), ("sim-nas", "DOWN"), ("sim-offline", "UNREACHABLE"))


def demo_catalog():
    return Catalog.from_config({"schema": "targets/1", "targets": [
        {"id": identity, "name": "Service synthétique " + identity, "kind": "lan_service",
         "aliases": aliases, "destination": "fixture://" + identity,
         "capabilities": [{"name": SERVICE_CAPABILITY, "effect": "none"}]}
        for identity, aliases in (("sim-memory", ["mémoire", "service"]),
                                  ("sim-nas", ["nas", "service"]), ("sim-offline", ["offline"]))]})


@dataclass(frozen=True)
class SyntheticProbe:
    """Fixed service states, real observation timestamp, no external I/O."""
    max_age_seconds: int = 60

    def __post_init__(self):
        if type(self.max_age_seconds) is not int or not 1 <= self.max_age_seconds <= 300:
            raise ContractError("observation age bound must be 1..300 seconds")

    def validate(self, parameters, context):
        if (not isinstance(parameters, dict) or set(parameters) != {"target"}
                or not isinstance(parameters["target"], str) or parameters["target"] not in dict(FIXTURES)):
            raise ContractError("synthetic observation requires one known fixture target id")

    def execute(self, parameters, context):
        self.validate(parameters, context)
        return {"target_id": parameters["target"], "state": dict(FIXTURES)[parameters["target"]],
                "observed_at": datetime.now(timezone.utc).isoformat(),
                "observation_id": str(uuid.uuid4()), "source": "synthetic-service/1", "synthetic": True}

    def verify(self, parameters, context, result):
        self.validate(parameters, context)
        if not isinstance(result, dict) or set(result) != {
                "target_id", "state", "observed_at", "observation_id", "source", "synthetic"}:
            return False
        if (result["target_id"] != parameters["target"] or result["synthetic"] is not True
                or result["source"] != "synthetic-service/1"
                or result["state"] != dict(FIXTURES)[parameters["target"]]):
            return False
        try:
            uuid.UUID(result["observation_id"])
            at = datetime.fromisoformat(result["observed_at"])
            if at.tzinfo is None:
                return False
            age = (datetime.now(timezone.utc) - at).total_seconds()
        except (ValueError, TypeError, AttributeError):
            return False
        return 0 <= age <= self.max_age_seconds

    def tool(self):
        version = digest({"fixtures": FIXTURES, "max_age_seconds": self.max_age_seconds})
        return Tool(SERVICE_TOOL, version, "none", self.validate, self.execute, self.verify,
                    "synthetic-observation/1/" + str(self.max_age_seconds))


def synthetic_runtime(store, *, catalog=None, allowed_targets=None, model=None, **kwargs):
    # Import locally to keep the pure provider independent of orchestration.
    from .model import DiagnosticModel
    from .runtime import Runtime
    allowed = tuple(identity for identity, _ in FIXTURES) if allowed_targets is None else tuple(allowed_targets)
    return Runtime(store, model=model or DiagnosticModel(), catalog=catalog or demo_catalog(),
                   registry=Registry([SyntheticProbe().tool()]),
                   policy=Policy(allowed_tools=(SERVICE_TOOL,),
                                 target_grants=tuple((identity, SERVICE_CAPABILITY) for identity in allowed)),
                   **kwargs)
