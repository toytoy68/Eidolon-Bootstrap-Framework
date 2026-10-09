# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : probe_storage_memory.py
# Description : Mesure isolée du refus de TEXT volumineux avant lecture SQLite
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Linux RSS bench, synthetic temporary SQLite; each reader in a fresh process."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile

BUILD = """
import sqlite3,sys
c=sqlite3.connect(sys.argv[1]);c.execute('CREATE TABLE missions (id TEXT PRIMARY KEY, revision INTEGER, cancel_requested INTEGER, body TEXT)')
c.execute("INSERT INTO missions VALUES ('fixture',0,0,CAST(zeroblob(?) AS TEXT))",(256*1024*1024,))
c.execute('CREATE TABLE events (sequence INTEGER PRIMARY KEY, mission_id TEXT, at TEXT, kind TEXT, detail TEXT)')
c.execute("INSERT INTO events VALUES (1,?,'2026-10-09T00:00:00Z','fixture',CAST(zeroblob(?) AS TEXT))",('m-'+'a'*32,256*1024*1024))
c.commit();c.close()
"""
MEASURE = """
import json,resource,sqlite3,sys
from eidolon_core.client_sync import read_mission_row,read_event_row,SyncError
c=sqlite3.connect('file:'+sys.argv[1]+'?mode=ro',uri=True);c.execute('PRAGMA query_only=ON');c.execute('BEGIN')
before=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
if sys.argv[2]=='legacy_substr':
 sql=('SELECT substr(CAST(body AS BLOB),1,16777217) FROM missions' if sys.argv[3]=='mission' else
      'SELECT substr(CAST(detail AS BLOB),1,16777217) FROM events')
 raw=c.execute(sql).fetchone()[0]
 result={'returned_bytes':len(raw)}
else:
 try:
  if sys.argv[3]=='mission':read_mission_row(c,'fixture')
  else:read_event_row(c)
 except SyncError as e:result={'error':str(e)}
 else:raise AssertionError('oversized TEXT accepted')
result.update(mode=sys.argv[2],field=sys.argv[3],sqlite=sqlite3.sqlite_version,rss_peak_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,rss_before_kib=before)
c.close();print(json.dumps(result))
"""

def main():
    with tempfile.TemporaryDirectory(prefix='eidolon-sqlite-bound-') as root:
        path = str(Path(root) / 'fixture.sqlite3')
        subprocess.run([sys.executable, '-c', BUILD, path], check=True, timeout=30)
        results = []
        for field in ('mission', 'event'):
            for mode in ('legacy_substr', 'incremental_read'):
                p = subprocess.run([sys.executable, '-c', MEASURE, path, mode, field], check=True,
                                   capture_output=True, text=True, timeout=30)
                result = json.loads(p.stdout)
                delta = result['rss_peak_kib'] - result['rss_before_kib']
                if mode == 'incremental_read':
                    assert result['error'] == field.upper() + '_SIZE_LIMIT'
                    assert delta < 64 * 1024
                else:
                    assert delta > 128 * 1024
                results.append(result)
        print(json.dumps({'status': 'PASS', 'fixture_bytes': 256 * 1024 * 1024,
                          'fresh_reader_processes': True, 'results': results}, indent=2))

if __name__ == '__main__':
    main()
