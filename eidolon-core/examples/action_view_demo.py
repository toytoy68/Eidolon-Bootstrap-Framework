# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : action_view_demo.py
# Description : Démonstration des accords et effets sans confusion d'affichage
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

"""Six synthetic action states, including a consumed but never authorized call."""
import argparse
import tempfile

from eidolon_core.action_view import action_view
from eidolon_core.actions import ActionRuntime
from eidolon_core.contracts import encode
from eidolon_core.presentation import render_result
from eidolon_core.runtime import Limits
from eidolon_core.store import Store


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--format", choices=("json", "human"), default="json")
    args = parser.parse_args(argv)
    cases = [("pending", "AWAITING_DECISION", "NOT_STARTED", 0),
             ("approved", "RECHECK_REQUIRED", "NOT_STARTED", 0),
             ("condition-changed", "STALE_CONDITION", "NOT_STARTED", 0),
             ("cancelled-before-authorization", "MISSION_CLOSED", "NOT_AUTHORIZED", 0),
             ("configuration-mismatch", "CONFIGURATION_MISMATCH", "NOT_STARTED", 0),
             ("verified-then-down", "MISSION_CLOSED", "VERIFIED_PAST_EFFECT", 1)]
    for name, applicability, effect, count in cases:
        with tempfile.TemporaryDirectory(prefix="eidolon-view-") as root:
            store = Store(root)
            runtime = ActionRuntime(store)
            m = runtime.run(runtime.create_restart("nas")["id"])
            if name != "pending":
                m = runtime.decide(m["id"], expected_sha256=m["proposal"]["sha256"],
                                   decision="approve", actor="synthetic-operator", reason="view demonstration")
            if name == "condition-changed":
                runtime.world.set_state("sim-nas", "UP")
                m = runtime.run(m["id"])
            elif name == "cancelled-before-authorization":
                def checkpoint(kind):
                    if kind == "CALL_STARTED":
                        store.request_cancel(m["id"])
                m = ActionRuntime(store, checkpoint=checkpoint).run(m["id"])
            elif name == "configuration-mismatch":
                m = ActionRuntime(store, limits=Limits(9)).run(m["id"])
            elif name == "verified-then-down":
                m = runtime.run(m["id"])
                runtime.world.set_state("sim-nas", "DOWN")
            before = store.get(m["id"])
            view = action_view(m)
            if (view["applicability"]["code"], view["effect"]["code"]) != (applicability, effect):
                raise AssertionError(f"unexpected view for {name}")
            if runtime.world.observe("sim-nas")["restarts"] != count or store.get(m["id"]) != before:
                raise AssertionError("view changed state or wrong synthetic effect count")
            print(render_result(m) if args.format == "human" else encode({
                "scenario": name, "synthetic": True, "mission_status": m["status"],
                "action_view": view, "verified_synthetic_restart_count": count}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
