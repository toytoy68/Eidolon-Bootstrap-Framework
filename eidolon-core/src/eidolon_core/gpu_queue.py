# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : gpu_queue.py
# Description : Services hors VM G273, configuration opérateur explicite
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Durable cooperative admission, explicit estimated budgets, no GPU claims.

One logical device pool, no summing VRAM across GPUs. Active/uncertain reservations
survive process death; only exact completion or reviewed release frees capacity.
"""
import argparse
from datetime import datetime, timezone
import json
import re
import sqlite3
import time
import threading
import uuid
from .contracts import digest, ContractError
from .offline_state import database

class Queue:
    def __init__(self, config, *, clock=time.time):
        fields={'schema','directory','capacity_mib','resident_mib','dialogue_mib','media_mib'}
        if type(config) is not dict or set(config)!=fields or config['schema']!='eidolon-gpu-queue/1': raise ValueError('INVALID_GPU_CONFIG')
        from pathlib import Path
        if type(config['directory']) is not str or not Path(config['directory']).is_absolute(): raise ValueError('INVALID_GPU_DIRECTORY')
        for k in fields-{'schema','directory'}:
            if type(config[k]) is not int or not 0<=config[k]<=1048576: raise ValueError('INVALID_GPU_BUDGET')
        if not 0<=config['resident_mib']<config['capacity_mib'] or any(not 0<config[k]<=config['capacity_mib']-config['resident_mib'] for k in ('dialogue_mib','media_mib')): raise ValueError('INVALID_GPU_BUDGET')
        self.config,self.clock=json.loads(json.dumps(config)),clock
        self._pending=set();self._pending_lock=threading.Lock();self._closing=threading.Event()
        with self.db(True) as db:
            db.execute('CREATE TABLE IF NOT EXISTS binding (sha TEXT)')
            row=db.execute('SELECT sha FROM binding').fetchone()
            if row and row[0]!=digest(config): raise ValueError('GPU_CONFIG_CHANGED')
            if not row: db.execute('INSERT INTO binding VALUES (?)',(digest(config),))
            db.execute('CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, kind TEXT, mib INTEGER, created REAL, state TEXT, lease TEXT, ended REAL)')

    def db(self,write=False): return database(self.config['directory'],'gpu-queue.sqlite3',write=write)

    def enqueue(self, key, kind):
        if type(key) is not str or not re.fullmatch('[A-Za-z0-9_-]{1,100}',key) or kind not in ('dialogue','media'): raise ValueError('INVALID_GPU_REQUEST')
        with self.db(True) as db:
            row=db.execute('SELECT * FROM jobs WHERE id=?',(key,)).fetchone()
            if row:
                if row['kind']!=kind: raise ValueError('GPU_KEY_REUSED')
                return dict(row)
            if db.execute('SELECT count(*) FROM jobs').fetchone()[0]>=10000 or db.execute("SELECT count(*) FROM jobs WHERE state='WAITING'").fetchone()[0]>=1000: raise ValueError('GPU_QUEUE_FULL')
            db.execute("INSERT INTO jobs VALUES (?,?,?,?,'WAITING',NULL,NULL)",(key,kind,self.config[kind+'_mib'],self.clock()))
            return dict(db.execute('SELECT * FROM jobs WHERE id=?',(key,)).fetchone())

    def acquire(self, key):
        now=self.clock()
        with self.db(True) as db:
            own=db.execute('SELECT * FROM jobs WHERE id=?',(key,)).fetchone()
            if own is None: raise ValueError('GPU_JOB_UNKNOWN')
            if own['state']!='WAITING': return dict(own)
            waiting=db.execute("SELECT * FROM jobs WHERE state='WAITING'").fetchall()
            # Aging eventually beats new dialogue requests. FIFO for equal priorities.
            first=min(waiting,key=lambda r:(-((100 if r['kind']=='dialogue' else 10)+max(0,int((now-r['created'])//30))),r['created'],r['id']))
            used=db.execute("SELECT coalesce(sum(mib),0) FROM jobs WHERE state IN ('ACTIVE','UNKNOWN')").fetchone()[0]
            if first['id']==key and used+own['mib']<=self.config['capacity_mib']-self.config['resident_mib']:
                db.execute("UPDATE jobs SET state='ACTIVE',lease=? WHERE id=?",(uuid.uuid4().hex,key))
            return dict(db.execute('SELECT * FROM jobs WHERE id=?',(key,)).fetchone())

    def finish(self,key,lease,*,uncertain=False,reviewed=False):
        with self.db(True) as db:
            row=db.execute('SELECT * FROM jobs WHERE id=?',(key,)).fetchone()
            if row is None or not lease or row['lease']!=lease or row['state'] not in ('ACTIVE','UNKNOWN'): raise ValueError('GPU_LEASE_MISMATCH')
            if row['state']=='UNKNOWN' and not reviewed and not uncertain: raise ValueError('GPU_REVIEW_REQUIRED')
            db.execute('UPDATE jobs SET state=?,ended=? WHERE id=?',('UNKNOWN' if uncertain else 'DONE',None if uncertain else self.clock(),key))

    def cancel_waiting(self,key):
        with self.db(True) as db:
            if db.execute("UPDATE jobs SET state='CANCELLED',ended=? WHERE id=? AND state='WAITING'",(self.clock(),key)).rowcount!=1: raise ValueError('GPU_NOT_WAITING')

    def inspect(self):
        with self.db() as db:
            rows=[dict(r) for r in db.execute("SELECT * FROM jobs WHERE state IN ('WAITING','ACTIVE','UNKNOWN') ORDER BY created,id LIMIT 1001")]
            counts={r[0]:r[1] for r in db.execute("SELECT state,count(*) FROM jobs WHERE state IN ('WAITING','ACTIVE','UNKNOWN') GROUP BY state")}
            reserved=db.execute("SELECT coalesce(sum(mib),0) FROM jobs WHERE state IN ('ACTIVE','UNKNOWN')").fetchone()[0]
        return {'schema':'eidolon-gpu-queue-report/1','jobs':rows[:1000],'jobs_truncated':len(rows)>1000,
                'counts':{s:counts.get(s,0) for s in ('WAITING','ACTIVE','UNKNOWN')},
                'reserved_mib':reserved,'available_mib':self.config['capacity_mib']-self.config['resident_mib']-reserved,
                'review_required':bool(counts),'live_owners_checked':False,'capacity_mib':self.config['capacity_mib'],'resident_mib':self.config['resident_mib'],'hardware_measured':False,'preemption':False,'automatic_expiry':False}

    def _withdraw(self,key):
        return self._withdraw_many((key,))

    def _withdraw_many(self,keys):
        """Best effort: cancel only still-WAITING requests, never admitted ones."""
        if not keys: return True
        for attempt in range(3):
            try:
                with self.db(True) as db:
                    db.execute("UPDATE jobs SET state='CANCELLED',ended=? WHERE id IN ("+",".join("?" for _ in keys)+") AND state='WAITING'",(self.clock(),*keys))
                return True
            except (sqlite3.Error, OSError, ValueError):
                if attempt<2: time.sleep(.5)
        return False

    def close(self):
        """Drain this process's pending admissions only; preserve inherited/active jobs."""
        with self._pending_lock:
            self._closing.set()
            keys=tuple(self._pending)
        return self._withdraw_many(keys)

    def wait(self,key,kind,seconds=30,stopped=None):
        with self._pending_lock:
            if self._closing.is_set(): raise ContractError("GPU_ADMISSION_CANCELLED: queue closing")
            self.enqueue(key,kind)
            self._pending.add(key)
        deadline=time.monotonic()+seconds
        # G274-F003: any exit without a lease (stop, timeout, SQLite busy, error)
        # withdraws the request; an orphan WAITING head would block every later turn.
        try:
            while True:
                if self._closing.is_set() or stopped is not None and stopped.is_set():
                    raise ContractError("GPU_ADMISSION_CANCELLED: no engine started")
                row=self.acquire(key)
                if row['state']=='ACTIVE': return row['lease']
                if row['state']!='WAITING': raise ValueError('GPU_JOB_NOT_WAITING')
                if time.monotonic()>=deadline:
                    raise ContractError('GPU_ADMISSION_TIMEOUT: no engine started')
                time.sleep(min(.05,max(0,deadline-time.monotonic())))
        except BaseException as exc:
            if not self._withdraw(key):
                exc.add_note("GPU_WAITING_REVIEW_REQUIRED: withdrawal could not be confirmed")
            raise
        finally:
            with self._pending_lock: self._pending.discard(key)


