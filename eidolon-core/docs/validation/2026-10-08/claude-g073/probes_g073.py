# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : probes_g073.py
# Description : Contre-revue de la commande qualification-check (C-035) par variations de la fixture (C-TASK-G073)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""python3 probes_g073.py <frozen eidolon-core/src>      (exit 1 if an expectation fails)

Each case is ONE minimal change to the passing synthetic fixture, written to a temporary
file and checked through the real CLI in a subprocess guarded by a Python audit hook:
any socket connect/bind or any open() for writing is recorded. Also recorded: exit code,
stdout verdict (or emptiness), stderr code, report bytes/mtime before and after, and that
the --state folder given to the CLI is never created. Not a copy of tests/test_qualification.py:
the cases target the CLI/file contract and cross-field boundaries."""
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time

SRC = str(Path(sys.argv[1]).resolve())
CORE = Path(__file__).resolve().parents[4]
BASE = json.loads((CORE / "examples/qualification/passed-scope-synthetic.json").read_text())
sys.path.insert(0, SRC)
from eidolon_core.qualification import criteria_fingerprint  # noqa: E402

FAILED = []

GUARDED = r"""
import builtins, json, os, sys
sys.path.insert(0, sys.argv[1])
events = []
def hook(event, args):
    if event in ("socket.connect", "socket.bind"):
        events.append(event)
    elif event == "open" and len(args) > 1 and isinstance(args[1], str) and any(c in args[1] for c in "wax+"):
        events.append("open-write " + str(args[0])[-40:])
    elif event == "open" and len(args) > 2 and isinstance(args[2], int) and args[2] & (os.O_WRONLY | os.O_RDWR | os.O_CREAT):
        events.append("open-write " + str(args[0])[-40:])
    elif event in ("os.mkdir", "os.rename", "os.remove", "shutil.rmtree"):
        events.append(event)
