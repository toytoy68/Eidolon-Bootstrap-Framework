# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : retention_preview.py
# Description : Services hors VM G273, configuration opérateur explicite
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Read-only inventory and logical payload redaction proposal. Never deletes.

Request keys, current document versions, effects and turn provenance remain
protected. Counts are logical UTF-8 payload bytes, not reclaimable disk space.
"""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
import sqlite3
from .offline_state import database
from .contracts import digest


def protected_inventory(root):
    from .profile_files import opened
    import stat
    totals={'files':0,'logical_bytes':0,'allocated_bytes':0,'protected':True}
    entries=0
    def visit(path,depth):
        nonlocal entries
        if depth>16: raise ValueError('INVENTORY_BUDGET')
        with opened(root,path,directory=True) as fd:
            with os.scandir(fd) as rows:
                for row in rows:
                    entries+=1
                    if entries>10000: raise ValueError('INVENTORY_BUDGET')
                    info=row.stat(follow_symlinks=False)
                    if stat.S_ISLNK(info.st_mode): raise ValueError('INVENTORY_LINK')
                    relative=path+'/'+row.name if path else row.name
                    if stat.S_ISDIR(info.st_mode): visit(relative,depth+1)
                    elif stat.S_ISREG(info.st_mode):
                        if info.st_nlink!=1: raise ValueError('INVENTORY_LINK')
                        totals['files']+=1;totals['logical_bytes']+=info.st_size
                        totals['allocated_bytes']+=info.st_blocks*512
                    else: raise ValueError('INVENTORY_SPECIAL_FILE')
    visit('',0)
    return totals


def preview(directory, *, days, now=None, protected_roots=None):
    if type(days) is not int or not 1<=days<=36500: raise ValueError("EXPLICIT_RETENTION_REQUIRED")
    now=now or datetime.now(timezone.utc)
    if now.tzinfo is None: raise ValueError("AWARE_TIME_REQUIRED")
    cutoff=now-timedelta(days=days);items=[];protected=0;logical=0;stores=[]
    # Fixed filenames and roles; unknown files are not eligible for cleanup.
    for name in ('library.sqlite3','actions.sqlite3'):
        try:
            with database(directory,name) as db:
                stores.append(name)
                if name=='library.sqlite3':
                    rows=db.execute("SELECT v.rowid,v.*,EXISTS(SELECT 1 FROM files f WHERE f.profile=v.profile AND f.root=v.root AND f.path=v.path AND f.sha=v.sha) AS current FROM versions v LIMIT 10001").fetchall()
                    if len(rows)>10000: raise ValueError("RETENTION_BUDGET")
                    for r in rows:
                        size=len(r['excerpt'].encode());logical+=size
                        at=datetime.fromisoformat(r['created_at'])
                        if at.tzinfo is None: raise ValueError("INVALID_DATE")
                        if not r['current'] and at<cutoff:
                            items.append({'store':name,'row':r['rowid'],'operation':'REVIEW_EXCERPT_REDACTION','bytes':size,'payload_sha256':hashlib.sha256(r['excerpt'].encode()).hexdigest()})
                        else: protected+=1
                else:
                    rows=db.execute("SELECT id,proposal,result,state FROM actions LIMIT 10001").fetchall()
                    if len(rows)>10000: raise ValueError("RETENTION_BUDGET")
                    for r in rows:
                        logical+=len(r['proposal'].encode())+len((r['result'] or '').encode());protected+=1
                    # Receipts preserve idempotence and effects; never select by age alone.
                    tables={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                    if 'identity_templates' in tables:
                        for r in db.execute("SELECT templates FROM identity_templates"):
                            protected+=1;logical+=len(r[0].encode())
                    if 'identity_sessions' in tables:
                        for r in db.execute("SELECT samples FROM identity_sessions LIMIT 10001"):
                            protected+=1;logical+=len(r[0].encode())
        except FileNotFoundError: continue
    other={}
    for role,path in (protected_roots or {}).items():
        if role not in ('histories','memory','media','backups','credentials'): raise ValueError('INVALID_PROTECTED_ROLE')
        other[role]=protected_inventory(path)
    report={'schema' :'eidolon-retention-preview/1','state':'REVIEW_ONLY','as_of':now.isoformat(),'older_than_days':days,'stores':stores,
            'protected_roots':other,'logical_bytes':logical,'candidate_logical_bytes':sum(x['bytes'] for x in items),'protected_rows':protected,'candidates':items,
            'disk_reclaim_bytes':None,'deleted':False,'backup_erasure':False,'execution_authorized':False,
            'outside_scope':['Core conversations and pairings','Memory corpus and journals','Qdrant generations','media artifacts','backups']}
    report['proposal_sha256']=digest(report)
    return report


def main(argv=None):
    p=argparse.ArgumentParser(description='Aperçu de conservation Eidolon, aucune suppression')
    p.add_argument('--directory',required=True);p.add_argument('--older-than-days',required=True,type=int)
    p.add_argument('--protected-root',action='append',default=[],metavar='ROLE=CHEMIN')
    a=p.parse_args(argv)
    try:
        roots={}
        for value in a.protected_root:
            role,path=value.split('=',1)
            if role in roots: raise ValueError('DUPLICATE_ROLE')
            roots[role]=path
        print(json.dumps(preview(a.directory,days=a.older_than_days,protected_roots=roots),ensure_ascii=False));return 0
    except (OSError,ValueError,sqlite3.Error): print('{"state":"INVENTORY_REFUSED","deleted":false}');return 2

if __name__=='__main__': raise SystemExit(main())
