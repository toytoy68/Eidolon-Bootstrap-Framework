# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : darme_service.py
# Description : Collecte locale passive et statut via socket prive
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Trusted in-process probes only. No ingestion, acknowledgement or execution API."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import time
from datetime import datetime, timezone

from .darme import DarmeMonitor, SecurityEvent, Severity
from .darme_store import DarmeJournal
from .darme_machine import MachineMetrics

ALLOWED_UNITS = frozenset(('eidolon-core-api.service', 'eidolon-gpu-tunnel.service',
                          'eidolon-memory-tunnel.service', 'eidolon-memory-bridge.service',
                          'eidolon-collaboration.service', 'eidolon-darme-ssh.service'))

def validate_config(data):
    if not isinstance(data, dict) or set(data) not in ({'units', 'interval'}, {'units', 'interval', 'ssh_feed'}):
        raise ValueError('invalid configuration')
    units = data['units']
    if (not isinstance(units, list) or not units or len(set(units)) != len(units)
            or any(unit not in ALLOWED_UNITS for unit in units)):
        raise ValueError('invalid unit allowlist')
    if type(data['interval']) is not int or not 5 <= data['interval'] <= 30:
        raise ValueError('invalid polling interval')
    if 'ssh_feed' in data and type(data['ssh_feed']) is not bool:
        raise ValueError('invalid SSH feed setting')
    return data

def probe(unit):
    result = subprocess.run(['/usr/bin/systemctl', 'is-active', unit],
                            capture_output=True, timeout=3,
                            env={'PATH': '/usr/bin:/bin', 'LANG': 'C'})
    state = result.stdout[:64].decode('ascii', 'replace').strip()
    if state not in {'active', 'inactive', 'failed', 'activating', 'deactivating', 'reloading'}:
        raise ValueError('unavailable service probe')
    return state == 'active'

class Collector:
    def __init__(self, journal, units, directory, service_probe=probe, disk_probe=shutil.disk_usage,
                 *, ssh_feed=False):
        self.journal, self.units, self.directory = journal, units, directory
        self.service_probe, self.disk_probe = service_probe, disk_probe
        self.previous = {}
        self.sources = list(units) + ['journal-disk', 'security-telemetry']
        self.feed = None
        if ssh_feed:
            from .darme_ssh import FeedVerifier
            self.sources.append('ssh-auth')
            self.feed = FeedVerifier('/etc/eidolon-darme/ssh-public.raw', Path(directory)/'ssh-receiver.json')
        self.metrics = MachineMetrics(directory)
        self.machine = None
        self.feed_healthy = False
        self.error = False
        # Replay before serving: corruption must fail startup, never show healthy.
        historical = journal.replay(DarmeMonitor(self.sources))
        for identity, event in historical.events.items():
            if event.category == 'local_availability' and identity not in historical.acknowledged:
                self.previous[event.source] = False

    def sample(self):
        health = {}
        self.error = False
        self.machine = self.metrics.sample()
        self.feed_healthy = False
        if self.feed:
            from .darme_ssh import read_bounded
            try:
                payload, events, digest = self.feed.verify(read_bounded('/run/eidolon-darme-ssh/feed.json'))
                for event in events:
                    self.journal.record(event)
                self.feed.commit(payload, digest)
                self.feed_healthy = payload['healthy']
            except (OSError, ValueError, OverflowError) as exc:
                self.feed_healthy = False
                self.error = isinstance(exc, OverflowError)
        for unit in self.units:
            try:
                healthy = self.service_probe(unit)
                if type(healthy) is not bool:
                    raise ValueError('invalid probe result')
                health[unit] = healthy
            except (OSError, ValueError, subprocess.SubprocessError):
                health[unit] = False
        try:
            usage = self.disk_probe(self.directory)
            health['journal-disk'] = usage.free >= 256 * 1024 * 1024 and usage.free / usage.total >= .05
        except (OSError, ZeroDivisionError):
            health['journal-disk'] = False
        for source, healthy in health.items():
            if not healthy and self.previous.get(source) is not False:
                instant = datetime.now(timezone.utc).isoformat()
                identity = hashlib.sha256((source + instant).encode()).hexdigest()
                try:
                    self.journal.record(SecurityEvent(identity, source, 'local_availability',
                                                      Severity.WARNING, instant, source))
                except (OSError, ValueError, OverflowError):
                    self.error = True
                    continue  # Retry admission on the next sample; never claim collection complete.
            self.previous[source] = healthy
        monitor = self.journal.replay(DarmeMonitor(self.sources))
        for source, healthy in health.items():
            monitor.health(source, healthy)
        if self.feed:
            monitor.health('ssh-auth', self.feed_healthy)
        monitor.ingestion_paused |= self.error
        self.monitor = monitor

    def status(self):
        result = self.monitor.snapshot()
        result.pop('events')  # Read endpoint never discloses raw event subjects.
        result.update(service_schema='eidolon-darme-service/1',
                      scope='local_service_availability_and_journal_disk',
                      security_telemetry_installed=False, advisor='fixed',
                      generated_at=datetime.now(timezone.utc).isoformat(),
                      machine=self.machine, ssh_auth_monitoring=self.feed is not None,
                      ssh_feed_healthy=self.feed_healthy)
        return result

def serve(config, state, runtime):
    os.umask(0o077)
    units = validate_config(json.loads(Path(config).read_text()))
    journal = DarmeJournal(Path(state) / 'journal.sqlite')
    collector = Collector(journal, units['units'], state, ssh_feed=units.get('ssh_feed', False))
    endpoint = Path(runtime) / 'status.sock'
    # RuntimeDirectory is owned by the dedicated account; refuse unexpected objects.
    if endpoint.exists() or endpoint.is_symlink():
        raise ValueError('existing endpoint refused')
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    running = True
    def stop(signum, frame):
        nonlocal running
        running = False
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        server.bind(str(endpoint))
        os.chmod(endpoint, 0o660)
        server.listen(8)
        server.settimeout(1)
        due = 0
        while running:
            if time.monotonic() >= due:
                collector.sample()
                due = time.monotonic() + units['interval']
            try:
                connection, _ = server.accept()
            except socket.timeout:
                continue
            with connection:
                connection.settimeout(1)
                try:
                    request = connection.recv(65)
                    if request != b'STATUS\n':
                        connection.sendall(b'{"error":"read-only protocol"}\n')
                    else:
                        connection.sendall(json.dumps(collector.status(), sort_keys=True).encode() + b'\n')
                except (OSError, socket.timeout):
                    pass
    finally:
        server.close()
        endpoint.unlink(missing_ok=True)
        journal.close()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', required=True)
    parser.add_argument('--state', required=True)
    parser.add_argument('--runtime', required=True)
    args = parser.parse_args()
    serve(args.config, args.state, args.runtime)

if __name__ == '__main__':
    main()
