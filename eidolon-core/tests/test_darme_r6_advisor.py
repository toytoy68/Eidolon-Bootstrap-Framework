# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_darme_r6_advisor.py
# Description : Relecture bornee, dates, fraicheur et conseiller sans autorite
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
import json,os,sqlite3,tempfile,threading,unittest
from pathlib import Path
from eidolon_core.darme import DarmeMonitor,SecurityEvent,Severity
from eidolon_core.darme_store import DarmeJournal,JournalCapacityError
from eidolon_core.darme_advisor import request,validate,fixed,advise
from eidolon_core.ollama_model import OllamaModel,OllamaConfig

class ReplayTests(unittest.TestCase):
    def event(self,i,level=Severity.INFO):
        return SecurityEvent(str(i),'nas','test',level,'2026-10-12T03:00:00Z')
    def test_many_alerts_keep_total_and_red(self):
        with tempfile.TemporaryDirectory() as d:
            j=DarmeJournal(Path(d)/'j.db')
            for i in range(12):j.record(self.event(i,Severity.CRITICAL))
            m=j.replay(DarmeMonitor(['nas'],max_events=3))
            self.assertEqual(len(m.events),3)
            self.assertEqual(m.snapshot()['unacknowledged_alerts'],12)
            self.assertEqual(m.snapshot()['unrepresented_alerts'],9)
            self.assertEqual(m.snapshot()['badge'],'red')
            self.assertEqual(m.snapshot()['visibility'],'partial');j.close()
    def test_warning_survives_later_acknowledged_critical(self):
        with tempfile.TemporaryDirectory() as d:
            j=DarmeJournal(Path(d)/'j.db')
            j.record(self.event('warn',Severity.WARNING))
            j.record(self.event('crit',Severity.CRITICAL));j.acknowledge('crit','op','seen')
            m=j.replay(DarmeMonitor(['nas'],max_events=1))
            self.assertEqual(list(m.events),['warn'])
            self.assertEqual(m.snapshot()['unacknowledged_alerts'],1);j.close()
    def test_critical_priority_over_warning_and_routine(self):
        with tempfile.TemporaryDirectory() as d:
            j=DarmeJournal(Path(d)/'j.db')
            for i in range(5):j.record(self.event(i,Severity.WARNING))
            j.record(self.event('crit',Severity.CRITICAL))
            m=j.replay(DarmeMonitor(['nas'],max_events=1))
            self.assertEqual(list(m.events),['crit'])
            self.assertEqual(m.snapshot()['unrepresented_alerts'],5);j.close()
    def test_routine_uses_latest_without_claiming_full_projection(self):
        with tempfile.TemporaryDirectory() as d:
            j=DarmeJournal(Path(d)/'j.db')
            for i in range(4):j.record(self.event(i))
            m=DarmeMonitor(['nas'],max_events=2);m.health('nas',True);j.replay(m)
            self.assertEqual(set(m.events),{'2','3'})
            self.assertEqual(m.snapshot()['badge'],'grey');j.close()
    def test_record_cap_preserves_duplicate_and_history(self):
        with tempfile.TemporaryDirectory() as d:
            j=DarmeJournal(Path(d)/'j.db',max_records=1);e=self.event('a');j.record(e)
            self.assertFalse(j.record(e))
            with self.assertRaises(JournalCapacityError):j.record(self.event('b',Severity.CRITICAL))
            self.assertEqual(j.db.execute('SELECT COUNT(*) FROM events').fetchone()[0],1);j.close()
    def test_byte_cap_rolls_back_failed_insert(self):
        with tempfile.TemporaryDirectory() as d:
            j=DarmeJournal(Path(d)/'j.db',max_bytes=32768)
            accepted=0
            for i in range(1000):
                try:j.record(SecurityEvent(str(i),'nas','x',Severity.INFO,'2026-10-12T03:00:00Z','x'*256));accepted+=1
                except JournalCapacityError:break
            self.assertLess(accepted,1000)
            self.assertEqual(j.db.execute('SELECT COUNT(*) FROM events').fetchone()[0],accepted)
            self.assertLessEqual((Path(d)/'j.db').stat().st_size,32768);j.close()
    def test_existing_over_record_limit_can_still_replay(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'j.db';j=DarmeJournal(p)
            for i in range(4):j.record(self.event(i,Severity.CRITICAL))
            j.close();j=DarmeJournal(p,max_records=1)
            self.assertEqual(j.replay(DarmeMonitor(['nas'],max_events=1)).snapshot()['unacknowledged_alerts'],4)
            with self.assertRaises(JournalCapacityError):j.record(self.event('new'))
            j.close()
    def test_timestamp_is_persistent_and_retry_does_not_rewrite(self):
        with tempfile.TemporaryDirectory() as d:
            j=DarmeJournal(Path(d)/'j.db');j.record(self.event('x'))
            at='2026-10-12T04:00:00Z'
            j.acknowledge('x','op','seen',acknowledged_at=at)
            self.assertFalse(j.acknowledge('x','op','seen'))
            with self.assertRaises(ValueError):j.acknowledge('x','op','seen',acknowledged_at='2026-10-12T05:00:00Z')
            self.assertEqual(j.db.execute('SELECT acknowledged_at FROM acknowledgements').fetchone()[0],at);j.close()
    def test_legacy_ack_date_remains_unknown(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'j.db';db=sqlite3.connect(p)
            db.execute('CREATE TABLE events (id TEXT PRIMARY KEY,payload TEXT NOT NULL)')
            db.execute('CREATE TABLE acknowledgements (id TEXT PRIMARY KEY,actor TEXT NOT NULL,reason TEXT NOT NULL)')
            db.execute("INSERT INTO acknowledgements VALUES ('x','op','seen')");db.commit();db.close();p.chmod(0o600)
            j=DarmeJournal(p)
            self.assertIsNone(j.db.execute('SELECT acknowledged_at FROM acknowledgements').fetchone()[0]);j.close()
    def test_concurrent_admission_does_not_exceed_cap(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'j.db';j=DarmeJournal(p,max_records=1);j.close()
            barrier=threading.Barrier(2);results=[]
            def writer(i):
                db=DarmeJournal(p,max_records=1);barrier.wait()
                try:results.append(db.record(self.event(i)))
                except JournalCapacityError:results.append(False)
                finally:db.close()
            threads=[threading.Thread(target=writer,args=(i,)) for i in range(2)]
            for t in threads:t.start()
            for t in threads:t.join(10)
            self.assertEqual(sorted(results),[False,True])
            j=DarmeJournal(p);self.assertEqual(j.db.execute('SELECT COUNT(*) FROM events').fetchone()[0],1);j.close()

class FreshnessTests(unittest.TestCase):
    def test_ttl_and_clock_regression_degrade_visibility(self):
        now=[100.0];m=DarmeMonitor(['nas'],health_ttl=10,clock=lambda:now[0]);m.health('nas',True)
        self.assertEqual(m.snapshot()['badge'],'gold')
        now[0]=111;self.assertEqual(m.snapshot()['badge'],'grey')
        m.health('nas',True);now[0]=110;self.assertEqual(m.snapshot()['badge'],'grey')
    def test_expiration_never_hides_critical(self):
        now=[0.0];m=DarmeMonitor(['nas'],health_ttl=1,clock=lambda:now[0]);m.health('nas',True)
        m.ingest(SecurityEvent('a','nas','test',Severity.CRITICAL,'2026-10-12T03:00:00Z'))
        now[0]=2;self.assertEqual(m.snapshot()['badge'],'red');self.assertFalse(m.snapshot()['sources']['nas'])
    def test_invalid_ttl_refused(self):
        for ttl in [True,0,-1,float('nan'),4000]:
            with self.assertRaises(ValueError):DarmeMonitor(['nas'],health_ttl=ttl)

class AdviceTests(unittest.TestCase):
    def setUp(self):
        self.source=dict(information_id='doc',revision=2,content='Observation de reference.',epistemic_status='UNVERIFIED')
    def test_number_resolved_without_exposing_identifier_to_model(self):
        messages,refs=request('warning','ssh','Une alerte.',[self.source])
        self.assertNotIn('doc@2',json.dumps(messages))
        result=validate(dict(explanation='Des echecs SSH necessitent une verification.',sources=[1]),'warning',refs)
        self.assertEqual(result.citations,('doc@2',));self.assertFalse(result.authorizes_execution)
    def test_extra_authority_fields_refused(self):
        for key in ['triage','action','command']:
            result=validate(dict(explanation='Test',sources=[],**{key:'critical'}),'info',())
            self.assertEqual(result.origin,'fixed')
    def test_invalid_source_numbers_refused(self):
        for numbers in [[0],[2],[True],['1'],None]:
            result=validate(dict(explanation='Test',sources=numbers),'info',('doc@1',))
            self.assertEqual(result.origin,'fixed')
    def test_contradictory_level_refused(self):
        result=validate(dict(explanation="L'alerte est de niveau info.",sources=[]),'critical',())
        self.assertEqual(result.reason,'contradictory_level')
    def test_positive_command_refused_but_negation_allowed(self):
        blocked=validate(dict(explanation='Redemarre le serveur.',sources=[]),'warning',())
        self.assertEqual(blocked.reason,'action_instruction')
        allowed=validate(dict(explanation='Ne redemarre pas le serveur.',sources=[]),'warning',())
        self.assertEqual(allowed.origin,'model')
    def test_denial_of_known_alert_is_rejected(self):
        for text in ["Aucune alerte connue.", "Le niveau n est plus critique."]:
            self.assertEqual(validate(dict(explanation=text,sources=[]),"critical",()).origin,"fixed")
    def test_modal_action_instruction_is_rejected(self):
        for text in ["Je vais bloquer le canal.", "Il faut redemarrer le serveur."]:
            self.assertEqual(validate(dict(explanation=text,sources=[]),"warning",()).reason,"action_instruction")
    def test_credentials_removed_from_inputs_and_outputs(self):
        messages,refs=request('info','token=SYNTHETIC_CATEGORY','Bearer SYNTHETIC_SECRET',[])
        wire=json.dumps(messages)
        self.assertNotIn('SYNTHETIC_CATEGORY',wire);self.assertNotIn('SYNTHETIC_SECRET',wire)
        result=validate(dict(explanation='token=SYNTHETIC_LEAK',sources=[]),'info',())
        self.assertEqual(result.reason,'sensitive_output')
    def test_fixed_fallback_has_no_authority(self):
        for level in ['info','warning','critical','unknown']:
            result=fixed(level);self.assertFalse(result.authorizes_execution);self.assertTrue(result.advisory_only)
    def test_adapter_failure_and_length_fall_back(self):
        class Transport:
            def __init__(self,length=False):self.length=length
            def post(self,url,body,**kwargs):
                self.body=json.loads(body);self.kwargs=kwargs
                raw=dict(done=True,done_reason='length' if self.length else 'stop',message=dict(content=json.dumps(dict(explanation='Une alerte reste a verifier.',sources=[1]))))
                return 200,'application/json',json.dumps(raw).encode()
        transport=Transport();adapter=OllamaModel(OllamaConfig('http://127.0.0.1:11434','synthetic',think=False),transport)
        result=advise(adapter,'warning','ssh','Test',[self.source])
        self.assertEqual(result.origin,'model')
        self.assertNotIn('triage',transport.body['format']['properties'])
        self.assertLessEqual(transport.kwargs['timeout'],15)
        transport.length=True;self.assertEqual(advise(adapter,'warning','ssh','Test',[self.source]).origin,'fixed')
        class Broken:
            def post(self,*a,**k):raise TimeoutError()
        adapter.transport=Broken()
        self.assertEqual(advise(adapter,'critical','ssh','Test',[]).origin,'fixed')
if __name__=='__main__':unittest.main()
