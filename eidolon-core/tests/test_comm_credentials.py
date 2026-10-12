# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_comm_credentials.py
# Description : Authentification sans migration ni ecriture de Core
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
import hashlib
from pathlib import Path
import sqlite3
import tempfile
import unittest
from eidolon_core.store import Store
from eidolon_core.client_credentials import ClientCredentials,CredentialError
from eidolon_core.comm_credentials import ReadOnlyCredentialStore,ReadOnlyClientCredentials

class ReadOnlyCommTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.directory=Path(self.temp.name)/'state'
        self.store=Store(self.directory)
        self.clients=ClientCredentials(self.store,create=True)
        self.token=self.clients.pair(client_id='test',actor='test')['token']
    def tearDown(self):self.temp.cleanup()
    def test_authentication_does_not_change_database_and_tracks_revocation(self):
        before={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in (self.store.path,self.clients.path)}
        view=ReadOnlyClientCredentials(ReadOnlyCredentialStore(self.directory))
        self.assertEqual(view.authenticate(self.token)['client_id'],'test')
        self.assertEqual(before,{p:hashlib.sha256(p.read_bytes()).hexdigest() for p in before})
        self.clients.revoke('test')
        self.assertIsNone(view.authenticate(self.token))
    def test_no_writer_or_schema_initializer(self):
        view=ReadOnlyCredentialStore(self.directory)
        with self.assertRaises(ValueError):
            with view.connection() as db:db.execute("INSERT INTO sync_metadata VALUES ('unexpected','write')")
        clients=ReadOnlyClientCredentials(view)
        with self.assertRaises(CredentialError):clients.pair(client_id='other',actor='test')
        with self.assertRaises(CredentialError):clients.revoke('test')
    def test_missing_database_not_created(self):
        missing=self.directory/'missing';missing.mkdir()
        with self.assertRaises(FileNotFoundError):ReadOnlyCredentialStore(missing)
        self.assertEqual(list(missing.iterdir()),[])
    def test_recovery_refused(self):
        view=ReadOnlyCredentialStore(self.directory)
        (self.directory/'RECOVERY-REVIEW-ONLY').touch()
        with self.assertRaises(ValueError):
            with view.connection():pass
    def test_symlink_and_database_replacement_refused(self):
        link=Path(self.temp.name)/'link';link.symlink_to(self.directory)
        with self.assertRaises(ValueError):ReadOnlyCredentialStore(link)
        view=ReadOnlyCredentialStore(self.directory)
        copied=self.directory/'copied';copied.write_bytes(self.store.path.read_bytes());copied.replace(self.store.path)
        with self.assertRaises(ValueError):
            with view.connection():pass
    def test_group_writable_state_without_private_enclosure_refused(self):
        Path(self.temp.name).chmod(0o755)
        self.directory.chmod(0o775)
        with self.assertRaises(ValueError):ReadOnlyCredentialStore(self.directory)
