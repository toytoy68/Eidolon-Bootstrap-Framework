# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : model.py
# Description : Modèle simulé déterministe interchangeable
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

from dataclasses import dataclass

from .contracts import encode, reference
from .memory import DEMO_REQUEST


@dataclass(frozen=True)
class DeterministicModel:
    """Fixture planner, deliberately not a general-purpose language model."""
    model_id: str = "deterministic-demo/1"

    def propose(self, request, context):
        if request != DEMO_REQUEST:
            raise ValueError("demo model only supports the documented synthetic mission")
        return encode({"version": 1, "steps": [
            {"id": f"stats-{i + 1}", "tool": "text.stats",
             "parameters": {"reference": reference(item)}}
            for i, item in enumerate(context["items"])
        ]})


@dataclass(frozen=True)
class DiagnosticModel:
    """Planner for an explicit synthetic mission, supplied by the runtime."""
    model_id: str = "deterministic-service-diagnostic/1"

    def propose(self, request, context):
        mission = context["_core_mission"]
        if mission["kind"] != "service_diagnostic.synthetic":
            raise ValueError("unsupported diagnostic intent")
        return encode({"version": 1, "steps": [{"id": "observe", "tool": mission["tool"],
                       "parameters": {"target": mission["target_id"]}}]})
