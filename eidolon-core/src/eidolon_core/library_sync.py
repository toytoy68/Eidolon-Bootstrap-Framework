# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : library_sync.py
# Description : Services hors VM G273, configuration opérateur explicite
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Versioned local/NAS excerpts. No canonical Memory writes or source deletions.

One bounded full inventory per tick; failures never imply source deletion. Roots
come only from the operator's beta configuration. PC roots must be mounted on the
Linux host. Restart rescans hashes and deduplicates, never trusts mtimes alone.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import signal
import sqlite3
import stat
import threading
import time
from .contracts import digest, encode
from . import documents, profile_files
from .offline_state import database, lease
from .beta_state import configuration

MAX_FILES = 1000
MAX_BYTES = 32 * 1024 * 1024
MAX_VERSIONS = 10000

def binding(config):
    return digest({"clients":config["clients"], "roots":{p:c["file_roots"] for p,c in config["profiles"].items()}})

def inventory(root, *, deadline):
    result=[]; budget=[0]
    def visit(relative, depth):
        if depth>16 or time.monotonic()>deadline: raise ValueError("LIBRARY_SCAN_BUDGET")
        with profile_files.opened(root, relative, directory=True) as fd:
            before=os.fstat(fd)
            with os.scandir(fd) as entries:
                for entry in entries:
                    budget[0]+=1
                    if budget[0]>5000 or len(result)>=MAX_FILES or time.monotonic()>deadline:
                        raise ValueError("LIBRARY_SCAN_BUDGET")
                    path=relative+"/"+entry.name if relative else entry.name
                    info=entry.stat(follow_symlinks=False)
                    if stat.S_ISLNK(info.st_mode): raise ValueError("LIBRARY_LINK_REFUSED")
                    if stat.S_ISDIR(info.st_mode): visit(path,depth+1)
                    elif stat.S_ISREG(info.st_mode):
                        if entry.name.rsplit('.',1)[-1].lower() in documents.FORMATS:
                            if info.st_nlink!=1: raise ValueError("LIBRARY_LINK_REFUSED")
                            result.append(path)
            after=os.fstat(fd)
            if (before.st_ino,before.st_mtime_ns,before.st_ctime_ns)!=(after.st_ino,after.st_mtime_ns,after.st_ctime_ns):
                raise ValueError("LIBRARY_CHANGED")
    visit('',0)
    return sorted(result)

