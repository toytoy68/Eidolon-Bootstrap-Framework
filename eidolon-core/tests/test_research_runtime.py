# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_research_runtime.py
# Description : Contrats, preuves, budget et reprise des missions de recherche synthétique
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from eidolon_core.client_sync import ClientSync
from eidolon_core.contracts import ContractError, encode
from eidolon_core.objectives import RESEARCH_TOOL
from eidolon_core.memory import SyntheticMemory
from eidolon_core.presentation import render_result
from eidolon_core.query_history import read_history
from eidolon_core.research_guard import ResearchGuard
from eidolon_core.research_runtime import ResearchRuntime, ResearchFixturePolicy, ResearchVerificationUnavailable
from eidolon_core.runtime import Limits
from eidolon_core.store import Store
from eidolon_core.tools import Policy
from tests.support import EmptyMemory, FixedModel


class InjectedMemory(SyntheticMemory):
    def recall(self, query):
        result=super().recall(query)
        result['_core_research']={'query':'evil injected query','required_pages':0,'operation_id':'m-'+'0'*32}
        return result


class Crash(BaseException):
    pass


def crash_after_result(kind):
    if kind == 'RESULT_SAVED':raise Crash()


def crash_after_return(kind):
    if kind == 'TOOL_RETURNED':raise Crash()


class ResearchRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.store=Store(self.tmp.name)
        self.runtime=ResearchRuntime(self.store)

    def execute(self,query='notice jean@example.invalid',pages=2,runtime=None):
        runtime=runtime or self.runtime
        return runtime.run(runtime.create_research(query,required_pages=pages)['id'])

    def guard(self):
        return ResearchGuard(self.store.directory/'research-fixture/guard',create=False)

    def test_end_to_end_success_is_retrieval_not_truth(self):
        result=self.execute()
        self.assertEqual((result['status'],result['outcome']['status']),('SUCCEEDED','ACHIEVED'))
        self.assertEqual(result['outcome']['scope'],'synthetic_retrieved_text')
        self.assertEqual(result['invocation_budget']['used'],4)
        self.assertEqual(result['result']['research']['readable_pages'],2)
        self.assertIn('non confirmé',result['result']['summary'])
        history=read_history(self.guard())['entries']
        self.assertEqual(history[0]['text'],'notice')
        run=self.guard().inspect()['runs'][0]
        self.assertEqual(run['descriptor']['operation_id'],result['id'])
        self.assertEqual(result['calls'][0]['status'],'VERIFIED')
        self.assertEqual(ClientSync(self.store).snapshot(result['id'])['snapshot']['mission']['outcome_status'],'ACHIEVED')
        self.assertEqual(self.runtime.run(result['id']),result)
        self.assertEqual(len(self.guard().inspect()['runs']),1)

    def test_memory_cannot_replace_runtime_objective_and_human_scope_is_exact(self):
        result=self.execute(runtime=ResearchRuntime(self.store,memory=InjectedMemory()))
        self.assertEqual(result['status'],'SUCCEEDED')
        self.assertEqual(result['calls'][0]['step']['parameters']['query'],'notice jean@example.invalid')
        human=render_result(result)
        self.assertIn('pages synthétiques récupérées',human)
        self.assertIn('contenu non confirmé',human)
        self.assertNotIn('pas tout le corpus',human)

    def test_empty_memory_does_not_block_an_explicit_retrieval_objective(self):
        result=self.execute(runtime=ResearchRuntime(self.store,memory=EmptyMemory()))
        self.assertEqual(result['status'],'SUCCEEDED')
        self.assertEqual(result['context']['items'],[])

    def test_partial_empty_and_blocked_have_verified_evidence_without_success(self):
        for scenario,status,pages in [('partial','PARTIAL',1),('empty','NOT_ACHIEVED',0),('blocked','NOT_ACHIEVED',0)]:
            with self.subTest(scenario=scenario),tempfile.TemporaryDirectory() as root:
                r=ResearchRuntime(Store(root),scenario=scenario)
                result=self.execute(runtime=r)
                self.assertEqual(result['status'],'BLOCKED')
                self.assertEqual(result['outcome']['status'],status)
                self.assertEqual(result['calls'][0]['status'],'VERIFIED')
                self.assertEqual(result['calls'][0]['output']['readable_pages'],pages)
                self.assertEqual(result['error']['code'],'RETRIEVAL_TARGET_NOT_MET')
                self.assertIsNone(result['result'])
                used=result['invocation_budget']['used']
                resumed=r.run(result['id'])
                self.assertEqual(resumed['invocation_budget']['used'],used)
                self.assertEqual(len(ResearchGuard(Path(root)/'research-fixture/guard').inspect()['runs']),1)

    def test_cleaned_empty_is_not_a_success_or_provider_call(self):
        result=self.execute('jean@example.invalid')
        output=result['calls'][0]['output']
        self.assertEqual(output['providers'],[])
        self.assertEqual(output['status'],'QUERY_EMPTY_AFTER_CLEANUP')
        self.assertEqual(result['status'],'BLOCKED')
        self.assertEqual(read_history(self.guard())['entries'][0]['emission'],'NOT_REQUESTED')

    def test_default_pure_policy_and_explicit_denial_prevent_retrieval(self):
        for policy in (Policy(),ResearchFixturePolicy(allowed_tools=())):
            result=self.execute(runtime=ResearchRuntime(self.store,policy=policy))
            self.assertEqual(result['status'],'BLOCKED')
            self.assertEqual(result['error']['code'],'PREFLIGHT_REFUSED')
            self.assertEqual(result['calls'],[])
        self.assertEqual(self.guard().inspect()['runs'],[])

    def test_model_cannot_change_query_count_or_operation_identity(self):
        for change in ({'query':'other'},{'required_pages':1},{'operation_id':'m-'+'0'*32}):
            params={'query':'query','required_pages':2,'operation_id':'m-'+'0'*32,**change}
            model=FixedModel(encode({'version':1,'steps':[{'id':'retrieve','tool':RESEARCH_TOOL,'parameters':params}]}))
            # Persist this configured model in a new mission, then build its exact malicious plan.
            r=ResearchRuntime(self.store,model=model)
            m=r.create_research('query',required_pages=2)
            params['operation_id']=change.get('operation_id',m['id'])
            r.model=FixedModel(encode({'version':1,'steps':[{'id':'retrieve','tool':RESEARCH_TOOL,'parameters':params}]}))
            result=r.run(m['id'])
            self.assertEqual(result['status'],'BLOCKED',result.get('error'))
            self.assertEqual(result['error']['code'],'PREFLIGHT_REFUSED')
        self.assertEqual(self.guard().inspect()['runs'],[])

    def test_invalid_query_or_page_count_creates_no_mission(self):
        for query,count in [('x',True),('x',0),('x',3),('',1),('x'*1001,1),('secret\x00',1)]:
            with self.assertRaises(ContractError):self.runtime.create_research(query,required_pages=count)
        self.assertEqual(self.guard().inspect()['runs'],[])

    def test_wrong_scenario_or_guard_identity_blocks_resume(self):
        mission=self.runtime.create_research('query')
        altered=ResearchRuntime(self.store,scenario='empty')
        result=altered.run(mission['id'])
        self.assertEqual(result['error']['code'],'CONFIGURATION_CHANGED')
        self.assertEqual(self.guard().inspect()['runs'],[])

    def test_budget_preserves_room_for_verification(self):
        r=ResearchRuntime(self.store,limits=Limits(max_invocations=3))
        result=self.execute(runtime=r)
        self.assertEqual(result['error']['code'],'INVOCATION_BUDGET_EXHAUSTED')
        self.assertEqual(self.guard().inspect()['runs'],[])
        self.assertEqual(result['invocation_budget']['used'],2)

    def test_crash_after_durable_result_only_retries_verification(self):
        r=ResearchRuntime(self.store,checkpoint=crash_after_result)
        mission=r.create_research('query',required_pages=2)
        with self.assertRaises(Crash):r.run(mission['id'])
        self.assertEqual(self.store.get(mission['id'])['calls'][0]['status'],'RETURNED')
        before=len(self.guard().inspect()['runs'])
        resumed=ResearchRuntime(self.store).run(mission['id'])
        self.assertEqual(resumed['status'],'SUCCEEDED')
        self.assertEqual(len(self.guard().inspect()['runs']),before)
        self.assertEqual(resumed['invocation_budget']['used'],4)

    def test_busy_guard_delays_verification_without_failure_or_research_replay(self):
        r=ResearchRuntime(self.store,checkpoint=crash_after_result)
        mission=r.create_research('query',required_pages=2)
        with self.assertRaises(Crash):r.run(mission['id'])
        guard=self.guard()
        with guard._exclusive():
            blocked=self.runtime.run(mission['id'])
        self.assertEqual(blocked['status'],'BLOCKED')
        self.assertEqual(blocked['error']['code'],'VERIFICATION_UNAVAILABLE')
        self.assertEqual(blocked['calls'][0]['status'],'RETURNED')
        resumed=self.runtime.run(mission['id'])
        self.assertEqual(resumed['status'],'SUCCEEDED')
        self.assertEqual(len(guard.inspect()['runs']),1)
        self.assertEqual(resumed['invocation_budget']['used'],5)

    def test_crash_before_mission_receipt_never_blindly_replays_research(self):
        r=ResearchRuntime(self.store,checkpoint=crash_after_return)
        mission=r.create_research('query',required_pages=2)
        with self.assertRaises(Crash):r.run(mission['id'])
        before=len(self.guard().inspect()['runs'])
        resumed=ResearchRuntime(self.store).run(mission['id'])
        self.assertIn(resumed['status'],{'REVIEW_REQUIRED','SUCCEEDED'})
        self.assertEqual(len(self.guard().inspect()['runs']),before)

    def test_cancel_before_run_creates_no_research(self):
        mission=self.runtime.create_research('query')
        result=self.runtime.cancel(mission['id'])
        self.assertEqual(result['status'],'CANCELLED')
        self.assertEqual(self.guard().inspect()['runs'],[])

    def test_verifier_refuses_tampered_report_and_other_mission_replay(self):
        result=self.execute();call=result['calls'][0];backend=self.runtime.backend
        params=call['step']['parameters'];output=call['output']
        before=self.guard().path.read_bytes()
        with patch.object(backend,'execute',side_effect=AssertionError('verification executed')):
            self.assertTrue(backend.verify(params,{},output))
            for change in ({'readable_pages':0},{'status':'READ_TARGET_MET_FORGED'},{'query_sha256':'0'*64}):
                self.assertFalse(backend.verify(params,{},dict(output,**change)))
            self.assertFalse(backend.verify(dict(params,operation_id='m-'+'0'*32),{},output))
        self.assertEqual(self.guard().path.read_bytes(),before)

    def test_missing_guard_does_not_get_recreated_by_verifier_or_executor(self):
        result=self.execute();call=result['calls'][0]
        path=self.guard().path;path.unlink()
        with self.assertRaises(ResearchVerificationUnavailable):
            self.runtime.backend.verify(call['step']['parameters'],{},call['output'])
        with self.assertRaises(ContractError):self.runtime.backend.execute(call['step']['parameters'],{})
        self.assertFalse(path.exists())

    def test_fixture_backend_never_uses_socket_or_external_dns(self):
        params={'query':'notice','required_pages':2,'operation_id':'m-'+'1'*32}
        with patch('socket.socket',side_effect=AssertionError('socket created')),patch('socket.getaddrinfo',side_effect=AssertionError('DNS called')):
            output=self.runtime.backend.execute(params,{})
            self.assertTrue(self.runtime.backend.verify(params,{},output))

    def test_cli_research_profile_and_resume(self):
        with tempfile.TemporaryDirectory() as root:
            args=[sys.executable,'-m','eidolon_core','--state',root,'--profile','research-sim']
            p=subprocess.run(args+['research','notice','--required-pages','2'],capture_output=True,text=True,timeout=10)
            self.assertEqual(p.returncode,0,p.stderr)
            result=json.loads(p.stdout)
            self.assertEqual(result['status'],'SUCCEEDED')
            p=subprocess.run(args+['run',result['id']],capture_output=True,text=True,timeout=10)
            self.assertEqual(p.returncode,0,p.stderr)
            self.assertEqual(json.loads(p.stdout)['revision'],result['revision'])
            p=subprocess.run(args[:-2]+['research','notice'],capture_output=True,text=True,timeout=10)
            self.assertEqual(p.returncode,2)


if __name__=='__main__':unittest.main()
