# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : probe_g085_storage.py
# Description : Contre-revue G085 sur copies synthétiques, sans modifier le module Claude
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import tempfile

from eidolon_core.conversation_store import ConversationStore
from eidolon_core.store import Store


def main():
    findings = []
    with tempfile.TemporaryDirectory(prefix='eidolon-g085-review-') as directory:
        root = Path(directory)
        # Initialization follows a terminal symlink and writes its target before identity checks.
        store = Store(root / 'linked'); folder = root / 'linked/conversations'; folder.mkdir(mode=0o700)
        external = root / 'external.sqlite3'
        with sqlite3.connect(external) as db: db.execute('CREATE TABLE unrelated (value TEXT)')
        before = hashlib.sha256(external.read_bytes()).hexdigest()
        (folder / 'conversations.sqlite3').symlink_to(external)
        error = None
        try: ConversationStore(store)
        except Exception as exc: error = type(exc).__name__
        with sqlite3.connect(external) as db:
            tables = sorted(row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'"))
        findings.append({'id':'G085-R1','terminal_symlink_accepted':error is None,
                         'external_target_changed':before != hashlib.sha256(external.read_bytes()).hexdigest(),
                         'tables_added':sorted(set(tables)-{'unrelated'}),'error':error})
        # A live object does not recheck the Store binding when opening a replacement DB.
        a = ConversationStore(Store(root / 'a')); b = ConversationStore(Store(root / 'b'))
        a.path.unlink(); shutil.copyfile(b.path, a.path)
        opened = a.open(client_id='fixture',client_key='after-replacement')
        with sqlite3.connect(a.path) as db:
            bound = db.execute("SELECT value FROM meta WHERE key='store_id'").fetchone()[0]
            count = db.execute('SELECT count(*) FROM conversations').fetchone()[0]
        findings.append({'id':'G085-R2','replacement_foreign_identity':bound != a.store_id,
                         'write_accepted':opened['created'],'rows_in_foreign_database':count})
        # A failed read silently recreates a missing file.
        c = ConversationStore(Store(root / 'c')); cid=c.open(client_id='fixture',client_key='read')['conversation_id']
        c.path.unlink(); error=None
        try:c.page(cid)
        except Exception as exc:error=str(exc).split(':')[0]
        findings.append({'id':'G085-R3','read_error':error,'missing_file_recreated':c.path.exists(),
                         'created_bytes':c.path.stat().st_size if c.path.exists() else None})
        # Context's SQL LIMIT accepts negative values; it then reads every turn.
        d=ConversationStore(Store(root/'d'));cid=d.open(client_id='fixture',client_key='budget')['conversation_id']
        for i in range(3):d.append_turn(cid,client_id='fixture',client_turn_key='t'+str(i),text='Synthetic turn')
        result=d.context(cid,max_turns=-1,max_chars=10000)
        findings.append({'id':'G085-R4','negative_turn_budget_accepted':True,'turns_returned':len(result['turns'])})
    assert findings[0]['external_target_changed']
    assert findings[1]['write_accepted'] and findings[1]['replacement_foreign_identity']
    assert findings[2]['missing_file_recreated']
    assert findings[3]['turns_returned']==3
    print(json.dumps({'status':'FINDINGS_REPRODUCED','source':'G085 at e512bd3','synthetic_only':True,'findings':findings},indent=2))

if __name__=='__main__':main()
