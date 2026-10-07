# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : probes_g047.py
# Description : Vérification indépendante de beta_check, du paquet et du vérificateur d'archive (C-TASK-G047)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""python3 probes_g047.py <frozen d9265fa eidolon-core> <frozen 0fdf18e repo root> <git repo>
Everything runs in temporary folders (TMPDIR is redirected to observe leftovers). Only
127.0.0.1 is used by the recipe's own servers. Nothing is installed outside a temporary venv."""
import gzip
import io
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tarfile
import tempfile
import time
import zipfile

D9, REPO_0F, GIT = (Path(p).resolve() for p in sys.argv[1:4])
TOKENISH = re.compile(rb"(?<![A-Za-z0-9_-])[A-Za-z0-9_-]{43}(?![A-Za-z0-9_-])")


def env(tmp, pythonpath=True):
    e = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", TMPDIR=str(tmp))
    if pythonpath:
        e["PYTHONPATH"] = str(D9 / "src")
    else:
        e.pop("PYTHONPATH", None)
    return e


def leftovers(tmp):
    dirs = sorted(p.name for p in Path(tmp).iterdir())
    procs = subprocess.run(["pgrep", "-f", f"eidolon_core.http_api --state {tmp}"], capture_output=True, text=True).stdout.split()
    return dirs, procs


def recipe(tmp, python=sys.executable, cwd=None, fmt="json", pythonpath=True, web_root=None):
    t0 = time.perf_counter()
    r = subprocess.run([python, "-m", "eidolon_core.beta_check", "--web-root", str(web_root or D9 / "desktop/connected"), "--format", fmt],
                       cwd=cwd or D9, env=env(tmp, pythonpath), capture_output=True)
    return r, time.perf_counter() - t0


def tokenish(blob):
    return [m for m in TOKENISH.findall(blob) if not re.fullmatch(rb"[0-9a-f]{43}", m)]