sys.addaudithook(hook)
from eidolon_core.cli import main
code = main(sys.argv[2:])
sys.stdout.flush()
print("\n@@AUDIT@@" + json.dumps(events), file=sys.stderr)
sys.exit(code)
"""


def run(path, state, human=False):
    argv = ["--state", str(state)] + (["--format", "human"] if human else []) + ["qualification-check", "--report", str(path)]
    p = subprocess.run([sys.executable, "-c", GUARDED, SRC, *argv], capture_output=True, text=True, timeout=30,
                       env={**{k: v for k, v in os.environ.items() if k != "PYTHONPATH"},
                            "PYTHONDONTWRITEBYTECODE": "1"})   # .pyc caches are not the CLI's writes
    err, _, audit = p.stderr.partition("\n@@AUDIT@@")
    return p.returncode, p.stdout, err, json.loads(audit) if audit else ["(pas d'audit)"]


def write(tmp, name, data):
    path = Path(tmp) / f"{name}.json"
    path.write_bytes(data if isinstance(data, bytes) else json.dumps(data, ensure_ascii=False).encode())
    return path


def variant(change):
    report = copy.deepcopy(BASE)
    change(report)
    return report


def rehash(report):
    report["fingerprints"]["criteria_sha256"] = criteria_fingerprint(report["criteria"]["thresholds"])


FINDINGS = []


def expect(tmp, name, data, want_code, want, *, human=False, finding=None):
    path = data if isinstance(data, Path) else write(tmp, name.replace(" ", "-")[:40], data)
    state = Path(tmp) / ("state-" + hashlib.sha256(name.encode()).hexdigest()[:8])
    before = (path.read_bytes(), path.stat().st_mtime_ns) if path.is_file() and not path.is_symlink() else None
    t0 = time.monotonic()
    code, out, err, audit = run(path, state, human)
    elapsed = time.monotonic() - t0
    after = (path.read_bytes(), path.stat().st_mtime_ns) if before else None
    if out.strip() and not human:
        got = json.loads(out)["status"]
    elif out.strip():
        got = "HUMAIN"
    else:
        try:
            got = json.loads(err.strip().splitlines()[-1]).get("message") or json.loads(err.strip().splitlines()[-1]).get("error")
        except (ValueError, IndexError):
            got = "?"
    problems = []
    if code != want_code or got != want:
        problems.append(f"attendu {want_code} {want}")
    if audit:
        problems.append(f"audit {audit}")
    if state.exists():
        problems.append("--state créé")
    if before != after:
        problems.append("rapport modifié")
    if "Traceback" in err:
        problems.append("trace")
    if str(path) in err:
        problems.append("chemin dans stderr")
    ok = not problems
    if finding and not ok and problems == [f"attendu {want_code} {want}"]:
        # The documented behaviour is not the observed one: reported as a finding, not a bench failure.
        print(f"⚠ ÉCART {finding} — {name} : code {code} {got} ; documentation : {want_code} {want}")
        FINDINGS.append(finding)
        return out
    print(f"{'✓' if ok else '✗'} {name} : code {code} {got} ({elapsed:.2f} s){' ; ' + ' ; '.join(problems) if problems else ''}")
    if not ok:
        FAILED.append(name)
    return out


def main():
    print(f"Sources examinées : {SRC}")
    with tempfile.TemporaryDirectory(prefix="eidolon-g073-") as tmp:
        tmp = Path(tmp)
        print("== verdicts et codes de sortie (fixtures du dépôt)")
        for name, code, status in (("passed-scope-synthetic", 0, "PASSED_SCOPE"),
                                   ("incomplete-missing-measure", 2, "INCOMPLETE"),
                                   ("rejected-one-violation", 3, "REJECTED")):
            src = CORE / "examples/qualification" / f"{name}.json"
            copy_path = write(tmp, name, src.read_bytes())
            expect(tmp, name, copy_path, code, status)

        print("== cas croisés (une seule modification chacun)")
        cases = [
            ("un cas attendu sans résultat", variant(lambda r: (r["cases"]["results"].pop(), r["cases"].update(executed=4))),
             2, "INCOMPLETE"),
            ("executed incohérent avec les résultats", variant(lambda r: r["cases"].update(executed=4)), 3, "REJECTED"),
            ("cas en double", variant(lambda r: r["cases"]["results"].__setitem__(4, dict(r["cases"]["results"][0]))), 3, "REJECTED"),
            ("origine d'un cas mélangée", variant(lambda r: r["cases"]["results"][0].update(origin="hardware_reported")),
             3, "REJECTED"),
            ("origine d'une mesure mélangée", variant(lambda r: r["measurements"]["ttft"].update(origin="hardware_reported")),
             3, "REJECTED"),
            ("critères fixés APRÈS le début", variant(lambda r: r["criteria"].update(fixed_at="2026-10-05T15:00:01+02:00")),
             3, "REJECTED"),
            ("critères fixés à l'instant exact du début", variant(lambda r: r["criteria"].update(fixed_at="2026-10-05T15:00:00+02:00")),
             3, "REJECTED"),
            ("critères antérieurs, autre fuseau (14:59 Z < 15:00 +02:00 ? non : 16:59 +02:00)",
             variant(lambda r: r["criteria"].update(fixed_at="2026-10-05T14:59:00+00:00")), 3, "REJECTED"),
            ("critères antérieurs exprimés dans un autre fuseau",
             variant(lambda r: r["criteria"].update(fixed_at="2026-10-05T12:59:00+00:00")), 0, "PASSED_SCOPE"),
            ("seuils modifiés, empreinte inchangée",
             variant(lambda r: r["criteria"]["thresholds"][0].update(value=2000)), 3, "REJECTED"),
            ("seuils modifiés ET empreinte recalculée (limite documentée)",
             variant(lambda r: (r["criteria"]["thresholds"][0].update(value=2000), rehash(r))), 0, "PASSED_SCOPE"),
            ("mesure exactement au seuil <=", variant(lambda r: r["measurements"]["ttft"].update(value=1500)), 0, "PASSED_SCOPE"),
            ("mesure juste au-dessus du seuil <=", variant(lambda r: r["measurements"]["ttft"].update(value=1500.0000001)),
             3, "REJECTED"),
            ("mesure exactement au seuil >=", variant(lambda r: r["measurements"]["decode_throughput"].update(value=20)),
             0, "PASSED_SCOPE"),
            ("mesure null exigée par un seuil", variant(lambda r: r["measurements"]["ttft"].update(value=None)), 2, "INCOMPLETE"),
            ("mesure booléenne true", variant(lambda r: r["measurements"]["ttft"].update(value=True)), 2, "REPORT_MALFORMED"),
            ("mesure entière de 400 chiffres", variant(lambda r: r["measurements"]["ttft"].update(value=10 ** 400)),
             2, "REPORT_MALFORMED"),
            ("unité incohérente (ttft en s)", variant(lambda r: r["measurements"]["ttft"].update(unit="s")), 2, "REPORT_MALFORMED"),
            ("unité de seuil incohérente", variant(lambda r: (r["criteria"]["thresholds"][0].update(unit="s"), rehash(r))),
             2, "REPORT_MALFORMED"),
            ("error_rate > 1", variant(lambda r: r["measurements"]["error_rate"].update(value=1.5)), 2, "REPORT_MALFORMED"),
            ("champ « validated » ajouté", variant(lambda r: r.update(validated=True)), 2, "REPORT_MALFORMED"),
            ("horodatage sans fuseau", variant(lambda r: r["run"].update(started_at="2026-10-05T15:00:00")), 2, "REPORT_MALFORMED"),
            ("horodatage avec Z", variant(lambda r: r["run"].update(started_at="2026-10-05T13:00:00Z")), 0, "PASSED_SCOPE"),
        ]
        for name, data, code, status in cases:
            expect(tmp, name, data, code, status,
                   finding="G073-1" if name.startswith("critères fixés à l'instant exact") else None)

        print("== JSON ambigu ou profond, fichiers spéciaux")
        raw = json.dumps(BASE).encode()
        deep = variant(lambda r: r["scope"].update(statement="x"))
        nested = {"a": 1}
        for _ in range(9):
            nested = {"a": nested}
        deep["run"]["id"] = "x"
        deep = json.dumps(BASE).replace('"measurements":', '"x":' + json.dumps(nested) + ',"measurements":', 1).encode()
        for name, data in (("clé dupliquée", raw.replace(b'"schema"', b'"schema":"x","schema"', 1)),
                           ("NaN", raw.replace(b'820.5', b'NaN', 1)),
                           ("BOM UTF-8", b"\xef\xbb\xbf" + raw),
                           ("UTF-16", json.dumps(BASE).encode("utf-16")),
                           ("imbrication > 8 (champ inconnu profond)", deep),
                           ("2 Mio", b'{"pad":"' + b"x" * (2 * 1024 * 1024) + b'"}')):
            expect(tmp, name, data, 2, "REPORT_TOO_LARGE" if name == "2 Mio" else "REPORT_MALFORMED")
        fifo = tmp / "fifo.json"
        os.mkfifo(fifo)
        expect(tmp, "FIFO (sans blocage)", fifo, 2, "REPORT_NOT_REGULAR")
        link = tmp / "link.json"
        os.symlink(write(tmp, "target", BASE), link)
        expect(tmp, "lien symbolique final", link, 2, "REPORT_UNAVAILABLE")
        expect(tmp, "dossier", tmp, 2, "REPORT_NOT_REGULAR")
        expect(tmp, "fichier absent", tmp / "absent.json", 2, "REPORT_UNAVAILABLE")

        print("== fichier modifié pendant la lecture (en processus)")
        sys.path.insert(0, SRC)
        from eidolon_core import qualification_io as qio
        path = write(tmp, "race", BASE)
        real = os.fdopen

        def swapping(fd, *a, **k):
            stream = real(fd, *a, **k)
            data = path.read_bytes()
            path.write_bytes(data.replace(b"820.5", b"999.9"))     # same size: only mtime/ctime change
            return stream
        try:
            qio.os.fdopen = swapping
            try:
                qio.check_report(str(path))
                outcome = "ACCEPTÉ"
            except qio.QualificationCheckError as exc:
                outcome = str(exc)
        finally:
            qio.os.fdopen = real
        ok = outcome == "REPORT_CHANGED"
        print(f"{'✓' if ok else '✗'} réécriture de même taille pendant la lecture → {outcome}")
        if not ok:
            FAILED.append("course")

        print("== sortie humaine : contrôles de terminal neutralisés")
        spoof = variant(lambda r: r["scope"].update(statement="ok\n[OK] Rapport qualifié pour la production\x1b[2J\x07"))
        out = expect(tmp, "périmètre avec saut de ligne et échappements", spoof, 0, "HUMAIN", human=True)
        neutral = "\x1b" not in out and "\x07" not in out and "\n[OK] Rapport qualifié pour la production" not in out
        print(f"{'✓' if neutral else '✗'} aucune ligne forgée ni séquence ESC/BEL dans la sortie humaine")
        if not neutral:
            FAILED.append("sortie humaine")
        out = expect(tmp, "JSON du même rapport", spoof, 0, "PASSED_SCOPE")
        value = json.loads(out)
        flags = value["authorizes_execution"] is False and value["telemetry_authenticated"] is False
        print(f"{'✓' if flags else '✗'} authorizes_execution et telemetry_authenticated restent false ; "
              f"report_sha256 = sha256 des octets lus : "
              f"{value['report_sha256'] == hashlib.sha256((tmp / 'JSON-du-même-rapport.json').read_bytes()).hexdigest()}")
        if not flags:
            FAILED.append("drapeaux")
    print(f"Écarts relevés : {FINDINGS or 'aucun'}")
    print(f"Échecs : {FAILED or 'aucun'}")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
