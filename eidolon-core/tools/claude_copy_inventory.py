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
_before_final = None # test hook: runs between the inventory pass and the final coherence check
MAX_CHUNK = 64 * 1024 * 1024
_DIR = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
_FILE = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC


class InventoryRefused(ValueError):
    def __init__(self, code, path=""):
        super().__init__(f"{code}: {path}")
        self.code, self.path = code, path


def _version(st):
    return (st.st_dev, st.st_ino, st.st_mode, st.st_size, st.st_mtime_ns, st.st_ctime_ns)


def _open_root(path):
    """Walk from '/' one component at a time WITHOUT following links (G266-1): an alias or a linked
    ancestor anywhere in the path is refused, never resolved."""
    base = Path(path)
    if not base.is_absolute() or ".." in base.parts or "\0" in str(path):
        raise InventoryRefused("INVENTORY_PATH", str(path))
    fd = os.open("/", _DIR)
    try:
        for part in base.parts[1:]:
            try:
                child = os.open(part, _DIR, dir_fd=fd)
            except FileNotFoundError:
                raise InventoryRefused("INVENTORY_PATH", str(path)) from None
            except NotADirectoryError:
                raise InventoryRefused("INVENTORY_PATH", str(path)) from None
            except OSError as exc:
                if exc.errno == 40:                                  # ELOOP: a symbolic link
                    raise InventoryRefused("INVENTORY_PATH", str(path)) from None
                if exc.errno in _RESOURCE:
                    raise InventoryRefused("INVENTORY_RESOURCE", str(path)) from None
                raise InventoryRefused("INVENTORY_UNREADABLE", str(path)) from None
            os.close(fd)
            fd = child
        return fd
    except BaseException:
        os.close(fd)
        raise


def _budgets(max_entries, max_bytes, chunk):
    for name, value, high in (("max_entries", max_entries, None), ("max_bytes", max_bytes, None),
                              ("chunk", chunk, MAX_CHUNK)):
        if type(value) is not int or value < 1 or (high is not None and value > high):
            raise InventoryRefused("INVENTORY_BUDGET", name)


def inventory(root, *, max_entries, max_bytes, chunk=1 << 20, final_check=True):
    """{relative path: dict(type, size, sha256, uid, mode)}; raises InventoryRefused with a stable code.

    Guarantee (G266-2): the result describes ONE state only if nothing visible changed between each
    entry's first visit and the final check (same entries, same versions). That needs a STOPPED tree;
    it is not an atomic snapshot and detects nothing that changes and changes back in between."""
    _budgets(max_entries, max_bytes, chunk)
    result, versions, read_total = {}, {}, 0
    # G268 counter-review: depth-first, one descriptor per LEVEL (not per sibling directory), so a wide
    # tree never exhausts descriptors; exhaustion (a pathologically deep tree) is INVENTORY_RESOURCE.
    frames = [_frame("", _open_root(root), versions)]
    try:
        while frames:
            rel_dir, dfd, names = frames[-1]
            name = next(names, None)
            if name is None:
                os.close(frames.pop()[1])
                continue
            rel = f"{rel_dir}/{name}" if rel_dir else name
            if len(result) >= max_entries:
                raise InventoryRefused("INVENTORY_ENTRY_BUDGET", rel)
            try:
                st = os.stat(name, dir_fd=dfd, follow_symlinks=False)
            except FileNotFoundError:
                raise InventoryRefused("INVENTORY_RACE", rel) from None
            meta = dict(uid=st.st_uid, mode=oct(stat.S_IMODE(st.st_mode)))
            if stat.S_ISDIR(st.st_mode):
                child = _open_dir(dfd, name, rel, "INVENTORY_RACE")
                if (os.fstat(child).st_dev, os.fstat(child).st_ino) != (st.st_dev, st.st_ino):
                    os.close(child)                         # replaced between listing and opening
                    raise InventoryRefused("INVENTORY_RACE", rel)
                result[rel] = dict(type="dir", size=None, sha256=None, **meta)
                frames.append(_frame(rel, child, versions))
                continue
            if not stat.S_ISREG(st.st_mode):
                raise InventoryRefused("INVENTORY_LINK_OR_SPECIAL", rel)
            digest, read = _hash(dfd, name, rel, st, chunk, max_bytes - read_total)
            read_total += read
            result[rel] = dict(type="file", size=st.st_size, sha256=digest, **meta)
            versions[rel] = ("file", None, _version(st))
        if final_check:
            if _before_final is not None:
                _before_final()
            _final_check(root, versions, result, chunk, max_bytes)
    finally:
        for _, dfd, _ in frames:
            os.close(dfd)
    return result


