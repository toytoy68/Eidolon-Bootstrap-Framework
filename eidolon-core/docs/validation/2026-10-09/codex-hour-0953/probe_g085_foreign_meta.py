# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : probe_g085_foreign_meta.py
# Description : Revue complémentaire de la création explicite sur base étrangère non vide
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
from eidolon_core.conversation_store import ConversationStore
from eidolon_core.store import Store

with tempfile.TemporaryDirectory(prefix='eidolon-g085-foreign-meta-') as folder:
    root=Path(folder);store=Store(root/'state');directory=root/'state/conversations';directory.mkdir(mode=0o700)
    path=directory/'conversations.sqlite3'
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE unrelated (value TEXT)')
        db.execute("INSERT INTO unrelated VALUES ('synthetic unrelated content')")
        db.execute('CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
        db.execute('PRAGMA user_version=1')
    path.chmod(0o600)
    before=hashlib.sha256(path.read_bytes()).hexdigest()
    result=ConversationStore(store,create=True)
    with sqlite3.connect(path) as db:
        rows=dict(db.execute('SELECT key,value FROM meta'))
        tables=sorted(row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'"))
    changed=hashlib.sha256(path.read_bytes()).hexdigest()!=before
    assert changed and rows['store_id']==result.store_id and tables==['meta','unrelated']
    print(json.dumps({'status':'FINDING_REPRODUCED','source':'C106 / 3ad4aa8','id':'G085-R5',
        'synthetic_only':True,'existing_foreign_database_nonempty':True,'explicit_create_accepted':True,
        'foreign_database_modified':changed,'meta_keys_added':sorted(rows),'tables_after':tables},indent=2))
