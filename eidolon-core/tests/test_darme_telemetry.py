# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_darme_telemetry.py
# Description : Mesures locales, signature, reprise et retrait des donnees
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
import base64
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
from eidolon_core.darme_machine import MachineMetrics
from eidolon_core.darme_ssh import FeedVerifier, canonical, event_from_row, SCHEMA, read_bounded
try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives import serialization
except ImportError:
    Ed25519PrivateKey = None

def row(message='Failed password for test from 203.0.113.10 port 1234 ssh2'):
    return {'_SYSTEMD_UNIT':'ssh.service','_COMM':'sshd-session','_UID':'0',
            'MESSAGE':message,'__CURSOR':'test-cursor','__REALTIME_TIMESTAMP':'1791786103913150'}

class MachineTests(unittest.TestCase):
    def test_cpu_delta_memory_and_first_sample(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/'stat').write_text('cpu 100 0 50 100 0 0 0 0 50 0\n')
            (root/'meminfo').write_text('MemTotal: 1000 kB\nMemAvailable: 200 kB\nSwapTotal: 100 kB\nSwapFree: 90 kB\n')
            clock = [1]
            metrics = MachineMetrics(tmp,proc=tmp,clock=lambda:clock[0])
            first = metrics.sample()
            self.assertIsNone(first['cpu_percent'])
            self.assertEqual(first['memory']['used_bytes'],800*1024)
            self.assertEqual(first['swap']['used_bytes'],10*1024)
            (root/'stat').write_text('cpu 125 0 75 150 0 0 0 0 75 0\n')
            clock[0] += 10
            self.assertEqual(metrics.sample()['cpu_percent'],50)
    def test_missing_proc_is_unavailable(self):
        with tempfile.TemporaryDirectory() as tmp:
            value = MachineMetrics(tmp,proc=tmp).sample()
            self.assertIsNone(value['cpu_percent'])
            self.assertIsNone(value['memory'])
            self.assertEqual(value['errors'],['cpu_unavailable','memory_unavailable'])
            self.assertIsNone(value['gpu'])
    def test_negative_counters_and_clock_regression(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/'stat').write_text('cpu -1 0 0 1 0 0 0 0\n')
            self.assertIsNone(MachineMetrics(tmp,proc=tmp).sample()['cpu_percent'])
            (root/'stat').write_text('cpu 10 0 0 10 0 0 0 0\n')
            clock=[10];metrics=MachineMetrics(tmp,proc=tmp,clock=lambda:clock[0]);metrics.sample()
            clock[0]=9
            (root/'stat').write_text('cpu 20 0 0 20 0 0 0 0\n')
            self.assertIsNone(metrics.sample()['cpu_percent'])

class ReductionTests(unittest.TestCase):
    def test_failed_auth_redacted(self):
        value=event_from_row(row())
        self.assertEqual(value['category'],'ssh_auth_failure')
        self.assertNotIn('203.0.113',json.dumps(value))
        self.assertNotIn('test from',json.dumps(value))
    def test_accepted_key_not_security_alert(self):
        self.assertIsNone(event_from_row(row('Accepted publickey for test')))
    def test_untrusted_unit_comm_uid_refused(self):
        for key,value in (('_SYSTEMD_UNIT','other.service'),('_COMM','logger'),('_UID','1000')):
            item=row();item[key]=value
            self.assertIsNone(event_from_row(item))
    def test_cursor_bounded(self):
        item=row();item['__CURSOR']='x'*2049
        with self.assertRaises(ValueError):event_from_row(item)
    def test_file_bound_and_symlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            file=Path(tmp)/'feed';file.write_bytes(b'x'*10)
            with self.assertRaises(ValueError):read_bounded(file,9)
            link=Path(tmp)/'link';link.symlink_to(file)
            with self.assertRaises(OSError):read_bounded(link)

