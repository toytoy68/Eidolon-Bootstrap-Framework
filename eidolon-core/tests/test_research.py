# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_research.py
# Description : Recherche simulée, blocages et preuves indépendantes des extraits
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
from dataclasses import replace
import hashlib
import itertools
import socket
import unittest
from unittest.mock import patch

from eidolon_core.contracts import ContractError, encode
from eidolon_core.egress import WebPolicy
from eidolon_core.research import AccessFailure, Hit, Page, ResearchCoordinator, ResearchLimits


class Clock:
    def __init__(self): self.value = 0
    def __call__(self): return self.value


class Provider:
    def __init__(self, identity, hits): self.provider_id, self.hits, self.calls = identity, hits, 0
    def search(self, query, limit):
        self.calls += 1
        if isinstance(self.hits, Exception): raise self.hits
        return self.hits


class Reader:
    reader_id = "synthetic-reader/1"
    def __init__(self, replies=None): self.replies, self.calls = replies or {}, []
    def read(self, url, policy):
        self.calls.append(url)
        reply = self.replies.get(url, {})
        if isinstance(reply, Exception): raise reply
        return Page(**{**dict(url=url, status=200, media_type="text/plain", body=b"Ne pas confirmer sans preuve.",
                             policy_id=policy.policy_id), **reply})


def dns(*args): return ["9.9.9.9"]

def hit(path="a", **kw): return Hit("https://docs.example/"+path, "Synthetic reference", **kw)


