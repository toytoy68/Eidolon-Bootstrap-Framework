# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_monitor_tools.py
# Description : Outils monitoring bornes sans autorite d'action
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
from datetime import datetime,timezone,timedelta
import unittest
from unittest import mock
from eidolon_core.monitor_tools import (validate_status,validate_parameters,evidence,verify_evidence,
                                       execute_machine,monitoring_registry,monitoring_policy)
from eidolon_core.tools import default_registry,Policy

def snapshot():
    return {'service_schema':'eidolon-darme-service/1','authorizes_execution':False,
            'enforcement_enabled':False,'badge':'grey','visibility':'partial',
            'machine':{'schema':'eidolon-machine/1','sampled_at':datetime.now(timezone.utc).isoformat(),
                       'cpu_percent':0.1,'cpu_count':2,'load_1_5_15':[.1,.1,.1],
                       'memory':{'total_bytes':10,'available_bytes':8,'used_bytes':2},
                       'swap':None,'disk':None}}

class MonitorToolsTests(unittest.TestCase):
    def test_existing_evidence_verified_without_new_probe(self):
        result=evidence(snapshot())
        with mock.patch('eidolon_core.monitor_tools.read_status',side_effect=AssertionError('must not probe')):
            self.assertTrue(verify_evidence({}, {},result))
        result['sha256']='0'*64
        self.assertFalse(verify_evidence({}, {},result))
    def test_no_commands_paths_or_targets_accepted(self):
        for value in ({'command':'id'},{'path':'/etc/shadow'},{'target':'memory'},[],'status'):
            with self.assertRaises(ValueError):validate_parameters(value,{})
    def test_optin_read_only_registry(self):
        registry=monitoring_registry();policy=monitoring_policy()
        self.assertIsNone(default_registry().get('monitor.machine'))
        self.assertFalse(Policy().allows(registry.get('monitor.machine')))
        self.assertTrue(policy.allows(registry.get('monitor.machine')))
        self.assertTrue(policy.allows(registry.get('monitor.darme')))
    def test_execute_uses_local_status_only(self):
        value=snapshot()
        with mock.patch('eidolon_core.monitor_tools.read_status',return_value=value):
            result=execute_machine({}, {})
        self.assertFalse(result['authorizes_execution'])
        self.assertEqual(result['scope'],'local_vm_only')
        self.assertTrue(verify_evidence({}, {},result))
    def test_stale_invalid_authority_and_raw_events_refused(self):
        for change in ({'events':[]},{'authorizes_execution':True},{'enforcement_enabled':True}):
            with self.assertRaises(ValueError):validate_status(dict(snapshot(),**change))
        value=snapshot();value['machine']['sampled_at']=(datetime.now(timezone.utc)-timedelta(seconds=61)).isoformat()
        with self.assertRaises(ValueError):validate_status(value)
    def test_nan_bool_and_bad_memory_refused(self):
        for cpu in (True,float('nan'),101,-1):
            value=snapshot();value['machine']['cpu_percent']=cpu
            with self.assertRaises(ValueError):validate_status(value)
        value=snapshot();value['machine']['memory']['used_bytes']=20
        with self.assertRaises(ValueError):validate_status(value)
