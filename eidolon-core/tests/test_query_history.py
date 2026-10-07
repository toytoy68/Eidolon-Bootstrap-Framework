# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_query_history.py
# Description : Atomicité, confidentialité, pagination et coupures de l'historique local
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from eidolon_core.contracts import digest
from eidolon_core.query_cleanup import clean_query
from eidolon_core.query_history import QueryHistoryError, read_history
from eidolon_core.research import ResearchCoordinator
from eidolon_core.research_guard import GuardError, ResearchGuard
from tests.test_research import Provider, Reader, dns

CHILD = '''import os, sys
from pathlib import Path
from eidolon_core.research import ResearchCoordinator
from eidolon_core.research_guard import ResearchGuard
from tests.test_research import Provider, Reader, dns
root=Path(sys.argv[1]); stage=sys.argv[2]
g=ResearchGuard(root/'guard',retain_queries=True)
if stage=='during_write':
 real=g._write
 def write(db,record,**kw):
  real(db,record,**kw)
  if kw.get('insert'):os._exit(43)
 g._write=write
class P(Provider):
 def search(self,q,limit):
  if stage=='before_contact':os._exit(43)
  (root/'contacts').write_text(q)
  if stage=='during_contact':os._exit(43)
  return []
ResearchCoordinator([P('p',[])],Reader(),resolver=dns,guard=g).run('diagnostic jean@example.invalid')
'''


class QueryHistoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.guard = ResearchGuard(self.root / 'guard', retain_queries=True)
        self.provider = Provider('p', [])
        self.coordinator = ResearchCoordinator([self.provider], Reader(), resolver=dns, guard=self.guard)

    def run_query(self, text='diagnostic jean@example.invalid'):
        return self.coordinator.run(text)

    def entries(self):
        return read_history(self.guard)['entries']

    def test_exact_cleaned_text_is_atomic_with_intent_before_provider(self):
        observed = []
        class Inspecting(Provider):
            def search(inner, q, limit):
                rows = self.entries()
                observed.append((q, rows[0]['text'], rows[0]['state'], rows[0]['emission']))
                return []
        c = ResearchCoordinator([Inspecting('p',[])], Reader(), resolver=dns, guard=self.guard)
        report = c.run('diagnostic jean@example.invalid')
        self.assertEqual(observed, [('diagnostic','diagnostic','INTENT','UNKNOWN')])
        row, = self.entries()
        self.assertEqual(row['run_id'], report['research_guard']['run_id'])
        self.assertEqual(row['cleanup'], report['query_cleanup'])
        self.assertEqual((row['state'],row['emission']), ('COMPLETED','CALL_SEQUENCE_COMPLETED'))
        self.assertFalse(row['delivery_confirmed'])

    def test_no_removed_text_or_raw_hash_in_any_database_file_or_report(self):
        raw = 'notice jean@example.invalid 198.51.100.7:25565 /srv/secrets/SYNTH_PRIVATE'
        report = self.run_query(raw)
        for path in self.guard.directory.iterdir():
            data = path.read_bytes()
            for private in ('jean@example.invalid','198.51.100.7','25565','SYNTH_PRIVATE',
                            digest(raw),hashlib.sha256(raw.encode()).hexdigest()):
                self.assertNotIn(private.encode(),data)
        self.assertNotIn('"text"',json.dumps(report))
        self.assertNotIn('"text"',json.dumps(self.guard.inspect()))
        self.assertEqual(self.entries()[0]['text'],'notice')

    def test_empty_query_is_recorded_without_any_provider_or_dns(self):
        self.run_query('jean@example.invalid')
        row, = self.entries()
        self.assertEqual((row['text'],row['outcome'],row['emission']), ('','QUERY_EMPTY_AFTER_CLEANUP','NOT_REQUESTED'))
        self.assertEqual(self.provider.calls,0)

    def test_reopen_keeps_history_mandatory_without_flag(self):
        self.run_query()
        reopened = ResearchGuard(self.guard.directory)
        self.assertTrue(reopened.retain_queries)
        ResearchCoordinator([self.provider], Reader(), resolver=dns, guard=reopened).run('deuxième')
        self.assertEqual(len(read_history(reopened)['entries']),2)
        with self.assertRaisesRegex(QueryHistoryError,'CLEANED_QUERY_REQUIRED'):
            reopened.execute(lambda:self.fail('unguarded query'), descriptor={'query_sha256':'a'*64,'policy_id':'p/1','providers':['p']})

    def test_legacy_upgrade_is_explicit_and_old_text_is_not_invented(self):
        old = ResearchGuard(self.root/'old')
        ResearchCoordinator([Provider('p',[])],Reader(),resolver=dns,guard=old).run('historique absent')
        before = old.path.read_bytes()
        with self.assertRaisesRegex(QueryHistoryError,'QUERY_HISTORY_NOT_ENABLED'):
            read_history(old)
        with self.assertRaisesRegex(GuardError,'QUERY_HISTORY_NOT_ENABLED'):
            ResearchGuard(old.directory,create=False,retain_queries=True)
        self.assertEqual(before,old.path.read_bytes())
        upgraded = ResearchGuard(old.directory,retain_queries=True)
        data = read_history(upgraded)
        self.assertEqual((data['entries'],data['legacy_runs_without_text']),([],1))
        with self.assertRaisesRegex(GuardError,'UNSUPPORTED_RESEARCH_GUARD'):
            old.inspect()

    def test_insert_failure_rolls_back_intent_and_contacts_nobody(self):
        with self.guard._connection() as db:
            db.execute("CREATE TRIGGER fail BEFORE INSERT ON cleaned_queries BEGIN SELECT RAISE(ABORT,'SYNTH_SECRET'); END")
        with self.assertRaisesRegex(GuardError,'RESEARCH_GUARD_UNAVAILABLE') as caught:
            self.run_query()
        self.assertNotIn('SYNTH_SECRET',str(caught.exception))
        self.assertEqual(self.provider.calls,0)
        self.assertEqual(self.guard.inspect()['runs'],[])
        self.assertEqual(self.entries(),[])

    def test_finish_failure_keeps_text_intent_and_blocks_retry(self):
        with self.guard._connection() as db:
            db.execute("CREATE TRIGGER fail BEFORE UPDATE ON runs BEGIN SELECT RAISE(ABORT,'synthetic'); END")
        with self.assertRaises(GuardError): self.run_query()
        self.assertEqual(self.entries()[0]['state'],'INTENT')
        with self.assertRaisesRegex(GuardError,'WEB_RESEARCH_UNCERTAIN'): self.run_query('autre')
        self.assertEqual(self.provider.calls,1)

    def test_real_crashes_before_commit_and_around_provider(self):
        for stage, expected, contacts in [('during_write',0,False),('before_contact',1,False),('during_contact',1,True)]:
            with self.subTest(stage=stage), tempfile.TemporaryDirectory() as tmp:
                result = subprocess.run([sys.executable,'-c',CHILD,tmp,stage],capture_output=True,text=True,timeout=10)
                self.assertEqual(result.returncode,43,result.stderr)
                root=Path(tmp); guard=ResearchGuard(root/'guard',create=False)
                rows=read_history(guard)['entries']
                self.assertEqual(len(rows),expected)
                self.assertEqual((root/'contacts').exists(),contacts)
                if expected:
                    self.assertEqual((rows[0]['text'],rows[0]['state'],rows[0]['emission']),('diagnostic','INTENT','UNKNOWN'))
                    with self.assertRaisesRegex(GuardError,'WEB_RESEARCH_UNCERTAIN'):
                        ResearchCoordinator([Provider('p',[])],Reader(),resolver=dns,guard=guard).run('autre')
                    guard.resolve(rows[0]['run_id'],expected_revision=1,actor='fixture',reason='accept uncertainty')
                    self.assertEqual(read_history(guard)['entries'][0]['emission'],'UNKNOWN')

    def test_capacity_never_evicts_and_refuses_before_new_contact(self):
        with patch('eidolon_core.research_guard.MAX_RUNS',2):
            self.run_query('première'); self.run_query('deuxième')
            before=self.guard.path.read_bytes()
            with self.assertRaisesRegex(GuardError,'RESEARCH_HISTORY_CAPACITY_REACHED'):self.run_query('troisième')
            self.assertEqual(self.provider.calls,2)
            self.assertEqual(self.guard.path.read_bytes(),before)
            self.assertEqual(len(self.entries()),2)

    def test_sqlite_busy_refuses_without_contact(self):
        other=sqlite3.connect(self.guard.path); self.addCleanup(other.close)
        other.execute('BEGIN IMMEDIATE')
        with self.assertRaisesRegex(GuardError,'RESEARCH_GUARD_UNAVAILABLE'):self.run_query()
        self.assertEqual(self.provider.calls,0)
        other.rollback()
        self.assertEqual(self.entries(),[])

    def test_process_exclusion_is_kept_with_history_enabled(self):
        code='''import sys
from eidolon_core.research import ResearchCoordinator
from eidolon_core.research_guard import ResearchGuard
from tests.test_research import Provider,Reader,dns
try:
 g=ResearchGuard(sys.argv[1],retain_queries=True)
 ResearchCoordinator([Provider('p',[])],Reader(),resolver=dns,guard=g).run('concurrent')
except Exception as e: print(str(e))
'''
        with self.guard._exclusive():
            p=subprocess.run([sys.executable,'-c',code,str(self.guard.directory)],capture_output=True,text=True,timeout=5)
        self.assertEqual(p.stdout.strip(),'WEB_RESEARCH_IN_FLIGHT')
        self.assertEqual(self.entries(),[])

    def test_tampering_missing_text_or_orphan_refuses_new_contact(self):
        for operation in ('delete','text','receipt','orphan'):
            with self.subTest(operation=operation),tempfile.TemporaryDirectory() as tmp:
                g=ResearchGuard(Path(tmp)/'g',retain_queries=True)
                p=Provider('p',[]); c=ResearchCoordinator([p],Reader(),resolver=dns,guard=g);c.run('diagnostic')
                with g._connection() as db:
                    if operation=='delete': db.execute('DELETE FROM cleaned_queries')
                    elif operation=='orphan':db.execute("INSERT INTO cleaned_queries VALUES ('r-orphan','{}')")
                    else:
                        row=json.loads(db.execute('SELECT body FROM cleaned_queries').fetchone()[0])
                        if operation=='text':row['text']='changed'
                        else:row['cleanup']['normalized']=not row['cleanup']['normalized']
                        db.execute('UPDATE cleaned_queries SET body=?',(json.dumps(row),))
                with self.assertRaises(QueryHistoryError):c.run('autre')
                self.assertEqual(p.calls,1)

    def test_pagination_and_reset_after_append_or_review(self):
        for i in range(3):self.run_query(f'notice {i}')
        first=read_history(self.guard,limit=1); cursor=first['next_cursor']
        second=read_history(self.guard,limit=2,cursor=cursor)
        self.assertIsNone(second['next_cursor'])
        self.assertEqual(len({r['run_id'] for r in first['entries']+second['entries']}),3)
        self.run_query('append')
        with self.assertRaisesRegex(QueryHistoryError,'QUERY_HISTORY_RESET_REQUIRED'):
            read_history(self.guard,cursor=cursor)
        other=ResearchGuard(self.root/'different',retain_queries=True)
        with self.assertRaisesRegex(QueryHistoryError,'QUERY_HISTORY_RESET_REQUIRED'):read_history(other,cursor=cursor)

    def test_bad_pagination_or_payload_inputs_are_constant_errors(self):
        for limit in (True,0,51,1.5,'1'):
            with self.assertRaises(QueryHistoryError):read_history(self.guard,limit=limit)
        for cursor in (1,'secret','x'*151):
            with self.assertRaises(QueryHistoryError) as caught:read_history(self.guard,cursor=cursor)
            self.assertNotIn('secret',str(caught.exception))
        clean=clean_query('notice')
        for bad in (None,replace(clean,text='changed'),replace(clean,text='secret\x00')):
            with self.assertRaises(QueryHistoryError):
                self.guard.execute(lambda:self.fail('invalid'),descriptor={'query_sha256':clean.cleaned_sha256,'policy_id':'p/1','providers':['p']},cleaned_query=bad)
        self.assertEqual(self.entries(),[])

    def test_cli_reads_only_and_does_not_create_or_upgrade(self):
        self.run_query()
        before=self.guard.path.read_bytes()
        args=[sys.executable,'-m','eidolon_core.query_history','--directory',str(self.guard.directory)]
        p=subprocess.run(args,capture_output=True,text=True,timeout=5)
        self.assertEqual(p.returncode,0,p.stderr)
        self.assertEqual(json.loads(p.stdout)['entries'][0]['text'],'diagnostic')
        self.assertEqual(self.guard.path.read_bytes(),before)
        p=subprocess.run(args+['--format','human'],capture_output=True,text=True,timeout=5)
        self.assertIn('Eidolon Core Technologies',p.stdout)
        missing=self.root/'SYNTH_PRIVATE_PATH'
        p=subprocess.run(args[:-1]+[str(missing)],capture_output=True,text=True,timeout=5)
        self.assertEqual(p.returncode,2)
        self.assertNotIn('SYNTH_PRIVATE_PATH',p.stderr)
        self.assertFalse(missing.exists())

    def test_private_files_and_downgraded_schema_are_refused(self):
        for p in (self.guard.path,self.guard.lock_path):self.assertEqual(p.stat().st_mode & 0o777,0o600)
        with self.guard._connection() as db:db.execute('PRAGMA user_version=1')
        with self.assertRaises(GuardError):self.run_query()
        self.assertEqual(self.provider.calls,0)


if __name__=='__main__':unittest.main()
