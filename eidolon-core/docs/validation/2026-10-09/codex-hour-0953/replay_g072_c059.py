# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : replay_g072_c059.py
# Description : Rejeu G072 intact, sauf attente resserrée pour le diagnostic EOF corrigé
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
import hashlib
from pathlib import Path
import sys

core=Path(__file__).resolve().parents[4]
source=core/'docs/validation/2026-10-08/claude-g072/probes_g072.py'
body=source.read_text()
old='("EOF au milieu des en-têtes", [(b"HTTP/1.1 200 OK\\r\\nContent-Ty", 0)], {"TRANSPORT", "BAD_RESPONSE"})'
new='("EOF au milieu des en-têtes", [(b"HTTP/1.1 200 OK\\r\\nContent-Ty", 0)], {"INCOMPLETE_HTTP"})'
assert body.count(old)==1
print('Original Claude probe SHA-256:',hashlib.sha256(source.read_bytes()).hexdigest(),flush=True)
print('Only adaptation: G072-1 expected INCOMPLETE_HTTP; original file unchanged.',flush=True)
sys.argv=[str(source),str(core/'src')]
exec(compile(body.replace(old,new),str(source),'exec'),{'__name__':'__main__','__file__':str(source)})
