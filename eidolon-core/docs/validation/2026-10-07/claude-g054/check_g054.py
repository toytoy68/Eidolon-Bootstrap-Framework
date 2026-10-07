# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : check_g054.py
# Description : Diagnostics constants du binaire Tauri pour des entrées invalides (C-TASK-G054)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""python3 check_g054.py <binary>

Every case must exit with code 2 before any window, and stderr must be one constant
line that contains none of the synthetic secret values given as input."""
import os
import subprocess
import sys

BINARY = sys.argv[1]
SECRET = b"tok_9fK2synthetiqueG054xYz"
CASES = [
    ("argument inconnu porteur d'un secret", [SECRET], {}),
    ("--port suivi d'un secret", [b"--port", SECRET], {}),
    ("--port répété", [b"--port", b"9000", b"--port", b"9100"], {}),
    ("--port=valeur", [b"--port=" + SECRET], {}),
    ("--port sans valeur", [b"--port"], {}),
    ("séquence d'échappement terminal", [b"--port", b"\x1b[31m9000"], {}),
    ("retour chariot + en-tête injecté", [b"--port", b"9000\r\nX-Injected: 1"], {}),
    ("octets non UTF-8 en argument", [b"--port", b"90\xff0"], {}),
    ("port 1023", [b"--port", b"1023"], {}),
    ("port 65536", [b"--port", b"65536"], {}),
    ("variable d'environnement secrète", [], {b"EIDOLON_CORE_PORT": SECRET}),
    ("variable non UTF-8", [], {b"EIDOLON_CORE_PORT": b"90\xff0"}),
    ("argument valide + variable invalide", [b"--port", b"9000"], {b"EIDOLON_CORE_PORT": SECRET}),
]

failures = 0
for label, args, extra in CASES:
    env = {k: v for k, v in os.environb.items() if k != b"EIDOLON_CORE_PORT"}
    env.update(extra)
    env.pop(b"DISPLAY", None)    # no display: an accepted input would fail later, visibly
    env.pop(b"WAYLAND_DISPLAY", None)
    p = subprocess.run([BINARY.encode(), *args], env=env, capture_output=True, timeout=30)
    err = p.stderr
    lines = err.splitlines()
    echoed = any(x in err for x in (SECRET, b"\x1b[31m", b"X-Injected", b"\xff", b"9100", b"1023", b"65536"))
    ok = p.returncode == 2 and len(lines) == 1 and lines[0].startswith("eidolon-consultation : ".encode()) and not echoed
    failures += not ok
    print(f"{'OK ' if ok else 'ÉCHEC'} {label} : code {p.returncode} ; stderr {err.decode('utf-8', 'replace').strip()!r}")
print(f"{len(CASES) - failures}/{len(CASES)} conformes")
sys.exit(1 if failures else 0)
