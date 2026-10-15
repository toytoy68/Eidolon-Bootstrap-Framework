# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : tests/test_claude_bundle_inventory_g264.py
# Description : Inventaire hors ligne de l'archive bêta : secrets, corpus, modèles, commandes documentées (G264-9)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Synthetic archives built in memory, plus one real archive from tools/build_beta_bundle.py at HEAD.
Nothing is extracted or executed; no dependency is downloaded."""
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile

import pytest

TOOL = Path(__file__).resolve().parents[1] / "tools" / "claude_bundle_inventory.py"
SPEC = importlib.util.spec_from_file_location("claude_bundle_inventory", TOOL)
inv = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(inv)
REPO = Path(__file__).resolve().parents[2]

PYPROJECT = b'[project]\nname = "x"\n[project.scripts]\neidolon-core = "eidolon_core.cli:main"\n'
CLI = b"import argparse\n\ndef main():\n    argparse.ArgumentParser()\n"
BASE = {"eidolon-core/pyproject.toml": PYPROJECT, "eidolon-core/src/eidolon_core/cli.py": CLI,
        "eidolon-core/docs/BETA.md": b"Run `python3 -m eidolon_core.cli --help`.\n",
        "eidolon-core/examples/media/a.json": b"{}"}


def archive(tmp_path, extra=None, *, members=None):
    path = tmp_path / "bundle.tar.gz"
    with tarfile.open(path, "w:gz") as tar:
        for name, data in {**BASE, **(extra or {})}.items():
            info = tarfile.TarInfo("eidolon-beta-0123456789ab/" + name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
        for info in members or ():
            tar.addfile(info, io.BytesIO(b"") if info.isreg() else None)
    return path


def rules(report):
    return {(f["rule"], f["path"]) for f in report["findings"]}


def test_a_clean_synthetic_archive(tmp_path):
    report = inv.inventory(archive(tmp_path))
    assert report["findings"] == [] and report["entry_points"]["eidolon-core"]["present"]
    assert report["documented_commands"]["eidolon_core.cli"]["present"] is True
    assert report["fixtures"] == ["eidolon-core/examples/media/a.json"]          # declared, kept apart


@pytest.mark.parametrize("name, data, rule", [
    ("eidolon-core/src/eidolon_core/k.py", b"KEY = '''-----BEGIN PRIVATE KEY-----\n" + b"A" * 80 + b"\n'''",
     "SECRET_PRIVATE_KEY"),
    ("eidolon-core/docs/x.md", b"token ghp_" + b"a" * 36, "SECRET_GITHUB_TOKEN"),
    ("eidolon-core/docs/y.md", b"EIDOLON_MEMORY_BRIDGE_TOKEN=" + b"z" * 40, "SECRET_BRIDGE_TOKEN_VALUE"),
    ("eidolon-core/docs/z.md", b"Authorization: Bearer " + b"q" * 40, "SECRET_BEARER_LITERAL"),
    ("eidolon-core/data/state.sqlite3", b"x", "FORBIDDEN_FILE_TYPE"),
    ("eidolon-core/models/model.safetensors", b"x", "FORBIDDEN_FILE_TYPE"),
    ("eidolon-core/memory/persistent/a.md", b"x", "FORBIDDEN_LOCATION"),
    ("eidolon-core/corpus/private.md", b"x", "FORBIDDEN_LOCATION"),
    ("eidolon-core/.venv/lib.py", b"x", "FORBIDDEN_LOCATION"),
])
def test_secrets_corpus_models_and_state_are_reported(tmp_path, name, data, rule):
    assert (rule, name) in rules(inv.inventory(archive(tmp_path, {name: data})))


def test_a_pem_header_in_code_is_not_a_key(tmp_path):
    code = b'if not out.startswith(b"-----BEGIN PRIVATE KEY-----"):\n    raise ValueError\n'
    assert inv.inventory(archive(tmp_path, {"eidolon-core/src/eidolon_core/sig.py": code}))["findings"] == []


def test_oversized_members_and_missing_documented_commands(tmp_path):
    report = inv.inventory(archive(tmp_path, {
        "eidolon-core/big.dat": b"0" * (inv.MAX_MEMBER + 1),
        "eidolon-core/docs/run.md": b"python3 -m eidolon_core.absent_tool --x\npython3 tools/build_beta_bundle.py\n"}))
    assert {("OVERSIZED", "eidolon-core/big.dat"), ("DOCUMENTED_BUT_ABSENT", "eidolon_core.absent_tool"),
            ("DOCUMENTED_BUT_ABSENT", "eidolon-core/tools/build_beta_bundle.py")} <= rules(report)


def test_a_missing_or_mainless_entry_point_is_reported(tmp_path):
    report = inv.inventory(archive(tmp_path, {"eidolon-core/src/eidolon_core/cli.py": b"x = 1\n"}))
    assert ("ENTRY_POINT_MISSING", "eidolon-core") in rules(report)


@pytest.mark.parametrize("kind", ["symlink", "absolute", "dotdot", "device"])
def test_unsafe_members_refuse_the_whole_archive(tmp_path, kind):
    info = tarfile.TarInfo({"absolute": "/etc/passwd", "dotdot": "eidolon-beta-x/../escape"}.get(
        kind, "eidolon-beta-x/odd"))
    if kind == "symlink":
        info.type, info.linkname = tarfile.SYMTYPE, "/etc/passwd"
    elif kind == "device":
        info.type = tarfile.CHRTYPE
    with pytest.raises(inv.BundleRefused):
        inv.inventory(archive(tmp_path, members=[info]))


def test_the_real_archive_at_head_is_clean_and_says_whether_g265_is_documented(tmp_path):
    sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True).stdout.strip()
    if len(sha) != 40:
        pytest.skip("no git checkout")
    out = tmp_path / "beta.tar.gz"
    built = subprocess.run([sys.executable, str(REPO / "eidolon-core/tools/build_beta_bundle.py"), "--commit", sha,
                            "--output", str(out)], capture_output=True, text=True, timeout=120)
    if built.returncode != 0:
        pytest.skip("bundle not buildable here: " + built.stdout[-200:])
    r = subprocess.run([sys.executable, str(TOOL), str(out)], capture_output=True, text=True, timeout=60)
    report = json.loads(r.stdout)
    assert r.returncode == 0 and report["status"] == "CLEAN", report["findings"]
    assert all(v["present"] for v in report["entry_points"].values())
    assert all(v["present"] for v in report["documented_commands"].values())
    assert isinstance(report["storage_check_documented"], bool)        # reported, not invented


def test_the_tool_never_extracts_or_executes():
    source = TOOL.read_text(encoding="utf-8")
    for forbidden in ("extractall", "subprocess", "exec(", "eval(", "import_module", "urllib", "socket"):
        assert forbidden not in source
