# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : monitor_tools.py
# Description : Outils de lecture du statut local DARME et de la machine
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Explicit opt-in registry; no change to default mission permissions."""
from datetime import datetime, timezone
import hashlib
import json
import math
import pwd
import socket
import struct
import time

from .darme import _instant

class MonitorUnavailable(RuntimeError):
    pass

def validate_status(value, *, now=None):
    if (not isinstance(value, dict) or value.get('service_schema') != 'eidolon-darme-service/1'
            or value.get('authorizes_execution') is not False or value.get('enforcement_enabled') is not False
            or value.get('badge') not in ('grey','gold','red','blue')
            or value.get('visibility') not in ('partial','complete') or 'events' in value):
        raise ValueError('invalid monitoring snapshot')
    machine=value.get('machine')
    if not isinstance(machine,dict) or machine.get('schema') != 'eidolon-machine/1':
        raise ValueError('machine metrics unavailable')
    instant=now or datetime.now(timezone.utc)
    if not -5 <= (instant-_instant(machine['sampled_at'])).total_seconds() <= 60:
        raise ValueError('machine metrics stale')
    cpu=machine.get('cpu_percent')
    if cpu is not None and (type(cpu) not in (int,float) or not math.isfinite(cpu) or not 0 <= cpu <= 100):
        raise ValueError('invalid CPU value')
    if type(machine.get('cpu_count')) is not int or not 1 <= machine['cpu_count'] <= 4096:
        raise ValueError('invalid CPU count')
    load=machine.get('load_1_5_15')
    if load is not None and (not isinstance(load,list) or len(load)!=3
            or any(type(x) not in (int,float) or not math.isfinite(x) or x<0 for x in load)):
        raise ValueError('invalid load')
    for name,fields in (('memory',('total_bytes','available_bytes','used_bytes')),
                        ('swap',('total_bytes','free_bytes','used_bytes')),
                        ('disk',('total_bytes','free_bytes','used_bytes'))):
        item=machine.get(name)
        if item is None:
            continue
        if (not isinstance(item,dict) or any(type(item.get(f)) is not int or item[f]<0 for f in fields)
                or item[fields[1]]+item[fields[2]]>item['total_bytes']):
            raise ValueError('invalid byte counters')
    return value

def read_status():
    try:
        expected=pwd.getpwnam('eidolon-darme').pw_uid
        deadline=time.monotonic()+2
        with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as connection:
            connection.settimeout(2)
            connection.connect('/run/eidolon-darme/status.sock')
            pid,uid,gid=struct.unpack('3i',connection.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12))
            if uid != expected:
                raise ValueError('unexpected monitoring peer')
            connection.sendall(b'STATUS\n')
            raw=b''
            while not raw.endswith(b'\n'):
                remaining=deadline-time.monotonic()
                if remaining <= 0:
                    raise OSError('monitoring deadline exceeded')
                connection.settimeout(remaining)
                part=connection.recv(min(4096,32769-len(raw)))
                if not part:
                    raise ValueError('truncated monitoring response')
                raw+=part
                if len(raw)>32768:
                    raise ValueError('monitoring response too large')
            return validate_status(json.loads(raw))
    except (OSError, ValueError, KeyError, TypeError, struct.error) as exc:
        raise MonitorUnavailable('local monitoring unavailable') from exc

def validate_parameters(parameters,context):
    if not isinstance(parameters,dict) or parameters:
        raise ValueError('monitoring accepts no parameters')

def execute_machine(parameters,context):
    validate_parameters(parameters,context)
    value=read_status()
    return evidence(value)

def evidence(value):
    encoded=json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
    return {'snapshot':value,'sha256':hashlib.sha256(encoded).hexdigest(),
            'authorizes_execution':False,'scope':'local_vm_only'}

def verify_evidence(parameters,context,result):
    # Recheck existing evidence only: no second probe and no execution retry.
    try:
        validate_parameters(parameters,context)
        if not isinstance(result,dict) or set(result)!= {'snapshot','sha256','authorizes_execution','scope'}:
            return False
        validate_status(result['snapshot'])
        return result==evidence(result['snapshot'])
    except (ValueError,KeyError,TypeError):
        return False

def monitoring_registry():
    from .tools import Registry, Tool, default_registry
    original=default_registry()
    tools=[original.get(name) for name in original.manifest()]
    for name in ('monitor.machine','monitor.darme'):
        tools.append(Tool(name,'1','none',validate_parameters,execute_machine,verify_evidence,
                          'local-monitor-snapshot/1'))
    return Registry(tools)

def monitoring_policy():
    from .tools import Policy
    return Policy(allowed_tools=('text.stats','monitor.machine','monitor.darme'),
                  policy_id='local-readonly-monitoring/1')

if __name__ == '__main__':
    print(json.dumps(read_status(),sort_keys=True,allow_nan=False))
