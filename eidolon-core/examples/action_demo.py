# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : action_demo.py
# Description : Approbation, refus et état changé sur services fictifs
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

"""All actors, services and actions are synthetic. No external service calls."""
from pathlib import Path
import tempfile

from eidolon_core.actions import ActionRuntime
from eidolon_core.contracts import encode
from eidolon_core.store import Store


def main():
    with tempfile.TemporaryDirectory(prefix="eidolon-actions-") as directory:
        for scenario in ("pending", "approve", "reject", "revoke", "state-changed", "cancel"):
            runtime = ActionRuntime(Store(Path(directory) / scenario))
            mission = runtime.run(runtime.create_restart("nas")["id"])
            assert mission["error"]["code"] == "APPROVAL_REQUIRED"
            proposal = mission["proposal"]
            def decide(decision):
                return runtime.decide(mission["id"], expected_sha256=proposal["sha256"],
                                      decision=decision, actor="synthetic-demo-operator", reason="explicit simulation scenario " + scenario)
            if scenario in {"approve", "revoke", "state-changed"}:
                decide("approve")
            if scenario == "reject":
                decide("reject")
            if scenario == "revoke":
                decide("revoke")
            if scenario == "state-changed":
                runtime.world.set_state("sim-nas", "UP")
            if scenario == "cancel":
                runtime.cancel(mission["id"])
            assert runtime.world.observe("sim-nas")["restarts"] == 0
            result = runtime.run(mission["id"])
            state = runtime.world.observe("sim-nas")
            if scenario == "approve":
                assert result["status"] == "SUCCEEDED" and result["outcome"]["status"] == "ACHIEVED"
                assert state["restarts"] == 1
            else:
                assert result["status"] == ("CANCELLED" if scenario == "cancel" else "BLOCKED")
                assert state["restarts"] == 0 and result["result"] is None
            print(encode({"scenario": scenario, "mission_id": mission["id"], "status": result["status"],
                          "outcome": result["outcome"], "error": result["error"],
                          "proposal": result["proposal"], "simulated_service": state, "result": result["result"]}))


if __name__ == "__main__":
    main()
