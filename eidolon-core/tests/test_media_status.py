# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_media_status.py
# Description : Inspection humaine, reçu après coupure, contenu non fiable et absence d'effets
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
import copy
from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from eidolon_core.media_agents import MediaError, execute, inspect
from eidolon_core.media_cli import main
from eidolon_core.media_status import PHASES, render_job


class JobStatusTests(unittest.TestCase):
    def record(self, state='QUEUED'):
        return {'schema':'media-job/1','id':'media-'+'a'*32,'agent':'image','operation':'create',
                'state':state,'backend':{'adapter':'comfyui-prompt/2','endpoint':'http://127.0.0.1:8188'},
                'phase':'QUEUE_ACKNOWLEDGED','phase_evidence':{'prompt_id':'fixture-id'},
                'result':{'state':'QUEUED','prompt_id':'fixture-id'},'automatic_retry':False}

    def test_receipt_after_interruption_can_be_consulted_but_never_means_success(self):
        for state in ('QUEUED','INTENT','REVIEW_REQUIRED'):
            record=self.record(state); before=copy.deepcopy(record)
            rendered=render_job(record)
            self.assertIn('eidolon-media poll',rendered)
            self.assertIn('fixture-id',rendered)
            self.assertIn('Ne pas renvoyer automatiquement',rendered)
            self.assertNotIn('[OK]',rendered)
            self.assertNotIn('SUCCEEDED',rendered)
            self.assertEqual(record,before)
            if state!='QUEUED': self.assertIn('revue nécessaire',rendered)

    def test_before_acknowledgement_a_queue_call_may_have_happened(self):
        record=self.record('INTENT');record['phase']='QUEUE_SUBMITTING';record['phase_evidence']={}
        rendered=render_job(record)
        self.assertNotIn('eidolon-media poll',rendered)
        self.assertIn('Aucun reçu de file exploitable',rendered)
        self.assertIn("ne prouve ni absence d'effet",rendered)

    def test_source_phases_keep_remote_presence_uncertain(self):
        for phase in PHASES:
            record=self.record('REVIEW_REQUIRED');record['phase']=phase;record['phase_evidence']={}
            rendered=render_job(record)
            self.assertIn(PHASES[phase],rendered)
            if phase.startswith('SOURCE_'):
                self.assertIn('Une source peut déjà être présente',rendered)
            self.assertNotIn('eidolon-media poll',rendered)

    def test_analysis_is_unverified_and_its_model_text_is_not_terminal_output(self):
        record=self.record('RESULT_UNVERIFIED');record.update(agent='video',operation='analyze',phase='ANALYSIS_SUBMITTING')
        record['result']={'state':'RESULT_UNVERIFIED','text':'\x1b[2J<private model text>','frames_analyzed':8}
        rendered=render_job(record)
        self.assertIn("réponse d'analyse enregistrée ; contenu non vérifié",rendered)
        self.assertNotIn('eidolon-media poll',rendered)
        self.assertNotIn('private model text',rendered)
        self.assertNotIn('\x1b',rendered)
        self.assertIn('aucune collecte ComfyUI',rendered)

    def test_bad_receipt_backend_or_endpoint_never_suggests_poll(self):
        for key,value in (('result',{}),('result',{'prompt_id':'../bad'}),('backend',None),
                          ('backend',{'adapter':'comfyui-prompt/2','endpoint':'http://example.invalid:8188'})):
            record=self.record();record[key]=value
            rendered=render_job(record)
            self.assertNotIn('eidolon-media poll',rendered)
            self.assertIn('Aucun reçu de file exploitable',rendered)

    def test_unknown_untrusted_fields_have_fixed_labels_and_no_terminal_injection(self):
        record=self.record();marker='PRIVATE\x1b[2J';record.update(id=marker,state=[marker],phase={'x':marker},
            operation=marker,request={'prompt':marker},failure_code=marker,observed_state='SUCCEEDED')
        rendered=render_job(record)
        self.assertNotIn('PRIVATE',rendered);self.assertNotIn('\x1b',rendered)
        self.assertNotIn('SUCCEEDED',rendered);self.assertIn('état non reconnu',rendered)
        for value in (None,[],{}, {'schema':'other'}):
            with self.assertRaisesRegex(MediaError,'INVALID_JOB'): render_job(value)

    def test_cli_reads_real_durable_ack_without_source_network_process_or_mutation(self):
        class Cut(BaseException): pass
        class Backend:
            def plan(self,request,evidence):return {'adapter':'comfyui-prompt/2','endpoint':'http://127.0.0.1:8188'}
            def run(self,request,source,evidence,plan,*,progress):
                progress('QUEUE_SUBMITTING',{})
                progress('QUEUE_ACKNOWLEDGED',{'prompt_id':'recorded-before-cut'})
                raise Cut()
        with tempfile.TemporaryDirectory() as folder:
            job=Path(folder)/'job'
            with self.assertRaises(Cut):
                execute({'agent':'image','operation':'create','prompt':'private','format':'square'}, {},job,backend=Backend())
            before=(job/'job.json').read_bytes();mtime=(job/'job.json').stat().st_mtime_ns
            out,err=io.StringIO(),io.StringIO()
            with patch('socket.socket',side_effect=AssertionError('socket')), patch('subprocess.run',side_effect=AssertionError('process')), patch('eidolon_core.media_agents.read_source',side_effect=AssertionError('source')),redirect_stdout(out),redirect_stderr(err):
                code=main(['inspect','--job',str(job),'--format','human'])
            self.assertEqual((code,err.getvalue()),(0,''))
            self.assertIn('Eidolon Core Technologies',out.getvalue());self.assertIn('recorded-before-cut',out.getvalue())
            self.assertIn('revue nécessaire',out.getvalue());self.assertNotIn('private',out.getvalue())
            self.assertEqual((job/'job.json').read_bytes(),before)
            self.assertEqual((job/'job.json').stat().st_mtime_ns,mtime)
            self.assertEqual(sorted(p.name for p in job.iterdir()),['job.json'])
            out=io.StringIO()
            with redirect_stdout(out): self.assertEqual(main(['inspect','--job',str(job)]),0)
            self.assertEqual(json.loads(out.getvalue()),inspect(job))

    def test_missing_job_human_error_on_stderr_and_no_directory_created(self):
        with tempfile.TemporaryDirectory() as folder:
            job=Path(folder)/'missing';out,err=io.StringIO(),io.StringIO()
            with redirect_stdout(out),redirect_stderr(err):code=main(['inspect','--job',str(job),'--format','human'])
            self.assertEqual((code,out.getvalue()),(2,''));self.assertIn('[ERREUR]',err.getvalue())
            self.assertFalse(job.exists())