class Library:
    def __init__(self, config, directory):
        self.config, self.directory, self.binding = config, str(directory), binding(config)

    def _schema(self, db):
        db.execute("CREATE TABLE IF NOT EXISTS binding (fingerprint TEXT NOT NULL)")
        row=db.execute("SELECT fingerprint FROM binding").fetchone()
        if row and row[0]!=self.binding: raise ValueError("LIBRARY_BINDING_CHANGED")
        if not row: db.execute("INSERT INTO binding VALUES (?)",(self.binding,))
        db.execute("CREATE TABLE IF NOT EXISTS versions (profile TEXT, root TEXT, path TEXT, sha TEXT, bytes INTEGER, excerpt TEXT, created_at TEXT, PRIMARY KEY(profile,root,path,sha))")
        db.execute("CREATE TABLE IF NOT EXISTS files (profile TEXT, root TEXT, path TEXT, sha TEXT, present INTEGER, seen_at TEXT, PRIMARY KEY(profile,root,path))")
        db.execute("CREATE TABLE IF NOT EXISTS scans (profile TEXT, root TEXT, completed_at TEXT, files INTEGER, PRIMARY KEY(profile,root))")

    def _scope(self, client, root):
        profile=self.config['clients'].get(client)
        if profile is None or root not in self.config['profiles'][profile]['file_roots']:
            raise ValueError("LIBRARY_SCOPE_REFUSED")
        return profile,self.config['profiles'][profile]['file_roots'][root]

    def scan(self, client, root, *, stopped=None):
        with lease(self.directory,"library-scan.lock"):
            return self._scan(client,root,stopped=stopped)

    def _scan(self, client, root, *, stopped=None):
        profile,path=self._scope(client,root);deadline=time.monotonic()+30
        # Only commit a complete bounded generation. Interrupted scans leave the old one intact.
        names=inventory(path,deadline=deadline); batch=[];total=0;cache={}
        with database(self.directory,'library.sqlite3',write=True) as db:
            self._schema(db)
            known={(r[0],r[1]) for r in db.execute("SELECT sha,json_extract(excerpt,'$.format') FROM versions WHERE profile=?",(profile,))}
            count=db.execute("SELECT count(*) FROM versions").fetchone()[0]
        for relative in names:
            if time.monotonic()>deadline or stopped and stopped.is_set(): raise ValueError("LIBRARY_SCAN_INTERRUPTED")
            raw=profile_files.read_bytes(path,relative,max_bytes=documents.MAX_BYTES);total+=len(raw)
            if total>MAX_BYTES: raise ValueError("LIBRARY_SCAN_BUDGET")
            sha=hashlib.sha256(raw).hexdigest()
            # Reuse only this profile's exact content hash, never another person's excerpt.
            excerpt=None
            cache_key=(sha,documents.extension(Path(relative).name))
            if cache_key not in known:
                if cache_key not in cache: cache[cache_key]=documents.extract(raw,Path(relative).name)
                excerpt=dict(cache[cache_key],name=Path(relative).name)
            batch.append((relative,sha,len(raw),excerpt))
        if inventory(path,deadline=deadline)!=names: raise ValueError("LIBRARY_CHANGED")
        # A second content pass detects changes during extraction (not an atomic filesystem snapshot).
        for relative,sha,_,_ in batch:
            if time.monotonic()>deadline or stopped and stopped.is_set(): raise ValueError("LIBRARY_SCAN_INTERRUPTED")
            if hashlib.sha256(profile_files.read_bytes(path,relative,max_bytes=documents.MAX_BYTES)).hexdigest()!=sha:
                raise ValueError("LIBRARY_CHANGED")
        now=datetime.now(timezone.utc).isoformat();added=0;duplicates=0
        with database(self.directory,'library.sqlite3',write=True) as db:
            self._schema(db)
            missing=sum(not db.execute("SELECT 1 FROM versions WHERE profile=? AND root=? AND path=? AND sha=?",(profile,root,p,s)).fetchone() for p,s,_,_ in batch)
            if db.execute("SELECT count(*) FROM versions").fetchone()[0]+missing>MAX_VERSIONS: raise ValueError("LIBRARY_STORAGE_BUDGET")
            db.execute("UPDATE files SET present=0 WHERE profile=? AND root=?",(profile,root))
            for relative,sha,size,excerpt in batch:
                if excerpt is None:
                    row=db.execute("SELECT excerpt FROM versions WHERE profile=? AND sha=? AND json_extract(excerpt,'$.format')=? LIMIT 1",(profile,sha,documents.extension(Path(relative).name))).fetchone()
                    if row is None: raise ValueError("LIBRARY_SOURCE_CHANGED")
                    excerpt=json.loads(row[0]);excerpt['name']=Path(relative).name;duplicates+=1
                added+=db.execute("INSERT OR IGNORE INTO versions VALUES (?,?,?,?,?,?,?)",(profile,root,relative,sha,size,encode(excerpt),now)).rowcount
                db.execute("INSERT INTO files VALUES (?,?,?,?,1,?) ON CONFLICT(profile,root,path) DO UPDATE SET sha=excluded.sha,present=1,seen_at=excluded.seen_at",(profile,root,relative,sha,now))
            db.execute("INSERT INTO scans VALUES (?,?,?,?) ON CONFLICT(profile,root) DO UPDATE SET completed_at=excluded.completed_at,files=excluded.files",(profile,root,now,len(batch)))
        return {"state":"SYNCED_EXCERPTS_ONLY","files":len(batch),"new_versions":added,"reused_excerpts":duplicates,"bytes_read":total*2,"memory_written":False,"source_deleted":False}

    def page(self, client, root, after=''):
        profile,_=self._scope(client,root)
        if type(after) is not str or len(after)>1024: raise ValueError("INVALID_CURSOR")
        with database(self.directory,'library.sqlite3') as db:
            if db.execute("SELECT fingerprint FROM binding").fetchone()[0]!=self.binding: raise ValueError("LIBRARY_BINDING_CHANGED")
            rows=db.execute("SELECT path,sha,present,seen_at FROM files WHERE profile=? AND root=? AND path>? ORDER BY path LIMIT 51",(profile,root,after)).fetchall()
            scan=db.execute("SELECT completed_at,files FROM scans WHERE profile=? AND root=?",(profile,root)).fetchone()
        return {"entries":[dict(r) for r in rows[:50]],"next_after":rows[49]['path'] if len(rows)>50 else None,"last_scan":dict(scan) if scan else None,"memory_written":False}

def main(argv=None):
    p=argparse.ArgumentParser(description='Bibliothèque Eidolon : aperçu ou synchronisation explicite, sans écriture Memory')
    p.add_argument('--config',required=True);p.add_argument('--directory',required=True)
    p.add_argument('--client',required=True);p.add_argument('--root',required=True)
    p.add_argument('--sync',action='store_true');p.add_argument('--watch',action='store_true')
    p.add_argument('--interval',type=int,default=300)
    a=p.parse_args(argv)
    if a.watch and not a.sync or not 60<=a.interval<=86400: p.error('watch exige sync ; intervalle entre 60 et 86400 secondes')
    stop=threading.Event()
    for sig in (signal.SIGINT,signal.SIGTERM): signal.signal(sig,lambda *_:stop.set())
    try:
        library=Library(configuration(a.config),a.directory)
        while True:
            try:
                value=library.scan(a.client,a.root,stopped=stop) if a.sync else library.page(a.client,a.root)
                print(json.dumps(value,ensure_ascii=False),flush=True);code=0
            except (OSError,ValueError,sqlite3.Error) as exc:
                print(json.dumps({'state':'SCAN_REFUSED_OLD_GENERATION_PRESERVED','error':type(exc).__name__}),flush=True);code=2
            if not a.watch or stop.wait(a.interval): return code
    except (OSError,ValueError,sqlite3.Error): print('{"state":"CONFIGURATION_REFUSED"}');return 2

if __name__=='__main__': raise SystemExit(main())
