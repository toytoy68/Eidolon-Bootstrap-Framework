# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : research_pauses_demo.py
# Description : Pause HTTP synthétique persistante, redémarrage et revue locale
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Real coordinator, transport parser and SQLite; entirely fake DNS/HTTP IO."""
import argparse
from pathlib import Path
import tempfile

from eidolon_core.contracts import encode
from eidolon_core.presentation import header, message
from eidolon_core.research import Hit, ResearchCoordinator
from eidolon_core.research_pauses import ResearchPauses, origin_scope
from eidolon_core.web_reader import WebReader
from eidolon_core.web_transport import RawResponse


class Provider:
    provider_id = 'synthetic-reference/1'
    def search(self, query, limit):
        return [Hit('https://sources.example/manual', 'Document fictif')]


class Connector:
    def __init__(self):
        self.calls = 0
        self.refuse = True

    def exchange(self, **kwargs):
        self.calls += 1
        if self.refuse:
            return RawResponse(429, (('Retry-After', 'invalid'),), b'', True)
        body = b'Synthetic reference; this content is not a confirmed fact.'
        return RawResponse(200, (('Content-Type', 'text/plain'), ('Content-Length', str(len(body)))), body, True)


def run_demo():
    with tempfile.TemporaryDirectory(prefix='eidolon-web-pauses-') as directory:
        path = Path(directory) / 'research-pauses.sqlite3'
        wall = [1_000_000.0]  # explicit fake wall clock; never a measurement of server time
        dns = lambda host, port: ['9.9.9.9']  # never resolved or contacted
        connector = Connector()
        reader = WebReader(dns, connector, transport_id='synthetic-pauses/1')
        pauses = ResearchPauses(path, clock=lambda: wall[0])
        first = ResearchCoordinator([Provider()], reader, resolver=dns, pauses=pauses).run('synthetic reference')
        assert first['sources'][0]['state'] == 'RATE_LIMITED'
        wall[0] += 3600
        reopened = ResearchPauses(path, clock=lambda: wall[0])
        coordinator = ResearchCoordinator([Provider()], reader, resolver=dns, pauses=reopened)
        after_restart = coordinator.run('synthetic reference')
        assert after_restart['read_calls'] == 0 and connector.calls == 1
        assert after_restart['sources'][0]['state'] == 'RETRY_WAIT'
        pause = reopened.active(origin_scope('sources.example', 443))
        release = reopened.release(pause['id'], expected_revision=pause['revision'],
                                   actor='synthetic-operator', reason='fixture reviewed; explicit next attempt')
        assert connector.calls == 1 and release['request_sent'] is False
        connector.refuse = False
        final = coordinator.run('synthetic reference')  # separate explicit call after release
        assert final['status'] == 'READ_TARGET_MET' and connector.calls == 2
        return {'synthetic': True, 'network_used': False, 'fake_clock': True,
                'first': first, 'after_restart': after_restart, 'release': release, 'final': final,
                'gate': reopened.inspect(), 'verified': {'connector_calls': 2, 'calls_during_pause': 0,
                    'calls_caused_by_release': 0, 'committed_pause_survived_restart': True}}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--format', choices=('json', 'human'), default='json')
    args = parser.parse_args()
    result = run_demo()
    if args.format == 'human':
        print(header(title='Suspensions Web simulées'))
        print(message('INFO', 'DNS, HTTP et horloge simulés ; base SQLite temporaire.'))
        print(message('OK', 'Pause 429 conservée après redémarrage : aucun nouvel appel.'))
        print(message('OK', 'Levée explicite journalisée, sans envoi de requête.'))
        print(message('OK', 'Nouvelle recherche explicite : texte fictif reçu et identifié.'))
        print(message('ATTENTION', 'Texte reçu ne signifie pas fait confirmé ; aucun accès Internet réel.'))
    else:
        print(encode(result))


if __name__ == '__main__':
    main()
