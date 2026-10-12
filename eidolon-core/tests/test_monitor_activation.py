# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_monitor_activation.py
# Description : Activation explicite des outils de surveillance : défaut inchangé, paramètres fermés, preuve sans re-sonde (G168)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from eidolon_core import monitor_tools
from eidolon_core.diagnostics import synthetic_runtime
from eidolon_core.monitor_activation import activate, compose, load_activation
from eidolon_core.store import Store
from eidolon_core.tools import Policy, default_registry


def snapshot():
    now = datetime.now(timezone.utc).isoformat()
    return {"service_schema": "eidolon-darme-service/1", "badge": "grey", "visibility": "partial",
            "authorizes_execution": False, "enforcement_enabled": False, "sources": {"x.service": True},
            "generated_at": now,
            "machine": {"schema": "eidolon-machine/1", "sampled_at": now, "cpu_count": 8, "cpu_percent": 3.0,
                        "load_1_5_15": [0.1, 0.1, 0.1], "memory": {"total_bytes": 100, "available_bytes": 60, "used_bytes": 40},
                        "swap": None, "disk": None, "gpu": None, "errors": []}}


class ActivationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "activation.json"

    def write(self, value, mode=0o600):
        self.path.write_text(json.dumps(value)); os.chmod(self.path, mode)
        return self.path

    def good(self, tools=("monitor.machine",)):
        return load_activation(self.write({"schema": "eidolon-monitor-tools-activation/1", "tools": list(tools),
                                           "approved_by": "toytoy", "reason": "état des machines dans la conversation"}))

    def test_defaults_are_never_widened(self):
        runtime = synthetic_runtime(Store(Path(self.tmp.name) / "state"))
        for registry, policy in ((runtime.registry, runtime.policy), (default_registry(), Policy())):
            self.assertIsNone(registry.get("monitor.machine"))
            self.assertNotIn("monitor.machine", policy.allowed_tools)
        before = (runtime.registry.manifest(), runtime.policy.manifest())
        self.assertEqual(compose(runtime.registry, runtime.policy, None), (runtime.registry, runtime.policy))
        activate(synthetic_runtime(Store(Path(self.tmp.name) / "other")), self.good())
        fresh = synthetic_runtime(Store(Path(self.tmp.name) / "third"))
        self.assertEqual((fresh.registry.manifest(), fresh.policy.manifest()), before)   # nothing global changed

    def test_activation_adds_only_listed_tools_and_keeps_everything_else(self):
        runtime = synthetic_runtime(Store(Path(self.tmp.name) / "state"))
        old_tools, old_policy = runtime.registry.manifest(), runtime.policy
        activate(runtime, self.good())
        tool = runtime.registry.get("monitor.machine")
        self.assertTrue(runtime.policy.allows(tool))
        self.assertIsNone(runtime.registry.get("monitor.darme"))
        self.assertFalse(runtime.policy.allows(monitor_tools.monitoring_registry().get("monitor.darme")))
        for name in old_tools:
            self.assertTrue(runtime.policy.allows(runtime.registry.get(name)) == old_policy.allows(runtime.registry.get(name)))
        self.assertEqual(runtime.policy.target_grants, old_policy.target_grants)
        self.assertEqual(runtime.policy.policy_id, old_policy.policy_id + "+monitor:monitor.machine")
        self.assertIn("monitor.machine", runtime.registry.manifest())

    def test_parameters_are_closed_no_command_path_or_target(self):
        runtime = activate(synthetic_runtime(Store(Path(self.tmp.name) / "state")), self.good())
        tool = runtime.registry.get("monitor.machine")
        tool.validate({}, {})
        for parameters in ({"command": "systemctl stop x"}, {"path": "/etc/shadow"}, {"target": "memory"}, [], None):
            with self.assertRaises(ValueError, msg=parameters):
                tool.validate(parameters, {})

    def test_evidence_references_the_snapshot_and_is_verified_without_a_second_probe(self):
        runtime = activate(synthetic_runtime(Store(Path(self.tmp.name) / "state")), self.good())
        tool = runtime.registry.get("monitor.machine")
        value = snapshot()
        with mock.patch.object(monitor_tools, "read_status", return_value=value) as probe:
            result = tool.execute({}, {})
            self.assertEqual(probe.call_count, 1)
            self.assertEqual((result["snapshot"], result["authorizes_execution"], result["scope"]),
                             (value, False, "local_vm_only"))
            self.assertTrue(tool.verify({}, {}, result))
            tampered = json.loads(json.dumps(result)); tampered["snapshot"]["badge"] = "gold"
            self.assertFalse(tool.verify({}, {}, tampered))
            self.assertFalse(tool.verify({"target": "x"}, {}, result))
            self.assertEqual(probe.call_count, 1)                     # verification never probes again

    def test_activation_file_refusals(self):
        base = {"schema": "eidolon-monitor-tools-activation/1", "tools": ["monitor.machine"],
                "approved_by": "toytoy", "reason": "raison valable"}
        self.write(base, mode=0o644)
        with self.assertRaisesRegex(ValueError, "NOT_PRIVATE"):
            load_activation(self.path)
        for bad in ({**base, "tools": ["shell.execute"]}, {**base, "tools": []},
                    {**base, "tools": ["monitor.machine", "monitor.machine"]}, {**base, "approved_by": "Toy Toy"},
                    {**base, "extra": 1}, {**base, "schema": "x"}, {**base, "reason": ""}):
            with self.assertRaises(ValueError, msg=bad):
                load_activation(self.write(bad))
        link = self.path.with_name("link"); link.symlink_to(self.write(base))
        with self.assertRaises(OSError):
            load_activation(link)

    def test_conflicting_tool_name_refused(self):
        runtime = activate(synthetic_runtime(Store(Path(self.tmp.name) / "state")), self.good())
        with self.assertRaisesRegex(ValueError, "CONFLICT"):
            activate(runtime, self.good())


if __name__ == "__main__":
    unittest.main()
