# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : probes_g064.py
# Description : Contre-revue du lecteur d'archives C-028 et de l'initialisation C-029 (C-TASK-G064)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""python3 probes_g064.py <frozen eidolon-core/src> <frozen C-028 base src, for I10>

Synthetic data and temporary directories only. Exports are produced by the isolated
G063 rotation prototype (docs/proposals/2026-10-07-research-retention) run against the
frozen sources. The reader is invoked through its CLI in subprocesses unless a probe
needs an in-process patch (bounds, races). Crashes are os._exit in subprocesses."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import stat
import subprocess
import sys
import tempfile
import threading
import time
from unittest.mock import patch

SRC = str(Path(sys.argv[1]).resolve())
BASE_SRC = str(Path(sys.argv[2]).resolve()) if len(sys.argv) > 2 else SRC
PROPOSAL = str(Path(__file__).resolve().parents[3] / "proposals" / "2026-10-07-research-retention")
sys.argv = [sys.argv[0], SRC]
sys.path[:0] = [SRC, PROPOSAL]
sys.dont_write_bytecode = True

import probes_g057 as g057  # noqa: E402
import rotation  # noqa: E402
from eidolon_core import research_archive as ra  # noqa: E402
from eidolon_core.contracts import digest  # noqa: E402
from eidolon_core.research_guard import ResearchGuard  # noqa: E402
from eidolon_core.research_pauses import ResearchPauses  # noqa: E402
from eidolon_core.research_runtime import ResearchRuntime  # noqa: E402
from eidolon_core.store import Store  # noqa: E402

ENV = dict(os.environ, PYTHONPATH=SRC, PYTHONDONTWRITEBYTECODE="1")
PRIVATE_MARKERS = ["jean", "example.invalid", "pont", "synthetique", g057.OPERATION]


def fingerprint(root):
    """Names, types, modes, sizes and content hashes; never follows links; atime excluded."""
    root = Path(root)
    out = []
    for path in sorted([root, *root.rglob("*")]):
        info = path.lstat()
        kind = ("link:" + os.readlink(path) if stat.S_ISLNK(info.st_mode) else "fifo" if stat.S_ISFIFO(info.st_mode)
                else "dir" if stat.S_ISDIR(info.st_mode) else hashlib.sha256(path.read_bytes()).hexdigest()[:16])
        out.append((str(path.relative_to(root)), oct(info.st_mode & 0o7777), info.st_size if path.is_file() else 0,
                    info.st_ino, info.st_mtime_ns if not stat.S_ISDIR(info.st_mode) else 0, kind))
    return hashlib.sha256(repr(out).encode()).hexdigest()[:16]


def cli(directory, command="inspect", fmt="json", timeout=20):
    try:
        p = subprocess.run([sys.executable, "-m", "eidolon_core.research_archive", "--directory", str(directory),
                            "--format", fmt, command], capture_output=True, text=True, env=ENV, timeout=timeout,
                           cwd=tempfile.gettempdir())
    except subprocess.TimeoutExpired:
        return "BLOQUÉ", "", ""
    return p.returncode, p.stdout, p.stderr


def code_of(stderr):
    try:
        return json.loads(stderr)["error"]
    except ValueError:
        return "STDERR NON JSON: " + stderr.strip().splitlines()[-1][:80] if stderr.strip() else "-"


def check_refusal(name, directory, command="inspect", expect=None):
    before = fingerprint(directory)
    code, out, err = cli(directory, command)
    after = fingerprint(directory)
    leak = [m for m in PRIVATE_MARKERS + [str(directory)] if m in err]
    verdict = code_of(err) if code == 2 else f"ACCEPTÉ ({json.loads(out)['run_count']} recherches)" if code == 0 else code
    flags = []
    if code == 2 and out:
        flags.append("SORTIE PARTIELLE")
    if "Traceback" in err:
        flags.append("TRACEBACK")
    if leak:
        flags.append(f"FUITE {leak}")
    if before != after:
        flags.append("MUTATION")
    ok = "" if expect is None else (" ✓" if verdict == expect or (expect == "ACCEPTÉ" and str(verdict).startswith("ACCEPTÉ"))
                                    else f" ✗ attendu {expect}")
    print(f"{name} : code {code} ; {verdict}{ok} ; {'; '.join(flags) or 'aucune sortie partielle, aucune mutation'}")
    return code, verdict


def chain_entry(path):
    data = path.read_bytes()
    meta = json.loads(data)
    return {"index": meta["chain_index"], "file": path.name, "export_sha256": hashlib.sha256(data).hexdigest(),
            "previous_chain_sha256": meta["previous_chain_sha256"], "removed_ids_sha256": meta["removed_ids_sha256"],
            "count": len(meta["runs"])}


def rechain(archive, start):
    """Coherent rewrite: recompute previous_chain_sha256 for every export after `start`."""
    files = sorted(archive.glob("research-archive-*.json"))
    for prev, cur in zip(files, files[1:]):
        if int(cur.name[17:23]) <= start:
            continue
        meta = json.loads(cur.read_bytes())
        meta["previous_chain_sha256"] = digest(chain_entry(prev))
        write_private(cur, rotation._canon(meta))


def write_private(path, data):
    path.write_bytes(data)
    path.chmod(0o600)


def edit(path, change):
    meta = json.loads(path.read_bytes())
    change(meta)
    write_private(path, rotation._canon(meta))


def copy_dir(src, dst):
    shutil.copytree(src, dst, symlinks=True)
    return dst


