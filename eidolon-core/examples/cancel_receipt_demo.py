# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : cancel_receipt_demo.py
# Description : Annulation demandée, accusé perdu et effet inconnu conservé
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

"""Local synthetic cancellation; no network and no forced external stop."""
import argparse
from pathlib import Path
import tempfile

from eidolon_core.client_sync import ClientSync
from eidolon_core.commands import CANCEL_PROTOCOL, CancelCommands, lookup_receipt
from eidolon_core.contracts import encode
from eidolon_core.memory import DEMO_REQUEST
from eidolon_core.presentation import header, message
from eidolon_core.runtime import Runtime
from eidolon_core.store import Store


class Interrupted(BaseException):
    pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--format', choices=('json', 'human'), default='json')
    args = parser.parse_args()
    cases = []
    with tempfile.TemporaryDirectory(prefix='eidolon-cancel-demo-') as directory:
        for scenario in ('before-execution', 'interrupted-call'):
            store = Store(Path(directory) / scenario)
            runtime = Runtime(store)
            mission = runtime.create(DEMO_REQUEST)
            if scenario == 'interrupted-call':
                def crash(kind):
                    if kind == 'CALL_STARTED':
                        raise Interrupted()
                try:
                    Runtime(store, checkpoint=crash).run(mission['id'])
                except Interrupted:
                    pass
                else:
                    raise AssertionError('expected interruption at the durable launch marker')
            initial = ClientSync(store).snapshot(mission['id'])
            command = dict(protocol=CANCEL_PROTOCOL, store_id=initial['store_id'],
                           client_id='synthetic-desktop', command_key='cancel-001', mission_id=mission['id'],
                           actor='synthetic-demo-operator', reason='explicit local cancellation')
            with store.lock(mission['id']):
                CancelCommands(store).submit(command)  # Discard reply to simulate a lost ACK.
            reopened = Store(store.directory)
            lookup = lookup_receipt(reopened, **{k: command[k] for k in ('store_id', 'client_id', 'command_key')})
            assert lookup['status'] == 'FOUND' and not lookup['receipt']['effect_absence_evidence']
            events = reopened.events(mission['id'])
            assert CancelCommands(reopened).submit(command) == lookup['receipt']
            assert reopened.events(mission['id']) == events
            pending = ClientSync(reopened).poll(mission['id'], initial['cursor'])
            assert pending['snapshot']['mission']['cancel_requested']
            assert pending['snapshot']['mission']['status'] == ('NEW' if scenario == 'before-execution' else 'RUNNING')
            result = Runtime(reopened).run(mission['id'])
            assert result['status'] == ('CANCELLED' if scenario == 'before-execution' else 'REVIEW_REQUIRED')
            assert result['result'] is None
            cases.append(dict(scenario=scenario, command=command, lookup=lookup,
                              after_request=pending, final=ClientSync(reopened).snapshot(mission['id']),
                              duplicate_added_events=False))
    if args.format == 'json':
        print(encode({'synthetic': True, 'scenarios': cases}))
    else:
        print(header(title="Reçus d'annulation") + '\n'.join([
            message('OK', 'Demande enregistrée sous verrou ; accusé perdu puis reçu retrouvé.'),
            message('OK', 'Commande répétée sans nouvel événement ; aucun outil lancé par la demande.'),
            message('OK', 'Avant exécution : annulation confirmée par le runtime.'),
            message('ATTENTION', 'Appel interrompu : REVIEW_REQUIRED conservé, absence d’effet non déduite.'),
            message('INFO', 'Simulation locale uniquement ; aucun service personnel contacté.')]))


if __name__ == '__main__':
    main()