_RESOURCE = (23, 24)                                     # ENFILE, EMFILE: out of descriptors, not a change


def _open_dir(dfd, name, rel, vanished):
    try:
        return os.open(name, _DIR, dir_fd=dfd)
    except OSError as exc:
        if exc.errno in _RESOURCE:
            raise InventoryRefused("INVENTORY_RESOURCE", rel) from None
        raise InventoryRefused(vanished if exc.errno in (2, 20, 40) else "INVENTORY_UNREADABLE", rel) from None


def _list(dfd, rel_dir):
    try:
        return os.listdir(dfd)                          # duplicates the descriptor internally
    except OSError as exc:
        raise InventoryRefused("INVENTORY_RESOURCE" if exc.errno in _RESOURCE else "INVENTORY_UNREADABLE",
                               rel_dir) from None


def _frame(rel_dir, dfd, versions):
    """List a directory once and record its version; the caller owns `dfd` from here on."""
    try:
        names = sorted(_list(dfd, rel_dir))
        versions[rel_dir or "."] = ("dir", tuple(names), _version(os.fstat(dfd)))
    except BaseException:
        os.close(dfd)
        raise
    return rel_dir, dfd, iter(names)


def _hash(dfd, name, rel, st, chunk, remaining, *, run_hook=True):
    if st.st_size > remaining:
        raise InventoryRefused("INVENTORY_BYTE_BUDGET", rel)
    try:
        fd = os.open(name, _FILE, dir_fd=dfd)
    except OSError as exc:
        if exc.errno in _RESOURCE:
            raise InventoryRefused("INVENTORY_RESOURCE", rel) from None
        raise InventoryRefused("INVENTORY_RACE" if exc.errno in (2, 40) else "INVENTORY_UNREADABLE", rel) from None
    try:
        if _version(os.fstat(fd)) != _version(st):
            raise InventoryRefused("INVENTORY_RACE", rel)
        digest, read = hashlib.sha256(), 0
        while True:
            # Never read more than the size seen at stat time + 1 byte, nor beyond the byte budget.
            part = os.read(fd, min(chunk, st.st_size + 1 - read))
            if not part:
                break
            read += len(part)
            if read > st.st_size:
                raise InventoryRefused("INVENTORY_RACE", rel)        # grew while read
            digest.update(part)
        if run_hook and _after_hash is not None:
            _after_hash(rel)
        os.lseek(fd, 0, os.SEEK_SET)
        repeated, repeated_bytes = hashlib.sha256(), 0
        while repeated_bytes <= st.st_size:
            part = os.read(fd, min(chunk, st.st_size + 1 - repeated_bytes))
            if not part: break
            repeated_bytes += len(part); repeated.update(part)
        if repeated_bytes != read or repeated.digest() != digest.digest():
            raise InventoryRefused("INVENTORY_RACE", rel)
        if read != st.st_size or _version(os.fstat(fd)) != _version(st):
            raise InventoryRefused("INVENTORY_RACE", rel)
    except PermissionError:
        raise InventoryRefused("INVENTORY_UNREADABLE", rel) from None
    finally:
        os.close(fd)
    try:
        if _version(os.stat(name, dir_fd=dfd, follow_symlinks=False)) != _version(st):
            raise InventoryRefused("INVENTORY_RACE", rel)
    except FileNotFoundError:
        raise InventoryRefused("INVENTORY_RACE", rel) from None
    return digest.hexdigest(), read


