# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : doc_index.py
# Description : Prototype E2-P0 d'index documentaire local (index.search) : générations atomiques, citations, retrait
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Local lexical index of PUBLIC documents, separate from the private Memory Engine (G192: index.search).

Prototype on synthetic corpora only: no dump, no crawl, no network. One directory holds immutable
generations (SQLite FTS5 files); a CURRENT pointer, replaced atomically, names the active one, and older
generations stay for rollback. A withdrawal list (also replaced atomically) hides a document at once,
before any rebuild. Every result carries its citation (source URL, title, licence, collection date,
revision, generation) and is marked untrusted: indexed text is data, never instructions.
"""
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import uuid

from .contracts import ContractError

SCHEMA = "eidolon-doc-index/1"
CURRENT = "CURRENT"
WITHDRAWN = "withdrawn.json"
LICENCES = frozenset({"CC-BY-SA-4.0", "CC-BY-SA-3.0", "GFDL-1.3-or-later", "PSF-2.0", "CC0-1.0", "CC-BY-4.0",
                      "synthetic"})
DOC_ID = re.compile(r"[a-z0-9][a-z0-9._:-]{0,127}")
GENERATION = re.compile(r"g-[0-9a-f]{32}")
MAX_DOCS = 100_000
MAX_TEXT = 200_000
MAX_RESULTS = 20
TOKEN = re.compile(r"\w+", re.UNICODE)


def _root(path):
    root = Path(path)
    info = os.lstat(root)
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o700:
        raise ContractError("INDEX_ROOT_NOT_PRIVATE")
    return root


def _utc(value):
    try:
        stamp = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        raise ContractError("INDEX_DOCUMENT_DATE") from None
    if stamp.utcoffset() != timedelta(0) or stamp > datetime.now(timezone.utc) + timedelta(minutes=5):
        raise ContractError("INDEX_DOCUMENT_DATE")
    return stamp.isoformat()


def _document(doc):
    if not isinstance(doc, dict) or set(doc) != {"doc_id", "source_url", "title", "text", "licence",
                                                  "collected_at", "revision"}:
        raise ContractError("INDEX_DOCUMENT_FIELDS")
    if not isinstance(doc["doc_id"], str) or not DOC_ID.fullmatch(doc["doc_id"]):
        raise ContractError("INDEX_DOCUMENT_ID")
    url = doc["source_url"]
    if not isinstance(url, str) or len(url) > 2048 or not re.fullmatch(r"https?://[^\s/@]+(/[^\s]*)?", url):
        raise ContractError("INDEX_DOCUMENT_URL")
    if doc["licence"] not in LICENCES:
        raise ContractError("INDEX_DOCUMENT_LICENCE")
    if not isinstance(doc["title"], str) or not 1 <= len(doc["title"]) <= 300:
        raise ContractError("INDEX_DOCUMENT_TITLE")
    if not isinstance(doc["text"], str) or not 1 <= len(doc["text"]) <= MAX_TEXT:
        raise ContractError("INDEX_DOCUMENT_TEXT")
    if not isinstance(doc["revision"], str) or not 1 <= len(doc["revision"]) <= 80:
        raise ContractError("INDEX_DOCUMENT_REVISION")
    return dict(doc, collected_at=_utc(doc["collected_at"]))


def _fsync_dir(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _write_atomic(root, name, data):
    temporary = root / f".{name}.{uuid.uuid4().hex}.tmp"
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        os.write(fd, data)
        os.fsync(fd)
    finally:
        os.close(fd)
    os.replace(temporary, root / name)
    _fsync_dir(root)


def build(root, documents):
    """Write a NEW immutable generation; return its id. Does not activate it (see activate)."""
    root = _root(root)
    docs = [_document(d) for d in documents]
    if not 1 <= len(docs) <= MAX_DOCS or len({d["doc_id"] for d in docs}) != len(docs):
        raise ContractError("INDEX_DOCUMENT_SET")
    generation = "g-" + uuid.uuid4().hex
    building = root / f".building-{generation}.sqlite"
    db = sqlite3.connect(building)
    try:
        db.executescript("""
            CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE docs (rowid INTEGER PRIMARY KEY, doc_id TEXT UNIQUE NOT NULL, source_url TEXT NOT NULL,
                               title TEXT NOT NULL, licence TEXT NOT NULL, collected_at TEXT NOT NULL,
                               revision TEXT NOT NULL, text_sha256 TEXT NOT NULL);
            CREATE VIRTUAL TABLE fts USING fts5(title, text, tokenize='unicode61 remove_diacritics 2');
        """)
        corpus = hashlib.sha256()
        for i, d in enumerate(sorted(docs, key=lambda d: d["doc_id"]), start=1):
            sha = hashlib.sha256(d["text"].encode("utf-8")).hexdigest()
            corpus.update(f"{d['doc_id']}\0{d['revision']}\0{sha}\n".encode())
            db.execute("INSERT INTO docs VALUES (?,?,?,?,?,?,?,?)", (i, d["doc_id"], d["source_url"], d["title"],
                       d["licence"], d["collected_at"], d["revision"], sha))
            db.execute("INSERT INTO fts(rowid, title, text) VALUES (?,?,?)", (i, d["title"], d["text"]))
        db.executemany("INSERT INTO meta VALUES (?,?)", [
            ("schema", SCHEMA), ("generation", generation), ("documents", str(len(docs))),
            ("corpus_sha256", corpus.hexdigest()), ("built_at", datetime.now(timezone.utc).isoformat())])
        db.commit()
    except BaseException:
        db.close()
        building.unlink(missing_ok=True)
        raise
    db.close()
    os.chmod(building, 0o400)
    fd = os.open(building, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    os.replace(building, root / f"{generation}.sqlite")      # visible only once complete
    _fsync_dir(root)
    return generation


def generations(root):
    root = _root(root)
    return sorted(p.stem for p in root.glob("g-*.sqlite") if GENERATION.fullmatch(p.stem))


def activate(root, generation):
    """Atomically point CURRENT at a complete generation (also the rollback path)."""
    root = _root(root)
    if not isinstance(generation, str) or not GENERATION.fullmatch(generation) \
            or not (root / f"{generation}.sqlite").is_file():
        raise ContractError("INDEX_GENERATION_UNKNOWN")
    _write_atomic(root, CURRENT, (generation + "\n").encode())


def current(root):
    root = _root(root)
    try:
        value = (root / CURRENT).read_text(encoding="ascii").strip()
    except FileNotFoundError:
        return None
    if not GENERATION.fullmatch(value) or not (root / f"{value}.sqlite").is_file():
        raise ContractError("INDEX_CURRENT_INVALID")
    return value


def _withdrawn(root):
    try:
        value = json.loads((root / WITHDRAWN).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    if not isinstance(value, dict) or not all(isinstance(k, str) and DOC_ID.fullmatch(k) for k in value):
        raise ContractError("INDEX_WITHDRAWN_INVALID")
    return value


def withdraw(root, doc_id, reason):
    """Hide a document at once in every generation (licence problem, error...); a rebuild drops it for good."""
    root = _root(root)
    if not isinstance(doc_id, str) or not DOC_ID.fullmatch(doc_id) or reason not in (
            "licence", "error", "request", "obsolete"):
        raise ContractError("INDEX_WITHDRAW_INVALID")
    value = _withdrawn(root)
    value[doc_id] = {"reason": reason, "at": datetime.now(timezone.utc).isoformat()}
    _write_atomic(root, WITHDRAWN, json.dumps(value, sort_keys=True).encode())


def _match(query):
    """Words only, each quoted: no FTS operator, column filter or wildcard from the caller survives."""
    words = TOKEN.findall(query)[:16]
    return " ".join('"' + w.replace('"', "") + '"' for w in words)


def search(root, query, *, limit=5):
    """index.search -> {status, generation, results[], untrusted}. Read-only; never touches the network."""
    root = _root(root)
    if not isinstance(query, str) or len(query) > 400 or type(limit) is not int or not 1 <= limit <= MAX_RESULTS:
        raise ContractError("INDEX_QUERY_INVALID")
    generation = current(root)
    if generation is None:
        return {"status": "UNAVAILABLE", "generation": None, "results": [], "untrusted": True}
    expression = _match(query)
    if not expression:
        return {"status": "EMPTY", "generation": generation, "results": [], "untrusted": True}
    hidden = _withdrawn(root)
    uri = (root / f"{generation}.sqlite").resolve().as_uri() + "?mode=ro"
    db = sqlite3.connect(uri, uri=True)
    try:
        rows = db.execute(
            "SELECT d.doc_id, d.source_url, d.title, d.licence, d.collected_at, d.revision, "
            "snippet(fts, 1, '', '', ' … ', 24) FROM fts JOIN docs d ON d.rowid = fts.rowid "
            "WHERE fts MATCH ? ORDER BY bm25(fts), d.doc_id LIMIT ?",
            (expression, limit + len(hidden))).fetchall()
    finally:
        db.close()
    results = [{"doc_id": r[0], "snippet": r[6][:500],
                "citation": {"source_url": r[1], "title": r[2], "licence": r[3], "collected_at": r[4],
                             "revision": r[5], "generation": generation}}
               for r in rows if r[0] not in hidden][:limit]
    return {"status": "OK" if results else "EMPTY", "generation": generation, "results": results,
            "untrusted": True}
