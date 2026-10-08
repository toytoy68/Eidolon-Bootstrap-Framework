# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : g070-environment.py
# Description : Instrumentation du prédicat alive de G070, assertions originales conservées
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
import json
import os
from pathlib import Path
import runpy
import sys

probe = Path(__file__).resolve().parents[2] / '2026-10-07/claude-g070/probes_g070.py'
namespace = runpy.run_path(str(probe), run_name='g070_diagnostic')
original = namespace['alive']
observations = []

def observed(pid):
    result = original(pid)
    if not result:
        item = {'pid': pid, 'original_alive': result}
        try:
            os.kill(pid, 0); item['kill_zero'] = 'OK'
        except OSError as exc:
            item['kill_zero'] = type(exc).__name__
        try:
            item['proc_state'] = Path(f'/proc/{pid}/stat').read_text().split()[2]
        except OSError as exc:
            item['proc_state'] = type(exc).__name__
        observations.append(item)
    return result

namespace['main'].__globals__['alive'] = observed
try:
    namespace['main']()
finally:
    print('ALIVE_DIAGNOSTIC ' + json.dumps(observations))