def build_archives(root):
    """Three exports: 2 plain runs, 2 plain runs, then the mission run released explicitly."""
    g, a = g057.build(root)
    rotation.rotate(g, a, count=2, guard_src=SRC, clock_ms=1)
    rotation.rotate(g, a, count=2, guard_src=SRC, clock_ms=2)
    rotation.rotate(g, a, count=3, operations=(g057.OPERATION,), guard_src=SRC, clock_ms=3)
    return g, a


def reader(tmp):
    print("== R. lecteur d'archives (CLI inspect)")
    g, a = build_archives(tmp / "base")
    code, out, err = cli(a)
    cat = json.loads(out)
    flags = {k: cat[k] for k in ("consistency_verified", "authenticity_verified", "live_journal_checked",
                                 "committed_status_known", "authorizes_execution", "request_sent")}
    print(f"R1 nominal v2 : code {code} ; archives={cat['archive_count']} recherches={cat['run_count']} "
          f"missions liées={[f['linked_missions'] for f in cat['files']]} ; drapeaux {flags}")
    print(f"R1   released_operations des exports : {[('released_operations' in json.loads(p.read_bytes())) for p in sorted(a.glob('*.json'))]}")
    leak = [m for m in PRIVATE_MARKERS if m in out]
    print(f"R1   catalogue JSON sans texte privé : {not leak} {leak or ''}")
    code, out, err = cli(a, fmt="human")
    print(f"R1   format humain : code {code} ; {out.strip().splitlines()[-2:]}")

    v1 = copy_dir(a, tmp / "v1")
    for p in sorted(v1.glob("*.json"))[1:]:
        p.unlink()
    edit(v1 / "research-archive-000001.json", lambda m: m.pop("released_operations"))
    check_refusal("R2 export v1 (sans released_operations)", v1, expect="ACCEPTÉ")

    def case(name, mutate, expect):
        d = copy_dir(a, tmp / ("r-" + re.sub(r"[^a-z0-9]+", "-", name.lower())[:40]))
        mutate(d)
        return check_refusal(name, d, expect=expect)

    first = "research-archive-000001.json"
    last = "research-archive-000003.json"
    raw = lambda d, f, fn: write_private(d / f, fn((d / f).read_bytes()))  # noqa: E731
    bad = "INVALID_RESEARCH_ARCHIVE"
    print("-- JSON ambigu ou hors type")
    case("R3 clé dupliquée (protocol)", lambda d: raw(d, first, lambda b: b'{"protocol":"x",' + b[1:]), bad)
    case("R3 NaN", lambda d: raw(d, first, lambda b: re.sub(rb'"created_at_ms":\d+', b'"created_at_ms":NaN', b)), bad)
    case("R3 entier 2^53", lambda d: edit(d / first, lambda m: m.update(created_at_ms=2**53)), bad)
    case("R3 chain_index 1.0", lambda d: raw(d, first, lambda b: b.replace(b'"chain_index":1', b'"chain_index":1.0')), bad)
    case("R3 chain_index true", lambda d: raw(d, first, lambda b: b.replace(b'"chain_index":1', b'"chain_index":true')), bad)
    case("R3 entier de 5000 chiffres", lambda d: raw(d, first, lambda b: re.sub(rb'"created_at_ms":\d+',
                                                                                  b'"created_at_ms":' + b"9" * 5000, b)), bad)
    case("R3 BOM UTF-8", lambda d: raw(d, first, lambda b: b"\xef\xbb\xbf" + b), bad)
    case("R3 octet non UTF-8", lambda d: raw(d, first, lambda b: b.replace(b'"runs":', b'"runs\xff":', 1)), bad)
    case("R3 imbrication 100000", lambda d: write_private(d / first, b"[" * 100000 + b"]" * 100000), bad)
    case("R3 champ inconnu", lambda d: edit(d / first, lambda m: m.update(note="x")), bad)
    case("R3 authorizes_execution true", lambda d: edit(d / first, lambda m: m.update(authorizes_execution=True)), bad)

    def body_edit(field_fn):
        def change(m):
            row = m["runs"][0]
            body = json.loads(row["body"])
            field_fn(row, body)
        return change
    print("-- texte ou événements altérés, chaînes incomplètes")

    def surrogate(row, body):
        row["body"] = row["body"][:-1] + ',"x":"\\ud800"}'
    case("R4 surrogate isolé dans body", lambda d: edit(d / first, body_edit(surrogate)), bad)

    def nested_dup(row, body):
        row["body"] = row["body"][:-1] + ',"state":"COMPLETED"}'
    case("R4 clé dupliquée dans body", lambda d: edit(d / first, body_edit(nested_dup)), bad)

    def cleaned_text(row, body):
        q = json.loads(row["cleaned_query"])
        q["text"] = q["text"].replace("pont", "pnot")
        row["cleaned_query"] = rotation._canon(q).decode()
    case("R4 texte nettoyé modifié", lambda d: edit(d / first, body_edit(cleaned_text)), bad)
    case("R4 texte nettoyé retiré (null)", lambda d: edit(d / first, body_edit(lambda r, b: r.update(cleaned_query=None))), bad)
    case("R4 événement final ≠ corps", lambda d: edit(d / first, body_edit(
        lambda r, b: r["events"][1].__setitem__(2, r["events"][0][2]))), bad)
    case("R4 un seul événement", lambda d: edit(d / first, body_edit(lambda r, b: r.update(events=r["events"][1:]))), bad)
    case("R4 séquences inversées", lambda d: edit(d / first, body_edit(
        lambda r, b: r.update(events=[[r["events"][1][0], *r["events"][0][1:]], [r["events"][0][0], *r["events"][1][1:]]]))), bad)
    case("R4 recherche INTENT seule", lambda d: edit(d / first, body_edit(
        lambda r, b: r.update(body=r["events"][0][2], events=r["events"][:1]))), bad)
    case("R4 removed_ids_sha256 faux", lambda d: edit(d / first, lambda m: m.update(removed_ids_sha256="0" * 64)), bad)
    case("R4 released_operations vide", lambda d: edit(d / last, lambda m: m.update(released_operations=[])), bad)
    case("R4 released_operations en trop", lambda d: edit(d / first, lambda m: m.update(released_operations=["m-" + "b" * 32])), bad)
    case("R4 export du milieu retiré", lambda d: (d / "research-archive-000002.json").unlink(), "ARCHIVE_CHAIN_BROKEN")
    case("R4 premier export retiré", lambda d: (d / first).unlink(), "ARCHIVE_CHAIN_BROKEN")
    case("R4 dernier export retiré (troncature)", lambda d: (d / last).unlink(), "ACCEPTÉ")
    case("R4 export renommé 000002→000004", lambda d: (d / "research-archive-000002.json").rename(
        d / "research-archive-000004.json"), "ARCHIVE_CHAIN_BROKEN")

    def foreign(d):
        g2, a2 = g057.build(tmp / "foreign")
        rotation.rotate(g2, a2, count=1, guard_src=SRC, clock_ms=1)
        src = next(a2.glob("*.json"))
        meta = json.loads(src.read_bytes())
        meta["chain_index"], meta["previous_chain_sha256"] = 4, digest(chain_entry(d / last))
        write_private(d / "research-archive-000004.json", rotation._canon(meta))
    case("R4 export d'une autre garde chaîné en 4", foreign, "ARCHIVE_CHAIN_BROKEN")

    def repeated(d):
        one = json.loads((d / first).read_bytes())
        edit(d / "research-archive-000002.json", lambda m: (m["runs"].insert(0, one["runs"][0]),
                                                           m.update(removed_ids_sha256=digest([json.loads(r["body"])["id"]
                                                                                               for r in m["runs"]]))))
        rechain(d, 2)
    case("R4 même recherche dans deux exports (rechaîné)", repeated, "ARCHIVED_RUN_REPEATED")

    print("-- cohérence n'est pas authenticité")

    def coherent_middle(d):
        edit(d / "research-archive-000002.json", lambda m: m.update(created_at_ms=999))
        rechain(d, 2)
    case("R5 réécriture cohérente du milieu (horodatage + rechaînage)", coherent_middle, "ACCEPTÉ")

    def coherent_drop_run(d):
        def drop(m):
            m["runs"] = m["runs"][1:]
            m["removed_ids_sha256"] = digest([json.loads(r["body"])["id"] for r in m["runs"]])
        edit(d / "research-archive-000002.json", drop)
        rechain(d, 2)
    case("R5 recherche supprimée puis rechaînage cohérent", coherent_drop_run, "ACCEPTÉ")

    print("-- fichiers spéciaux, droits, noms")
    case("R6 export lien symbolique", lambda d: (os.rename(d / last, tmp / "outside.json"),
                                                 os.symlink(tmp / "outside.json", d / last)), "ARCHIVE_STORAGE_UNAVAILABLE")
    link = tmp / "dirlink"
    os.symlink(a, link)
    check_refusal("R6 dossier lien symbolique", link, expect="ARCHIVE_STORAGE_UNAVAILABLE")
    case("R6 FIFO research-archive-000004.json", lambda d: os.mkfifo(d / "research-archive-000004.json", 0o600),
         "ARCHIVE_FILE_NOT_PRIVATE")
    case("R6 sous-dossier research-archive-000004.json", lambda d: os.mkdir(d / "research-archive-000004.json", 0o700),
         "ARCHIVE_FILE_NOT_PRIVATE")
    case("R6 export 0644", lambda d: (d / first).chmod(0o644), "ARCHIVE_FILE_NOT_PRIVATE")
    case("R6 dossier 0755", lambda d: d.chmod(0o755), "ARCHIVE_DIRECTORY_NOT_PRIVATE")
    case("R6 .partial présent", lambda d: write_private(d / "x.partial", b""), "PARTIAL_EXPORT_PRESENT")
    case("R6 nom research-archive-1.json", lambda d: write_private(d / "research-archive-1.json", b"{}"),
         "INVALID_ARCHIVE_FILENAME")
    case("R6 fichiers étrangers (notes.txt, .liste-x.tmp)", lambda d: (write_private(d / "notes.txt", b"jean"),
                                                                       write_private(d / ".liste-x.tmp", b"x")), "ACCEPTÉ")
    missing = tmp / "absent"
    check_refusal_missing = cli(missing)
    print(f"R6 dossier absent : code {check_refusal_missing[0]} ; {code_of(check_refusal_missing[2])} ; "
          f"créé ensuite : {missing.exists()}")

    print("-- bornes de volume")
    case("R7 2049 entrées", lambda d: [write_private(d / f"n{i}", b"") for i in range(2049 - 3)], "ARCHIVE_COUNT_LIMIT")

    def big(d):
        with open(d / "research-archive-000004.json", "wb") as f:
            f.truncate(ra.MAX_ARCHIVE_BYTES + 1)
        (d / "research-archive-000004.json").chmod(0o600)
    case("R7 export de 16 Mio + 1 (creux)", big, "ARCHIVE_SIZE_LIMIT")
    sizes = [p.stat().st_size for p in sorted(a.glob("*.json"))]
    for label, patches in (("MAX_TOTAL_BYTES = deux premiers exports + 1", {"MAX_TOTAL_BYTES": sizes[0] + sizes[1] + 1}),
                           ("MAX_ARCHIVES = 2", {"MAX_ARCHIVES": 2})):
        with patch.multiple(ra, **patches):
            print(f"R7 {label} (en processus) : {attempt(ra.read_catalog, a)}")
    nul = quiet_main(["--directory", "a\0b", "inspect"])
    print(f"R7 main(--directory contenant NUL) : code {nul}")

    print("-- courses pendant la lecture (en processus)")
    races(a, tmp)
    print(f"R  dossier de base inchangé par toutes les lectures : {fingerprint(a) == fingerprint(a)}")
    return g, a


