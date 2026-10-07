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
               "eidolon-core/docs/HTTP-RECEIPTS.md", "eidolon-core/docs/HTTP-PREFLIGHT.md",
               "eidolon-core/docs/BETA-LOCAL-CHECK.md", "eidolon-core/docs/READ-TOKEN.md")
# Include newer contracts when present without rejecting older valid bundles.
OPTIONAL_FILES = ("eidolon-core/docs/QUERY-CLEANUP.md", "eidolon-core/docs/RESEARCH-GUARD.md",
                  "eidolon-core/docs/INVOCATION-BUDGET.md", "eidolon-core/docs/QUERY-HISTORY.md",
                  "eidolon-core/docs/RESEARCH-MISSIONS.md", "eidolon-core/docs/RUNTIME-INSPECTION.md", "eidolon-core/docs/RECOVERY-REVIEW.md",
                  "eidolon-core/docs/DIAGNOSTIC-WORKFLOW.md", "eidolon-core/docs/RESEARCH-ARCHIVES.md", "eidolon-core/docs/HTTP-RESEARCH-ARCHIVES.md")
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
    return path in ALLOW_FILES or path in OPTIONAL_FILES or path.startswith(ALLOW_PREFIXES)


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
    """Check bounded archive structure and manifest consistency, not authenticity."""
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise BundleError("duplicate JSON key")
            result[key] = value
        return result

    with tarfile.open(path, "r:gz") as tar:
        members, names, total = [], set(), 0
        for member in tar:
            if (not member.isfile() or member.name in names or member.size > 16 * 1024 * 1024
                    or len(members) >= 1024):
                raise BundleError("invalid, duplicate or oversized member")
            total += member.size
            if total > 64 * 1024 * 1024:
                raise BundleError("archive exceeds verification budget")
            names.add(member.name)
            members.append(member)
        if not members:
            raise BundleError("empty archive")
        root = members[0].name.split("/")[0]
        manifest_name = root + "/MANIFEST.json"
        if manifest_name not in names:
            raise BundleError("manifest missing")
        manifest = json.loads(tar.extractfile(manifest_name).read(), object_pairs_hook=unique)
        if (type(manifest) is not dict or manifest.get("protocol") != PROTOCOL
                or type(manifest.get("commit")) is not str or not SHA.fullmatch(manifest["commit"])
                or type(manifest.get("tree")) is not str or not SHA.fullmatch(manifest["tree"])
                or root != "eidolon-beta-" + manifest["commit"][:12] or manifest.get("root") != root
                or type(manifest.get("commit_time")) is not int or manifest["commit_time"] < 0
                or type(manifest.get("files")) is not list):
            raise BundleError("invalid manifest")
        expected = {}
        for f in manifest["files"]:
            if type(f) is not dict or set(f) != {"path", "sha256", "size", "mode"}:
                raise BundleError("invalid file description")
            name = f["path"]
            if (type(name) is not str or not name.isprintable() or "\\" in name
                    or str(PurePosixPath(name)) != name or PurePosixPath(name).is_absolute()
                    or ".." in PurePosixPath(name).parts or not allowed(name) or FORBIDDEN.search(name)):
                raise BundleError("unsafe or non allow-listed path in manifest")
            if (name in expected or type(f["sha256"]) is not str or not re.fullmatch(r"[0-9a-f]{64}", f["sha256"])
                    or type(f["size"]) is not int or not 0 <= f["size"] <= 16 * 1024 * 1024
                    or type(f["mode"]) is not int or f["mode"] not in (0o644, 0o755)):
                raise BundleError("invalid or duplicate manifest entry")
            expected[name] = f
        if not set(ALLOW_FILES) <= expected.keys():
            raise BundleError("required files missing from manifest")
        if names != {root + "/" + n for n in expected} | {manifest_name, root + "/START-HERE.md"}:
            raise BundleError("archive and manifest member sets differ")
        for m in members:
            name = m.name[len(root) + 1:]
            if (m.uid != 0 or m.gid != 0 or m.uname or m.gname or m.mtime != manifest["commit_time"]):
                raise BundleError("member metadata mismatch")
            if name == "MANIFEST.json":
                if m.mode != 0o644:
                    raise BundleError("manifest mode mismatch")
                continue
            data = tar.extractfile(m).read()
            if name == "START-HERE.md":
                if m.mode != 0o644 or data != start_here(manifest["commit"]).encode():
                    raise BundleError("start document mismatch")
                continue
            f = expected[name]
            if len(data) != f["size"] or m.mode != f["mode"] or hashlib.sha256(data).hexdigest() != f["sha256"]:
                raise BundleError("member size, mode or hash mismatch")
    return {"verified": True, "commit": manifest["commit"], "files": len(expected),
            "authenticity_verified": False}


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
