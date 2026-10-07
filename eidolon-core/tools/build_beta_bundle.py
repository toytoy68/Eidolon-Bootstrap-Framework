# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : build_beta_bundle.py
# Description : Archive de sources bêta reproductible depuis un commit Git explicite (C-TASK-G044)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Build a deterministic .tar.gz of the beta sources from ONE explicit commit.

    python3 eidolon-core/tools/build_beta_bundle.py --commit <40-hex sha> --output <new file.tar.gz>

Everything is read from Git objects (git ls-tree / git cat-file), never from the working
tree: untracked files, local state, tokens and caches cannot enter. Only tracked paths in
ALLOW are packed; a symlink, a submodule or a forbidden name inside them is an error.
Same commit -> same bytes (sorted entries, fixed owner/mode/mtime, gzip mtime 0).
The output must not exist; nothing is overwritten. No binary, no install, no publication.
This development archive is not a beta qualification.
"""
import argparse
import gzip
import hashlib
import io
import json
import os
from pathlib import PurePosixPath
import re
import subprocess
import sys
import tarfile

PROTOCOL = "eidolon-beta-source-bundle/1"
# Tracked paths (relative to the repository root) that may enter the archive.
ALLOW_PREFIXES = ("eidolon-core/src/eidolon_core/", "eidolon-core/desktop/connected/launchers/")
ALLOW_FILES = ("LICENSE", "eidolon-core/README.md", "eidolon-core/pyproject.toml",
               "eidolon-core/desktop/connected/index.html", "eidolon-core/desktop/connected/app.js",
               "eidolon-core/desktop/connected/style.css", "eidolon-core/desktop/connected/README.md",
               "eidolon-core/docs/BETA-ACCEPTANCE.md", "eidolon-core/docs/BETA-FIXTURE.md",
               "eidolon-core/docs/BETA-SERVER-PC.md", "eidolon-core/docs/HTTP-READ-API.md",
               "eidolon-core/docs/HTTP-RECEIPTS.md", "eidolon-core/docs/HTTP-PREFLIGHT.md")
# Names refused even when tracked inside the allow-list: state, secrets, caches, bytecode.
FORBIDDEN = re.compile(r"(^|/)(__pycache__|\.git|\.env|read-token|[^/]*\.(pyc|pyo|sqlite3?|db|key|pem|p12|log))(/|$)", re.I)
SHA = re.compile(r"[0-9a-f]{40}")


class BundleError(Exception):
    pass


def git(repo, *args, binary=False):
    done = subprocess.run(["git", "-C", str(repo), *args], capture_output=True)
    if done.returncode != 0:
        raise BundleError("git " + args[0] + " failed: " + done.stderr.decode(errors="replace").strip()[:200])
    return done.stdout if binary else done.stdout.decode()


def allowed(path):
    return path in ALLOW_FILES or path.startswith(ALLOW_PREFIXES)


def collect(repo, commit):
    if not SHA.fullmatch(commit or ""):
        raise BundleError("an explicit full 40-hex commit SHA is required (no branch, tag or short SHA)")
    if git(repo, "cat-file", "-t", commit).strip() != "commit":
        raise BundleError("not a commit: " + commit)
    commit_time = int(git(repo, "show", "-s", "--format=%ct", commit).strip())
    tree = git(repo, "rev-parse", commit + "^{tree}").strip()
    entries = []
    for line in git(repo, "ls-tree", "-r", "-z", "--full-tree", commit).split("\0"):
        if not line:
            continue
        meta, path = line.split("\t", 1)
        mode, kind, oid = meta.split()
        if not allowed(path):
            continue
        if kind != "blob" or mode not in ("100644", "100755"):
            raise BundleError(f"symlink or submodule refused: {path} (mode {mode})")
        if FORBIDDEN.search(path):
            raise BundleError("forbidden name in allow-list: " + path)
        if PurePosixPath(path).is_absolute() or ".." in PurePosixPath(path).parts:
            raise BundleError("unsafe path: " + path)
        entries.append((path, mode, oid))
    missing = [f for f in ALLOW_FILES if f not in {p for p, _, _ in entries}]
    if missing:
        raise BundleError("allow-listed files missing from the commit: " + ", ".join(missing))
    entries.sort()
    files = []
    for path, mode, oid in entries:
        data = git(repo, "cat-file", "blob", oid, binary=True)
        files.append({"path": path, "mode": 0o755 if mode == "100755" else 0o644, "data": data,
                      "sha256": hashlib.sha256(data).hexdigest(), "size": len(data)})
    return commit_time, tree, files


def start_here(commit):
    return f"""# Eidolon Core — archive de sources bêta

Archive de **développement** construite depuis le commit `{commit}`.
Elle ne qualifie pas la bêta et ne remplace aucune recette.

