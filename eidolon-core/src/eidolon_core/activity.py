# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : activity.py
# Description : Live Core activity receipts for conservative host maintenance
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""One exporter per private directory. Restart starts a new idle waiting period.

All busy requests count as active until completion; an alive idle server refreshes
observation time without changing last user activity. A stopped exporter leaves
stale evidence, which the maintenance collector refuses. This observes Core,
not keyboard activity in unrelated applications on the PC.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import stat
import threading
import uuid
from .runtime_json import _open_directory


class Activity:
    def __init__(self, directory, source, *, clock=None, interval=10):
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.directory, self.source = Path(directory), source
        self.fd = _open_directory(str(self.directory))
        info = os.fstat(self.fd)
        if info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o700:
            os.close(self.fd)
            raise ValueError("private activity directory required")
        try:
            self.lease = os.open("activity.lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK,
                                 0o600, dir_fd=self.fd)
            info = os.fstat(self.lease)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_mode & 0o077:
                raise ValueError("invalid activity lock")
            fcntl.flock(self.lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BaseException:
            if hasattr(self, "lease"):
                os.close(self.lease)
            os.close(self.fd)
            raise
        self.lock, self.stop = threading.RLock(), threading.Event()
        self.last, self.busy, self.closed = self.clock(), 0, False
        self.flush()
        self.thread = threading.Thread(target=self._run, args=(interval,), daemon=True)
        self.thread.start()

    def touch(self):
        with self.lock:
            self.last = self.clock()
            self.flush()

    @contextmanager
    def request(self):
        with self.lock:
            self.busy += 1
            self.touch()
        try:
            yield
        finally:
            with self.lock:
                self.busy -= 1
                self.touch()

    def flush(self):
        with self.lock:
            now = self.clock()
            if self.busy or now < self.last:
                self.last = now
            receipt = {"schema": "eidolon-activity-receipt/1", "source": self.source,
                       "observed_at": now.isoformat(), "last_activity": self.last.isoformat()}
            if self.closed:
                return receipt
            name = ".activity-" + uuid.uuid4().hex
            fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600, dir_fd=self.fd)
            try:
                with os.fdopen(fd, "wb") as output:
                    output.write(json.dumps(receipt).encode())
                    output.flush()
                    os.fsync(output.fileno())
                os.replace(name, "activity.json", src_dir_fd=self.fd, dst_dir_fd=self.fd)
                os.fsync(self.fd)
            finally:
                try:
                    os.unlink(name, dir_fd=self.fd)
                except FileNotFoundError:
                    pass
            return receipt

    def _run(self, interval):
        while not self.stop.wait(interval):
            try:
                self.flush()
            except OSError:
                # No false fresh evidence on export failure.
                pass

    def close(self):
        self.stop.set()
        self.thread.join(timeout=2)
        if self.thread.is_alive():
            return  # keep descriptors valid until process teardown
        with self.lock:
            if not self.closed:
                self.closed = True
                os.close(self.lease)
                os.close(self.fd)


def read_remote(port, token_file):
    """Read Core activity over an operator-provisioned loopback SSH forward.

    Read credential only; this endpoint does not count its own poll as activity.
    No retry or stale cache. The host collector checks source and timestamps.
    """
    import http.client
    from .bridge_credentials import read_bridge_token
    if type(port) is not int or not 1024 <= port <= 65535:
        raise ValueError("invalid Core activity port")
    token = read_bridge_token(token_file)
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
    try:
        connection.request("GET", "/v1/activity", headers={"Authorization": "Bearer " + token})
        response = connection.getresponse()
        if response.status != 200:
            raise ValueError("activity unavailable")
        raw = response.read(4097)
        if len(raw) > 4096:
            raise ValueError("activity response too large")
        return json.loads(raw)
    finally:
        connection.close()