def load(filename):
    from pathlib import Path
    from .runtime_json import read_json_snapshot
    p=Path(filename).absolute()
    return Queue(read_json_snapshot(str(p.parent),p.name,max_bytes=8192,max_depth=3))

class ScheduledModel:
    """Synchronous reply wrapper; exceptions retain the reservation for review."""
    def __init__(self,model,queue,*,stopped=None,seconds=30):
        self.model,self.queue,self.stopped,self.seconds=model,queue,stopped,seconds
    @property
    def model_id(self): return getattr(self.model,'model_id',None)
    @property
    def adapter(self): return getattr(self.model,'adapter',None)
    def reply(self,*args,**kwargs):
        key='dialogue-'+uuid.uuid4().hex;lease=self.queue.wait(key,'dialogue',seconds=self.seconds,stopped=self.stopped)
        if self.stopped is not None and self.stopped.is_set():
            self.queue.finish(key,lease);raise ContractError('GPU_ADMISSION_CANCELLED: no engine started')
        try: answer=self.model.reply(*args,**kwargs)
        except BaseException:
            self.queue.finish(key,lease,uncertain=True);raise
        self.queue.finish(key,lease)
        return answer


def main(argv=None):
    p=argparse.ArgumentParser(description='File GPU coopérative Eidolon, budgets déclarés')
    p.add_argument('--config',required=True);sub=p.add_subparsers(dest='command',required=True)
    sub.add_parser('status')
    q=sub.add_parser('enqueue');q.add_argument('--key',required=True);q.add_argument('--kind',choices=('dialogue','media'),required=True)
    q=sub.add_parser('acquire');q.add_argument('--key',required=True)
    q=sub.add_parser('cancel-waiting');q.add_argument('--key',required=True)
    q=sub.add_parser('release');q.add_argument('--key',required=True);q.add_argument('--lease',required=True);q.add_argument('--engine-idle-reviewed',required=True,action='store_true')
    a=p.parse_args(argv)
    try:
        queue=load(a.config)
        if a.command=='enqueue': result=queue.enqueue(a.key,a.kind)
        elif a.command=='acquire': result=queue.acquire(a.key)
        elif a.command=='cancel-waiting': queue.cancel_waiting(a.key);result={'state':'CANCELLED_BEFORE_ADMISSION'}
        elif a.command=='release': queue.finish(a.key,a.lease,reviewed=a.engine_idle_reviewed);result={'state':'RELEASED_BY_OPERATOR','engine_idle_measured':False}
        else: result=queue.inspect()
        print(json.dumps(result));return 0
    except (OSError,ValueError,sqlite3.Error,ContractError): print('{"state":"GPU_QUEUE_REFUSED"}');return 2

if __name__=='__main__': raise SystemExit(main())