def _final_check(root, versions, result, chunk, max_bytes):
    """Content and identity second pass, using single-component opens like the hash pass.

    G268: O_NOFOLLOW protects only the LAST component. Never pass a nested relative
    path to stat/open: an already-checked ancestor could have become a link since.
    Validate directory identity before listing it, including substituted real dirs.
    G268 counter-review: depth-first like the first pass (one descriptor per level); a directory's
    version is checked again AFTER its whole subtree; descriptor exhaustion is INVENTORY_RESOURCE.
    """
    frames = []; remaining = max_bytes
    try:
        frames.append(_checked_frame("", _open_root(root), versions))
        while frames:
            rel_dir, dfd, names = frames[-1]
            name = next(names, None)
            if name is None:
                if _version(os.fstat(dfd)) != versions[rel_dir or "."][2]:
                    raise InventoryRefused("INVENTORY_CHANGED", rel_dir)
                # Open from the trusted path again: an already-open ancestor may
                # have been renamed while its timestamps remained unchanged.
                try:
                    current = _open_root(str(Path(root) / rel_dir))
                    try:
                        if _version(os.fstat(current)) != versions[rel_dir or "."][2]:
                            raise InventoryRefused("INVENTORY_CHANGED", rel_dir)
                    finally: os.close(current)
                except InventoryRefused as exc:
                    if exc.code == "INVENTORY_RESOURCE": raise
                    raise InventoryRefused("INVENTORY_CHANGED", rel_dir) from None
                os.close(frames.pop()[1])
                continue
            rel = f"{rel_dir}/{name}" if rel_dir else name
            kind, _, expected = versions[rel]
            try:
                st = os.stat(name, dir_fd=dfd, follow_symlinks=False)
            except OSError:
                raise InventoryRefused("INVENTORY_CHANGED", rel) from None
            if _version(st) != expected:
                raise InventoryRefused("INVENTORY_CHANGED", rel)
            if kind == "dir":
                frames.append(_checked_frame(rel, _open_dir(dfd, name, rel, "INVENTORY_CHANGED"), versions))
            else:
                try:
                    digest, count = _hash(dfd, name, rel, st, chunk, remaining, run_hook=False)
                except InventoryRefused as exc:
                    if exc.code == "INVENTORY_RACE":
                        raise InventoryRefused("INVENTORY_CHANGED", rel) from None
                    raise
                remaining -= count
                if digest != result[rel]["sha256"]:
                    raise InventoryRefused("INVENTORY_CHANGED", rel)
    finally:
        for _, dfd, _ in frames:
            os.close(dfd)


def _checked_frame(rel_dir, dfd, versions):
    """Identity and version BEFORE listing (never list a substituted directory), then same names."""
    try:
        _, names, version = versions[rel_dir or "."]
        if _version(os.fstat(dfd)) != version or tuple(sorted(_list(dfd, rel_dir))) != names:
            raise InventoryRefused("INVENTORY_CHANGED", rel_dir)
    except BaseException:
        os.close(dfd)
        raise
    return rel_dir, dfd, iter(names)


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
        # Unreadable is not a refusal of the tree's shape: the state is unknown (G262 contract kept).
        verdict = "UNKNOWN" if exc.code in ("INVENTORY_UNREADABLE", "INVENTORY_RESOURCE") else "REFUSED"
        print(json.dumps(dict(verdict=verdict, code=exc.code, path=exc.path), ensure_ascii=False))
        return 2
    except OSError as exc:                       # anything not mapped above: stable, content-free
        print(json.dumps(dict(verdict="UNKNOWN", code="INVENTORY_UNREADABLE", errno=exc.errno)))
        return 2
    report = compare(a, b)
    report["verdict"] = "IDENTICAL" if report["identical"] else "DIFFERENT"
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report["identical"] else 1


if __name__ == "__main__":
    sys.exit(main())
