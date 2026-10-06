# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_abandon_verification.py
# Description : Abandon explicite d'un résultat reçu mais invérifiable (C-TASK-G023)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
from contextlib import contextmanager
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from eidolon_core import runtime as module
from eidolon_core.action_view import action_view
from eidolon_core.actions import ActionRuntime
from eidolon_core.memory import DEMO_REQUEST
from eidolon_core.runtime import Runtime
from eidolon_core.store import Busy, Store
from eidolon_core.tools import verify_stats
from eidolon_core.worker import CallFailure
from tests.support import MultipleMemory

ACTOR, REASON = 'synthetic-operator', 'verifier unavailable for good; close with evidence kept'


class AbandonUnverifiedTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = Store(self.temp.name)
        self.runtime = ActionRuntime(self.store)

    @contextmanager
    def verifier_down(self, verifier, on_call=None):
        original = module.invoke
        def unavailable(function, args, **kwargs):
            if function == verifier:
                if on_call:
                    on_call()  # e.g. a stop request committed after the tool returned
                raise CallFailure('TIMEOUT', 'synthetic verifier outage')
            return original(function, args, **kwargs)
        with patch.object(module, 'invoke', side_effect=unavailable):
            yield

    def blocked_restart(self, cancel=False):
        self.runtime.world.set_state('sim-nas', 'DOWN')  # each case restarts a fresh synthetic outage
        m = self.runtime.run(self.runtime.create_restart('nas')['id'])
        self.runtime.decide(m['id'], expected_sha256=m['proposal']['sha256'], decision='approve',
                            actor=ACTOR, reason='synthetic approval')
        stop = (lambda: self.store.request_cancel(m['id'])) if cancel else None
        with self.verifier_down(self.runtime.world.verify, stop):
            blocked = self.runtime.run(m['id'])
        self.assertEqual((blocked['status'], blocked['phase'], blocked['calls'][-1]['status'], blocked['cancel_requested']),
                         ('BLOCKED', 'VERIFY', 'RETURNED', cancel))
        return blocked

    def abandon(self, identity, **changes):
        options = dict(decision='abandon', actor=ACTOR, reason=REASON)
        options.update(changes)
        return self.runtime.reconcile(identity, **options)

    def kinds(self, identity, kind):
        return sum(e['kind'] == kind for e in self.store.events(identity))

    def test_abandon_keeps_returned_evidence_with_or_without_cancellation(self):
        for cancel in (False, True):
            with self.subTest(cancel=cancel):
                blocked = self.blocked_restart(cancel)
                call = blocked['calls'][-1]
                with patch.object(module, 'invoke', side_effect=AssertionError('no call during abandon')):
                    closed = self.abandon(blocked['id'])
                self.assertEqual(closed['status'], 'ABANDONED')
                self.assertEqual(closed['error']['code'], 'RESULT_UNVERIFIED')
                self.assertIsNone(closed['result'])
                kept = closed['calls'][-1]
                self.assertEqual(kept['status'], 'RETURNED')
                for key in ('output', 'output_sha256', 'receipt_origin'):
                    self.assertEqual(kept[key], call[key])
                self.assertNotEqual(closed['outcome']['status'], 'ACHIEVED')
                self.assertEqual(action_view(closed)['effect']['code'], 'RESULT_UNVERIFIED')
                self.assertEqual(action_view(closed)['applicability']['code'], 'MISSION_CLOSED')
                event = [e for e in self.store.events(closed['id']) if e['kind'] == 'ABANDONED'][-1]['detail']
                self.assertEqual((event['actor'], event['reason'], event['result_state'], event['output_sha256']),
                                 (ACTOR, REASON, 'RETURNED_UNVERIFIED', call['output_sha256']))
                self.assertEqual(self.store.get(closed['id']), closed)

    def test_nothing_runs_after_abandon(self):
        closed = self.abandon(self.blocked_restart()['id'])
        before = (self.kinds(closed['id'], 'CALL_STARTED'), self.runtime.world.observe('sim-nas')['restarts'])
        with patch.object(module, 'invoke', side_effect=AssertionError('no call after abandon')):
            again = self.runtime.run(closed['id'])
        self.assertEqual(again, closed)
        self.assertEqual((self.kinds(closed['id'], 'CALL_STARTED'), self.runtime.world.observe('sim-nas')['restarts']), before)
        self.assertEqual(before, (1, 1))

    def test_other_decisions_output_and_invalid_labels_are_refused_without_change(self):
        blocked = self.blocked_restart()
        for changes in (dict(decision='no-effect'), dict(decision='observed-result', output=blocked['calls'][-1]['output']),
                        dict(decision='use-receipt'), dict(output={'state': 'UP'}), dict(actor=' '),
                        dict(reason=''), dict(actor='x' * 201), dict(decision='forget')):
            with self.subTest(changes=list(changes)), self.assertRaises(ValueError):
                self.abandon(blocked['id'], **changes)
        self.assertEqual(self.store.get(blocked['id']), blocked)

    def test_refused_for_terminal_prepared_or_missing_result(self):
        pending = self.runtime.run(self.runtime.create_restart('nas')['id'])
        with self.assertRaises(ValueError):
            self.abandon(pending['id'])  # BLOCKED awaiting a decision, call PREPARED
        self.assertEqual(self.store.get(pending['id']), pending)
        done = self.blocked_restart()
        verified = self.runtime.run(done['id'])
        self.assertEqual(verified['status'], 'SUCCEEDED')
        with self.assertRaises(ValueError):
            self.abandon(verified['id'])
        self.assertEqual(self.store.get(verified['id']), verified)

    def test_old_cancelled_mission_with_returned_call_is_not_reopened(self):
        blocked = self.blocked_restart()
        legacy = dict(blocked, status='CANCELLED', error={'code': 'VERIFICATION_UNAVAILABLE', 'message': 'legacy E1 state'})
        self.store.save(legacy, 'CANCELLED')
        legacy = self.store.get(blocked['id'])
        with self.assertRaises(ValueError):
            self.abandon(legacy['id'])
        self.assertEqual(self.store.get(legacy['id']), legacy)

    def test_busy_lock_refuses_without_change(self):
        blocked = self.blocked_restart()
        with self.store.lock(blocked['id']):
            with self.assertRaises(Busy):
                self.abandon(blocked['id'])
        self.assertEqual(self.store.get(blocked['id'])['status'], 'BLOCKED')

    def test_partial_verified_evidence_stays_partial(self):
        runtime = Runtime(self.store, memory=MultipleMemory())
        identity = runtime.create(DEMO_REQUEST)['id']
        seen = []
        original = module.invoke
        def second_verifier_down(function, args, **kwargs):
            if function is verify_stats:
                seen.append(1)
                if len(seen) == 2:
                    raise CallFailure('TIMEOUT', 'synthetic verifier outage')
            return original(function, args, **kwargs)
        with patch.object(module, 'invoke', side_effect=second_verifier_down):
            blocked = runtime.run(identity)
        self.assertEqual([c['status'] for c in blocked['calls']], ['VERIFIED', 'RETURNED'])
        closed = runtime.reconcile(identity, decision='abandon', actor=ACTOR, reason=REASON)
        self.assertEqual([c['status'] for c in closed['calls']], ['VERIFIED', 'RETURNED'])
        self.assertEqual(closed['outcome']['status'], 'PARTIAL')
        self.assertEqual(closed['progress']['completed'], 1)
        self.assertIsNone(closed['result'])

    def test_unknown_effect_abandon_is_unchanged(self):
        from dataclasses import replace
        from eidolon_core.tools import Registry
        from tests.test_actions import FaultAction
        tool = replace(self.runtime.world.tool(), execute=FaultAction(self.runtime.world, 'lost').execute)
        runtime = ActionRuntime(self.store, registry=Registry([tool]))
        m = runtime.run(runtime.create_restart('nas')['id'])
        runtime.decide(m['id'], expected_sha256=m['proposal']['sha256'], decision='approve', actor=ACTOR, reason='x')
        self.assertEqual(runtime.run(m['id'])['status'], 'REVIEW_REQUIRED')
        closed = runtime.reconcile(m['id'], decision='abandon', actor=ACTOR, reason=REASON)
        self.assertEqual((closed['status'], closed['error']['code'], closed['calls'][-1]['status']),
                         ('ABANDONED', 'EFFECT_UNKNOWN', 'UNKNOWN'))

    def test_cli_reconcile_abandon(self):
        blocked = self.blocked_restart()
        command = [sys.executable, '-m', 'eidolon_core', '--state', self.temp.name, '--profile', 'action-sim',
                   'reconcile', blocked['id'], '--decision', 'abandon', '--actor', ACTOR, '--reason', REASON]
        result_file = Path(self.temp.name) / 'result.json'
        result_file.write_text(json.dumps({'state': 'UP'}), encoding='utf-8')
        refused = subprocess.run(command + ['--result', str(result_file)], capture_output=True, text=True, timeout=60)
        self.assertEqual(refused.returncode, 2, refused.stderr)
        self.assertEqual(self.store.get(blocked['id'])['status'], 'BLOCKED')
        done = subprocess.run(command, capture_output=True, text=True, timeout=60)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(json.loads(done.stdout)['status'], 'ABANDONED')
        self.assertEqual(json.loads(done.stdout)['action_view']['effect']['code'], 'RESULT_UNVERIFIED')


if __name__ == '__main__':
    unittest.main()