class ResearchTests(unittest.TestCase):
    def coordinator(self, providers=None, reader=None, **kw):
        return ResearchCoordinator(providers or [Provider("p1", [hit()])], reader or Reader(), resolver=dns, **kw)

    def test_fallback_and_receipt_not_snippet(self):
        a, b = Provider("p1", AccessFailure("RATE_LIMITED", 30)), Provider("p2", [hit(snippet="Tout est confirmé.")])
        r = self.coordinator([a,b]).run("référence synthétique")
        self.assertEqual(r["status"], "READ_TARGET_MET")
        self.assertEqual([p["status"] for p in r["providers"]], ["RATE_LIMITED", "OK"])
        s = r["sources"][0]
        self.assertEqual(s["text"], "Ne pas confirmer sans preuve.")
        self.assertEqual(s["body_sha256"], hashlib.sha256(s["text"].encode()).hexdigest())
        self.assertEqual(s["found_by"][0]["snippet"], "Tout est confirmé.")
        self.assertEqual((a.calls,b.calls), (1,1))

    def test_blocked_pages_do_not_become_successful_sources(self):
        for reply, state in [(dict(status=403),"ACCESS_DENIED"), (dict(status=429),"RATE_LIMITED"),
            (dict(status=500),"HTTP_ERROR"), (dict(body=b""),"EMPTY_CONTENT"),
            (dict(body=b"\xff"),"INVALID_ENCODING"), (dict(complete=False),"TRUNCATED"),
            (dict(media_type="application/pdf"),"UNSUPPORTED_CONTENT")]:
            with self.subTest(state=state):
                r = self.coordinator(reader=Reader({hit().url:reply})).run("reference")
                self.assertEqual(r["status"], "NO_READABLE_SOURCE")
                self.assertEqual(r["sources"][0]["state"], state)
                self.assertIsNone(r["sources"][0]["text"])

    def test_http_200_challenge_login_and_legitimate_captcha_article(self):
        cases=[("<title>Just a moment...</title><p>Wait</p>","CHALLENGE_SUSPECTED"),
               ('<title>Account</title><input type="password">',"LOGIN_SUSPECTED"),
               ("<title>Research about CAPTCHA</title><p>CAPTCHA</p>","UNSUPPORTED_CONTENT")]
        for html,state in cases:
            r=self.coordinator(reader=Reader({hit().url:dict(media_type="text/html",body=html.encode())})).run("reference")
            self.assertEqual(r["sources"][0]["state"],state)
            self.assertEqual(r["readable_pages"],0)
        r=self.coordinator(reader=Reader({hit().url:dict(body=b"Article about CAPTCHA detection.")})).run("reference")
        self.assertEqual(r["status"],"READ_TARGET_MET")

    def test_unicode_challenge_title_variants_are_not_readable_evidence(self):
        from eidolon_core.html_extract import ExtractLimits
        titles = ["Just a moment…", "Just a moment&#8230;", "Ｊｕｓｔ ａ ｍｏｍｅｎｔ...",
                  "Just a mo\u200bment...", "Verify\u00a0you are human"]
        for title in titles:
            for media in ("text/html", "text/plain"):
                with self.subTest(title=title, media=media):
                    body = f"<title>{title}</title><p>Wait for access</p>".encode()
                    report = self.coordinator(reader=Reader({hit().url:dict(
                        media_type=media,body=body,html_limits=ExtractLimits())})).run("reference")
                    self.assertEqual(report["sources"][0]["state"], "CHALLENGE_SUSPECTED")
                    self.assertEqual(report["readable_pages"], 0)
        for title in ("Research about CAPTCHA", "Why sites say Just a moment…"):
            body = f"<title>{title}</title><p>Technical article</p>".encode()
            report = self.coordinator(reader=Reader({hit().url:dict(
                media_type="text/html",body=body,html_limits=ExtractLimits())})).run("reference")
            self.assertEqual(report["sources"][0]["state"], "READ")

    def test_bom_text_deduplicates_without_changing_source_fingerprint(self):
        from eidolon_core.html_extract import ExtractLimits
        plain = "Ne pas confirmer sans preuve."
        replies = {hit().url:dict(body=("\ufeff" + plain).encode()),
                   hit("b").url:dict(body=plain.encode()),
                   hit("c").url:dict(body=("<p>" + plain + "</p>").encode(),
                                       media_type="text/html",html_limits=ExtractLimits())}
        c = self.coordinator([Provider("p",[hit(),hit("b"),hit("c")])], Reader(replies))
        for _ in range(2):  # Repeat from the bounded RAM cache too.
            report = c.run("reference",required_pages=3)
            self.assertEqual(report["readable_pages"], 1)
            self.assertEqual([s["state"] for s in report["sources"]], ["READ","DUPLICATE_CONTENT","DUPLICATE_CONTENT"])
            self.assertEqual(len({s["text_sha256"] for s in report["sources"]}), 1)
            self.assertEqual(len({s["body_sha256"] for s in report["sources"]}), 3)
            for source in report["sources"]:
                self.assertEqual(source["text"], plain)
        self.assertEqual(len(c.reader.calls), 3)
        for body in (b"\xef\xbb\xbf", b"\xef\xbb\xbf \n"):
            report = self.coordinator(reader=Reader({hit().url:dict(body=body)})).run("reference")
            self.assertEqual(report["sources"][0]["state"], "EMPTY_CONTENT")

    def test_mislabeled_html_challenge_is_not_plain_text_evidence(self):
        for body,state in [(b"<html><title>Just a moment...</title></html>","CHALLENGE_SUSPECTED"),
                           (b"<!doctype html><html><p>Unknown HTML</p></html>","UNSUPPORTED_CONTENT")]:
            r=self.coordinator(reader=Reader({hit().url:dict(media_type="text/plain",body=body)})).run("reference")
            self.assertEqual(r["sources"][0]["state"],state)
            self.assertEqual(r["readable_pages"],0)

    def test_snippets_alone_do_not_meet_read_target(self):
        r=self.coordinator([Provider("p1",[hit(snippet="Detailed but unverified source excerpt")])],
                           Reader({hit().url:AccessFailure("UNAVAILABLE")})).run("reference")
        self.assertEqual(r["readable_pages"],0)
        self.assertIsNone(r["sources"][0]["text"])

    def test_partial_sources_preserved(self):
        r=self.coordinator([Provider("p1",[hit(),hit("b")])],Reader({hit("b").url:AccessFailure("ACCESS_DENIED")})).run("reference",required_pages=2)
        self.assertEqual((r["status"],r["readable_pages"]),("PARTIAL",1))
        self.assertEqual(r["sources"][0]["state"],"READ")

    def test_same_url_from_two_providers_is_one_source(self):
        a,b=Provider("p1",[hit()]),Provider("p2",[hit()])
        reader=Reader()
        r=self.coordinator([a,b],reader).run("reference",required_pages=2)
        self.assertEqual((len(r["sources"]),r["readable_pages"],len(reader.calls)),(1,1,1))
        self.assertEqual(len(r["sources"][0]["found_by"]),2)

    def test_redirects_to_same_final_are_not_independent_pages(self):
        reader=Reader({hit("b").url:dict(url=hit().url)})
        r=self.coordinator([Provider("p1",[hit(),hit("b")])],reader).run("reference",required_pages=2)
        self.assertEqual(r["readable_pages"],1)
        self.assertEqual(r["sources"][1]["state"],"DUPLICATE_FINAL")

    def test_denied_destination_never_reaches_reader(self):
        reader=Reader()
        r=self.coordinator([Provider("p1",[Hit("https://127.0.0.1/","local")])],reader).run("reference")
        self.assertEqual(r["sources"][0]["state"],"POLICY_REFUSED")
        self.assertEqual(reader.calls,[])

    def test_final_policy_and_reader_fingerprint_checked(self):
        for reply,state in [(dict(url="https://127.0.0.1/"),"POLICY_REFUSED"),
                            (dict(policy_id="wrong"),"READER_ERROR")]:
            r=self.coordinator(reader=Reader({hit().url:reply})).run("reference")
            self.assertEqual(r["sources"][0]["state"],state)
            self.assertEqual(r["readable_pages"],0)

    def test_read_and_provider_budgets(self):
        r=self.coordinator([Provider("p1",[hit(),hit("b")])],Reader({hit().url:dict(status=500)}),
                           limits=ResearchLimits(reads=1)).run("reference")
        self.assertEqual((r["read_calls"],r["limitation"]),(1,"READ_BUDGET"))
        last=Provider("p2",[hit()])
        r=self.coordinator([Provider("p1",[]),last],limits=ResearchLimits(providers=1)).run("reference")
        self.assertEqual((r["limitation"],last.calls),("PROVIDER_BUDGET",0))

    def test_huge_provider_iterator_is_bounded(self):
        r=self.coordinator([Provider("p1",itertools.repeat(hit()))]).run("reference")
        self.assertEqual(r["providers"][0]["status"],"PROVIDER_ERROR")
        self.assertEqual(r["read_calls"],0)

    def test_malformed_provider_batch_rejected_before_reader(self):
        for hits in [[hit(),{}],[hit(),replace(hit(),title="\ud800")]]:
            r=self.coordinator([Provider("p1",hits)]).run("reference")
            self.assertEqual(r["read_calls"],0)
            self.assertEqual(r["providers"][0]["status"],"PROVIDER_ERROR")

    def test_empty_and_failed_provider_are_distinct(self):
        r=self.coordinator([Provider("p1",[]),Provider("p2",OSError("synthetic-secret"))]).run("reference")
        self.assertEqual([p["status"] for p in r["providers"]],["EMPTY","PROVIDER_ERROR"])
        self.assertNotIn("synthetic-secret",encode(r))

    def test_cache_reuse_expiry_and_output_isolation(self):
        clock=Clock();reader=Reader();c=self.coordinator(reader=reader,clock=clock,limits=ResearchLimits(cache_seconds=5))
        a=c.run("reference"); observed=a["sources"][0]["observed_at"]
        a["sources"][0]["text"]="changed by consumer"
        b=c.run("reference")
        self.assertTrue(b["sources"][0]["cache_hit"])
        self.assertEqual(b["sources"][0]["observed_at"],observed)
        self.assertNotEqual(b["sources"][0]["text"],"changed by consumer")
        clock.value=5;c.run("reference")
        self.assertEqual(len(reader.calls),2)

    def test_changed_policy_or_dns_cannot_disclose_cached_page(self):
        c=self.coordinator();c.run("reference")
        c.policy=WebPolicy(blocked_networks=("9.9.9.9",))
        r=c.run("reference")
        self.assertEqual(r["sources"][0]["state"],"POLICY_REFUSED")
        self.assertIsNone(r["sources"][0]["text"])
        c.policy=WebPolicy();c.resolver=lambda *a:["127.0.0.1"]
        self.assertEqual(c.run("reference")["sources"][0]["state"],"POLICY_REFUSED")

    def test_cached_redirect_final_destination_rechecked(self):
        c=self.coordinator(reader=Reader({hit().url:dict(url="https://final.example/")}))
        c.run("reference")
        c.resolver=lambda host,port:["127.0.0.1" if host=="final.example" else "9.9.9.9"]
        r=c.run("reference")
        self.assertEqual(r["sources"][0]["state"],"POLICY_REFUSED")
        self.assertIsNone(r["sources"][0]["text"])

    def test_cache_capacity_evicts_oldest(self):
        p=Provider("p1",[hit()]);reader=Reader();c=self.coordinator([p],reader,limits=ResearchLimits(cache_entries=1))
        c.run("reference");p.hits=[hit("b")];c.run("reference");p.hits=[hit()];c.run("reference")
        self.assertEqual(len(reader.calls),3)

    def test_cooldown_skips_domain_until_elapsed_without_sleep(self):
        clock=Clock();reader=Reader({hit().url:dict(status=429,retry_after=5)})
        c=self.coordinator([Provider("p1",[hit(),hit("b")])],reader,clock=clock)
        r=c.run("reference");self.assertEqual(len(reader.calls),1)
        self.assertEqual([s["state"] for s in r["sources"]],["RATE_LIMITED","RATE_LIMITED"])
        c.run("reference");self.assertEqual(len(reader.calls),1)
        clock.value=5;reader.replies={};r=c.run("reference")
        self.assertEqual(r["status"],"READ_TARGET_MET")

    def test_cancel_before_search_and_after_receipt(self):
        p=Provider("p1",[hit()]);c=self.coordinator([p])
        self.assertEqual(c.run("reference",cancelled=lambda:True)["status"],"CANCELLED")
        self.assertEqual(p.calls,0)
        cancelled=[False]
        class CancellingReader(Reader):
            def read(self,url,policy):
                page=super().read(url,policy);cancelled[0]=True;return page
        r=self.coordinator(reader=CancellingReader()).run("reference",cancelled=lambda:cancelled[0])
        self.assertEqual(r["status"],"CANCELLED")
        self.assertEqual(r["sources"][0]["state"],"READ")

    def test_deadline_after_read_keeps_receipt_without_claiming_target_success(self):
        clock=Clock()
        class SlowReader(Reader):
            def read(self,url,policy):
                page=super().read(url,policy);clock.value=31;return page
        r=self.coordinator(reader=SlowReader(),clock=clock).run("reference")
        self.assertEqual(r["status"],"DEADLINE")
        self.assertEqual(r["sources"][0]["state"],"READ")
        self.assertEqual(r["readable_pages"],1)

    def test_limits_inputs_and_body_bounds(self):
        for kw in [dict(reads=True),dict(seconds=float("nan")),dict(cache_seconds=-1),dict(body_bytes=129000)]:
            with self.assertRaises(ContractError):ResearchLimits(**kw)
        for query in ["",None,"\ud800"]:
            with self.assertRaises(ContractError):self.coordinator().run(query)
        with self.assertRaises(ContractError):self.coordinator().run("query",required_pages=True)
        r=self.coordinator(reader=Reader({hit().url:dict(body=b"a"*20)}),limits=ResearchLimits(body_bytes=10)).run("reference")
        self.assertEqual(r["sources"][0]["state"],"TOO_LARGE")

    def test_no_network_when_providers_are_synthetic(self):
        with patch.object(socket,"socket",side_effect=AssertionError("no socket")),patch.object(socket,"getaddrinfo",side_effect=AssertionError("no DNS")):
            self.assertEqual(self.coordinator().run("reference")["status"],"READ_TARGET_MET")


if __name__ == "__main__":unittest.main()
