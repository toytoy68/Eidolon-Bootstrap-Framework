# ==========================================================
# Projet      : Eidolon Bootstrap
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test_add_debian_components.py
# Description : Teste seule la fonction add_debian_components de 02-nvidia.sh sur des fichiers fictifs
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""From the repository root: python3 eidolon-core/docs/validation/2026-10-06/claude-bootstrap-fix/test_add_debian_components.py

The installer is neither executed nor sourced (AGENTS.md): only the text of the
function is extracted and run by bash on synthetic files in a temporary folder."""
import re, subprocess, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
func = re.search(r"add_debian_components\(\) \{.*?\n\}\n", (ROOT / "02-nvidia.sh").read_text(), re.S).group(0)
LIST = """# deb cdrom:[Debian GNU/Linux 13] trixie main
deb http://deb.debian.org/debian trixie main non-free-firmware
deb-src http://deb.debian.org/debian trixie main non-free-firmware
deb http://security.debian.org/debian-security trixie-security main
deb [arch=amd64 signed-by=/etc/apt/keyrings/x.gpg] http://deb.debian.org/debian trixie-updates main contrib
deb http://deb.debian.org/debian trixie-backports main contrib non-free non-free-firmware
deb https://download.docker.com/linux/debian trixie stable
"""
DEB822 = """Types: deb
URIs: http://deb.debian.org/debian
Suites: trixie trixie-updates
Components: main non-free-firmware

Types: deb
URIs: http://security.debian.org/debian-security
Suites: trixie-security
Components: main
"""
with tempfile.TemporaryDirectory() as d:
    d = Path(d)
    (d / "func.sh").write_text(func)
    for name, content in (("sources.list", LIST), ("debian.sources", DEB822)):
        (d / name).write_text(content)
        run = lambda: subprocess.run(["bash", "-c", f"set -euo pipefail; source ./func.sh; add_debian_components {name}"], cwd=d, check=True)
        run(); once = (d / name).read_text()
        run(); twice = (d / name).read_text()
        print(f"--- {name}: idempotent={once == twice}")
        print(once)
        assert once == twice
        for line in once.splitlines():
            words = line.split()
            if (line.startswith(("deb ", "deb-src ")) or line.startswith("Components:")) and "main" in words:
                assert all(words.count(c) == 1 for c in ("contrib", "non-free", "non-free-firmware")), line
        assert "# deb cdrom:[Debian GNU/Linux 13] trixie main\n" in once or name != "sources.list"
        assert "download.docker.com/linux/debian trixie stable\n" in once or name != "sources.list"
print("OK")
