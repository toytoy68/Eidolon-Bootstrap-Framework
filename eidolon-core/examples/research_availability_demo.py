# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : research_availability_demo.py
# Description : Capacité des pauses, doublons et découverte Web simulés
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Synthetic providers, DNS and pages only; no Internet or mission execution."""
import argparse
from pathlib import Path
import tempfile

from eidolon_core.contracts import encode
from eidolon_core.presentation import header, message
from eidolon_core.research import AccessFailure, Hit, Page, ResearchCoordinator
from eidolon_core.research_pauses import MAX_RECORDS, PauseCapacityError, ResearchPauses, provider_scope


class Provider:
    provider_id = 'availability-fixture/1'
    def __init__(self, mode='hits'):
        self.mode, self.calls = mode, 0

    def search(self, query, limit):
        self.calls += 1
        if self.mode == 'unavailable':
            raise AccessFailure('UNAVAILABLE')
        if self.mode == 'empty':
            return []
        return [Hit('https://docs.example/a', 'Document synthétique'),
                Hit('https://docs.example/a?utm_source=fixture', 'Copie synthétique')]


class Reader:
    reader_id = 'availability-fixture/1'
    def __init__(self):
        self.calls = 0

    def read(self, url, policy):
        self.calls += 1
        return Page(url, 200, 'text/plain', b'Same synthetic body, not independent evidence.', policy.policy_id)


def coordinator(provider, reader, **kwargs):
    return ResearchCoordinator([provider], reader, resolver=lambda *args: ['9.9.9.9'], **kwargs)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--format', choices=('json', 'human'), default='json')
    args = parser.parse_args(argv)
    reader = Reader()
    core = coordinator(Provider(), reader)
    first = core.run('synthetic', required_pages=2)
    cached = core.run('synthetic', required_pages=2)
    assert first['status'] == cached['status'] == 'PARTIAL'
    assert first['readable_pages'] == cached['readable_pages'] == 1
    assert first['sources'][1]['state'] == 'DUPLICATE_CONTENT'
    assert first['sources'][1]['duplicate_of'] == first['sources'][0]['id']
    assert reader.calls == 2 and all(s['cache_hit'] for s in cached['sources'])
    empty = coordinator(Provider('empty'), Reader()).run('synthetic')
    down = coordinator(Provider('unavailable'), Reader()).run('synthetic')
    assert empty['discovery_status'] == 'EMPTY' and down['discovery_status'] == 'UNAVAILABLE'
    with tempfile.TemporaryDirectory() as root:
        pauses = ResearchPauses(Path(root) / 'pauses.sqlite3', clock=lambda: 1000)
        for i in range(MAX_RECORDS):
            row = pauses.pause([provider_scope(f'occupied-{i}')], reason='ACCESS_DENIED')[0]
        provider, reader = Provider(), Reader()
        core = coordinator(provider, reader, pauses=pauses)
        refusals = 0
        for _ in range(2):
            try:
                core.run('synthetic')
            except PauseCapacityError:
                refusals += 1
        assert refusals == 2 and provider.calls == reader.calls == 0
        release = pauses.release(row['id'], expected_revision=row['revision'],
                                 actor='synthetic-reviewer', reason='reviewed fixture only')
        assert not release['request_sent'] and provider.calls == reader.calls == 0
        resumed = core.run('synthetic')
        assert resumed['status'] == 'READ_TARGET_MET' and reader.calls == 1
        history = pauses.inspect()
        assert len(history['pauses']) == MAX_RECORDS and history['audit_events'] == MAX_RECORDS + 1
    if args.format == 'human':
        print(header(title='Disponibilité et comptage Web simulés'))
        print(message('INFO', 'Fournisseurs, DNS et pages fictifs ; aucun réseau.'))
        print(message('OK', 'Deux URL et deux reçus, mais un seul contenu compté ; cache vérifié.'))
        print(message('OK', 'Recherche vide distincte des fournisseurs indisponibles.'))
        print(message('OK', 'Capacité refusée deux fois, puis place libérée par revue explicite.'))
        print(message('OK', 'Historique conservé ; reprise uniquement sur nouvelle demande.'))
        print(message('ATTENTION', 'Comparaison exacte seulement ; aucune preuve de vérité ou indépendance.'))
    else:
        print(encode({'synthetic': True, 'duplicate_report': first, 'cached_report': cached,
                      'discovery': [empty['discovery_status'], down['discovery_status']],
                      'capacity_refusals': refusals, 'release': release,
                      'resumed_status': resumed['status'], 'retained_audit_events': history['audit_events']}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
