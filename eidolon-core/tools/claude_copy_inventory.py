# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : tools/claude_copy_inventory.py
# Description : Inventaire EXPÉRIMENTAL hors ligne comparant un original et sa copie (Claude, G262-4)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""EXPERIMENTAL, read-only. Compares two directory trees for the Memory migration-by-copy (proposal:
docs/proposals/2026-10-15-memory-service-account.md, step 4). It never copies, moves, changes or prints
file content: only relative paths, types, sizes and SHA-256. Owner and mode are reported SEPARATELY,
since the copy is expected to change them. Links and special files are refused. A file that changes while
it is hashed is a RACE, never a match. Budgets are explicit; exceeding one is UNKNOWN, never a pass.

  python tools/claude_copy_inventory.py --source A --copy B --max-entries N --max-bytes N [--json]
Exit: 0 identical content, 1 differences, 2 refused/unknown.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import sys

_after_hash = None   # test hook: runs after a file is hashed, before its second stat


class InventoryRefused(ValueError):
    def __init__(self, code, path=""):
        super().__init__(f"{code}: {path}")
        self.code, self.path = code, path


def _version(st):
    return (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns)


def inventory(root, *, max_entries, max_bytes, chunk=1 << 20):
    """{relative path: dict(type, size, sha256, uid, mode)}; raises InventoryRefused with a stable code."""
    for name, value in (("max_entries", max_entries), ("max_bytes", max_bytes)):
        if type(value) is not int or value < 1:
            raise InventoryRefused("INVENTORY_BUDGET", name)
    base = Path(root)
    if not base.is_absolute() or ".." in base.parts:
        raise InventoryRefused("INVENTORY_PATH", str(root))
    try:
        top = os.lstat(base)
    except FileNotFoundError:
        raise InventoryRefused("INVENTORY_PATH", str(root)) from None
    if not stat.S_ISDIR(top.st_mode):
        raise InventoryRefused("INVENTORY_PATH", str(root))
    result, pending, hashed = {}, [base], 0
    while pending:
        directory = pending.pop()
        with os.scandir(directory) as entries:
            for entry in entries:
                rel = Path(entry.path).relative_to(base).as_posix()
                if len(result) >= max_entries:
                    raise InventoryRefused("INVENTORY_ENTRY_BUDGET", rel)
                st = os.lstat(entry.path)
                meta = dict(uid=st.st_uid, mode=oct(stat.S_IMODE(st.st_mode)))
                if stat.S_ISDIR(st.st_mode):
                    result[rel] = dict(type="dir", size=None, sha256=None, **meta)
                    pending.append(Path(entry.path))
                    continue
                if not stat.S_ISREG(st.st_mode):
                    raise InventoryRefused("INVENTORY_LINK_OR_SPECIAL", rel)
                hashed += st.st_size
                if hashed > max_bytes:
                    raise InventoryRefused("INVENTORY_BYTE_BUDGET", rel)
                digest = hashlib.sha256()
                fd = os.open(entry.path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
                try:
                    opened = os.fstat(fd)
                    if _version(opened) != _version(st):
                        raise InventoryRefused("INVENTORY_RACE", rel)
                    read = 0
                    while read <= st.st_size:
                        part = os.read(fd, chunk)
                        if not part:
                            break
                        read += len(part)
                        digest.update(part)
                    if _after_hash is not None:
                        _after_hash(rel)
                    if read != st.st_size or _version(os.fstat(fd)) != _version(st):
                        raise InventoryRefused("INVENTORY_RACE", rel)
                finally:
                    os.close(fd)
                try:
                    if _version(os.lstat(entry.path)) != _version(st):
                        raise InventoryRefused("INVENTORY_RACE", rel)
                except FileNotFoundError:
                    raise InventoryRefused("INVENTORY_RACE", rel) from None
                result[rel] = dict(type="file", size=st.st_size, sha256=digest.hexdigest(), **meta)
    return result


def compare(source, copy):
    """Content differences (what must be identical) and metadata differences (reported, expected to vary)."""
    content = dict(missing=sorted(set(source) - set(copy)), added=sorted(set(copy) - set(source)), changed=[])
    metadata = []
    for rel in sorted(set(source) & set(copy)):
        a, b = source[rel], copy[rel]
        if (a["type"], a["size"], a["sha256"]) != (b["type"], b["size"], b["sha256"]):
            content["changed"].append(rel)
        if (a["uid"], a["mode"]) != (b["uid"], b["mode"]):
            metadata.append(dict(path=rel, source=dict(uid=a["uid"], mode=a["mode"]),
                                 copy=dict(uid=b["uid"], mode=b["mode"])))
    identical = not any(content.values())
    return dict(identical=identical, content=content, metadata=metadata,
                entries=dict(source=len(source), copy=len(copy)))


def main(argv=None):
    parser = argparse.ArgumentParser(description="Compare a tree and its copy (read-only, no content shown).")
    parser.add_argument("--source", required=True)
    parser.add_argument("--copy", required=True)
    parser.add_argument("--max-entries", type=int, required=True)
    parser.add_argument("--max-bytes", type=int, required=True)
    args = parser.parse_args(argv)
    try:
        a = inventory(args.source, max_entries=args.max_entries, max_bytes=args.max_bytes)
        b = inventory(args.copy, max_entries=args.max_entries, max_bytes=args.max_bytes)
    except InventoryRefused as exc:
        print(json.dumps(dict(verdict="REFUSED", code=exc.code, path=exc.path), ensure_ascii=False))
        return 2
    except OSError as exc:
        print(json.dumps(dict(verdict="UNKNOWN", code="INVENTORY_UNREADABLE", errno=exc.errno)))
        return 2
    report = compare(a, b)
    report["verdict"] = "IDENTICAL" if report["identical"] else "DIFFERENT"
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report["identical"] else 1


if __name__ == "__main__":
    sys.exit(main())
