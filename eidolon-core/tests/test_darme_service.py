# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_darme_service.py
# Description : Recette collecte locale et conservation des alertes
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
import tempfile
import unittest
from collections import namedtuple
from pathlib import Path
from eidolon_core.darme_service import Collector, validate_config
from eidolon_core.darme_store import DarmeJournal

Disk = namedtuple('Disk', 'total used free')
UNIT = 'eidolon-core-api.service'

class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'journal.sqlite'
        self.journal = DarmeJournal(self.path)
        self.healthy = True
        self.disk = Disk(10**10, 10**9, 9*10**9)
        self.collector = Collector(self.journal, [UNIT], self.temp.name,
                                   lambda _: self.healthy, lambda _: self.disk)
    def tearDown(self):
        self.journal.close()
        self.temp.cleanup()
    def test_partial_without_security_collectors(self):
        self.collector.sample()
        result = self.collector.status()
        self.assertEqual(result['badge'], 'grey')
        self.assertEqual(result['visibility'], 'partial')
        self.assertFalse(result['authorizes_execution'])
        self.assertNotIn('events', result)
    def test_failure_recovery_does_not_clear_alert(self):
        self.healthy = False
        self.collector.sample()
        self.collector.sample()
        self.assertEqual(self.collector.status()['unacknowledged_alerts'], 1)
        self.healthy = True
        self.collector.sample()
        self.assertEqual(self.collector.status()['badge'], 'red')
        self.assertTrue(self.collector.status()['sources'][UNIT])
    def test_replay_after_restart(self):
        self.healthy = False
        self.collector.sample()
        self.journal.close()
        self.journal = DarmeJournal(self.path)
        self.collector = Collector(self.journal, [UNIT], self.temp.name,
                                   lambda _: True, lambda _: self.disk)
        self.collector.sample()
        self.assertEqual(self.collector.status()['unacknowledged_alerts'], 1)
    def test_disk_pressure(self):
        self.disk = Disk(10**10, 99*10**8, 10**8)
        self.collector.sample()
        self.assertEqual(self.collector.status()['badge'], 'red')
        self.assertFalse(self.collector.status()['sources']['journal-disk'])
    def test_restart_ongoing_failure_not_duplicated(self):
        self.healthy = False
        self.collector.sample()
        self.journal.close()
        self.journal = DarmeJournal(self.path)
        self.collector = Collector(self.journal, [UNIT], self.temp.name,
                                   lambda _: False, lambda _: self.disk)
        self.collector.sample()
        self.assertEqual(self.collector.status()['unacknowledged_alerts'], 1)
    def test_probe_exception_degrades(self):
        def fail(_):
            raise OSError('sensitive details must not leave the collector')
        self.collector.service_probe = fail
        self.collector.sample()
        self.assertFalse(self.collector.status()['sources'][UNIT])
        self.assertNotIn('sensitive', str(self.collector.status()))
    def test_quota_admission_retry(self):
        self.journal.max_records = 1
        self.healthy = False
        self.collector.sample()
        self.healthy = True
        self.collector.sample()
        self.disk = Disk(10**10, 99*10**8, 10**8)
        self.collector.sample()
        self.assertTrue(self.collector.status()['ingestion_paused'])
        self.assertTrue(self.collector.previous['journal-disk'])
        self.collector.sample()
        self.assertTrue(self.collector.status()['ingestion_paused'])
    def test_config_rejects_arbitrary_commands(self):
        for data in ({'units':['sshd.service'], 'interval':10},
                     {'units':[UNIT], 'interval':True},
                     {'units':[UNIT,UNIT], 'interval':10},
                     {'units':[UNIT], 'interval':10, 'command':'id'}):
            with self.assertRaises(ValueError):
                validate_config(data)
        self.assertEqual(validate_config({'units':[UNIT], 'interval':10})['interval'], 10)
