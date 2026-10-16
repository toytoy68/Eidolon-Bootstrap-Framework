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
MAX_EXCLUDED_HASH_BYTES = 32 * 1024 * 1024

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
                    elif entry.name.rsplit('.',1)[-1].lower() in documents.FORMATS:
                        raise ValueError("LIBRARY_SPECIAL_REFUSED")
            after=os.fstat(fd)
            if (before.st_ino,before.st_mtime_ns,before.st_ctime_ns)!=(after.st_ino,after.st_mtime_ns,after.st_ctime_ns):
                raise ValueError("LIBRARY_CHANGED")
    visit('',0)
    return sorted(result)

def file_version(root, relative):
    """Metadata for a no-follow regular file, including files too large to read."""
    with profile_files.opened(root, relative) as fd:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ValueError("LIBRARY_LINK_OR_SPECIAL_REFUSED")
        return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def excluded_fingerprint(root, relative, *, expected_size, deadline, stopped=None):
    """Bounded streaming integrity check only; oversized documents are never extracted."""
    with profile_files.opened(root, relative) as fd:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size != expected_size:
            raise ValueError("LIBRARY_CHANGED")
        digest = hashlib.sha256(); count = 0
        while count <= expected_size:
            if time.monotonic() > deadline or stopped and stopped.is_set():
                raise ValueError("LIBRARY_SCAN_INTERRUPTED")
            chunk = os.read(fd, min(1024 * 1024, expected_size + 1 - count))
            if not chunk: break
            count += len(chunk); digest.update(chunk)
        after = os.fstat(fd)
        version = lambda v: (v.st_dev, v.st_ino, v.st_size, v.st_mtime_ns, v.st_ctime_ns, v.st_nlink)
        if count != expected_size or version(before) != version(after):
            raise ValueError("LIBRARY_CHANGED")
        return digest.hexdigest()


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
        db.execute("CREATE TABLE IF NOT EXISTS extraction_errors (profile TEXT, root TEXT, path TEXT, code TEXT, bytes INTEGER, PRIMARY KEY(profile,root,path))")
        db.execute("CREATE TABLE IF NOT EXISTS scans (profile TEXT, root TEXT, completed_at TEXT, files INTEGER, PRIMARY KEY(profile,root))")

    def _scope(self, client, root):
        if type(client) is not str or type(root) is not str: raise ValueError("LIBRARY_SCOPE_REFUSED")
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
        skipped={}; observed={}; errors={}; excluded_hashes={}; excluded_bytes=0
        for relative in names:
            if time.monotonic()>deadline or stopped and stopped.is_set(): raise ValueError("LIBRARY_SCAN_INTERRUPTED")
            # G274-F002: a file above the extraction bound is listed (no hash, no excerpt)
            # instead of aborting the root. Links, changes and budgets still abort.
            observed[relative]=file_version(path,relative);size=observed[relative][2]
            if size>documents.MAX_BYTES:
                error="FILE_TOO_LARGE_CONTENT_UNVERIFIED"
                if size <= MAX_EXCLUDED_HASH_BYTES - excluded_bytes:
                    excluded_hashes[relative]=excluded_fingerprint(path,relative,expected_size=size,deadline=deadline,stopped=stopped)
                    excluded_bytes+=size
                    error="FILE_TOO_LARGE"
                skipped[error]=skipped.get(error,0)+1
                errors[relative]=error
                batch.append((relative,None,size,None));continue
            raw=profile_files.read_bytes(path,relative,max_bytes=documents.MAX_BYTES);total+=len(raw)
            if total>MAX_BYTES: raise ValueError("LIBRARY_SCAN_BUDGET")
            sha=hashlib.sha256(raw).hexdigest()
            # Reuse only this profile's exact content hash, never another person's excerpt.
            excerpt=None
            cache_key=(sha,documents.extension(Path(relative).name))
            if cache_key not in known:
                if cache_key not in cache:
                    try: cache[cache_key]=documents.extract(raw,Path(relative).name)
                    except documents.DocumentError as exc:
                        # Empty, image-only, protected or malformed: present, not extracted,
                        # retried at the next pass (no error is cached as a version).
                        cache[cache_key]=str(exc)
                if type(cache[cache_key]) is str:
                    errors[relative]=cache[cache_key]
                    skipped[cache[cache_key]]=skipped.get(cache[cache_key],0)+1
                    batch.append((relative,sha,len(raw),False));continue
                excerpt=dict(cache[cache_key],name=Path(relative).name)
            batch.append((relative,sha,len(raw),excerpt))
        if inventory(path,deadline=deadline)!=names: raise ValueError("LIBRARY_CHANGED")
        # A second content pass detects changes during extraction (not an atomic filesystem snapshot).
        for relative,sha,size,_ in batch:
            if time.monotonic()>deadline or stopped and stopped.is_set(): raise ValueError("LIBRARY_SCAN_INTERRUPTED")
            if file_version(path,relative)!=observed[relative]: raise ValueError("LIBRARY_CHANGED")
            if sha is None:
                if relative in excluded_hashes and excluded_fingerprint(path,relative,expected_size=size,deadline=deadline,stopped=stopped)!=excluded_hashes[relative]:
                    raise ValueError("LIBRARY_CHANGED")
                continue
            if hashlib.sha256(profile_files.read_bytes(path,relative,max_bytes=documents.MAX_BYTES)).hexdigest()!=sha:
                raise ValueError("LIBRARY_CHANGED")
        now=datetime.now(timezone.utc).isoformat();added=0;duplicates=0
        with database(self.directory,'library.sqlite3',write=True) as db:
            self._schema(db)
            missing=sum(not db.execute("SELECT 1 FROM versions WHERE profile=? AND root=? AND path=? AND sha=?",(profile,root,p,s)).fetchone() for p,s,_,e in batch if s is not None and e is not False)
            if db.execute("SELECT count(*) FROM versions").fetchone()[0]+missing>MAX_VERSIONS: raise ValueError("LIBRARY_STORAGE_BUDGET")
            db.execute("UPDATE files SET present=0 WHERE profile=? AND root=?",(profile,root))
            db.execute("DELETE FROM extraction_errors WHERE profile=? AND root=?",(profile,root))
            for relative,sha,size,excerpt in batch:
                if relative in errors:
                    db.execute("INSERT INTO extraction_errors VALUES (?,?,?,?,?)",(profile,root,relative,errors[relative],size))
                if sha is None or excerpt is False:
                    db.execute("INSERT INTO files VALUES (?,?,?,?,1,?) ON CONFLICT(profile,root,path) DO UPDATE SET sha=excluded.sha,present=1,seen_at=excluded.seen_at",(profile,root,relative,sha,now))
                    continue
                if excerpt is None:
                    row=db.execute("SELECT excerpt FROM versions WHERE profile=? AND sha=? AND json_extract(excerpt,'$.format')=? LIMIT 1",(profile,sha,documents.extension(Path(relative).name))).fetchone()
                    if row is None: raise ValueError("LIBRARY_SOURCE_CHANGED")
                    excerpt=json.loads(row[0]);excerpt['name']=Path(relative).name;duplicates+=1
                added+=db.execute("INSERT OR IGNORE INTO versions VALUES (?,?,?,?,?,?,?)",(profile,root,relative,sha,size,encode(excerpt),now)).rowcount
                db.execute("INSERT INTO files VALUES (?,?,?,?,1,?) ON CONFLICT(profile,root,path) DO UPDATE SET sha=excluded.sha,present=1,seen_at=excluded.seen_at",(profile,root,relative,sha,now))
            db.execute("INSERT INTO scans VALUES (?,?,?,?) ON CONFLICT(profile,root) DO UPDATE SET completed_at=excluded.completed_at,files=excluded.files",(profile,root,now,len(batch)))
        return {"state":"SYNCED_EXCERPTS_ONLY","files":len(batch),"new_versions":added,"reused_excerpts":duplicates,"bytes_read":(total+excluded_bytes)*2,"not_extracted":dict(sorted(skipped.items())),"memory_written":False,"source_deleted":False}

    def page(self, client, root, after=''):
        profile,_=self._scope(client,root)
        if type(after) is not str or len(after)>1024: raise ValueError("INVALID_CURSOR")
        with database(self.directory,'library.sqlite3') as db:
            if db.execute("SELECT fingerprint FROM binding").fetchone()[0]!=self.binding: raise ValueError("LIBRARY_BINDING_CHANGED")
            # Read old G273 state without migrating it; the next explicit scan adds diagnostics.
            has_errors=db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='extraction_errors'").fetchone()
            error_sql="(SELECT code FROM extraction_errors e WHERE e.profile=f.profile AND e.root=f.root AND e.path=f.path)" if has_errors else "NULL"
            rows=db.execute("SELECT path,sha,present,seen_at,"+error_sql+" AS extraction_error, EXISTS(SELECT 1 FROM versions v WHERE v.profile=f.profile AND v.root=f.root AND v.path=f.path AND v.sha=f.sha) AS excerpt_available FROM files f WHERE profile=? AND root=? AND path>? ORDER BY path LIMIT 51",(profile,root,after)).fetchall()
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
