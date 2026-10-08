# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : probe_body_memory.py
# Description : Mémoire lue par SQLite pour mesurer la taille d'un corps TEXT de 256 Mio (G093, C-045)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""python3 probe_body_memory.py — one temporary database, each expression measured in a fresh process."""
import sqlite3, subprocess, sys, tempfile
from pathlib import Path

EXPRESSIONS = ("substr(CAST(body AS BLOB),1,16777217)", "length(body)", "octet_length(body)", "typeof(body)")
MEASURE = r"""
import resource, sqlite3, sys
db = sqlite3.connect('file:' + sys.argv[1] + '?mode=ro', uri=True)
value = db.execute('SELECT ' + sys.argv[2] + ' FROM m').fetchone()[0]
shown = len(value) if isinstance(value, bytes) else value
print(f"{sys.argv[2]} -> {shown} ; pic {resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024} Mio")
"""
BUILD = r"""
import sqlite3, sys
db = sqlite3.connect(sys.argv[1])
db.execute("CREATE TABLE m(id TEXT PRIMARY KEY, body TEXT)")
with db:
    db.execute("INSERT INTO m VALUES ('a', ?)", ("x" * (256 * 1024 * 1024),))
"""

with tempfile.TemporaryDirectory() as tmp:
    path = str(Path(tmp) / "big.sqlite3")
    # Built in a child: ru_maxrss is inherited across fork, so this process must stay small.
    subprocess.run([sys.executable, "-c", BUILD, path], check=True)
    print(f"SQLite {sqlite3.sqlite_version}, corps TEXT de 256 Mio")
    for expression in EXPRESSIONS:
        print(subprocess.run([sys.executable, "-c", MEASURE, path, expression], capture_output=True, text=True).stdout.strip())
