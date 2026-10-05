# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : service_diagnostic_demo.py
# Description : Cinq missions de diagnostic sans service externe
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

"""Reproducible outcomes; UUIDs and observation timestamps vary per run."""
import tempfile

from eidolon_core.contracts import encode
from eidolon_core.diagnostics import synthetic_runtime
from eidolon_core.store import Store


def main():
    with tempfile.TemporaryDirectory(prefix="eidolon-services-") as directory:
        store = Store(directory)
        for target, allowed, expected, state in (
            ("sim-memory", None, "SUCCEEDED", "UP"),
            ("nas", None, "SUCCEEDED", "DOWN"),
            ("offline", None, "SUCCEEDED", "UNREACHABLE"),
            ("service", None, "BLOCKED", None),
            ("nas", [], "BLOCKED", None),
        ):
            runtime = synthetic_runtime(store, allowed_targets=allowed)
            mission = runtime.run(runtime.create_diagnostic(target)["id"])
            assert mission["status"] == expected, mission["error"]
            result = mission["result"]
            if state:
                assert result["observation"]["state"] == state
                assert mission["outcome"]["status"] == "ACHIEVED"
            else:
                assert result is None and not mission["calls"]
            print(encode({"target_reference": target, "mission_id": mission["id"],
                          "status": mission["status"], "outcome": mission["outcome"],
                          "error": mission["error"], "result": result}))


if __name__ == "__main__":
    main()