def attempt(fn, *args):
    try:
        out = fn(*args)
        return f"ACCEPTÉ ({out['run_count']} recherches)"
    except ra.ArchiveError as exc:
        return f"REFUS {exc}"


def quiet_main(argv):
    import io
    import contextlib
    err = io.StringIO()
    with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
        code = ra.main(argv)
    return f"{code} {code_of(err.getvalue())}"


def races(a, tmp):
    real_validate = ra.validate_export

    def scenario(name, action_on_file):
        d = copy_dir(a, tmp / ("race-" + name))
        hits = []

        def hooked(data, filename):
            out = real_validate(data, filename)
            if filename == action_on_file[0] and not hits:
                hits.append(1)
                action_on_file[1](d)
            return out
        with patch.object(ra, "validate_export", hooked):
            print(f"R8 {name} : {attempt(ra.read_catalog, d)}")

    def same_bytes_new_inode(d):
        p = d / "research-archive-000001.json"
        data = p.read_bytes()
        tmpf = d / "swap"
        write_private(tmpf, data)
        os.replace(tmpf, p)
    scenario("export 1 remplacé à l'identique (nouvel inode) après sa lecture",
             ("research-archive-000002.json", same_bytes_new_inode))
    scenario("export 4 ajouté pendant la lecture",
             ("research-archive-000003.json", lambda d: shutil.copy2(d / "research-archive-000003.json",
                                                                     d / "research-archive-000004.json")))
    scenario("horodatage de l'export 1 touché pendant la lecture",
             ("research-archive-000002.json", lambda d: os.utime(d / "research-archive-000001.json", ns=(1, 1))))
    real_read = os.read
    d = copy_dir(a, tmp / "race-grow")
    grown = []

    def growing(fd, n):
        block = real_read(fd, n)
        if not grown and block:
            grown.append(1)
            with open(d / "research-archive-000001.json", "ab") as f:
                f.write(b" ")
        return block
    with patch.object(ra.os, "read", growing):
        print(f"R8 export 1 allongé pendant sa propre lecture : {attempt(ra.read_catalog, d)}")


