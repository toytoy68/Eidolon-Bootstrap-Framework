# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : research_disclosure_demo.py
# Description : Reçus après annulation et références Web minimisées, simulés
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""All data, DNS and reads are synthetic; no external service is contacted."""
import argparse
import hashlib

from eidolon_core.contracts import encode
from eidolon_core.presentation import header, message
from eidolon_core.research import Hit, Page, ResearchCoordinator


class Provider:
    provider_id = 'disclosure-fixture/1'
    def search(self, query, limit):
        return [Hit('https://docs.example/a?token=SYNTHETIC_VALUE', 'Document fictif')]


class Reader:
    reader_id = 'disclosure-fixture/1'
    def __init__(self):
        self.calls, self.cancelled = 0, False

    def read(self, url, policy):
        self.calls += 1
        self.cancelled = self.calls == 1
        return Page(url, 200, 'text/plain', b'Ne pas confondre lecture et fait confirme.', policy.policy_id)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--format', choices=('json', 'human'), default='json')
    args = parser.parse_args(argv)
    reader = Reader()
    c = ResearchCoordinator([Provider()], reader, resolver=lambda *args: ['9.9.9.9'])
    first = c.run('synthetic', cancelled=lambda: reader.cancelled)
    reader.cancelled = False
    second = c.run('synthetic', cancelled=lambda: reader.cancelled)
    third = c.run('synthetic')
    assert first['status'] == 'CANCELLED' and first['sources'][0]['state'] == 'READ'
    assert second['status'] == 'READ_TARGET_MET' and not second['sources'][0]['cache_hit']
    assert third['sources'][0]['cache_hit'] and reader.calls == 2
    reports = [first, second, third]
    assert 'SYNTHETIC_VALUE' not in encode(reports)
    expected = hashlib.sha256(b'https://docs.example/a?token=SYNTHETIC_VALUE').hexdigest()
    assert all(r['sources'][0]['url_sha256'] == expected for r in reports)
    if args.format == 'human':
        print(header(title='Reçus et URL Web simulés'))
        print(message('INFO', 'Données et lectures synthétiques ; aucun réseau.'))
        print(message('OK', 'Annulation : reçu conservé, aucune entrée de cache créée.'))
        print(message('OK', 'Nouvelle demande : lecture refaite, puis cache normal vérifié.'))
        print(message('OK', 'Paramètre absent des URL du rapport ; empreinte exacte vérifiée.'))
        print(message('ATTENTION', 'Chemins et textes non anonymisés ; une lecture ne confirme aucun fait.'))
    else:
        print(encode({'synthetic': True, 'read_calls': reader.calls, 'reports': reports}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
