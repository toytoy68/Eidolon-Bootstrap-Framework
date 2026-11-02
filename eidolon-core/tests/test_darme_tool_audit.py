import unittest
from eidolon_core.darme_tool_audit import denied_tool_event
from eidolon_core.darme import DarmeMonitor


class ToolAuditTests(unittest.TestCase):
    def test_denial_has_no_sensitive_parameters(self):
        event = denied_tool_event(request_id='r1', tool_name='network.upload', policy_id='deny',
                                  parameters={'token': 'SENSITIVE_TEST_VALUE'})
        self.assertNotIn('SENSITIVE_TEST_VALUE', event.subject)
        monitor = DarmeMonitor(('core-tool-policy',))
        monitor.ingest(event)
        self.assertEqual(monitor.snapshot()['unacknowledged_alerts'], 1)

    def test_same_input_has_stable_identity(self):
        kw = dict(request_id='r1', tool_name='network.upload', policy_id='deny', parameters={'a': 1})
        self.assertEqual(denied_tool_event(**kw).event_id, denied_tool_event(**kw).event_id)

    def test_invalid_identifier_refused(self):
        with self.assertRaises(ValueError):
            denied_tool_event(request_id='bad\nline', tool_name='x', policy_id='deny', parameters={})
