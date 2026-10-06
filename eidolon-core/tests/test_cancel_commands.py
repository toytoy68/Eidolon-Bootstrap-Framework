# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_cancel_commands.py
# Description : Annulation avec reçu sans confondre demande, arrêt et effet
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

from concurrent.futures import ThreadPoolExecutor
import io
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import replace
import unittest
from unittest.mock import patch

from eidolon_core.actions import ActionRuntime
from eidolon_core.cli import main
from eidolon_core.client_sync import ClientSync
from eidolon_core.commands import CANCEL_PROTOCOL, CancelCommands, DecisionCommands, lookup_receipt, parse_cancel_command
from eidolon_core.contracts import ContractError, encode
from eidolon_core.memory import DEMO_REQUEST
from eidolon_core.runtime import Limits, Runtime
from eidolon_core.store import Store
from eidolon_core.commands import PROTOCOL
from eidolon_core.tools import Registry
from tests.test_actions import FaultAction


class Crash(BaseException):
    pass


class CancelCommandTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = Store(self.temp.name)
        self.runtime = Runtime(self.store)
        self.mission = self.runtime.create(DEMO_REQUEST)
        self.command = self.request(self.mission['id'])
        self.commands = CancelCommands(self.store)

    def request(self, mission_id):
        return dict(protocol=CANCEL_PROTOCOL, store_id=ClientSync(self.store).snapshot(mission_id)['store_id'],
                    client_id='synthetic-desktop', command_key='cancel-001', mission_id=mission_id,
                    actor='synthetic-operator', reason='explicit cancellation test')

    def lookup(self, command=None):
        command = command or self.command
        return lookup_receipt(self.store, **{k: command[k] for k in ('store_id', 'client_id', 'command_key')})

    def test_request_and_receipt_do_not_run_or_finalize_mission(self):
        initial = ClientSync(self.store).snapshot(self.mission['id'])
        receipt = self.commands.submit(self.command)
        saved = self.store.get(self.mission['id'])
        self.assertTrue(saved['cancel_requested'])
        self.assertEqual(saved['status'], 'NEW')
        self.assertEqual(saved['revision'], self.mission['revision'])
        self.assertFalse(receipt['execution_evidence'])
        self.assertFalse(receipt['effect_absence_evidence'])
        self.assertEqual(receipt['cancel_outcome'], 'REQUESTED')
        delta = ClientSync(self.store).poll(saved['id'], initial['cursor'])
        self.assertTrue(delta['snapshot']['mission']['cancel_requested'])
        self.assertEqual([e['kind'] for e in delta['events']], ['CANCEL_REQUESTED'])
        self.assertEqual(delta['events'][0]['sequence'], receipt['event_sequence'])
        finished = self.runtime.run(saved['id'])
        self.assertEqual(finished['status'], 'CANCELLED')
        self.assertEqual(finished['calls'], [])
        self.assertIsNone(finished['result'])
        self.assertEqual(self.commands.submit(self.command), receipt)
        self.assertEqual(receipt['mission_status_at_recording'], 'NEW')

    def test_request_works_while_execution_lock_is_held(self):
        with self.store.lock(self.mission['id']):
            receipt = self.commands.submit(self.command)
            self.assertEqual(self.lookup()['receipt'], receipt)
        self.assertEqual(self.store.get(self.mission['id'])['status'], 'NEW')

    def test_reopen_and_duplicate_leave_no_new_event(self):
        receipt = self.commands.submit(self.command)
        events = self.store.events(self.mission['id'])
        self.assertEqual(CancelCommands(Store(self.temp.name)).submit(self.command), receipt)
        self.assertEqual(self.store.events(self.mission['id']), events)
        receipt['cancel_outcome'] = 'FORGED'
        self.assertEqual(self.lookup()['receipt']['cancel_outcome'], 'REQUESTED')

    def test_second_key_records_existing_request_without_another_flag_transition(self):
        self.store.request_cancel(self.mission['id'])  # Legacy request has no command receipt.
        receipt = self.commands.submit(self.command)
        self.assertEqual(receipt['cancel_outcome'], 'ALREADY_REQUESTED')
        self.assertEqual(receipt['mission_revision'], self.mission['revision'])
        second = {**self.command, 'command_key': 'cancel-002'}
        self.assertEqual(self.commands.submit(second)['cancel_outcome'], 'ALREADY_REQUESTED')
        events = self.store.events(self.mission['id'])
        self.assertEqual(sum(e['kind'] == 'CANCEL_REQUESTED' for e in events), 1)
        self.assertEqual(sum(e['kind'] == 'CANCEL_COMMAND_RECORDED' for e in events), 2)

    def test_terminal_success_is_preserved_and_receipt_says_too_late(self):
        completed = self.runtime.run(self.mission['id'])
        self.assertEqual(completed['status'], 'SUCCEEDED')
        receipt = self.commands.submit(self.command)
        self.assertEqual(receipt['cancel_outcome'], 'ALREADY_TERMINAL')
        self.assertEqual(receipt['mission_status_at_recording'], 'SUCCEEDED')
        self.assertFalse(receipt['cancel_requested_at_recording'])
        self.assertEqual(self.store.get(self.mission['id']), completed)

    def test_cancelled_failed_and_abandoned_are_not_rewritten(self):
        for status in ('CANCELLED', 'FAILED', 'ABANDONED'):
            m = self.runtime.create(DEMO_REQUEST)
            m.update(status=status, result=None)
            self.store.save(m, 'SYNTHETIC_TERMINAL_FIXTURE')
            cmd = {**self.request(m['id']), 'command_key': 'cancel-' + status}
            receipt = self.commands.submit(cmd)
            self.assertEqual(receipt['cancel_outcome'], 'ALREADY_TERMINAL')
            self.assertEqual(self.store.get(m['id']), m)

    def test_unknown_effect_remains_in_review_after_cancellation(self):
        def crash(kind):
            if kind == 'CALL_STARTED':
                raise Crash()
        runtime = Runtime(self.store, checkpoint=crash)
        with self.assertRaises(Crash):
            runtime.run(self.mission['id'])
        before = self.store.get(self.mission['id'])
        self.assertEqual(before['phase'], 'EXECUTING')
        receipt = self.commands.submit(self.command)
        self.assertEqual(receipt['mission_status_at_recording'], 'RUNNING')
        review = self.runtime.run(self.mission['id'])
        self.assertEqual(review['status'], 'REVIEW_REQUIRED')
        self.assertEqual(review['error']['code'], 'UNKNOWN_EFFECT')
        self.assertIsNone(review['result'])
        self.assertFalse(receipt['effect_absence_evidence'])
        self.assertEqual(self.runtime.run(self.mission['id'])['status'], 'REVIEW_REQUIRED')

    def test_cancel_request_prevents_later_success_commit(self):
        receipts = []
        def cancel_after_verification(kind):
            if kind == 'RESULT_VERIFIED':
                receipts.append(self.commands.submit(self.command))
        completed = Runtime(self.store, checkpoint=cancel_after_verification).run(self.mission['id'])
        self.assertEqual(receipts[0]['cancel_outcome'], 'REQUESTED')
        self.assertEqual(completed['status'], 'CANCELLED')
        self.assertIsNone(completed['result'])
        self.assertTrue(completed['cancel_requested'])
        self.assertEqual(completed['calls'][0]['status'], 'VERIFIED')

    def test_live_worker_effect_is_not_erased_by_cancellation_receipt(self):
        original = ActionRuntime(self.store)
        tool = replace(original.world.tool(), execute=FaultAction(original.world, 'timeout-after-commit').execute)
        runtime = ActionRuntime(self.store, registry=Registry([tool]), limits=Limits(10))
        m = runtime.run(runtime.create_restart('nas')['id'])
        runtime.decide(m['id'], expected_sha256=m['proposal']['sha256'], decision='approve',
                       actor='synthetic-operator', reason='test interrupted local effect')
        with ThreadPoolExecutor(1) as pool:
            running = pool.submit(runtime.run, m['id'])
            deadline = time.monotonic() + 5
            while original.world.observe('sim-nas')['restarts'] == 0 and time.monotonic() < deadline:
                if running.done():
                    break
                time.sleep(0.01)
            self.assertEqual(original.world.observe('sim-nas')['restarts'], 1)
            self.assertFalse(running.done())
            receipt = self.commands.submit(self.request(m['id']))
            self.assertEqual(receipt['mission_status_at_recording'], 'RUNNING')
            self.assertFalse(receipt['effect_absence_evidence'])
            stopped = running.result(timeout=10)
        self.assertEqual(stopped['status'], 'REVIEW_REQUIRED')
        self.assertIsNone(stopped['result'])
        self.assertIsNotNone(original.world.receipt(m['id']))
        self.assertEqual(runtime.run(m['id'])['status'], 'REVIEW_REQUIRED')
        self.assertEqual(original.world.observe('sim-nas')['restarts'], 1)

    def test_same_key_conflicts_across_commands_and_missions(self):
        self.commands.submit(self.command)
        another = self.runtime.create(DEMO_REQUEST)
        for change in ({'reason': 'changed'}, {'actor': 'other'}, {'mission_id': another['id']}):
            with self.assertRaisesRegex(ContractError, 'COMMAND_KEY_REUSED'):
                self.commands.submit({**self.command, **change})
        self.assertFalse(self.store.get(another['id'])['cancel_requested'])

    def test_approval_receipt_and_cancel_receipt_share_key_namespace(self):
        runtime = ActionRuntime(self.store)
        m = runtime.run(runtime.create_restart('nas')['id'])
        cancel = self.request(m['id'])
        approve = {**cancel, 'protocol': PROTOCOL, 'expected_revision': m['revision'],
                   'proposal_sha256': m['proposal']['sha256'], 'decision': 'approve'}
        decisions = DecisionCommands(runtime)
        decisions.submit(approve)
        with self.assertRaisesRegex(ContractError, 'COMMAND_KEY_REUSED'):
            self.commands.submit(cancel)
        self.assertFalse(self.store.get(m['id'])['cancel_requested'])
        receipt = self.commands.submit({**cancel, 'command_key': 'separate-cancel'})
        self.assertEqual(receipt['cancel_outcome'], 'REQUESTED')
        self.assertEqual(runtime.run(m['id'])['status'], 'CANCELLED')
        self.assertEqual(runtime.world.observe('sim-nas')['restarts'], 0)

    def test_cancel_commits_during_approval_preparation_without_lock_conflict(self):
        runtime = ActionRuntime(self.store)
        m = runtime.run(runtime.create_restart('nas')['id'])
        cancel = self.request(m['id'])
        approve = {**cancel, 'command_key': 'approve', 'protocol': PROTOCOL,
                   'expected_revision': m['revision'], 'proposal_sha256': m['proposal']['sha256'], 'decision': 'approve'}
        prepare = runtime._prepare_decision
        def race(*args, **kwargs):
            entry = prepare(*args, **kwargs)
            self.commands.submit(cancel)
            return entry
        with patch.object(runtime, '_prepare_decision', side_effect=race):
            with self.assertRaisesRegex(ContractError, 'CANCEL_REQUESTED'):
                DecisionCommands(runtime).submit(approve)
        self.assertEqual(self.store.get(m['id'])['proposal']['status'], 'PENDING')
        self.assertEqual(self.lookup(cancel)['status'], 'FOUND')
        self.assertEqual(self.lookup(approve)['status'], 'NOT_FOUND')

    def test_concurrent_same_command_returns_one_receipt_and_one_event(self):
        barrier = threading.Barrier(2)
        def submit(_):
            barrier.wait(timeout=5)
            return CancelCommands(Store(self.temp.name)).submit(self.command)
        with ThreadPoolExecutor(2) as pool:
            results = list(pool.map(submit, range(2)))
        self.assertEqual(results[0], results[1])
        self.assertEqual(len(self.store.events(self.mission['id'])), 2)

    def test_concurrent_key_collision_does_not_cancel_both_missions(self):
        another = self.runtime.create(DEMO_REQUEST)
        barrier = threading.Barrier(2)
        def submit(command):
            barrier.wait(timeout=5)
            try:
                return CancelCommands(self.store).submit(command)
            except ContractError as exc:
                return str(exc)
        with ThreadPoolExecutor(2) as pool:
            results = list(pool.map(submit, (self.command, self.request(another['id']))))
        self.assertEqual(sum(isinstance(r, dict) for r in results), 1)
        self.assertIn('COMMAND_KEY_REUSED', next(r for r in results if isinstance(r, str)))
        self.assertEqual(sum(self.store.cancel_requested(m['id']) for m in (self.mission, another)), 1)

    def test_invalid_command_changed_store_and_missing_mission_never_set_flag(self):
        for command in (None, [], {**self.command, 'expected_revision': 0},
                        {**self.command, 'protocol': PROTOCOL}, {**self.command, 'reason': '\ud800'},
                        {**self.command, 'actor': ''}, {**self.command, 'client_id': '../bad'},
                        {**self.command, 'reason': 'x' * 4001}):
            with self.subTest(command=repr(command)[:80]), self.assertRaises(ValueError):
                self.commands.submit(command)
        with self.assertRaisesRegex(ContractError, 'STORE_CHANGED'):
            self.commands.submit({**self.command, 'store_id': 's-' + 'f' * 32})
        with self.assertRaises(KeyError):
            self.commands.submit({**self.command, 'mission_id': 'm-' + 'f' * 32})
        self.assertEqual(self.store.get(self.mission['id']), self.mission)
        self.assertEqual(self.lookup()['status'], 'NOT_FOUND')

    def test_parser_rejects_malformed_json_and_wrong_command_kind(self):
        for raw in ('{', ' ' * 32769, '[', '{"protocol":1,"protocol":2}',
                    encode(self.command).encode('utf-16'), '[' * 2000 + ']' * 2000):
            with self.assertRaises(ContractError):
                parse_cancel_command(raw)
        self.assertEqual(parse_cancel_command(encode(self.command)), self.command)

    def test_sql_error_rolls_back_flag_event_and_receipt(self):
        with self.store.connection() as db:
            db.execute("CREATE TRIGGER fail_cancel BEFORE INSERT ON command_receipts BEGIN SELECT RAISE(ABORT,'injected failure'); END")
        with self.assertRaises(sqlite3.IntegrityError):
            self.commands.submit(self.command)
        self.assertEqual(self.store.get(self.mission['id']), self.mission)
        self.assertEqual(len(self.store.events(self.mission['id'])), 1)
        self.assertEqual(self.lookup()['status'], 'NOT_FOUND')

    def test_abrupt_exit_before_and_after_commit(self):
        code = '''
from contextlib import contextmanager
import json, os, sys
from eidolon_core.store import Store
from eidolon_core.commands import CancelCommands
class CrashStore(Store):
    @contextmanager
    def connection(self):
        with super().connection() as db:
            db.create_function('crash', 0, lambda: os._exit(73))
            yield db
store = CrashStore(sys.argv[1])
CancelCommands(store).submit(json.loads(sys.argv[2]))
os._exit(74)
'''
        with self.store.connection() as db:
            db.execute('CREATE TRIGGER crash_cancel BEFORE INSERT ON command_receipts BEGIN SELECT crash(); END')
        def child():
            return subprocess.run([sys.executable, '-c', code, self.temp.name, encode(self.command)],
                                  capture_output=True, text=True, timeout=15)
        result = child()
        self.assertEqual(result.returncode, 73, result.stderr)
        self.assertEqual(self.store.get(self.mission['id']), self.mission)
        self.assertEqual(len(self.store.events(self.mission['id'])), 1)
        self.assertEqual(self.lookup()['status'], 'NOT_FOUND')
        with self.store.connection() as db:
            db.execute('DROP TRIGGER crash_cancel')
        result = child()
        self.assertEqual(result.returncode, 74, result.stderr)
        self.assertTrue(self.store.cancel_requested(self.mission['id']))
        self.assertEqual(self.lookup()['status'], 'FOUND')
        self.assertEqual(self.commands.submit(self.command), self.lookup()['receipt'])
        self.assertEqual(len(self.store.events(self.mission['id'])), 2)

    def test_receipt_safe_integer_guard_rolls_back_cancellation(self):
        with self.store.connection() as db:
            db.execute("UPDATE sqlite_sequence SET seq=? WHERE name='events'", (2**53 - 1,))
        with self.assertRaisesRegex(ContractError, 'safe integer'):
            self.commands.submit(self.command)
        self.assertEqual(self.store.get(self.mission['id']), self.mission)
        self.assertEqual(self.lookup()['status'], 'NOT_FOUND')

    def test_cli_records_under_lock_without_creating_runtime_and_no_false_ok(self):
        path = Path(self.temp.name) / 'cancel.json'
        path.write_text(encode(self.command))
        args = ['--state', self.temp.name, '--format', 'human', 'command-cancel', '--request', str(path)]
        with self.store.lock(self.mission['id']), patch('eidolon_core.cli.Runtime', side_effect=AssertionError), \
                patch('eidolon_core.cli.ActionRuntime', side_effect=AssertionError), \
                patch('sys.stdout', new_callable=io.StringIO) as output:
            self.assertEqual(main(args), 0)
            self.assertIn('[INFO]', output.getvalue())
            self.assertNotIn('[OK]', output.getvalue())
        self.assertEqual(self.store.get(self.mission['id'])['status'], 'NEW')
        missing = Path(self.temp.name) / 'missing'
        with patch('sys.stderr', new_callable=io.StringIO):
            self.assertEqual(main(['--state', str(missing), 'command-cancel', '--request', str(path)]), 2)
        self.assertFalse(missing.exists())


if __name__ == '__main__':
    unittest.main()
