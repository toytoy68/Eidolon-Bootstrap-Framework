# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : recheck_g087_credentials.py
# Description : Vérification indépendante des corrections d'appairage C109
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
import json
from pathlib import Path
import shutil
import sqlite3
import tempfile
from eidolon_core.client_credentials import ClientCredentials, CredentialError
from eidolon_core.store import Store


def refuse(action, code):
    try:
        action()
    except CredentialError as exc:
        assert str(exc).split(':')[0] == code, str(exc)
    else:
        raise AssertionError('operation unexpectedly accepted')

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    a_store, b_store = Store(root/'a'), Store(root/'b')
    a = ClientCredentials(a_store, create=True)
    b = ClientCredentials(b_store, create=True)
    client = b.pair(client_id='fixture', actor='synthetic other Store')
    a.path.unlink(); shutil.copyfile(b.path, a.path); a.path.chmod(0o600)
    before = a.path.read_bytes()
    refuse(lambda: a.authenticate(client['token']), 'STORE_CHANGED')
    refuse(lambda: ClientCredentials(a_store), 'STORE_CHANGED')
    refuse(lambda: ClientCredentials(a_store, create=True), 'STORE_CHANGED')
    assert a.path.read_bytes() == before
    other = root/'other'; other.mkdir(mode=0o700)
    linked = Store(root/'linked')
    (linked.directory/'conversations').symlink_to(other, target_is_directory=True)
    refuse(lambda: ClientCredentials(linked, create=True), 'CREDENTIALS_UNAVAILABLE')
    assert list(other.iterdir()) == []
    with sqlite3.connect(b.path) as db:
        db.execute("UPDATE meta SET value='s-' || ? WHERE key='store_id'", ('0'*32,))
    before = b.path.read_bytes()
    refuse(lambda: b.authenticate(client['token']), 'STORE_CHANGED')
    assert b.path.read_bytes() == before
    b.path.unlink()
    refuse(lambda: b.authenticate(client['token']), 'CREDENTIALS_MISSING')
    assert not b.path.exists()
    print(json.dumps({'status':'PASS', 'source':'C109/C110 8f20041', 'synthetic_only':True,
        'checks':['R1 live replacement refused', 'R1 reopen/create refuse foreign identity without write',
                  'R2 linked parent target unchanged', 'same-inode identity checked under transaction',
                  'missing authentication database not recreated'], 'tokens_in_output':False},indent=2))
