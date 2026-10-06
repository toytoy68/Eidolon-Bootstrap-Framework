# ==========================================================
# Projet      : Eidolon Bootstrap
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_apt_boundaries.py
# Description : Frontières de add_debian_components (02-nvidia.sh) sur fichiers fictifs (C-TASK-G033)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""From the repository root:
    python3 eidolon-core/docs/validation/2026-10-06/claude-g033/test_apt_boundaries.py [script]
script defaults to ./02-nvidia.sh; pass an older copy to see the "before" result.

The installer is never executed nor sourced (AGENTS.md): only the text of the function
is extracted and run by bash on synthetic files in a temporary folder. No system file,
no package manager, no network. Each case prints PASS or FAIL; exit code 1 on any FAIL."""
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[5]
SCRIPT = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "02-nvidia.sh"
FUNC = re.search(r"add_debian_components\(\) \{.*?\n\}\n", SCRIPT.read_text(), re.S).group(0)
ADD = " contrib non-free non-free-firmware"
OFFICIAL = "deb http://deb.debian.org/debian trixie main"
failures = 0


def run(directory, name):
    return subprocess.run(["bash", "-c", f"set -euo pipefail; source ./func.sh; add_debian_components {name}"],
                          cwd=directory, capture_output=True, text=True)


def check(label, ok, detail=""):
    global failures
    failures += not ok
    print(f"{'PASS' if ok else 'FAIL'} {label}" + (f" — {detail}" if detail and not ok else ""))


def case(label, name, content, expected, note=None):
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        (d / "func.sh").write_text(FUNC)
        (d / name).write_text(content)
        result = run(d, name)
        got = (d / name).read_text()
        ok = result.returncode == 0 and got == expected
        if note is not None:
            ok = ok and (note in result.stderr)
        check(label, ok, f"rc={result.returncode} got={got!r} stderr={result.stderr!r}")


# ---- one-line format (sources.list) ---------------------------------------------------------
case("L1 commentaire en fin de ligne : composants AVANT le #", "sources.list",
     "deb https://deb.debian.org/debian trixie main # commentaire\n",
     "deb https://deb.debian.org/debian trixie main" + ADD + " # commentaire\n")
case("L2 source tierce avec main : intacte et signalée", "sources.list",
     "deb https://vendor.example/debian trixie main\n",
     "deb https://vendor.example/debian trixie main\n", note="non Debian officielle")
case("L3 domaine piège deb.debian.org.evil.example : intact", "sources.list",
     "deb http://deb.debian.org.evil.example/debian trixie main\n",
     "deb http://deb.debian.org.evil.example/debian trixie main\n")
case("L4 chemin piège mirror.example/deb.debian.org/debian : intact", "sources.list",
     "deb http://mirror.example/deb.debian.org/debian trixie main\n",
     "deb http://mirror.example/deb.debian.org/debian trixie main\n")
case("L5 ligne commentée : intacte", "sources.list", "# " + OFFICIAL + "\n", "# " + OFFICIAL + "\n")
case("L6 sans main : intacte", "sources.list",
     "deb http://deb.debian.org/debian trixie contrib\n", "deb http://deb.debian.org/debian trixie contrib\n")
case("L7 options entre crochets avec espaces", "sources.list",
     "deb [ arch=amd64 signed-by=/usr/share/keyrings/debian-archive-keyring.gpg ] http://deb.debian.org/debian trixie main\n",
     "deb [ arch=amd64 signed-by=/usr/share/keyrings/debian-archive-keyring.gpg ] http://deb.debian.org/debian trixie main" + ADD + "\n")
case("L8 sécurité https, barre finale, composants partiels", "sources.list",
     "deb-src https://security.debian.org/debian-security/ trixie-security main non-free-firmware\n",
     "deb-src https://security.debian.org/debian-security/ trixie-security main non-free-firmware contrib non-free\n")
case("L9 miroir national ftp.fr.debian.org", "sources.list",
     "deb http://ftp.fr.debian.org/debian trixie main\n", "deb http://ftp.fr.debian.org/debian trixie main" + ADD + "\n")
case("L10 dépôt Docker (sans main) et cdrom commenté intacts", "sources.list",
     "# deb cdrom:[Debian GNU/Linux 13] trixie main\ndeb https://download.docker.com/linux/debian trixie stable\n",
     "# deb cdrom:[Debian GNU/Linux 13] trixie main\ndeb https://download.docker.com/linux/debian trixie stable\n")
case("L11 options [ non fermées : intacte et signalée", "sources.list",
     "deb [arch=amd64 http://deb.debian.org/debian trixie main\n",
     "deb [arch=amd64 http://deb.debian.org/debian trixie main\n", note="non fermées")

# ---- deb822 (debian.sources) ------------------------------------------------------------------
STANZA = "Types: deb\nURIs: http://deb.debian.org/debian\nSuites: trixie trixie-updates\nComponents: main\n"
case("D1 strophe officielle", "debian.sources", STANZA, STANZA.replace("Components: main", "Components: main" + ADD))
VENDOR = "Types: deb\nURIs: https://vendor.example/debian\nSuites: trixie\nComponents: main\nSigned-By: /etc/apt/keyrings/vendor.gpg\n"
case("D2 strophe tierce avec main : intacte et signalée", "debian.sources", VENDOR, VENDOR, note="non Debian officielle")
MIXED = "Types: deb\nURIs: http://deb.debian.org/debian https://vendor.example/debian\nSuites: trixie\nComponents: main\n"
case("D3 URIs mêlées officielle + tierce : intacte", "debian.sources", MIXED, MIXED, note="non Debian officielle")
MULTI = "Types: deb\nURIs: http://deb.debian.org/debian\nSuites: trixie\nComponents: main\n non-free-firmware\n"
case("D4 Components sur plusieurs lignes : intacte et signalée", "debian.sources", MULTI, MULTI, note="plusieurs lignes")
URIS_MULTI = "Types: deb\nURIs: http://deb.debian.org/debian\n https://vendor.example/debian\nSuites: trixie\nComponents: main\n"
case("D5 URI tierce en ligne de continuation : intacte", "debian.sources", URIS_MULTI, URIS_MULTI, note="non Debian officielle")
TWO = "# commentaire\n" + STANZA + "\n" + VENDOR
case("D6 deux strophes : seule l'officielle change, commentaire gardé", "debian.sources", TWO,
     "# commentaire\n" + STANZA.replace("Components: main", "Components: main" + ADD) + "\n" + VENDOR)
LOWER = "types: deb\nuris: https://deb.debian.org/debian\nsuites: trixie\ncomponents: main\n"
case("D7 noms de champ en minuscules", "debian.sources", LOWER, LOWER.replace("components: main", "components: main" + ADD))

# ---- writing: idempotence, untouched file, permissions, failure ---------------------------------
with tempfile.TemporaryDirectory() as d:
    d = Path(d)
    (d / "func.sh").write_text(FUNC)
    target = d / "sources.list"
    target.write_text(OFFICIAL + "\n")
    os.chmod(target, 0o644)
    run(d, "sources.list")
    once = target.read_text()
    mode = stat.S_IMODE(target.stat().st_mode)
    check("W1 droits 0644 gardés après réécriture", mode == 0o644, oct(mode))
    inode, mtime = target.stat().st_ino, target.stat().st_mtime_ns
    run(d, "sources.list")
    check("W2 second passage : contenu identique et fichier non réécrit",
          target.read_text() == once and target.stat().st_ino == inode and target.stat().st_mtime_ns == mtime)
    check("W3 aucun fichier temporaire laissé", sorted(p.name for p in d.iterdir()) == ["func.sh", "sources.list"],
          str(sorted(p.name for p in d.iterdir())))
    missing = run(d, "absent.list")
    check("W4 fichier absent : échec, rien créé", missing.returncode != 0 and not (d / "absent.list").exists()
          and sorted(p.name for p in d.iterdir()) == ["func.sh", "sources.list"])

print("ÉCHECS :", failures)
sys.exit(1 if failures else 0)
