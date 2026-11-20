"""Integration regression: real Runtime preflight emits durable evidence."""
import unittest
from unittest.mock import Mock
from eidolon_core.runtime import Runtime
from eidolon_core.contracts import ContractError


class RuntimeAuditTests(unittest.TestCase):
    def test_denied_tool_records_event_before_refusal(self):
        runtime = Runtime(Mock())
        runtime._save = Mock()
        mission = {'id': 'm-' + 'a'*32, 'plan': {'steps': [
            {'id': 'blocked', 'tool': 'network.upload', 'parameters': {'secret': 'PRIVATE_SENTINEL'}}]}}
        with self.assertRaisesRegex(ContractError, 'POLICY_DENIED'):
            runtime._preflight(mission)
        runtime._save.assert_called_once()
        args = runtime._save.call_args.args
        self.assertEqual(args[1], 'DARME_TOOL_POLICY_DENIED')
        self.assertEqual(args[2]['category'], 'tool_policy_denied')
        self.assertNotIn('PRIVATE_SENTINEL', str(args[2]))

    def test_allowed_tool_does_not_emit_denial(self):
        runtime = Runtime(Mock())
        runtime._save = Mock()
        # Check the policy gate directly, without invoking any tool callback.
        self.assertTrue(runtime.policy.allows(runtime.registry.get('text.stats')))
        runtime._save.assert_not_called()
