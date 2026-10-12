# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_darme_acceptance.py
# Description : Disponibilite, reprise et limites du noyau passif
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
import os,tempfile,unittest,sqlite3
from pathlib import Path
from eidolon_core.darme import DarmeMonitor,SecurityEvent,Severity
from eidolon_core.darme_store import DarmeJournal

class DarmeAcceptance(unittest.TestCase):
    def event(self,identity='one',severity=Severity.INFO,source='nas'):
        return SecurityEvent(identity,source,'synthetic',severity,'2026-10-12T03:00:00Z')
    def monitor(self):
        m=DarmeMonitor(['nas'],max_events=1);m.health('nas',True);return m
    def test_capacity_degrades_visibility(self):
        m=self.monitor();m.ingest(self.event())
        with self.assertRaises(OverflowError):m.ingest(self.event('two'))
        self.assertEqual(m.snapshot()['badge'],'grey')
        self.assertEqual(m.snapshot()['visibility'],'partial')
        self.assertTrue(m.snapshot()['ingestion_paused'])
        m.health('nas',True)
        self.assertEqual(m.snapshot()['badge'],'grey')
    def test_capacity_does_not_hide_known_alert(self):
        m=self.monitor();m.ingest(self.event(severity=Severity.CRITICAL))
        with self.assertRaises(OverflowError):m.ingest(self.event('two'))
        self.assertEqual(m.snapshot()['badge'],'red')
        m.acknowledge('one')
        self.assertEqual(m.snapshot()['badge'],'grey')
    def test_duplicate_at_capacity_is_not_a_loss(self):
        m=self.monitor();e=self.event();m.ingest(e);m.ingest(e)
        self.assertFalse(m.snapshot()['ingestion_paused'])
    def test_trusted_source_collision_does_not_overwrite(self):
        m=self.monitor();m.ingest(self.event())
        with self.assertRaises(ValueError):m.ingest(self.event(severity=Severity.CRITICAL))
        self.assertEqual(m.snapshot()['events'][0]['severity'],'info')
    def test_explicit_lost_probe_is_unknown_after_restart(self):
        with tempfile.TemporaryDirectory() as d:
            j=DarmeJournal(Path(d)/'events.sqlite3');j.record(self.event());j.close()
            j=DarmeJournal(Path(d)/'events.sqlite3')
            m=j.replay(DarmeMonitor(['nas']))
            self.assertEqual(m.snapshot()['badge'],'grey');j.close()
    def test_acknowledgement_is_append_only(self):
        with tempfile.TemporaryDirectory() as d:
            j=DarmeJournal(Path(d)/'events.sqlite3');j.record(self.event())
            self.assertTrue(j.acknowledge('one','operator','reviewed'))
            self.assertFalse(j.acknowledge('one','operator','reviewed'))
            with self.assertRaises(ValueError):j.acknowledge('one','attacker','erase')
            self.assertEqual(j.db.execute('SELECT actor FROM acknowledgements').fetchone()[0],'operator');j.close()
    def test_cannot_forge_ack_with_control_character(self):
        with tempfile.TemporaryDirectory() as d:
            j=DarmeJournal(Path(d)/'events.sqlite3');j.record(self.event())
            with self.assertRaises(ValueError):j.acknowledge('one','operator','fake\nentry')
            self.assertEqual(j.db.execute('SELECT COUNT(*) FROM acknowledgements').fetchone()[0],0);j.close()
    def test_ancestor_symlink_refused(self):
        with tempfile.TemporaryDirectory() as d:
            real=Path(d)/'real';real.mkdir();(real/'nested').mkdir()
            alias=Path(d)/'alias';alias.symlink_to(real,target_is_directory=True)
            with self.assertRaises(ValueError):DarmeJournal(alias/'nested'/'journal.sqlite3')
    def test_journal_integrity_and_no_execution(self):
        with tempfile.TemporaryDirectory() as d:
            j=DarmeJournal(Path(d)/'events.sqlite3');j.record(self.event())
            self.assertEqual(j.db.execute('PRAGMA integrity_check').fetchone()[0],'ok')
            m=j.replay(DarmeMonitor(['nas']))
            self.assertFalse(m.snapshot()['enforcement_enabled'])
            self.assertFalse(m.snapshot()['authorizes_execution']);j.close()
    def test_invalid_log_boundaries(self):
        for text in ['x'*257,'bad\x1b','bad\n']:
            with self.subTest(text=text[:10]):
                with self.assertRaises(ValueError):
                    SecurityEvent('x','nas','log',Severity.INFO,'2026-10-12T03:00:00Z',text)
if __name__=='__main__':unittest.main()
