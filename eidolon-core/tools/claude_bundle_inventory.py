# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : tools/claude_bundle_inventory.py
# Description : Inventaire EXPÉRIMENTAL hors ligne d'une archive bêta, sans extraction ni exécution (Claude, G264-9)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""EXPERIMENTAL, read-only. Reads an archive made by tools/build_beta_bundle.py member by member, in memory:
nothing is extracted, installed, imported or executed; nothing is downloaded. Reports relative paths and
rules only, never file content.

Checks: unsafe members (links, devices, absolute or '..' paths); forbidden material (secret patterns,
private keys, databases, model weights, corpus folders, oversized files); declared synthetic fixtures kept
apart; entry points of pyproject.toml present with a main(); commands documented INSIDE the archive whose
module or script is absent; whether the Memory storage diagnostic (G265, --check-storage) is documented.

  python tools/claude_bundle_inventory.py ARCHIVE.tar.gz [--fixtures eidolon-core/examples/]
Exit: 0 no finding, 1 findings, 2 refused archive.
"""
import argparse
import ast
import json
import re
import sys
import tarfile
import tomllib

MAX_MEMBER = 5 * 1024 * 1024
FORBIDDEN_SUFFIXES = (".pem", ".key", ".p12", ".pfx", ".sqlite", ".sqlite3", ".db", ".bin", ".safetensors",
                      ".gguf", ".pt", ".pth", ".onnx", ".ckpt", ".npz", ".age", ".env")
FORBIDDEN_PARTS = ("memory/persistent", "memory/history", "corpus", ".venv", "node_modules", "models--",
                   "__pycache__", ".git/", "credentials/")
SECRET_PATTERNS = {
    # A header alone (a string literal in code checking PEM output) is not a key: require a base64 body.
    "private_key": re.compile(rb"-----BEGIN [A-Z ]*PRIVATE KEY-----\s*[A-Za-z0-9+/=\r\n]{64,}"),
    "github_token": re.compile(rb"\bgh[pousr]_[A-Za-z0-9]{30,}"),
    "api_key": re.compile(rb"\bsk-[A-Za-z0-9]{20,}"),
    "aws_key": re.compile(rb"\bAKIA[0-9A-Z]{16}\b"),
    "bearer_literal": re.compile(rb"Bearer [A-Za-z0-9._~+/-]{32,}"),
    "bridge_token_value": re.compile(rb"EIDOLON_MEMORY_BRIDGE_TOKEN\s*=\s*['\"]?[!-~]{32,}"),
}
_DOC_MODULE = re.compile(r"python3?\s+(?:-[A-Za-z]+\s+)*-m\s+(eidolon_core(?:\.[a-z_]+)+)")
_DOC_SCRIPT = re.compile(r"python3?\s+(?:-[A-Za-z]+\s+)*((?:eidolon-core/)?tools/[a-z_]+\.py)")


class BundleRefused(ValueError):
    pass


def _strip_root(name):
    parts = name.split("/", 1)
    return parts[1] if len(parts) == 2 else ""


def inventory(path, *, fixtures=("eidolon-core/examples/",)):
    files, findings, fixture_files = {}, [], []
    try:
        archive = tarfile.open(path, "r:gz")
    except (tarfile.TarError, OSError):
        raise BundleRefused("ARCHIVE_UNREADABLE") from None
    with archive:
        for member in archive.getmembers():
            name = member.name
            if name.startswith("/") or ".." in name.split("/") or "\\" in name:
                raise BundleRefused("UNSAFE_PATH")
            if member.isdir():
                continue
            if not member.isreg():
                raise BundleRefused("LINK_OR_SPECIAL_MEMBER")
            rel = _strip_root(name)
            if member.size > MAX_MEMBER:
                findings.append(dict(rule="OVERSIZED", path=rel))
                continue
            data = archive.extractfile(member).read(MAX_MEMBER + 1)
            files[rel] = data
    for rel, data in files.items():
        lower = rel.lower()
        if lower.endswith(FORBIDDEN_SUFFIXES):
            findings.append(dict(rule="FORBIDDEN_FILE_TYPE", path=rel))
        if any(part in lower for part in FORBIDDEN_PARTS):
            findings.append(dict(rule="FORBIDDEN_LOCATION", path=rel))
        for rule, pattern in SECRET_PATTERNS.items():
            if pattern.search(data):
                findings.append(dict(rule="SECRET_" + rule.upper(), path=rel))
        if any(rel.startswith(prefix) for prefix in fixtures):
            fixture_files.append(rel)
    entry_points, documented = _entry_points(files, findings), _documented(files, findings)
    docs = b"\n".join(d for r, d in files.items() if r.endswith(".md"))
    return dict(files=len(files), fixtures=sorted(fixture_files), entry_points=entry_points,
                documented_commands=documented, storage_check_documented=b"--check-storage" in docs,
                findings=sorted(findings, key=lambda f: (f["rule"], f["path"])))


def _module_file(files, module):
    base = "eidolon-core/src/" + module.replace(".", "/")
    return next((p for p in (base + ".py", base + "/__main__.py") if p in files), None)


def _has_main(source):
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return False
    return any(isinstance(n, ast.FunctionDef) and n.name == "main" for n in tree.body)


def _uses_argparse(source):
    return b"ArgumentParser(" in source


def _entry_points(files, findings):
    raw = files.get("eidolon-core/pyproject.toml")
    if raw is None:
        findings.append(dict(rule="PYPROJECT_ABSENT", path="eidolon-core/pyproject.toml"))
        return {}
    scripts = tomllib.loads(raw.decode("utf-8")).get("project", {}).get("scripts", {})
    result = {}
    for name, target in sorted(scripts.items()):
        module, _, func = target.partition(":")
        path = _module_file(files, module)
        ok = path is not None and func == "main" and _has_main(files[path])
        result[name] = dict(module=module, present=ok, argparse=bool(path) and _uses_argparse(files[path]))
        if not ok:
            findings.append(dict(rule="ENTRY_POINT_MISSING", path=name))
    return result


def _documented(files, findings):
    seen = {}
    for rel, data in files.items():
        if not rel.endswith(".md"):
            continue
        text = data.decode("utf-8", "replace")
        for module in _DOC_MODULE.findall(text):
            path = _module_file(files, module)
            seen.setdefault(module, dict(kind="module", present=path is not None,
                                         argparse=bool(path) and _uses_argparse(files[path]), docs=[]))
            seen[module]["docs"].append(rel)
        for script in _DOC_SCRIPT.findall(text):
            key = script if script.startswith("eidolon-core/") else "eidolon-core/" + script
            seen.setdefault(key, dict(kind="script", present=key in files, argparse=False, docs=[]))
            seen[key]["docs"].append(rel)
    for key, value in seen.items():
        value["docs"] = sorted(set(value["docs"]))
        if not value["present"]:
            findings.append(dict(rule="DOCUMENTED_BUT_ABSENT", path=key))
    return dict(sorted(seen.items()))


def main(argv=None):
    parser = argparse.ArgumentParser(description="Offline inventory of a beta archive (no extraction).")
    parser.add_argument("archive")
    parser.add_argument("--fixtures", action="append", help="declared synthetic fixture prefix (repeatable)")
    args = parser.parse_args(argv)
    try:
        report = inventory(args.archive, fixtures=tuple(args.fixtures or ("eidolon-core/examples/",)))
    except BundleRefused as exc:
        print(json.dumps(dict(status="REFUSED", code=str(exc))))
        return 2
    report["status"] = "FINDINGS" if report["findings"] else "CLEAN"
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 1 if report["findings"] else 0


if __name__ == "__main__":
    sys.exit(main())
