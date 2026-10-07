# ==========================================================
# Projet      : Eidolon Bootstrap
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_apt_extra_mirrors.py
# Description : Liste explicite de miroirs APT supplémentaires (décision C-D11) sur fichiers fictifs
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""From the repository root:
    python3 eidolon-core/docs/validation/2026-10-07/claude-apt-mirrors/test_apt_extra_mirrors.py [script]
The installer is never executed nor sourced: only add_debian_components is extracted and run
by bash on synthetic files in a temporary folder. No system file, no apt, no network."""
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[5]
SCRIPT = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "02-nvidia.sh"
FUNC = re.search(r"add_debian_components\(\) \{.*?\n\}\n", SCRIPT.read_text(), re.S).group(0)
ADD = " contrib non-free non-free-firmware"
failures = 0


def case(label, extra, name, content, expected, rc=0, note=None):
    global failures
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        (d / "func.sh").write_text(FUNC)
        (d / name).write_text(content)
        env = dict(os.environ)
        if extra is None:
            env.pop("EIDOLON_APT_EXTRA_MIRRORS", None)
        else:
            env["EIDOLON_APT_EXTRA_MIRRORS"] = extra
        r = subprocess.run(["bash", "-c", f"set -euo pipefail; source ./func.sh; add_debian_components {name}"],
                           cwd=d, env=env, capture_output=True, text=True)
        got = (d / name).read_text()
        leftovers = sorted(p.name for p in d.iterdir() if p.name not in ("func.sh", name))
        ok = r.returncode == rc and got == expected and not leftovers and (note is None or note in r.stderr)
        failures += not ok
        print(f"{'PASS' if ok else 'FAIL'} {label}" + ("" if ok else f" — rc={r.returncode} got={got!r} stderr={r.stderr!r} leftovers={leftovers}"))


MIRROR = "deb http://miroir.exemple.org/debian trixie main\n"
case("M1 sans liste : miroir non officiel intact, diagnostic qui indique la variable", None, "sources.list", MIRROR, MIRROR,
     note="EIDOLON_APT_EXTRA_MIRRORS")
case("M2 miroir listé : composants ajoutés", "miroir.exemple.org", "sources.list", MIRROR, MIRROR.replace("main", "main" + ADD))
case("M3 hôte:port listé (cache local)", "cache.local:3142", "sources.list",
     "deb http://cache.local:3142/debian trixie main # cache\n", "deb http://cache.local:3142/debian" + " trixie main" + ADD + " # cache\n")
case("M4 port différent : non listé, intact", "cache.local:3142", "sources.list",
     "deb http://cache.local:9999/debian trixie main\n", "deb http://cache.local:9999/debian trixie main\n")
case("M5 sous-domaine piège d'un miroir listé : intact", "miroir.exemple.org", "sources.list",
     "deb http://miroir.exemple.org.evil.example/debian trixie main\n", "deb http://miroir.exemple.org.evil.example/debian trixie main\n")
case("M6 miroir listé mais autre chemin : intact", "miroir.exemple.org", "sources.list",
     "deb http://miroir.exemple.org/autre trixie main\n", "deb http://miroir.exemple.org/autre trixie main\n")
case("M7 plusieurs miroirs, deb822", "a.exemple.org  b.exemple.org", "debian.sources",
     "Types: deb\nURIs: http://a.exemple.org/debian http://b.exemple.org/debian\nSuites: trixie\nComponents: main\n",
     "Types: deb\nURIs: http://a.exemple.org/debian http://b.exemple.org/debian\nSuites: trixie\nComponents: main" + ADD + "\n")
case("M8 tiers non listé toujours intact à côté d'un miroir listé", "miroir.exemple.org", "sources.list",
     MIRROR + "deb https://vendor.example/debian trixie main\n",
     MIRROR.replace("main", "main" + ADD) + "deb https://vendor.example/debian trixie main\n")
for bad in ("Miroir.Exemple.org", "*", "miroir.exemple.org/debian", "-x", "a;rm", "a:99999999"):
    case(f"M9 entrée invalide refusée sans rien modifier : {bad!r}", bad, "sources.list", MIRROR, MIRROR, rc=1, note="hôte invalide")
case("M10 liste vide explicite = comportement officiel seul", "", "sources.list", MIRROR, MIRROR)
print("ÉCHECS :", failures)
sys.exit(1 if failures else 0)