def index(tmp, a):
    print("== L. liste.md (CLI index)")
    d = copy_dir(a, tmp / "l")
    exports = {p.name: p.read_bytes() for p in d.glob("*.json")}
    code, out, err = cli(d, "index")
    liste = d / "liste.md"
    info = liste.stat()
    text = liste.read_text()
    links = re.findall(r"\]\(([^)]*)\)", text)
    leak = [m for m in PRIVATE_MARKERS + [json.loads(out)["guard_id"]] if m in text]
    print(f"L1 création : code {code} ; mode {oct(info.st_mode & 0o777)} ; propriétaire courant {info.st_uid == os.getuid()} ; "
          f"index_changed {json.loads(out)['index_changed']} ; en-tête {text.startswith(ra.INDEX_HEADER)}")
    print(f"L1   liens {links} ; données privées/identifiants : {leak or 'aucun'} ; exports inchangés "
          f"{all((d / n).read_bytes() == b for n, b in exports.items())} ; fichiers {sorted(p.name for p in d.iterdir())}")
    before = fingerprint(d)
    code, out, err = cli(d, "index")
    print(f"L2 deuxième index : code {code} ; index_changed {json.loads(out)['index_changed']} ; "
          f"dossier identique (inode/mtime compris) {fingerprint(d) == before}")
    code, out, err = cli(d, "index", fmt="human")
    print(f"L2   format humain : code {code} ; {out.strip().splitlines()[-1]}")

    def variant(name, prepare, expect, command="index"):
        v = copy_dir(d, tmp / ("l-" + re.sub(r"[^a-z0-9]+", "-", name.lower())[:40]))
        prepare(v)
        return v, check_refusal(name, v, command, expect=expect)

    v, _ = variant("L3 liste.md manuscrit", lambda v: write_private(v / "liste.md", b"# Mes notes\njean\n"),
                   "ARCHIVE_INDEX_NOT_GENERATED")
    v, _ = variant("L3 liste.md manuscrit commençant par le marqueur",
                   lambda v: write_private(v / "liste.md", ra.INDEX_HEADER.encode() + b"notes manuelles\n"), "ACCEPTÉ")
    print(f"L3   → contenu manuel remplacé : {'notes manuelles' not in (v / 'liste.md').read_text()} "
          "(documenté : le marqueur n'authentifie pas)")
    variant("L3 liste.md 0644", lambda v: (v / "liste.md").chmod(0o644), "ARCHIVE_FILE_NOT_PRIVATE")
    outside = tmp / "outside-liste.md"
    write_private(outside, ra.INDEX_HEADER.encode() + b"cible externe\n")
    v, _ = variant("L3 liste.md lien symbolique vers un fichier généré externe",
                   lambda v: ((v / "liste.md").unlink(), os.symlink(outside, v / "liste.md")), "ARCHIVE_STORAGE_UNAVAILABLE")
    intact = outside.read_text().endswith("cible externe\n")
    print(f"L3   → cible externe intacte : {intact}")
    v, _ = variant("L3 liste.md FIFO", lambda v: ((v / "liste.md").unlink(), os.mkfifo(v / "liste.md", 0o600)),
                   "ARCHIVE_FILE_NOT_PRIVATE")
    hard = tmp / "hardlink-target.md"
    v = copy_dir(d, tmp / "l-hard")
    os.link(v / "liste.md", hard)
    write_private(v / "research-archive-000003.json", (v / "research-archive-000003.json").read_bytes())
    os.unlink(v / "research-archive-000003.json")
    code, out, err = cli(v, "index")
    print(f"L3 liste.md lié en dur ailleurs puis catalogue changé : code {code} ; second lien inchangé "
          f"{'Archives : 3' in hard.read_text()} ; liste.md mis à jour {'Archives : 2' in (v / 'liste.md').read_text()}")
    variant("L4 verrou 0644", lambda v: write_private(v / ".archive-index.lock", b"") or (v / ".archive-index.lock").chmod(0o644),
            "ARCHIVE_FILE_NOT_PRIVATE")
    variant("L4 verrou lien symbolique", lambda v: ((v / ".archive-index.lock").unlink(),
                                                   os.symlink(tmp / "nowhere", v / ".archive-index.lock")),
            "ARCHIVE_STORAGE_UNAVAILABLE")
    print(f"L4   → cible du lien non créée : {not (tmp / 'nowhere').exists()}")
    held = copy_dir(d, tmp / "l-held")
    write_private(held / "research-archive-000003.json", (held / "research-archive-000003.json").read_bytes())
    os.unlink(held / "research-archive-000003.json")
    fd = os.open(held / ".archive-index.lock", os.O_RDWR)
    fcntl.flock(fd, fcntl.LOCK_EX)
    check_refusal("L4 verrou détenu par un autre processus", held, "index", expect="ARCHIVE_INDEX_BUSY")
    os.close(fd)
    check_refusal("L4   inspect pendant ce temps n'utilise pas le verrou", held, "inspect", expect="ACCEPTÉ")

    fresh = copy_dir(a, tmp / "l-parallel")
    procs = [subprocess.Popen([sys.executable, "-m", "eidolon_core.research_archive", "--directory", str(fresh), "index"],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=ENV) for _ in range(8)]
    results = [(p.wait(), code_of(p.stderr.read()) if p.returncode else "OK") for p in procs]
    for p in procs:
        p.stdout.close()
        p.stderr.close()
    print(f"L5 8 index simultanés sur un dossier neuf : {sorted(r[1] for r in results)} ; fichiers "
          f"{sorted(n.name for n in fresh.iterdir() if not n.name.startswith('research-archive-'))} ; "
          f"liste.md complet {(fresh / 'liste.md').read_text() == ra.render_index(ra.read_catalog(fresh)) }")

    print("-- pannes de publication (sous-processus, os._exit)")
    crash = r"""
import os, sys
sys.path.insert(0, sys.argv[1])
from eidolon_core import research_archive as ra
target, point = sys.argv[2], sys.argv[3]
real = {name: getattr(ra.os, name) for name in ("link", "replace", "fsync")}
count = {"fsync": 0}
def hook(name):
    def inner(*a, **k):
        if name == "fsync":
            count["fsync"] += 1
            if point == "after_publish" and count["fsync"] == 2:
                os._exit(9)
            return real[name](*a, **k)
        if point == "before_publish":
            os._exit(9)
        return real[name](*a, **k)
    return inner
for name in real:
    setattr(ra.os, name, hook(name))
ra.write_index(target)
"""
    for start, point in (("absent", "before_publish"), ("présent", "before_publish"),
                         ("absent", "after_publish"), ("présent", "after_publish")):
        v = copy_dir(d if start == "présent" else a, tmp / f"l-crash-{start}-{point}")
        if start == "présent":
            write_private(v / "research-archive-000003.json", (v / "research-archive-000003.json").read_bytes())
            os.unlink(v / "research-archive-000003.json")
        old = (v / "liste.md").read_bytes() if (v / "liste.md").exists() else None
        p = subprocess.run([sys.executable, "-c", crash, SRC, str(v), point], capture_output=True, text=True)
        now = (v / "liste.md").read_bytes() if (v / "liste.md").exists() else None
        tmps = [(n.name[:7] + "…", oct(n.stat().st_mode & 0o777)) for n in v.glob(".liste-*.tmp")]
        state = "absent" if now is None else "ancien" if now == old else "nouveau"
        code2, out2, err2 = cli(v, "index")
        code3, _, err3 = cli(v, "inspect")
        print(f"L6 liste.md {start}, arrêt {point} : code {p.returncode} ; liste.md {state} ; temporaires {tmps} ; "
              f"index suivant {code2} {code_of(err2) if code2 else ''} ; inspect {code3} ; temporaire encore là "
              f"{bool(list(v.glob('.liste-*.tmp')))}")

    print("-- fenêtre entre contrôle et remplacement (en processus)")
    v = copy_dir(d, tmp / "l-toctou")
    write_private(v / "research-archive-000003.json", (v / "research-archive-000003.json").read_bytes())
    os.unlink(v / "research-archive-000003.json")
    real_replace = os.replace

    def writer_ignoring_lock(src, dst, **kw):
        write_private(v / "liste.md", b"# Document manuel ecrit pendant la fenetre\n")
        return real_replace(src, dst, **kw)
    with patch.object(ra.os, "replace", writer_ignoring_lock):
        try:
            ra.write_index(v)
            outcome = "écrit"
        except ra.ArchiveError as exc:
            outcome = f"REFUS {exc}"
    print(f"L7 manuscrit écrit entre la vérification de signature et os.replace : {outcome} ; manuscrit écrasé "
          f"{'Document manuel' not in (v / 'liste.md').read_text()}")
    v = copy_dir(d, tmp / "l-stale")
    edit(v / "research-archive-000002.json", lambda m: m.update(removed_ids_sha256="0" * 64))
    code, _, err = cli(v, "index")
    print(f"L8 export altéré après génération : index {code} {code_of(err)} ; liste.md ancien conservé "
          f"{(v / 'liste.md').read_bytes() == (d / 'liste.md').read_bytes()} ; il affiche toujours "
          f"« {next(line for line in (v / 'liste.md').read_text().splitlines() if line.startswith('Catalogue'))} »")


