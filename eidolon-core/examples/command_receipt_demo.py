# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : command_receipt_demo.py
# Description : Accusé perdu, consultation du reçu et reprise synthétique
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

"""No network: a post-commit exception simulates loss of the decision reply."""
import argparse
import tempfile

from eidolon_core.actions import ActionRuntime
from eidolon_core.client_sync import ClientSync
from eidolon_core.commands import DecisionCommands, PROTOCOL, lookup_receipt
from eidolon_core.contracts import encode
from eidolon_core.presentation import header, message
from eidolon_core.store import Store


class LostReply(BaseException):
    pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--format', choices=('json', 'human'), default='json')
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='eidolon-command-demo-') as directory:
        store = Store(directory)
        def checkpoint(kind):
            if kind == 'COMMAND_RECORDED':
                raise LostReply()
        runtime = ActionRuntime(store, checkpoint=checkpoint)
        mission = runtime.run(runtime.create_restart('nas')['id'])
        capture = ClientSync(store).snapshot(mission['id'])
        command = dict(protocol=PROTOCOL, store_id=capture['store_id'],
                       client_id='synthetic-desktop', command_key='approval-001',
                       mission_id=mission['id'], expected_revision=mission['revision'],
                       proposal_sha256=mission['proposal']['sha256'], decision='approve',
                       actor='synthetic-demo-operator', reason='explicit local simulation')
        try:
            DecisionCommands(runtime).submit(command)
        except LostReply:
            pass
        else:
            raise AssertionError('the post-commit reply must be lost in this demo')
        reopened = Store(directory)
        found = lookup_receipt(reopened, **{k: command[k] for k in ('store_id', 'client_id', 'command_key')})
        assert found['status'] == 'FOUND' and not found['execution_evidence']
        assert runtime.world.observe('sim-nas')['restarts'] == 0
        assert reopened.get(mission['id'])['result'] is None
        resumed = ActionRuntime(reopened)
        events_before = reopened.events(mission['id'])
        duplicate = DecisionCommands(resumed).submit(command)  # Explicit duplicate probe, not a retry policy.
        assert duplicate == found['receipt']
        assert reopened.events(mission['id']) == events_before
        final = resumed.run(mission['id'])  # Separate explicit execution after receipt reconciliation.
        assert final['status'] == 'SUCCEEDED' and final['outcome']['status'] == 'ACHIEVED'
        assert resumed.world.observe('sim-nas')['restarts'] == 1
        events = reopened.events(mission['id'])
        decision_count = sum(e['kind'] == 'ACTION_DECISION' for e in events)
        launch_count = sum(e['kind'] == 'CALL_STARTED' for e in events)
        assert decision_count == launch_count == 1
        result = dict(synthetic=True, initial_snapshot=capture, command=command, lookup=found,
                      duplicate_receipt_unchanged=True, effects_before_explicit_run=0,
                      decision_events=decision_count, tool_launches=launch_count,
                      final_snapshot=ClientSync(reopened).snapshot(mission['id']))
        if args.format == 'json':
            print(encode(result))
        else:
            print(header(title='Reçu après coupure simulée') + '\n'.join([
                message('OK', 'Décision retrouvée après perte de son accusé ; aucun outil lancé à ce stade.'),
                message('OK', 'Commande répétée : même reçu, une seule décision enregistrée.'),
                message('OK', 'Reprise explicite : un redémarrage fictif, résultat vérifié.'),
                message('INFO', 'Tests locaux synthétiques ; aucun réseau, service personnel ou GPU.')]))


if __name__ == '__main__':
    main()
