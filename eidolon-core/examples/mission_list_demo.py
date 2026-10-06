# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : mission_list_demo.py
# Description : Inventaire paginé synthétique et changement entre pages
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Temporary local state only; no model service, network or private corpus."""
import argparse
import tempfile

from eidolon_core.contracts import encode
from eidolon_core.memory import DEMO_REQUEST
from eidolon_core.mission_list import MissionList
from eidolon_core.presentation import header, message
from eidolon_core.runtime import Runtime
from eidolon_core.store import Store


def run_demo():
    with tempfile.TemporaryDirectory(prefix='eidolon-mission-list-') as directory:
        store = Store(directory)
        runtime = Runtime(store)
        missions = [runtime.create(DEMO_REQUEST) for _ in range(3)]
        listing = MissionList(store)
        first = listing.page(limit=1)
        original_revision = store.get(missions[0]['id'])['revision']
        store.request_cancel(missions[0]['id'])
        interrupted = listing.page(cursor=first['next_cursor'], limit=1)
        assert interrupted['status'] == 'RESET_REQUIRED' and interrupted['items'] == []
        assert store.get(missions[0]['id'])['revision'] == original_revision
        pages = [listing.page(limit=1)]  # explicit fresh read, never an automatic command
        while pages[-1]['has_more']:
            pages.append(listing.page(cursor=pages[-1]['next_cursor'], limit=1))
        items = [i for p in pages for i in p['items']]
        assert [i['mission']['id'] for i in items] == sorted(m['id'] for m in missions)
        assert all(p['generation'] == pages[0]['generation'] for p in pages)
        assert sum(i['mission']['cancel_requested'] for i in items) == 1
        assert all(i['mission']['status'] == 'NEW' for i in items)
        assert not any(e['kind'] == 'CALL_STARTED' for m in missions for e in store.events(m['id']))
        return {'synthetic': True, 'network_used': False, 'initial_page': first,
                'changed_between_pages': interrupted, 'fresh_pages': pages,
                'verified': {'missions': len(items), 'pages': len(pages), 'unique_missions': len(items),
                             'tool_launches': 0, 'cancellation_is_not_stopping': True,
                             'mixed_generation_refused': True}}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--format', choices=('json', 'human'), default='json')
    args = parser.parse_args()
    result = run_demo()
    if args.format == 'human':
        print(header(title='Inventaire des missions'))
        print(message('INFO', 'Données synthétiques ; aucun réseau ni outil exécuté.'))
        print(message('OK', 'Trois missions sur trois pages cohérentes, sans doublon.'))
        print(message('OK', 'Changement entre pages détecté : RESET_REQUIRED, puis lecture recommencée.'))
        print(message('ATTENTION', "Une annulation demandée n'est pas un arrêt confirmé."))
    else:
        print(encode(result))


if __name__ == '__main__':
    main()