def interrupted(tmp, sig, kill_child=False):
    p = subprocess.Popen([sys.executable, "-m", "eidolon_core.beta_check", "--web-root", str(D9 / "desktop/connected")],
                         cwd=D9, env=env(tmp), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        pids = subprocess.run(["pgrep", "-f", f"eidolon_core.http_api --state {tmp}"], capture_output=True, text=True).stdout.split()
        if pids:
            break
        time.sleep(0.05)
    if kill_child:
        for pid in pids:
            os.kill(int(pid), signal.SIGKILL)
    else:
        p.send_signal(sig)
    out, _ = p.communicate(timeout=60)
    time.sleep(0.5)
    try:
        status = json.loads(out).get("status"), json.loads(out).get("error")
    except ValueError:
        status = ("pas de JSON", None)
    return p.returncode, status, leftovers(tmp)


def main():
    print("== P1 depuis le checkout figé d9265fa")
    with tempfile.TemporaryDirectory() as tmp:
        r, dt = recipe(tmp)
        rep = json.loads(r.stdout)
        print(f"P1 json : code {r.returncode} {rep['status']} {rep['checks_passed']} contrôles en {dt:.1f} s ; restes : {leftovers(tmp)}")
        print(f"P1 chaînes de type jeton dans la sortie JSON : {len(tokenish(r.stdout))}")
        h, _ = recipe(tmp, fmt="human")
        print(f"P1 human : code {h.returncode} ; chaînes de type jeton : {len(tokenish(h.stdout))} ; restes : {leftovers(tmp)}")
    print("== P2 hors du dossier source")
    with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as elsewhere:
        r, _ = recipe(tmp, cwd=elsewhere)
        print(f"P2 cwd ailleurs, PYTHONPATH absolu, web-root absolu : code {r.returncode} {json.loads(r.stdout)['status']}")
        r = subprocess.run([sys.executable, "-m", "eidolon_core.beta_check", "--web-root", "desktop/connected"], cwd=elsewhere,
                           env=env(tmp), capture_output=True, text=True)
        print(f"P2 web-root relatif depuis un autre dossier : code {r.returncode} {(json.loads(r.stdout).get('error') if r.stdout.strip() else r.stderr.strip()[-80:])}")
    print("== P3 à P6 erreurs et interruptions : nettoyage")
    for label, sig, kill in (("P3 serveur enfant tué (SIGKILL) en cours de recette", None, True),
                             ("P4 Ctrl+C (SIGINT) sur beta_check", signal.SIGINT, False),
                             ("P5 SIGTERM sur beta_check", signal.SIGTERM, False)):
        with tempfile.TemporaryDirectory() as tmp:
            code, status, left = interrupted(tmp, sig, kill)
            print(f"{label} : code {code} {status} ; dossiers restants {left[0]} ; serveurs restants {left[1]}")
            for pid in left[1]:
                os.kill(int(pid), signal.SIGKILL)
    with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as web:
        (Path(web) / "index.html").write_text("<!doctype html>")
        r, dt = recipe(tmp, web_root=web)
        print(f"P6 web-root incomplet : code {r.returncode} {json.loads(r.stdout).get('error')} en {dt:.1f} s ; restes {leftovers(tmp)}")
    print("== P7 paquet : wheel, venv temporaire, recette depuis le paquet installé")
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        src = tmp / "src-copy"
        subprocess.run(["cp", "-r", str(D9), str(src)], check=True)
        build = [sys.executable, "-m", "pip", "wheel", "--no-deps", "--no-build-isolation", "--no-index", "-w", str(tmp / "dist"), str(src)]
        w = subprocess.run(build, capture_output=True, text=True, env=env(tmp, False))
        tail = (w.stdout + w.stderr).strip().splitlines()
        print(f"P7 construction (setuptools système) : code {w.returncode} "
              f"{'install_layout' if 'install_layout' in w.stdout + w.stderr else (tail[-1][:80] if tail else '')}")
        if w.returncode != 0:  # Debian's setuptools: known workaround, documented in the report
            w = subprocess.run(build, capture_output=True, text=True, env=dict(env(tmp, False), SETUPTOOLS_USE_DISTUTILS="stdlib"))
            print(f"P7 construction avec SETUPTOOLS_USE_DISTUTILS=stdlib : code {w.returncode}")
        wheel = next((tmp / "dist").glob("*.whl"), None)
        print(f"P7 wheel : {wheel.name if wheel else 'aucun'}")
        names = zipfile.ZipFile(wheel).namelist()
        print(f"P7 contenu : {len(names)} entrées ; desktop {any('desktop' in n for n in names)} ; tests {any(n.startswith('tests/') for n in names)} ; "
              f"beta_check {any(n.endswith('beta_check.py') for n in names)} ; build_beta_bundle {any('build_beta_bundle' in n for n in names)}")
        subprocess.run([sys.executable, "-m", "venv", str(tmp / "venv")], check=True)
        py = tmp / "venv/bin/python"
        i = subprocess.run([str(py), "-m", "pip", "install", "--no-index", "--no-deps", str(wheel)], capture_output=True, text=True, env=env(tmp, False))
        print(f"P7 installation (sans réseau) : code {i.returncode}")
        site = Path(subprocess.run([str(py), "-c", "import eidolon_core, os; print(os.path.dirname(eidolon_core.__file__))"],
                                   capture_output=True, text=True, env=env(tmp, False), cwd=tmp).stdout.strip())
        diff = [p.name for p in (D9 / "src/eidolon_core").glob("*.py") if (site / p.name).read_bytes() != p.read_bytes()]
        print(f"P7 modules installés identiques aux sources : {not diff} {diff}")
        (tmp / "rt").mkdir()
        r, dt = recipe(tmp / "rt", python=py, cwd="/", pythonpath=False)
        print(f"P7 recette depuis le paquet, cwd=/ , sans PYTHONPATH : code {r.returncode} {json.loads(r.stdout)['status']} "
              f"version {json.loads(r.stdout)['package_version']} en {dt:.1f} s")
        r, _ = recipe(tmp / "rt", python=py, cwd="/", pythonpath=False, web_root=tmp / "absent")
        print(f"P7 recette depuis le paquet sans client Web : code {r.returncode} {r.stdout.decode()[-120:].strip() or r.stderr.decode()[-120:].strip()}")
    print("== P8 vérificateur G044 durci (0fdf18e)")
    tool = REPO_0F / "eidolon-core/tools/build_beta_bundle.py"
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        good = tmp / "good.tar.gz"
        b = subprocess.run([sys.executable, str(tool), "--repo", str(GIT), "--commit", "0fdf18e7a4256e980ca4657600b62366abca5e4b",
                            "--output", str(good)], capture_output=True, text=True)
        print(f"P8 construction de 0fdf18e : {json.loads(b.stdout)['status']} {json.loads(b.stdout).get('files')} fichiers")
        with tarfile.open(good, "r:gz") as t:
            members = [(m, t.extractfile(m).read() if m.isfile() else b"") for m in t.getmembers()]
        root = members[0][0].name.split("/")[0]

        def write(name, items, raw=None):
            path = tmp / (name + ".tar.gz")
            if raw is not None:
                path.write_bytes(raw)
                return path
            buf = io.BytesIO()
            with tarfile.open(fileobj=buf, mode="w", format=tarfile.PAX_FORMAT) as t:
                for m, d in items:
                    m = tarfile.TarInfo(m.name) if not isinstance(m, tarfile.TarInfo) else m
                    m.size = len(d) if m.isfile() else 0
                    t.addfile(m, io.BytesIO(d) if m.isfile() else None)
            gz = io.BytesIO()
            with gzip.GzipFile(fileobj=gz, mode="wb", mtime=0) as g:
                g.write(buf.getvalue())
            path.write_bytes(gz.getvalue())
            return path

        def clone(m, **kw):
            n = tarfile.TarInfo(kw.get("name", m.name))
            for a in ("mode", "mtime", "uid", "gid", "uname", "gname", "type", "linkname"):
                setattr(n, a, kw.get(a, getattr(m, a)))
            return n

        last_m, last_d = members[-1]
        sym = clone(last_m, name=root + "/eidolon-core/src/eidolon_core/lien.py", type=tarfile.SYMTYPE, linkname="/etc/hostname")
        many = members + [(clone(last_m, name=f"{root}/eidolon-core/src/eidolon_core/x{i}.py"), b"x") for i in range(1100)]
        big = tarfile.TarInfo(root + "/eidolon-core/src/eidolon_core/gros.py")
        cases = [("authentique", members),
                 ("membre dupliqué", members + [(clone(last_m), last_d)]),
                 ("contenu modifié", members[:-1] + [(clone(last_m), last_d + b"#")]),
                 ("membre ajouté hors manifeste", members + [(clone(last_m, name=root + "/eidolon-core/src/eidolon_core/ajout.py"), b"x")]),
                 ("membre du manifeste supprimé", members[:-1]),
                 ("mode 0777", members[:-1] + [(clone(last_m, mode=0o777), last_d)]),
                 ("START-HERE modifié", [(m, d + b"\nAjout." if m.name.endswith("START-HERE.md") else d) for m, d in members]),
                 ("lien symbolique", members + [(sym, b"")]),
                 ("chemin ../", members + [(clone(last_m, name=root + "/../evade.py"), b"x")]),
                 ("1100 membres en plus", many),
                 ("membre de 17 Mio", members + [(big, b"0" * (17 * 1024 * 1024))])]
        for n, (label, items) in enumerate(cases):
            path = write(f"cas-{n}", items)
            t0 = time.perf_counter()
            v = subprocess.run([sys.executable, str(tool), "--verify", str(path)], capture_output=True, text=True)
            out = json.loads(v.stdout)
            print(f"P8 {label} : code {v.returncode} {out.get('status')} {out.get('detail', '')[:70]} ({1000 * (time.perf_counter() - t0):.0f} ms)"
                  + (f" authenticity_verified={out.get('authenticity_verified')}" if label == "authentique" else ""))
        bomb = io.BytesIO()
        with gzip.GzipFile(fileobj=bomb, mode="wb", mtime=0) as g:
            for _ in range(200):
                g.write(b"\0" * (1024 * 1024))
        path = write("bombe", None, raw=bomb.getvalue())
        t0 = time.perf_counter()
        v = subprocess.run([sys.executable, str(tool), "--verify", str(path)], capture_output=True, text=True)
        print(f"P8 gzip de 200 Mio de zéros ({len(bomb.getvalue()) // 1024} Kio) : code {v.returncode} {json.loads(v.stdout).get('status')} "
              f"({1000 * (time.perf_counter() - t0):.0f} ms)")
        print(f"P8 aucun fichier extrait pendant les vérifications : {sorted(p.name for p in tmp.iterdir() if not p.name.endswith('.tar.gz'))}")


if __name__ == "__main__":
    main()
