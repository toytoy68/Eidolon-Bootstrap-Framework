"""Offline regression checks for model-to-tool privilege boundaries."""
import unittest
from eidolon_core.tools import Policy, Tool, Registry


def noop(*args):
    return None


class LlmBoundaryTests(unittest.TestCase):
    def test_default_policy_refuses_side_effect_tools_even_if_allowlisted(self):
        for effect in ('mutation', 'network', 'local_read'):
            with self.subTest(effect=effect):
                tool = Tool('model.request', '1', effect, noop, noop, noop, 'test')
                self.assertFalse(Policy(allowed_tools=('model.request',)).allows(tool))

    def test_unknown_tool_denied(self):
        self.assertFalse(Policy().allows(Registry([]).get('shell.execute')))

    def test_pure_tool_requires_allowlist(self):
        tool = Tool('safe.compute', '1', 'none', noop, noop, noop, 'test')
        self.assertFalse(Policy().allows(tool))
        self.assertTrue(Policy(allowed_tools=('safe.compute',)).allows(tool))


if __name__ == '__main__':
    unittest.main()

class DarmeEventBoundaryTests(unittest.TestCase):
    def test_denial_can_be_recorded_without_tool_execution(self):
        from datetime import datetime, timezone
        from eidolon_core.darme import DarmeMonitor, SecurityEvent, Severity
        calls = []
        def execute(*args):
            calls.append(True)
        tool = Tool("network.upload", "1", "network", noop, execute, noop, "test")
        monitor = DarmeMonitor(("core-tool-policy",))
        if not Policy(allowed_tools=("network.upload",)).allows(tool):
            monitor.ingest(SecurityEvent("denied-1", "core-tool-policy", "tool_policy_denied", Severity.WARNING, datetime.now(timezone.utc).isoformat(), "network.upload"))
        self.assertEqual(calls, [])
        self.assertEqual(monitor.snapshot()["unacknowledged_alerts"], 1)