@unittest.skipIf(Ed25519PrivateKey is None,'optional darme-ssh cryptography dependency missing')
class SignatureTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();root=Path(self.temp.name)
        self.key=Ed25519PrivateKey.generate()
        (root/'public').write_bytes(self.key.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw))
        self.now=datetime(2026,10,12,6,30,tzinfo=timezone.utc)
        self.verifier=FeedVerifier(root/'public',root/'checkpoint',now=lambda:self.now)
        self.payload={'schema':SCHEMA,'source':'ssh-auth','sequence':1,'generated_at':self.now.isoformat(),
                      'healthy':True,'events':[event_from_row(row())]}
    def tearDown(self):self.temp.cleanup()
    def signed(self,value=None):
        value=self.payload if value is None else value
        return canonical({'payload':value,'signature':base64.b64encode(self.key.sign(canonical(value))).decode()})
    def test_valid_feed_checkpoint_and_identical_repeat(self):
        payload,events,digest=self.verifier.verify(self.signed())
        self.assertEqual(len(events),1)
        self.verifier.commit(payload,digest)
        restarted=FeedVerifier(Path(self.temp.name)/'public',Path(self.temp.name)/'checkpoint',now=lambda:self.now)
        self.assertEqual(restarted.verify(self.signed())[0]['sequence'],1)
    def test_modified_feed_signature_refused(self):
        value=json.loads(self.signed());value['payload']['healthy']=False
        with self.assertRaises(ValueError):self.verifier.verify(canonical(value))
    def test_lower_sequence_and_same_sequence_changed_data_refused(self):
        self.payload['sequence']=2
        payload,events,digest=self.verifier.verify(self.signed());self.verifier.commit(payload,digest)
        self.payload['sequence']=1
        with self.assertRaises(ValueError):self.verifier.verify(self.signed())
        self.payload['sequence']=2;self.payload['healthy']=False
        with self.assertRaises(ValueError):self.verifier.verify(self.signed())
    def test_stale_future_bool_sequence(self):
        for change in ({'generated_at':(self.now-timedelta(seconds=61)).isoformat()},
                       {'generated_at':(self.now+timedelta(seconds=6)).isoformat()}, {'sequence':True}):
            value=dict(self.payload,**change)
            with self.assertRaises(ValueError):self.verifier.verify(self.signed(value))
    def test_semantics_and_duplicate_event_refused(self):
        for key,value in (('source','other'),('subject','password=secret'),('severity','critical')):
            item=dict(self.payload,events=[dict(self.payload['events'][0],**{key:value})])
            with self.assertRaises(ValueError):self.verifier.verify(self.signed(item))
        item=dict(self.payload,events=self.payload['events']*2)
        with self.assertRaises(ValueError):self.verifier.verify(self.signed(item))
    def test_capacity_and_oversize_refused(self):
        item=dict(self.payload,events=self.payload['events']*129)
        with self.assertRaises(ValueError):self.verifier.verify(self.signed(item))
        with self.assertRaises(ValueError):self.verifier.verify(b'x'*(128*1024+1))
    def test_collector_capacity_retains_events_and_sequence(self):
        from eidolon_core.darme_ssh import collect
        root=Path(self.temp.name)
        key_file=root/'private'
        key_file.write_bytes(self.key.private_bytes(serialization.Encoding.Raw,serialization.PrivateFormat.Raw,serialization.NoEncryption()))
        entries=[]
        for index in range(129):
            value=row();value['__CURSOR']=f'cursor-{index}';entries.append(value)
        (root/'checkpoint.json').write_bytes(canonical({'sequence':5,'cursor':'baseline','events':[],'overflow':False}))
        handlers={}
        def register(signum,handler):handlers[signum]=handler
        def stop(_):next(iter(handlers.values()))(0,None)
        with mock.patch('eidolon_core.darme_ssh.rows',return_value=entries), \
             mock.patch('eidolon_core.darme_ssh.signal.signal',side_effect=register), \
             mock.patch('eidolon_core.darme_ssh.time.sleep',side_effect=stop):
            collect(key_file,root,root)
        state=json.loads((root/'checkpoint.json').read_bytes())
        envelope=json.loads((root/'feed.json').read_bytes())
        self.assertEqual(state['sequence'],6)
        self.assertEqual(len(state['events']),128)
        self.assertTrue(state['overflow'])
        self.assertFalse(envelope['payload']['healthy'])
        self.assertNotIn('203.0.113',json.dumps(state))
    def test_service_feed_durable_idempotent_and_tamper_degrades(self):
        from eidolon_core.darme_service import Collector
        from eidolon_core.darme_store import DarmeJournal
        from collections import namedtuple
        disk=namedtuple('Disk','total used free')(10**10,10**9,9*10**9)
        journal=DarmeJournal(Path(self.temp.name)/'events.sqlite')
        try:
            with mock.patch('eidolon_core.darme_ssh.FeedVerifier',return_value=self.verifier):
                collector=Collector(journal,['eidolon-core-api.service'],self.temp.name,lambda _:True,lambda _:disk,ssh_feed=True)
            with mock.patch('eidolon_core.darme_ssh.read_bounded',return_value=self.signed()):
                collector.sample();collector.sample()
            self.assertTrue(collector.status()['ssh_feed_healthy'])
            self.assertEqual(collector.status()['unacknowledged_alerts'],1)
            with mock.patch('eidolon_core.darme_ssh.read_bounded',return_value=b'{}'):
                collector.sample()
            self.assertFalse(collector.status()['ssh_feed_healthy'])
            self.assertEqual(collector.status()['badge'],'red')
        finally:journal.close()
