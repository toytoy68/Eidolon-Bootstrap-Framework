# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_research_disclosure.py
# Description : Cache interrompu et projection des URL sans paramètres
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
import hashlib
import json
import unittest
from unittest.mock import patch

from eidolon_core.research import Hit, ResearchCoordinator, ResearchLimits
from eidolon_core.web_reader import WebReader
from eidolon_core.web_transport import RawResponse
from tests.test_research import Clock, Provider, Reader, dns, hit
from tests.test_web_transport import DNS, PUBLIC, OTHER_PUBLIC, FakeConnector, ok, redirect


class ResearchDisclosureTests(unittest.TestCase):
    def test_interrupted_receipt_is_retained_but_not_reused_from_cache(self):
        for cause in ('cancel', 'coordinator_timeout', 'reader_timeout'):
            with self.subTest(cause=cause):
                clock, cancelled = Clock(), [False]
                reader = Reader()
                original = reader.read
                def interrupted(url, policy):
                    if cause == 'cancel': cancelled[0] = True
                    if cause == 'coordinator_timeout': clock.value += 31
                    if cause == 'reader_timeout': reader.replies[url] = dict(deadline_exceeded=True)
                    return original(url, policy)
                c = ResearchCoordinator([Provider('p', [hit()])], reader, resolver=dns, clock=clock)
                with patch.object(reader, 'read', side_effect=interrupted):
                    first = c.run('synthetic', cancelled=lambda: cancelled[0])
                self.assertEqual(first['status'], 'CANCELLED' if cause == 'cancel' else 'DEADLINE')
                self.assertEqual(first['sources'][0]['state'], 'READ')
                self.assertIsNotNone(first['sources'][0]['body_sha256'])
                cancelled[0] = False
                reader.replies = {}
                second = c.run('synthetic')
                self.assertEqual(len(reader.calls), 2)
                self.assertFalse(second['sources'][0]['cache_hit'])
                self.assertEqual(second['status'], 'READ_TARGET_MET')

    def test_interrupt_during_cached_final_dns_does_not_adopt_cached_text(self):
        for cause in ('cancel', 'timeout'):
            with self.subTest(cause=cause):
                clock, cancelled = Clock(), [False]
                c = ResearchCoordinator([Provider('p', [hit()])], Reader({hit().url: dict(url='https://final.example/')}),
                                        resolver=dns, clock=clock)
                c.run('synthetic')
                def resolve(host, port):
                    if host == 'final.example':
                        if cause == 'cancel': cancelled[0] = True
                        else: clock.value += 31
                    return dns(host, port)
                c.resolver = resolve
                result = c.run('synthetic', cancelled=lambda: cancelled[0])
                self.assertEqual(result['status'], 'CANCELLED' if cause == 'cancel' else 'DEADLINE')
                self.assertEqual(result['readable_pages'], 0)
                self.assertIsNone(result['sources'][0]['text'])
                self.assertFalse(result['sources'][0]['cache_hit'])

    def test_late_stop_does_not_leave_new_cache_entries(self):
        clock = Clock()
        reader = Reader({hit('b').url: dict(body=b'A distinct second document.')})
        c = ResearchCoordinator([Provider('p', [hit(), hit('b')])], reader, resolver=dns, clock=clock)
        read = reader.read
        def slow_second(url, policy):
            if url.endswith('/b'): clock.value = 31
            return read(url, policy)
        with patch.object(reader, 'read', side_effect=slow_second):
            result = c.run('synthetic', required_pages=2)
        self.assertEqual(result['status'], 'DEADLINE')
        self.assertEqual(result['readable_pages'], 2)
        c.run('synthetic')
        self.assertEqual(len(reader.calls), 3)

    def test_query_removed_from_report_but_used_for_transport_and_cache(self):
        url = 'https://docs.example.com/a?token=ZQX_SECRET'
        connector = FakeConnector({(PUBLIC, '/a?token=ZQX_SECRET'): ok(b'fixture')})
        c = ResearchCoordinator([Provider('p', [Hit(url, 'fixture')])], WebReader(DNS, connector), resolver=DNS)
        first = c.run('synthetic')
        self.assertEqual(first['version'], 2)
        self.assertNotIn('ZQX_SECRET', json.dumps(first))
        source = first['sources'][0]
        for name in ('url', 'final_url'):
            self.assertEqual(source[name], 'https://docs.example.com/a')
            self.assertEqual(source[name+'_sha256'], hashlib.sha256(url.encode()).hexdigest())
        self.assertEqual(source['retrieval']['final_url_sha256'], source['final_url_sha256'])
        self.assertEqual(connector.calls[0]['target'], '/a?token=ZQX_SECRET')
        second = c.run('synthetic')
        self.assertTrue(second['sources'][0]['cache_hit'])
        self.assertEqual(first['sources'][0]['observed_at'], second['sources'][0]['observed_at'])
        self.assertEqual(len(connector.calls), 1)
        self.assertNotIn('ZQX_SECRET', json.dumps(second))

    def test_queries_distinguish_sources_even_when_display_urls_match(self):
        urls = [hit('a?variant=one').url, hit('a?variant=two').url]
        reader = Reader({url: dict(body=f'Distinct document {i}'.encode()) for i, url in enumerate(urls)})
        c = ResearchCoordinator([Provider('p', [Hit(u, 'fixture') for u in urls])], reader, resolver=dns)
        report = c.run('synthetic', required_pages=2)
        self.assertEqual(report['readable_pages'], 2)
        a,b = report['sources']
        self.assertEqual(a['url'], b['url'])
        self.assertNotEqual(a['url_sha256'], b['url_sha256'])
        self.assertNotEqual(a['id'], b['id'])
        self.assertEqual(reader.calls, urls)

    def test_redirect_and_refusal_minimize_both_urls_and_retrieval(self):
        for status in (200, 403, 429):
            with self.subTest(status=status):
                connector = FakeConnector({(PUBLIC, '/a?start=SECRET_A'): redirect('https://cdn.example.com/b?end=SECRET_B'),
                    (OTHER_PUBLIC, '/b?end=SECRET_B'): ok() if status == 200 else RawResponse(status, (), b'', True)})
                c = ResearchCoordinator([Provider('p', [Hit('https://docs.example.com/a?start=SECRET_A', 'fixture')])],
                                        WebReader(DNS, connector), resolver=DNS)
                result = c.run('synthetic')
                self.assertNotIn('SECRET_', json.dumps(result))
                source = result['sources'][0]
                self.assertEqual(source['url'], 'https://docs.example.com/a')
                self.assertEqual(source['final_url'], 'https://cdn.example.com/b')
                self.assertEqual(source['http_status'], status)
                self.assertEqual(len(connector.calls), 2)
                self.assertEqual(result['readable_pages'], int(status == 200))

    def test_projection_does_not_mutate_cache_or_erase_content(self):
        url = hit('a?secret=QUERY').url
        c = ResearchCoordinator([Provider('p', [Hit(url, 'Title stays', 'Snippet stays')])], Reader(), resolver=dns)
        result = c.run('synthetic')
        source = result['sources'][0]
        self.assertEqual(source['found_by'][0]['title'], 'Title stays')
        self.assertEqual(source['found_by'][0]['snippet'], 'Snippet stays')
        self.assertIn('Ne pas', source['text'])
        cached = next(iter(c._cache.values()))[1]
        self.assertEqual(cached['final_url'], url)
        source['text'] = 'changed'
        self.assertIn('Ne pas', c.run('synthetic')['sources'][0]['text'])

    def test_fragment_and_refused_credentials_are_never_reported(self):
        for url in ('https://docs.example/a?token=SECRET#FRAGMENT', 'https://user:SECRET@docs.example/a'):
            c = ResearchCoordinator([Provider('p', [Hit(url, 'fixture')])], Reader(), resolver=dns)
            result = c.run('synthetic')
            self.assertNotIn('SECRET', json.dumps(result))
            self.assertNotIn('FRAGMENT', json.dumps(result))

    def test_structured_hops_are_minimized_without_inventing_full_url_hash(self):
        from eidolon_core.research_report import project_report
        report = {'version': 1, 'sources': [{'url': None, 'final_url': None,
            'retrieval': {'final_url': 'https://docs.example/a?token=SECRET',
                          'hops': [{'url': 'https://user:PASS@docs.example/a?token=SECRET#FRAGMENT'}]}}]}
        original = json.dumps(report)
        result = project_report(report)
        self.assertNotIn('SECRET', json.dumps(result))
        self.assertNotIn('PASS', json.dumps(result))
        self.assertNotIn('FRAGMENT', json.dumps(result))
        hop = result['sources'][0]['retrieval']['hops'][0]
        self.assertEqual(hop['url'], 'https://docs.example/a')
        self.assertNotIn('url_sha256', hop)
        self.assertEqual(json.dumps(report), original)

    def test_malformed_optional_hops_are_omitted_with_diagnostic(self):
        from eidolon_core.research_report import project_report
        for hops in ('SECRET', [None], [{}]*12):
            with self.subTest(hops=hops):
                result = project_report({'sources': [{'retrieval': {'hops': hops}}]})
                retrieval = result['sources'][0]['retrieval']
                self.assertNotIn('hops', retrieval)
                self.assertEqual(retrieval['hops_omitted'], 'INVALID_HOPS')
        for url in (42, 'https://[bad/?SECRET', 'file:///SECRET', 'https://docs.example/'+'X'*2048, '\ud800'):
            with self.subTest(url=url):
                result = project_report({'sources': [{'retrieval': {'hops': [{'url': url}]}}]})
                hop = result['sources'][0]['retrieval']['hops'][0]
                self.assertIsNone(hop['url'])
                self.assertEqual(hop['url_omitted'], 'INVALID_URL')

    def test_report_projection_does_not_claim_to_redact_page_text_or_paths(self):
        from eidolon_core.research_report import project_report
        result = project_report({'sources': [{'url': 'https://docs.example/PATH_VALUE?token=QUERY_VALUE',
                                            'text': 'CONTENT_VALUE', 'found_by': [{'snippet': 'SNIPPET_VALUE'}]}]})
        serialized = json.dumps(result)
        self.assertNotIn('QUERY_VALUE', serialized)
        for retained in ('PATH_VALUE', 'CONTENT_VALUE', 'SNIPPET_VALUE'):
            self.assertIn(retained, serialized)