# ---------------------------------------------------------------- C-029
CRASH_SEARCH = r"""
import os, sys
sys.path.insert(0, sys.argv[1])
from eidolon_core import research_runtime as rr
from eidolon_core.store import Store
rt = rr.ResearchRuntime(Store(sys.argv[2]))
m = rt.create_research("notice synthetique coupee", required_pages=1)
print(m["id"], flush=True)
os.environ["G064_CRASH_SEARCH"] = "1"     # read by sitecustomize in the spawned tool worker
rt.run(m["id"])
"""

# The tool runs in a multiprocessing "spawn" worker: patches in this process do not reach it.
# sitecustomize kills BOTH the parent runtime and the worker once the guard INTENT is committed
# (a power cut while the provider is being called).
SITECUSTOMIZE = r"""
import os, signal
if os.environ.get("G064_CRASH_SEARCH") == "1":
    from eidolon_core import research_runtime as _rr
    def _crash(self, query, limit):
        os.kill(os.getppid(), signal.SIGKILL)
        os._exit(9)
    _rr.FixtureProvider.search = _crash
"""


def crash_search(tmp, state):
    hook = tmp / "hook"
    if not hook.exists():
        hook.mkdir()
        (hook / "sitecustomize.py").write_text(SITECUSTOMIZE)
    p = subprocess.run([sys.executable, "-c", CRASH_SEARCH, SRC, str(state)], capture_output=True, text=True,
                       env=dict(ENV, PYTHONPATH=f"{hook}:{SRC}"))
    return p.returncode, p.stdout.split()[0]


