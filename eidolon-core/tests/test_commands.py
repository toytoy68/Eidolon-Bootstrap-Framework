# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_commands.py
# Description : Reçus de décisions, coupures et concurrence locales
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import io
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

from eidolon_core.actions import ActionRuntime
from eidolon_core.cli import main
from eidolon_core.client_sync import ClientSync
from eidolon_core.commands import DecisionCommands, PROTOCOL, lookup_receipt, parse_command
from eidolon_core.contracts import ContractError, encode
from eidolon_core.store import Busy, Store


class CommandTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = Store(self.temp.name)
        self.runtime = ActionRuntime(self.store)
        self.mission = self.runtime.run(self.runtime.create_restart('nas')['id'])
        self.commands = DecisionCommands(self.runtime)
        self.command = self.request(self.mission)

    def request(self, mission, **changes):
        return dict(protocol=PROTOCOL, store_id=ClientSync(self.store).snapshot(mission['id'])['store_id'],
                    client_id='synthetic-desktop', command_key='decision-001', mission_id=mission['id'],
                    expected_revision=mission['revision'], proposal_sha256=mission['proposal']['sha256'],
                    decision='approve', actor='synthetic-operator', reason='explicit synthetic test', **changes)

    def lookup(self, command=None):
        command = command or self.command
        return lookup_receipt(self.store, **{k: command[k] for k in ('store_id', 'client_id', 'command_key')})

    def assert_unchanged(self):
        self.assertEqual(self.store.get(self.mission['id']), self.mission)
        self.assertEqual(self.lookup()['status'], 'NOT_FOUND')
        self.assertEqual(self.runtime.world.observe('sim-nas')['restarts'], 0)

    def test_recording_and_historical_receipt_never_prove_execution(self):
        receipt = self.commands.submit(self.command)
        self.assertEqual(receipt['status'], 'RECORDED')
        self.assertFalse(receipt['execution_evidence'])
        self.assertEqual(receipt['mission_revision'], self.mission['revision'] + 1)
        event = self.store.events(self.mission['id'])[-1]
        self.assertEqual((event['kind'], event['sequence']), ('ACTION_DECISION', receipt['event_sequence']))
        self.assertEqual(self.runtime.world.observe('sim-nas')['restarts'], 0)
        self.assertIsNone(self.store.get(self.mission['id'])['result'])
        result = self.runtime.run(self.mission['id'])
        self.assertEqual(result['status'], 'SUCCEEDED')
        self.assertEqual(self.commands.submit(self.command), receipt)
        self.assertEqual(self.lookup()['receipt'], receipt)
        self.assertEqual(self.runtime.world.observe('sim-nas')['restarts'], 1)
        self.assertEqual(receipt['approval_status_at_recording'], 'APPROVED')
        self.assertEqual(result['proposal']['status'], 'USED')

    def test_reopen_duplicate_and_lookup_do_not_change_journal(self):
        receipt = self.commands.submit(self.command)
        events = self.store.events(self.mission['id'])
        reopened = DecisionCommands(ActionRuntime(Store(self.temp.name)))
        self.assertEqual(reopened.submit(deepcopy(self.command)), receipt)
        self.assertEqual(self.lookup()['receipt'], receipt)
        self.assertEqual(self.store.events(self.mission['id']), events)
        receipt['status'] = 'FORGED'
        self.assertEqual(self.lookup()['receipt']['status'], 'RECORDED')

    def test_same_key_different_payload_is_refused_including_another_mission(self):
        self.commands.submit(self.command)
        another = self.runtime.run(self.runtime.create_restart('nas')['id'])
        for update in ({'reason': 'changed'}, {'decision': 'revoke'}, {'expected_revision': 0},
                       {'actor': 'other'}, {'mission_id': another['id']}):
            with self.subTest(update=update), self.assertRaisesRegex(ContractError, 'COMMAND_KEY_REUSED'):
                self.commands.submit({**self.command, **update})
        self.assertEqual(self.store.get(another['id']), another)

    def test_client_namespaces_are_distinct_but_do_not_bypass_revision(self):
        self.commands.submit(self.command)
        other = {**self.command, 'client_id': 'other-desktop'}
        self.assertEqual(self.lookup(other)['status'], 'NOT_FOUND')
        with self.assertRaisesRegex(ContractError, 'STALE_REVISION'):
            self.commands.submit(other)

    def test_stale_revision_and_proposal_do_not_write(self):
        for update, code in (({'expected_revision': 0}, 'STALE_REVISION'),
                             ({'proposal_sha256': '0' * 64}, 'exact proposal')):
            with self.subTest(update=update), self.assertRaisesRegex(ContractError, code):
                self.commands.submit({**self.command, **update})
            self.assert_unchanged()

    def test_invalid_commands_are_rejected_before_any_write(self):
        variants = [None, [], {**self.command, 'extra': True}]
        for key, values in {'protocol': ['other'], 'store_id': ['bad'], 'client_id': ['', '../x'],
                            'command_key': ['x' * 81], 'mission_id': ['bad'],
                            'expected_revision': [True, -1, 2**53, 1.5], 'proposal_sha256': ['x'],
                            'decision': ['cancel', [], {}], 'actor': ['', '\ud800'],
                            'reason': ['', 'x' * 4001, float('inf')]}.items():
            variants.extend({**self.command, key: value} for value in values)
        for variant in variants:
            with self.subTest(variant=repr(variant)[:100]), self.assertRaises(ValueError):
                self.commands.submit(variant)
        self.assert_unchanged()

    def test_parser_rejects_duplicates_depth_nonfinite_and_oversize(self):
        for raw in ('{"protocol":"x","protocol":"y"}', '[' * 2000 + ']' * 2000,
                    ' ' * 32769, '{', encode(self.command).encode('utf-16'), encode(self.command).replace('explicit synthetic test', '\\ud800'),
                    encode(self.command).replace('"expected_revision":' + str(self.command['expected_revision']), '"expected_revision":1e999')):
            with self.subTest(raw=raw[:60]), self.assertRaises(ContractError):
                parse_command(raw)
        self.assertEqual(parse_command(encode(self.command)), self.command)
        self.assert_unchanged()

    def test_changed_store_rejects_even_previously_recorded_command(self):
        self.commands.submit(self.command)
        with self.store.connection() as db:
            db.execute("UPDATE sync_metadata SET value=? WHERE key='store_id'", ('s-' + 'f' * 32,))
        for action in (lambda: self.lookup(), lambda: self.commands.submit(self.command)):
            with self.assertRaisesRegex(ContractError, 'STORE_CHANGED'):
                action()

    def test_cancel_between_validation_and_commit_prevents_decision(self):
        prepare = self.runtime._prepare_decision
        def race(*args, **kwargs):
            result = prepare(*args, **kwargs)
            self.store.request_cancel(self.mission['id'])
            return result
        with patch.object(self.runtime, '_prepare_decision', side_effect=race):
            with self.assertRaisesRegex(ContractError, 'CANCEL_REQUESTED'):
                self.commands.submit(self.command)
        saved = self.store.get(self.mission['id'])
        self.assertTrue(saved['cancel_requested'])
        self.assertEqual(saved['proposal']['status'], 'PENDING')
        self.assertEqual(self.lookup()['status'], 'NOT_FOUND')
        self.assertNotIn('ACTION_DECISION', [e['kind'] for e in self.store.events(saved['id'])])

    def test_legacy_decide_has_same_cancellation_race_guard(self):
        prepare = self.runtime._prepare_decision
        def race(*args, **kwargs):
            result = prepare(*args, **kwargs)
            self.store.request_cancel(self.mission['id'])
            return result
        with patch.object(self.runtime, '_prepare_decision', side_effect=race):
            with self.assertRaisesRegex(ContractError, 'CANCEL_REQUESTED'):
                self.runtime.decide(self.mission['id'], expected_sha256=self.command['proposal_sha256'],
                                    decision='approve', actor='test', reason='test')
        self.assertEqual(self.store.get(self.mission['id'])['proposal']['status'], 'PENDING')

    def test_revision_changes_between_validation_and_commit_roll_back(self):
        prepare = self.runtime._prepare_decision
        def race(*args, **kwargs):
            result = prepare(*args, **kwargs)
            self.store.save(self.store.get(self.mission['id']), 'SYNTHETIC_CONCURRENT_WRITE')
            return result
        with patch.object(self.runtime, '_prepare_decision', side_effect=race):
            with self.assertRaisesRegex(Busy, 'stale'):
                self.commands.submit(self.command)
        self.assertEqual(self.lookup()['status'], 'NOT_FOUND')
        self.assertEqual(self.store.get(self.mission['id'])['proposal']['status'], 'PENDING')

    def test_sql_failure_rolls_back_decision_event_and_receipt(self):
        before = self.store.events(self.mission['id'])
        with self.store.connection() as db:
            db.execute("CREATE TRIGGER fail_receipt BEFORE INSERT ON command_receipts BEGIN SELECT RAISE(ABORT,'synthetic disk failure'); END")
        with self.assertRaises(sqlite3.IntegrityError):
            self.commands.submit(self.command)
        self.assert_unchanged()
        self.assertEqual(self.store.events(self.mission['id']), before)

    def child(self, mode):
        code = '''
from contextlib import contextmanager
import json, os, sys
from eidolon_core.actions import ActionRuntime
from eidolon_core.commands import DecisionCommands
from eidolon_core.store import Store
class CrashStore(Store):
    @contextmanager
    def connection(self):
        with super().connection() as db:
            db.create_function('crash', 0, lambda: os._exit(73))
            yield db
def checkpoint(kind):
    if kind == 'COMMAND_RECORDED':
        os._exit(74)
store = CrashStore(sys.argv[1])
runtime = ActionRuntime(store, checkpoint=checkpoint)
DecisionCommands(runtime).submit(json.loads(sys.argv[2]))
'''
        if mode == 'before':
            with self.store.connection() as db:
                db.execute('CREATE TRIGGER crash_receipt BEFORE INSERT ON command_receipts BEGIN SELECT crash(); END')
        return subprocess.run([sys.executable, '-c', code, self.temp.name, encode(self.command)],
                              capture_output=True, text=True, timeout=20)

    def test_abrupt_process_exit_before_commit_recovers_without_partial_decision(self):
        before = self.store.events(self.mission['id'])
        result = self.child('before')
        self.assertEqual(result.returncode, 73, result.stderr)
        self.assert_unchanged()
        self.assertEqual(self.store.events(self.mission['id']), before)
        self.assertFalse(self.lookup()['authorizes_resend'])

    def test_abrupt_exit_after_commit_loses_ack_but_keeps_receipt(self):
        result = self.child('after')
        self.assertEqual(result.returncode, 74, result.stderr)
        receipt = self.lookup()['receipt']
        self.assertIsNotNone(receipt)
        self.assertEqual(self.commands.submit(self.command), receipt)
        self.assertEqual(len(self.store.get(self.mission['id'])['proposal']['decisions']), 1)
        self.assertEqual(self.runtime.world.observe('sim-nas')['restarts'], 0)

    def test_existing_receipt_available_while_mission_lock_held(self):
        receipt = self.commands.submit(self.command)
        with self.store.lock(self.mission['id']):
            self.assertEqual(self.commands.submit(self.command), receipt)
            self.assertEqual(self.lookup()['receipt'], receipt)
            with self.assertRaises(Busy):
                self.commands.submit({**self.command, 'command_key': 'new-key'})

    def test_concurrent_same_key_different_missions_only_one_decision_commits(self):
        another = self.runtime.run(self.runtime.create_restart('nas')['id'])
        other = self.request(another)
        barrier = threading.Barrier(2)
        prepare = self.runtime._prepare_decision
        def race(*args, **kwargs):
            entry = prepare(*args, **kwargs)
            barrier.wait(timeout=10)
            return entry
        def submit(command):
            try:
                return self.commands.submit(command)
            except ContractError as exc:
                return str(exc)
        with patch.object(self.runtime, '_prepare_decision', side_effect=race), ThreadPoolExecutor(2) as pool:
            results = list(pool.map(submit, (self.command, other)))
        self.assertEqual(sum(isinstance(r, dict) for r in results), 1)
        self.assertIn('COMMAND_KEY_REUSED', next(r for r in results if isinstance(r, str)))
        missions = [self.store.get(m['id']) for m in (self.mission, another)]
        self.assertEqual(sorted(m['proposal']['status'] for m in missions), ['APPROVED', 'PENDING'])
        self.assertEqual(sum(e['kind'] == 'ACTION_DECISION' for m in missions for e in self.store.events(m['id'])), 1)

    def test_revoke_keeps_both_receipts_and_old_ack_cannot_restore_approval(self):
        approve = self.commands.submit(self.command)
        revoked = {**self.command, 'command_key': 'decision-002', 'decision': 'revoke',
                   'expected_revision': approve['mission_revision']}
        receipt = self.commands.submit(revoked)
        self.assertEqual(receipt['approval_status_at_recording'], 'REVOKED')
        self.assertEqual(self.commands.submit(self.command), approve)
        self.assertEqual(self.lookup(revoked)['receipt'], receipt)
        self.assertEqual(self.runtime.run(self.mission['id'])['status'], 'BLOCKED')
        self.assertEqual(self.runtime.world.observe('sim-nas')['restarts'], 0)

    def test_reject_and_missing_receipt_do_not_claim_effect_absence(self):
        absent = self.lookup()
        self.assertEqual(absent['status'], 'NOT_FOUND')
        self.assertIsNone(absent['receipt'])
        self.assertFalse(absent['authorizes_resend'])
        receipt = self.commands.submit({**self.command, 'decision': 'reject'})
        self.assertEqual(receipt['approval_status_at_recording'], 'REJECTED')
        self.assertEqual(self.runtime.run(self.mission['id'])['status'], 'BLOCKED')

    def test_cli_submit_and_lookup_without_runtime(self):
        path = Path(self.temp.name) / 'command.json'
        path.write_text(encode(self.command))
        base = ['--state', self.temp.name]
        with patch('sys.stdout', new_callable=io.StringIO) as output:
            self.assertEqual(main(base + ['--profile', 'action-sim', 'command-submit', '--request', str(path)]), 0)
            receipt = json.loads(output.getvalue())
        args = base + ['command-receipt', '--store-id', self.command['store_id'],
                       '--client-id', self.command['client_id'], '--command-key', self.command['command_key']]
        with patch('eidolon_core.cli.Runtime', side_effect=AssertionError('no runtime')), \
                patch('eidolon_core.cli.ActionRuntime', side_effect=AssertionError('no runtime')), \
                patch('sys.stdout', new_callable=io.StringIO) as output:
            self.assertEqual(main(args), 0)
            self.assertEqual(json.loads(output.getvalue())['receipt'], receipt)
        with patch('sys.stdout', new_callable=io.StringIO) as output:
            self.assertEqual(main(args[:-1] + ['unknown']), 2)
            self.assertEqual(json.loads(output.getvalue())['status'], 'NOT_FOUND')

    def test_store_change_during_validation_prevents_commit(self):
        prepare = self.runtime._prepare_decision
        def race(*args, **kwargs):
            result = prepare(*args, **kwargs)
            with self.store.connection() as db:
                db.execute("UPDATE sync_metadata SET value=? WHERE key='store_id'", ('s-' + 'f' * 32,))
            return result
        with patch.object(self.runtime, '_prepare_decision', side_effect=race):
            with self.assertRaisesRegex(ContractError, 'STORE_CHANGED'):
                self.commands.submit(self.command)
        self.assertEqual(self.store.get(self.mission['id']), self.mission)

    def test_receipt_requires_json_safe_event_sequence(self):
        with self.store.connection() as db:
            db.execute("UPDATE sqlite_sequence SET seq=? WHERE name='events'", (2**53 - 1,))
        with self.assertRaisesRegex(ContractError, 'safe integer'):
            self.commands.submit(self.command)
        self.assert_unchanged()

    def test_lookup_cli_missing_store_does_not_create_it(self):
        missing = Path(self.temp.name) / 'missing'
        with patch('sys.stderr', new_callable=io.StringIO):
            code = main(['--state', str(missing), 'command-receipt', '--store-id', self.command['store_id'],
                         '--client-id', 'test', '--command-key', 'missing'])
        self.assertEqual(code, 2)
        self.assertFalse(missing.exists())


if __name__ == '__main__':
    unittest.main()
