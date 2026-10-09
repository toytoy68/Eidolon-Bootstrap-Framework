# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : recheck_g085_storage.py
# Description : Contre-vérification indépendante des corrections C106 sur copies synthétiques
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import tempfile
from eidolon_core.conversation_store import ConversationStore, ConversationError
from eidolon_core.store import Store


def refused(call, prefix):
    try:
        call()
    except ConversationError as exc:
        code = str(exc).split(':')[0]
        assert code == prefix, code
        return code
    raise AssertionError('operation accepted')


def main():
    checks = []
    with tempfile.TemporaryDirectory(prefix='eidolon-g085-fixed-') as folder:
        root = Path(folder)
        store = Store(root/'linked'); directory = root/'linked/conversations'; directory.mkdir(mode=0o700)
        target = root/'unrelated.sqlite3'
        with sqlite3.connect(target) as db: db.execute('CREATE TABLE unrelated (value TEXT)')
        before = target.read_bytes()
        (directory/'conversations.sqlite3').symlink_to(target)
        refused(lambda: ConversationStore(store, create=True), 'CONVERSATION_STORE_UNAVAILABLE')
        assert target.read_bytes() == before
        checks.append('R1: terminal link refused, external target byte-identical')
        a = ConversationStore(Store(root/'a'), create=True)
        b = ConversationStore(Store(root/'b'), create=True)
        a.path.unlink(); shutil.copyfile(b.path, a.path); a.path.chmod(0o600)
        before = a.path.read_bytes()
        refused(lambda: a.open(client_id='fixture', client_key='foreign'), 'STORE_CHANGED')
        assert a.path.read_bytes() == before
        checks.append('R2: replaced inode refused without modifying foreign database')
        c = ConversationStore(Store(root/'c'), create=True)
        cid = c.open(client_id='fixture', client_key='read')['conversation_id']
        c.path.unlink()
        refused(lambda: c.page(cid), 'CONVERSATION_STORE_MISSING')
        assert not c.path.exists()
        checks.append('R3: missing read refused without recreation')
        d = ConversationStore(Store(root/'d'), create=True)
        cid = d.open(client_id='fixture', client_key='bounds')['conversation_id']
        for values in ({'max_turns':-1},{'max_turns':True},{'max_turns':201}, {'max_chars':0},{'max_chars':200001}):
            refused(lambda: d.context(cid, **values), 'INVALID_CONVERSATION')
        checks.append('R4: negative, boolean, excessive and zero context bounds refused')
        e = ConversationStore(Store(root/'e'), create=True)
        with sqlite3.connect(e.path) as db: db.execute("UPDATE meta SET value='foreign' WHERE key='store_id'")
        before = e.path.read_bytes()
        refused(lambda: e.open(client_id='fixture',client_key='same-inode'), 'STORE_CHANGED')
        assert e.path.read_bytes()==before
        checks.append('same inode, changed Store identity refused inside transaction')
        with sqlite3.connect(d.path) as db: db.execute('PRAGMA user_version=2')
        before=d.path.read_bytes()
        refused(lambda: d.page(cid), 'CONVERSATION_STORE_UNAVAILABLE')
        assert d.path.read_bytes()==before
        checks.append('same inode, changed schema version refused inside transaction')
        missing = Store(root/'absent')
        refused(lambda: ConversationStore(missing), 'CONVERSATION_STORE_MISSING')
        assert not (root/'absent/conversations').exists()
        checks.append('reopening absent store creates no conversation directory')
    print(json.dumps({'status':'PASS','source':'C106 / 3ad4aa8','synthetic_only':True,'checks':checks},indent=2))

if __name__=='__main__': main()