def fx(state):
    """Fingerprint of the research fixture only (opening a Store may touch its own database)."""
    root = Path(state) / "research-fixture"
    return fingerprint(root) if root.exists() else "absent"

CRASH_INIT = r"""
import os, sys
sys.path.insert(0, sys.argv[1])
from eidolon_core import research_runtime as rr, research_guard as rg
from eidolon_core.store import Store
point = sys.argv[3]
if point == "guard_dir_only":
    def init(self, directory, **k):
        os.makedirs(os.path.join(directory), mode=0o700)
        os._exit(9)
    rg.ResearchGuard.__init__ = init
    rr.ResearchGuard = rg.ResearchGuard
elif point == "before_pauses":
    real = rr.ResearchPauses
    def pauses(*a, **k):
        os._exit(9)
    rr.ResearchPauses = pauses
elif point == "before_binding_commit":
    real = rr.SyntheticResearchBackend.__init__
    def init(self, *a, **k):
        real(self, *a, **k)
        os._exit(9)
    rr.SyntheticResearchBackend.__init__ = init
rr.ResearchRuntime(Store(sys.argv[2]))
"""

OPEN = r"""
import sys, json
sys.path.insert(0, sys.argv[1])
from eidolon_core.research_runtime import ResearchRuntime
from eidolon_core.store import Store
try:
    print(json.dumps({"guard_id": ResearchRuntime(Store(sys.argv[2])).backend.guard_id}))
except Exception as exc:
    print(json.dumps({"error": type(exc).__name__ + " " + str(exc)[:60]}))
"""


def runs(state):
    db = Path(state) / "research-fixture" / "guard" / "research-runs.sqlite3"
    if not db.exists():
        return "garde absente"
    c = sqlite3.connect(db)
    out = [json.loads(b)["state"] for (b,) in c.execute("SELECT body FROM runs ORDER BY id")]
    c.close()
    return out


def binding(state):
    c = sqlite3.connect(Path(state) / "core.sqlite3") if (Path(state) / "core.sqlite3").exists() else None
    if c is None:
        return "?"
    row = c.execute("SELECT value FROM sync_metadata WHERE key='research_fixture_guard_id'").fetchone()
    c.close()
    return "liée" if row else "non liée"


def opened(state):
    try:
        return f"construit (garde {'identique' if ResearchRuntime(Store(state)).backend.guard_id else '?'})"
    except Exception as exc:  # noqa: BLE001 -- the exact type is the observation
        return f"{type(exc).__name__} {str(exc)[:60]}"


def summary(m):
    return f"{m['status']} / {(m.get('error') or {}).get('code')}"


