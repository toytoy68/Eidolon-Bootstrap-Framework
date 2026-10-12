# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : darme_machine.py
# Description : Mesures locales bornees sans inspection des processus
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
import os
from pathlib import Path
import shutil
import time
from datetime import datetime, timezone

class MachineMetrics:
    def __init__(self, directory, *, proc='/proc', clock=time.monotonic):
        self.directory, self.proc, self.clock = directory, Path(proc), clock
        self.previous = None

    def sample(self):
        result = {'schema': 'eidolon-machine/1', 'cpu_percent': None,
                  'sampled_at': datetime.now(timezone.utc).isoformat(),
                  'cpu_count': os.cpu_count(), 'load_1_5_15': None,
                  'memory': None, 'swap': None, 'disk': None,
                  'gpu': None, 'errors': []}
        try:
            fields = (self.proc / 'stat').read_text()[:65536].splitlines()[0].split()
            if fields[0] != 'cpu' or len(fields) < 9:
                raise ValueError('invalid cpu counters')
            # guest counters are included in user/nice already; do not count twice.
            values = [int(value) for value in fields[1:9]]
            if any(value < 0 for value in values):
                raise ValueError('invalid cpu counters')
            total, idle = sum(values), values[3] + values[4]
            now = self.clock()
            if self.previous:
                old_total, old_idle, old_time = self.previous
                delta, inactive = total-old_total, idle-old_idle
                if now > old_time and delta > 0 and 0 <= inactive <= delta:
                    result['cpu_percent'] = round(100 * (delta-inactive) / delta, 2)
            self.previous = total, idle, now
        except (OSError, ValueError, IndexError):
            self.previous = None
            result['errors'].append('cpu_unavailable')
        try:
            result['load_1_5_15'] = list(os.getloadavg())
        except OSError:
            result['errors'].append('load_unavailable')
        try:
            fields = {}
            for line in (self.proc / 'meminfo').read_text()[:65536].splitlines():
                key, value = line.split(':', 1)
                parts = value.split()
                if parts and parts[-1] == 'kB':
                    fields[key] = int(parts[0]) * 1024
            total, available = fields['MemTotal'], fields['MemAvailable']
            swap, free_swap = fields['SwapTotal'], fields['SwapFree']
            if not 0 <= available <= total or not 0 <= free_swap <= swap or total <= 0:
                raise ValueError('invalid memory counters')
            result['memory'] = {'total_bytes': total, 'available_bytes': available,
                                'used_bytes': total-available}
            result['swap'] = {'total_bytes': swap, 'free_bytes': free_swap,
                              'used_bytes': swap-free_swap}
        except (OSError, ValueError, KeyError):
            result['errors'].append('memory_unavailable')
        try:
            disk = shutil.disk_usage(self.directory)
            result['disk'] = {'scope': 'journal_filesystem', 'total_bytes': disk.total,
                              'used_bytes': disk.used, 'free_bytes': disk.free}
        except OSError:
            result['errors'].append('disk_unavailable')
        return result