Contenu : sources Python de Core (`eidolon-core/src`), client connecté
(`eidolon-core/desktop/connected` : `index.html`, `app.js`, `style.css`), lanceur
candidat PowerShell, documentation de recette. Pas de tests, pas de scripts
Bootstrap, aucun état, jeton, cache ou binaire.

1. Vérifier l'archive : comparer son SHA-256 à celui publié avec elle, puis
   les empreintes de `MANIFEST.json` (outil : `--verify`).
2. Sur le serveur Linux (Python 3.11+), extraire dans un dossier neuf, puis
   suivre `eidolon-core/docs/BETA-FIXTURE.md` et `eidolon-core/docs/BETA-ACCEPTANCE.md`
   depuis `eidolon-core/`, avec `PYTHONPATH=src`. Assets du client :
   `--web-root desktop/connected`.
3. Sur le PC Windows : tunnel SSH selon la recette, ou lanceur candidat
   `eidolon-core/desktop/connected/launchers/eidolon-tunnel.ps1`.

Limites : non essayé sur la VM Debian 13 ni sous Windows ; pas d'installation,
pas de service, pas de mise à jour automatique ; aucune commande distante.
"""


def build(repo, commit, output):
    commit_time, tree, files = collect(repo, commit)
    root = "eidolon-beta-" + commit[:12]
    manifest = {"protocol": PROTOCOL, "commit": commit, "tree": tree, "commit_time": commit_time,
                "root": root, "files": [{k: f[k] for k in ("path", "sha256", "size", "mode")} for f in files],
                "excluded": "everything not in ALLOW_FILES/ALLOW_PREFIXES; untracked files never read",
                "qualifies_beta": False, "contains_state_or_token": False}
    extra = [("MANIFEST.json", (json.dumps(manifest, ensure_ascii=False, indent=1, sort_keys=True) + "\n").encode()),
             ("START-HERE.md", start_here(commit).encode())]
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w", format=tarfile.PAX_FORMAT) as tar:
        def add(name, data, mode):
            info = tarfile.TarInfo(root + "/" + name)
            info.size, info.mode, info.mtime = len(data), mode, commit_time
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            tar.addfile(info, io.BytesIO(data))
        for name, data in extra:
            add(name, data, 0o644)
        for f in files:
            add(f["path"], f["data"], f["mode"])
    compressed = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=compressed, mtime=0, compresslevel=9) as gz:
        gz.write(raw.getvalue())
    payload = compressed.getvalue()
    with open(output, "xb") as handle:          # never overwrite an existing file
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    return {"output": str(output), "sha256": hashlib.sha256(payload).hexdigest(), "bytes": len(payload),
            "files": len(files), "commit": commit, "root": root}


def verify(path):
    """Re-read an archive: every manifest hash must match, and nothing else may be present."""
    with tarfile.open(path, "r:gz") as tar:
        members = tar.getmembers()
        root = members[0].name.split("/")[0]
        manifest = json.loads(tar.extractfile(root + "/MANIFEST.json").read())
        for f in manifest["files"]:
            parts = PurePosixPath(f["path"]).parts
            if PurePosixPath(f["path"]).is_absolute() or ".." in parts or not allowed(f["path"]):
                raise BundleError("unsafe or non allow-listed path in manifest: " + f["path"])
        expected = {root + "/" + f["path"]: f["sha256"] for f in manifest["files"]}
        seen = set()
        for m in members:
            if not m.isfile() or m.name in (root + "/MANIFEST.json", root + "/START-HERE.md"):
                if not m.isfile():
                    raise BundleError("non-file member: " + m.name)
                continue
            if m.name not in expected:
                raise BundleError("member not in manifest: " + m.name)
            if hashlib.sha256(tar.extractfile(m).read()).hexdigest() != expected[m.name]:
                raise BundleError("hash mismatch: " + m.name)
            seen.add(m.name)
        if seen != set(expected):
            raise BundleError("manifest lists missing members")
    return {"verified": True, "commit": manifest["commit"], "files": len(seen)}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Eidolon Core — archive de sources bêta reproductible")
    parser.add_argument("--repo", default=".", help="repository (any folder inside it)")
    parser.add_argument("--commit", help="full 40-hex commit SHA")
    parser.add_argument("--output", help="new .tar.gz path; must not exist")
    parser.add_argument("--verify", help="verify an existing archive against its manifest")
    args = parser.parse_args(argv)
    try:
        if args.verify:
            result = verify(args.verify)
        else:
            if not args.commit or not args.output:
                parser.error("--commit and --output are required")
            repo = git(args.repo, "rev-parse", "--show-toplevel").strip()
            result = build(repo, args.commit, args.output)
    except (BundleError, FileExistsError, OSError, tarfile.TarError, ValueError, KeyError) as exc:
        print(json.dumps({"status": "REFUSED", "error": type(exc).__name__, "detail": str(exc)[:300]}, ensure_ascii=False))
        return 2
    print(json.dumps(dict(result, status="OK"), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
