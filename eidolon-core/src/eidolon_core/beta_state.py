# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : beta_state.py
# Description : Copie hors ligne vérifiée des reçus, quotas et gabarits privés
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Copy a stopped profile-services database into a NEW private directory.

Dry-run by default. Only state_directory and identity_config may change; client,
profile, Memory and file permissions cannot be reassigned by this tool. Source
stays byte-identical. Existing destinations are never replaced. Not a backup of
Core conversations, pairing credentials, Memory corpus, secrets or model files.
"""
import argparse
from contextlib import contextmanager, closing
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import stat
import time
import uuid

from .beta_runtime import validate_config
from .contracts import digest
from .runtime_json import read_json_snapshot, _open_directory


class StateError(ValueError):
    pass


def require(value, code):
    if not value: raise StateError(code)


def configuration(filename):
    p = Path(filename).absolute()
    fd = _open_directory(str(p.parent))
    try:
        s = os.stat(p.name,dir_fd=fd,follow_symlinks=False)
        require(stat.S_ISREG(s.st_mode) and s.st_uid == os.geteuid() and stat.S_IMODE(s.st_mode) == 0o600 and s.st_nlink == 1,
                "CONFIG_PRIVATE_REQUIRED")
    finally: os.close(fd)
    return validate_config(read_json_snapshot(str(p.parent),p.name,max_bytes=65536,max_depth=6))


@contextmanager
def private_directory(path):
    fd = _open_directory(path)
    try:
        s = os.fstat(fd)
        require(s.st_uid == os.geteuid() and stat.S_IMODE(s.st_mode) == 0o700,"DIRECTORY_PRIVATE_REQUIRED")
        yield fd
    finally: os.close(fd)


def private_file(directory, name, flags=os.O_RDONLY):
    fd = os.open(name, flags | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, dir_fd=directory)
    s = os.fstat(fd)
    if not (stat.S_ISREG(s.st_mode) and s.st_uid == os.geteuid() and stat.S_IMODE(s.st_mode) == 0o600 and s.st_nlink == 1):
        os.close(fd); raise StateError("FILE_PRIVATE_REQUIRED")
    return fd


def file_hash(fd):
    os.lseek(fd,0,os.SEEK_SET); h=hashlib.sha256()
    while True:
        data=os.read(fd,65536)
        if not data: break
        h.update(data)
    return h.hexdigest()


def copy_state(old_filename, new_filename, *, apply=False):
    old, new = configuration(old_filename), configuration(new_filename)
    stable = lambda c: {k:v for k,v in c.items() if k not in ("state_directory","identity_config")}
    require(stable(old)==stable(new),"PROFILE_OR_PERMISSION_REBIND_REFUSED")
    require(old["state_directory"]!=new["state_directory"],"NEW_DIRECTORY_REQUIRED")
    with private_directory(old["state_directory"]) as src, private_directory(new["state_directory"]) as dst:
        require((os.fstat(src).st_dev,os.fstat(src).st_ino)!=(os.fstat(dst).st_dev,os.fstat(dst).st_ino),"NEW_DIRECTORY_REQUIRED")
        require(not os.listdir(dst),"DESTINATION_NOT_EMPTY")
        lease=private_file(src,"activity.lock")
        try:
            try: fcntl.flock(lease,fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError: raise StateError("STOP_CORE_BEFORE_COPY") from None
            for name in ("actions.sqlite3-journal","actions.sqlite3-wal","actions.sqlite3-shm"):
                try: os.stat(name,dir_fd=src,follow_symlinks=False)
                except FileNotFoundError: continue
                raise StateError("SQLITE_RECOVERY_REQUIRED")
            source=private_file(src,"actions.sqlite3")
            try:
                before=os.fstat(source)
                require(before.st_size<=256*1024*1024,"STATE_SIZE_LIMIT")
                source_hash=file_hash(source)
                with closing(sqlite3.connect(f"file:/proc/self/fd/{source}?mode=ro&immutable=1",uri=True)) as db:
                    db.execute("PRAGMA trusted_schema=OFF")
                    deadline=time.monotonic()+30
                    db.set_progress_handler(lambda: int(time.monotonic()>deadline),10000)
                    require(db.execute("PRAGMA quick_check").fetchall()==[("ok",)],"SOURCE_INTEGRITY_FAILED")
                    require(db.execute("SELECT fingerprint FROM binding WHERE id=1").fetchone()==(digest(old),),"SOURCE_BINDING_MISMATCH")
                    counts={name:db.execute("SELECT count(*) FROM "+name).fetchone()[0] for name in ("actions","turn_sources")}
                    report={"schema":"eidolon-beta-state-copy/1","state":"PREVIEW","rows":counts,
                            "source_unchanged":True,"beta_authorized":False,"includes_credentials":False}
                    if not apply: return report
                    # Exclude a concurrent Core startup against the new directory.
                    target_lease=os.open("activity.lock",os.O_RDWR|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=dst)
                    temporary=".copy-"+uuid.uuid4().hex+".sqlite3"
                    target_fd=None
                    try:
                        fcntl.flock(target_lease,fcntl.LOCK_EX|fcntl.LOCK_NB)
                        require(os.listdir(dst)==["activity.lock"],"DESTINATION_CHANGED")
                        target_fd=os.open(temporary,os.O_RDWR|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=dst)
                        with closing(sqlite3.connect(f"/proc/self/fd/{dst}/{temporary}")) as target:
                            def progress(*_):
                                require(time.monotonic()<=deadline,"STATE_COPY_TIMEOUT")
                            db.backup(target,pages=128,progress=progress)
                            target.execute("PRAGMA secure_delete=ON")
                            with target:
                                target.execute("UPDATE binding SET fingerprint=? WHERE id=1",(digest(new),))
                                target.execute("UPDATE actions SET state='UNKNOWN' WHERE state='INFLIGHT'")
                                tables={r[0] for r in target.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                                if "identity_sessions" in tables:
                                    target.execute("UPDATE identity_sessions SET samples='[]',status='EXPIRED' WHERE status='COLLECTING'")
                            require(target.execute("PRAGMA quick_check").fetchall()==[("ok",)],"COPY_INTEGRITY_FAILED")
                            require(all(target.execute("SELECT count(*) FROM "+name).fetchone()[0]==count for name,count in counts.items()),"COPY_ROWS_MISMATCH")
                        require(file_hash(source)==source_hash and os.fstat(source).st_ino==before.st_ino,"SOURCE_CHANGED")
                        now=os.stat("actions.sqlite3",dir_fd=src,follow_symlinks=False)
                        require((now.st_dev,now.st_ino)==(before.st_dev,before.st_ino),"SOURCE_CHANGED")
                        os.fsync(target_fd)
                        # No replacement, even if another process created a destination meanwhile.
                        os.link(temporary,"actions.sqlite3",src_dir_fd=dst,dst_dir_fd=dst,follow_symlinks=False)
                        os.unlink(temporary,dir_fd=dst);os.fsync(dst)
                        report.update(state="COPIED_REVIEW_REQUIRED",source_sha256=source_hash,copy_sha256=file_hash(target_fd),
                                      config_sha256=digest(new),created_at=datetime.now(timezone.utc).isoformat())
                        manifest=os.open("state-copy.json",os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=dst)
                        with os.fdopen(manifest,"w") as out:
                            json.dump(report,out,sort_keys=True);out.write("\n");out.flush();os.fsync(out.fileno())
                        os.fsync(dst)
                        return report
                    finally:
                        if target_fd is not None: os.close(target_fd)
                        os.close(target_lease)
                        # Preserve partial files after failure for inspection; never clean an uncertain copy.
            finally: os.close(source)
        finally: os.close(lease)


def main(argv=None):
    from .presentation import header, message
    parser=argparse.ArgumentParser(description="Copie hors ligne des services de profils — aperçu par défaut",allow_abbrev=False)
    parser.add_argument("--config",required=True)
    parser.add_argument("--new-config",required=True)
    parser.add_argument("--apply",action="store_true")
    parser.add_argument("--format",choices=("json","human"),default="json")
    args=parser.parse_args(argv)
    try:
        report=copy_state(args.config,args.new_config,apply=args.apply);code=0
    except (ValueError,OSError,sqlite3.Error):
        # Do not expose private paths, identities, source text or SQLite values.
        report={"schema":"eidolon-beta-state-copy/1","state":"REFUSED_OR_INCOMPLETE",
                "beta_authorized":False,"review_destination":args.apply};code=2
    if args.format=="json": print(json.dumps(report,sort_keys=True))
    else:
        print(header(title="Copie privée hors ligne"))
        print(message("INFO" if code==0 else "ERREUR",report["state"]))
        print(message("ATTENTION","Copie distincte ; aucun service activé. Les corpus, secrets et conversations se sauvegardent séparément."))
    return code


if __name__=="__main__": raise SystemExit(main())
