# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : client_sync_demo.py
# Description : Reconnexion synthétique en lecture seule, mission réelle locale
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""No network: disconnect means retaining a cursor while local Core progresses."""
import argparse
import tempfile

from eidolon_core.client_sync import ClientSync
from eidolon_core.contracts import encode
from eidolon_core.memory import DEMO_REQUEST
from eidolon_core.presentation import header, message
from eidolon_core.runtime import Runtime
from eidolon_core.store import Store


def run_demo():
    with tempfile.TemporaryDirectory(prefix='eidolon-sync-') as directory:
        store = Store(directory)
        runtime = Runtime(store)
        mission = runtime.create(DEMO_REQUEST)
        sync = ClientSync(store)
        initial = sync.snapshot(mission['id'])
        result = runtime.run(mission['id'])  # user-authorized synthetic text.stats only
        assert result['status'] == 'SUCCEEDED'
        sync = ClientSync(Store(directory))  # reconstruct the reader; cursor remains valid
        first = sync.poll(mission['id'], initial['cursor'], limit=2)
        duplicate = sync.poll(mission['id'], initial['cursor'], limit=2)
        assert first['events'] == duplicate['events'] and first['cursor'] == duplicate['cursor']
        pages = [first]
        while pages[-1]['has_more']:
            pages.append(sync.poll(mission['id'], pages[-1]['cursor'], limit=2))
        sequences = [e['sequence'] for page in pages for e in page['events']]
        assert len(sequences) == len(set(sequences)) == len(store.events(mission['id'])) - 1
        assert sum(e['kind'] == 'CALL_STARTED' for e in store.events(mission['id'])) == 1
        assert pages[-1]['snapshot']['mission']['outcome_status'] == 'ACHIEVED'
        stale = {**pages[-1]['cursor'], 'anchor_sha256': '0' * 64}
        reset = sync.poll(mission['id'], stale)
        assert reset['status'] == 'RESET_REQUIRED'
        assert not any(p['authorizes_execution'] for p in [initial, *pages, reset])
        return {'synthetic': True, 'network_used': False, 'initial': initial,
                'pages': pages, 'reset_example': reset,
                'verified': {'unique_events': len(sequences), 'pages': len(pages),
                             'tool_launches': 1, 'duplicate_delivery_same_references': True,
                             'mission_status': result['status']}}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--format', choices=('json', 'human'), default='json')
    args = parser.parse_args()
    result = run_demo()
    if args.format == 'human':
        print('\n'.join([header(title='Reconnexion synthétique'),
              message('INFO', 'Client simulé ; aucun réseau, aucune commande distante.'),
              message('OK', f"Mission vérifiée, {result['verified']['unique_events']} événements récupérés "
                      f"sur {result['verified']['pages']} pages ; un seul lancement d'outil."),
              message('OK', 'Livraison répétée reconnue ; curseur incohérent → RESET_REQUIRED.'),
              message('ATTENTION', 'Prototype local : authentification, API réseau et Windows non livrés.')]))
    else:
        print(encode(result))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