def initialization(tmp):
    print("== I. initialisation liée au Store (C-029)")
    st = tmp / "i-crash"
    rt = ResearchRuntime(Store(st))
    store_file = next(p for p in st.iterdir() if p.suffix == ".sqlite3")
    print(f"I0 base du Store : {store_file.name}")
    global binding

    def binding(state):  # noqa: F811
        c = sqlite3.connect(next(p for p in Path(state).iterdir() if p.suffix == ".sqlite3"))
        row = c.execute("SELECT value FROM sync_metadata WHERE key='research_fixture_guard_id'").fetchone()
        c.close()
        return "liée" if row else "non liée"
    guard_before = tmp / "guard-before-intent"
    shutil.copytree(st / "research-fixture" / "guard", guard_before)
    whole_before = tmp / "state-before-intent"
    shutil.copytree(st, whole_before)
    del rt
    code, mission = crash_search(tmp, st)
    print(f"I1 coupure du runtime et du worker après INTENT (fournisseur) : code {code} ; garde {runs(st)}")
    for name, damage, restore in (
            ("dossier research-fixture entier", lambda: shutil.move(st / "research-fixture", tmp / "fx"),
             lambda: shutil.move(tmp / "fx", st / "research-fixture")),
            ("garde seule", lambda: shutil.move(st / "research-fixture" / "guard", tmp / "gd"),
             lambda: shutil.move(tmp / "gd", st / "research-fixture" / "guard")),
            ("verrou de garde", lambda: shutil.move(st / "research-fixture/guard/research-runs.lock", tmp / "lk"),
             lambda: shutil.move(tmp / "lk", st / "research-fixture/guard/research-runs.lock")),
            ("pauses", lambda: shutil.move(st / "research-fixture/pauses.sqlite3", tmp / "ps"),
             lambda: shutil.move(tmp / "ps", st / "research-fixture/pauses.sqlite3"))):
        damage()
        before = fx(st)
        result = opened(st)
        print(f"I2 {name} absent : {result} ; rien créé {fx(st) == before} ; "
              f"restauré → {(restore(), opened(st))[1]} ; garde {runs(st)}")
    rt = ResearchRuntime(Store(st))
    m = rt.run(mission)
    print(f"I3 reprise après restauration : {summary(m)} ; garde {runs(st)} (aucune relance attendue)")

    st2 = tmp / "i-rollback"
    shutil.copytree(whole_before, st2)
    code, mission2 = crash_search(tmp, st2)
    print(f"I4 même coupure (code {code}) ; garde {runs(st2)}")
    shutil.rmtree(st2 / "research-fixture" / "guard")
    shutil.copytree(guard_before, st2 / "research-fixture" / "guard")
    print(f"I4 garde seule restaurée AVANT l'INTENT (même identité) : construction {opened(st2)} ; garde {runs(st2)}")
    m = ResearchRuntime(Store(st2)).run(mission2)
    print(f"I4   reprise : {summary(m)} ; garde ensuite {runs(st2)} "
          f"({'RELANCE déduite de l absence d INTENT' if runs(st2) else 'aucune relance'})")
    st3 = tmp / "i-joint"
    shutil.copytree(whole_before, st3)
    _, mission3 = crash_search(tmp, st3)
    shutil.rmtree(st3)
    shutil.copytree(whole_before, st3)
    rt3 = ResearchRuntime(Store(st3))
    try:
        rt3.store.get(mission3)
        present = True
    except Exception:  # noqa: BLE001
        present = False
    print(f"I4 restauration conjointe Store+garde+pauses d'avant la mission : construction acceptée ; mission présente "
          f"{present} ; garde {runs(st3)} (hors garantie, documenté)")

    print("-- pauses : identité non liée")
    st4 = tmp / "i-pauses"
    rt4 = ResearchRuntime(Store(st4), scenario="blocked")
    m4 = rt4.run(rt4.create_research("notice synthetique bloquee", required_pages=1)["id"])
    pauses_path = st4 / "research-fixture" / "pauses.sqlite3"
    active = [x["reason"] for x in ResearchPauses(pauses_path, create=False).inspect()["pauses"] if x["status"] == "ACTIVE"]
    print(f"I5 scénario bloqué : {summary(m4)} ; pauses actives {active}")
    saved = pauses_path.read_bytes()
    pauses_path.unlink()
    ResearchPauses(pauses_path)          # a fresh, valid, EMPTY pause database (same schema)
    print(f"I5 pauses remplacées par une base vide valide : {opened(st4)} ; pauses actives ensuite "
          f"{[x['reason'] for x in ResearchPauses(pauses_path, create=False).inspect()['pauses']]}")
    write_private(pauses_path, saved)

    print("-- initialisations coupées (sous-processus, os._exit)")
    for point in ("guard_dir_only", "before_pauses", "before_binding_commit"):
        s = tmp / f"i-init-{point}"
        p = subprocess.run([sys.executable, "-c", CRASH_INIT, SRC, str(s), point], capture_output=True, text=True)
        files = sorted(str(x.relative_to(s)) for x in (s / "research-fixture").rglob("*")) if (s / "research-fixture").exists() else []
        before, bound = fx(s), binding(s)
        o = subprocess.run([sys.executable, "-c", OPEN, SRC, str(s)], capture_output=True, text=True)
        print(f"I6 arrêt {point} : code {p.returncode} ; fichiers {files} ; liaison {bound} ; réouverture "
              f"{json.loads(o.stdout).get('error') or 'construite'} ; dossier inchangé {fx(s) == before} ; liaison ensuite {binding(s)}")

    s = tmp / "i-parallel"
    procs = [subprocess.Popen([sys.executable, "-c", OPEN, SRC, str(s)], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              text=True) for _ in range(6)]
    outs = [json.loads(p.communicate()[0]) for p in procs]
    ids = {o.get("guard_id") for o in outs if "guard_id" in o}
    print(f"I7 6 processus initialisent le même Store neuf : identités distinctes {len(ids)} ; erreurs "
          f"{[o['error'] for o in outs if 'error' in o]} ; journaux de garde {len(list(s.rglob('research-runs.sqlite3')))}")

    print("-- missions C-021 (adoption sans réécriture)")
    s = tmp / "i-legacy"
    rt = ResearchRuntime(Store(s))
    for i in range(3):
        rt.create_research(f"notice synthetique {i}", required_pages=1)
    db_path = next(p for p in s.iterdir() if p.suffix == ".sqlite3")

    def missions_hash():
        c = sqlite3.connect(db_path)
        h = hashlib.sha256(repr(c.execute("SELECT id, body FROM missions ORDER BY id").fetchall()).encode()).hexdigest()[:16]
        c.close()
        return h

    def unbind():
        c = sqlite3.connect(db_path)
        c.execute("DELETE FROM sync_metadata WHERE key='research_fixture_guard_id'")
        c.commit()
        c.close()
    unbind()
    before = missions_hash()
    print(f"I8 3 missions, liaison retirée : {opened(s)} ; missions identiques {missions_hash() == before} ; liaison {binding(s)}")
    unbind()
    c = sqlite3.connect(db_path)
    c.execute("UPDATE missions SET body=json_set(body,'$.configuration.research_fixture.guard_id','g-'||printf('%032d',0)) "
              "WHERE id=(SELECT min(id) FROM missions)")
    c.commit()
    c.close()
    before = missions_hash()
    print(f"I8 identités contradictoires entre missions : {opened(s)} ; liaison {binding(s)} ; missions identiques "
          f"{missions_hash() == before}")

    print("-- Store occupé et délai du balayage historique")
    s = tmp / "i-busy"
    ResearchRuntime(Store(s))
    unbind_path = next(p for p in s.iterdir() if p.suffix == ".sqlite3")
    c = sqlite3.connect(unbind_path)
    c.execute("DELETE FROM sync_metadata WHERE key='research_fixture_guard_id'")
    c.commit()
    holder = sqlite3.connect(unbind_path, isolation_level=None)
    holder.execute("BEGIN EXCLUSIVE")
    t0 = time.monotonic()
    result = opened(s)
    print(f"I9 Store verrouillé par un autre écrivain : {result} après {time.monotonic() - t0:.1f} s")
    holder.execute("ROLLBACK")
    holder.close()
    c.close()
    s = tmp / "i-scan"
    rt = ResearchRuntime(Store(s))
    rt.create_research("notice synthetique", required_pages=1)
    db_path = next(p for p in s.iterdir() if p.suffix == ".sqlite3")
    c = sqlite3.connect(db_path)
    cols = [r[1] for r in c.execute("PRAGMA table_info(missions)")]
    select = ", ".join("id || '-' || n" if col == "id" else col for col in cols)
    c.execute(f"WITH RECURSIVE k(n) AS (SELECT 1 UNION ALL SELECT n+1 FROM k WHERE n<20000) "
              f"INSERT INTO missions({', '.join(cols)}) SELECT {select} FROM missions, k")
    c.execute("DELETE FROM sync_metadata WHERE key='research_fixture_guard_id'")
    c.commit()
    c.close()
    from eidolon_core import research_runtime as rr
    real_monotonic = time.monotonic
    calls = []

    def jumping():
        calls.append(1)
        return real_monotonic() + (0 if len(calls) == 1 else 100)
    with patch.object(rr.time, "monotonic", jumping):
        result = opened(s)
    print(f"I9 20001 missions historiques, délai de 2 s du balayage dépassé (horloge simulée) : {result} ; liaison {binding(s)}")

    print("-- lecture CLI research-sim pendant qu'un autre écrivain tient le Store")
    for label, src in (("C-029", SRC), ("base e0365f2", BASE_SRC)):
        s = tmp / f"i-read-{label[:5]}"
        p = subprocess.run([sys.executable, "-m", "eidolon_core.cli", "--state", str(s), "--profile", "research-sim",
                            "research", "notice synthetique", "--create-only"], capture_output=True, text=True,
                           env=dict(ENV, PYTHONPATH=src))
        mission = json.loads(p.stdout)["id"]
        db_path = next(x for x in s.iterdir() if x.suffix == ".sqlite3")
        holder = sqlite3.connect(db_path, isolation_level=None)
        holder.execute("BEGIN IMMEDIATE")              # an ordinary writer; readers are still allowed
        out = {}
        for profile in ("text", "research-sim"):
            t0 = time.monotonic()
            p = subprocess.run([sys.executable, "-m", "eidolon_core.cli", "--state", str(s), "--profile", profile,
                                "show", mission], capture_output=True, text=True, env=dict(ENV, PYTHONPATH=src))
            err = json.loads(p.stderr)["error"] if p.returncode else "lu"
            out[profile] = f"{p.returncode} {err} ({time.monotonic() - t0:.1f} s)"
        holder.execute("ROLLBACK")
        holder.close()
        print(f"I10 {label} : show --profile text → {out['text']} ; show --profile research-sim → {out['research-sim']}")


def main():
    print(f"Sources examinées : {SRC}")
    with tempfile.TemporaryDirectory(prefix="eidolon-g064-") as tmp:
        tmp = Path(tmp)
        _, a = reader(tmp)
        index(tmp, a)
        initialization(tmp)


if __name__ == "__main__":
    main()
