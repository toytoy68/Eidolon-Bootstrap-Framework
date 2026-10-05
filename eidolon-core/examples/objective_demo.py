# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : objective_demo.py
# Description : Démonstration synthétique de la couverture de mission
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

"""Temporary synthetic missions; no network, real model, or personal documents."""
from copy import deepcopy
from dataclasses import dataclass
import json
from pathlib import Path
import tempfile

from eidolon_core.contracts import encode
from eidolon_core.memory import DEMO_REQUEST, SyntheticMemory
from eidolon_core.model import DeterministicModel
from eidolon_core.runtime import Runtime
from eidolon_core.store import Store


@dataclass(frozen=True)
class PairMemory(SyntheticMemory):
    provider_id: str = "synthetic-pair-demo/1"

    def recall(self, request):
        context = super().recall(request)
        other = deepcopy(context["items"][0])
        other["information_id"] = "synthetic-second"
        other["provenance"]["source"] = "synthetic-second-fixture"
        context["items"].append(other)
        return context


@dataclass(frozen=True)
class IncompleteModel:
    model_id: str = "synthetic-incomplete-demo/1"

    def propose(self, request, context):
        plan = json.loads(DeterministicModel().propose(request, context))
        plan["steps"] = plan["steps"][:1]
        return encode(plan)


def main():
    cases = []
    with tempfile.TemporaryDirectory(prefix="eidolon-objectives-") as directory:
        store = Store(Path(directory) / "state")
        complete = Runtime(store, memory=PairMemory())
        incomplete = Runtime(store, memory=PairMemory(), model=IncompleteModel())
        for name, runtime, request in (
            ("complete", complete, DEMO_REQUEST),
            ("incomplete_plan", incomplete, DEMO_REQUEST),
            ("clarification", complete, "Vérifier le service du NAS."),
        ):
            m = runtime.run(runtime.create(request)["id"])
            cases.append({"case": name, "status": m["status"], "outcome": m["outcome"],
                          "calls": len(m["calls"]), "error": m["error"],
                          "evidence": m["result"]["evidence"] if m["result"] else []})
        # The first result is verified; the second is never called.
        def cancel_after_proof(kind):
            if kind == "RESULT_VERIFIED":
                store.request_cancel(identity)
        partial = Runtime(store, memory=PairMemory(), checkpoint=cancel_after_proof)
        identity = partial.create(DEMO_REQUEST)["id"]
        m = partial.run(identity)
        cases.append({"case": "cancelled_partial", "status": m["status"], "outcome": m["outcome"],
                      "calls": len(m["calls"]), "error": m["error"],
                      "evidence": [{"call_id": c["id"], "status": c["status"],
                                    "output_sha256": c.get("output_sha256")} for c in m["calls"]]})
        assert [(c["status"], c["outcome"]["status"], c["calls"]) for c in cases] == [
            ("SUCCEEDED", "ACHIEVED", 2), ("BLOCKED", "NOT_ACHIEVED", 0),
            ("BLOCKED", "CLARIFICATION", 0), ("CANCELLED", "PARTIAL", 1)]
    print(json.dumps({"synthetic": True, "temporary_state_removed": True, "cases": cases},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
