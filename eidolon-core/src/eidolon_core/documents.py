# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : documents.py
# Description : Extraction documentaire bornée, sans macros ni import implicite
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Extract text in an owned resource-limited process, never execute document code.

No OCR, formula calculation, layout fidelity or exhaustive document semantics.
The binary is never persisted. Returned excerpts are untrusted and visibly bounded.
"""
import hashlib
import io
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import zipfile
import xml.etree.ElementTree as ET

MAX_BYTES = 4 * 1024 * 1024
UPLOAD_BYTES = 512 * 1024
MAX_TEXT = 16000
FORMATS = ("txt", "md", "csv", "docx", "odt", "xlsx", "pptx", "pdf")


class DocumentError(ValueError):
    pass


def extension(name):
    if (type(name) is not str or not 1 <= len(name) <= 200 or name in (".", "..")
            or any(c in name for c in ("/", "\\")) or any(ord(c) < 32 for c in name)):
        raise DocumentError("DOCUMENT_NAME_INVALID")
    suffix = name.rsplit(".", 1)[-1].lower()
    if suffix not in FORMATS or "." not in name:
        raise DocumentError("DOCUMENT_FORMAT_UNSUPPORTED")
    return suffix


def _xml(raw):
    # Restrict to UTF-8 so DTD/entity checks cannot be bypassed via UTF-16/32.
    text = raw.decode("utf-8-sig")
    if "\0" in text or re.search(r"<!\s*(DOCTYPE|ENTITY)", text, re.I):
        raise DocumentError("DOCUMENT_XML_DECLARATION_REFUSED")
    if re.search(r'encoding\s*=\s*[\'"](?!utf-8[\'"])[^\'"]+', text[:200], re.I):
        raise DocumentError("DOCUMENT_XML_ENCODING_REFUSED")
    depth = count = 0
    parser = ET.iterparse(io.StringIO(text), events=("start", "end"))
    for event, _ in parser:
        if event == "start":
            depth += 1; count += 1
            if depth > 64 or count > 100000:
                raise DocumentError("DOCUMENT_XML_BUDGET")
        else:
            depth -= 1
    return parser.root


def _office(data, kind):
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        infos = archive.infolist()
        names = [x.filename for x in infos]
        if len(infos) > 512 or len(set(names)) != len(names):
            raise DocumentError("DOCUMENT_ARCHIVE_BUDGET")
        if sum(x.file_size for x in infos) > 16 * 1024 * 1024:
            raise DocumentError("DOCUMENT_ARCHIVE_BUDGET")
        for info in infos:
            name = info.filename
            parts = name.rstrip("/").split("/")
            if (name.startswith("/") or "\\" in name or ":" in name or any(p in ("", ".", "..") for p in parts)
                    or any(ord(c) < 32 for c in name) or info.flag_bits & 1
                    or info.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)
                    or info.file_size > 8 * 1024 * 1024 or info.file_size > max(1024, info.compress_size * 200)
                    or "vbaproject" in name.lower() or name.lower().endswith(".exe")):
                raise DocumentError("DOCUMENT_ARCHIVE_REFUSED")
        def read(name):
            with archive.open(name) as stream:
                raw = stream.read(8 * 1024 * 1024 + 1)
            if len(raw) > 8 * 1024 * 1024:
                raise DocumentError("DOCUMENT_ARCHIVE_BUDGET")
            return _xml(raw)
        def paragraphs(root, ptag, ttag):
            return ["".join(t.text or "" for t in p.iter(ttag)) for p in root.iter(ptag)]
        if kind == "docx":
            ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
            root = read("word/document.xml")
            if root.tag != ns + "document":
                raise DocumentError("DOCUMENT_STRUCTURE_INVALID")
            return "\n".join(paragraphs(root, ns+"p", ns+"t")), "Corps et tableaux ; en-têtes, notes, images et révisions non reconstruits."
        if kind == "odt":
            root = read("content.xml")
            ns = "{urn:oasis:names:tc:opendocument:xmlns:text:1.0}"
            office = "{urn:oasis:names:tc:opendocument:xmlns:office:1.0}"
            if root.tag != office + "document-content":
                raise DocumentError("DOCUMENT_STRUCTURE_INVALID")
            return "\n".join("".join(p.itertext()) for p in root.iter() if p.tag in (ns+"p", ns+"h")), "Texte principal ; présentation, espaces répétés, images et objets non reconstruits."
        if kind == "pptx":
            ns = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
            slides = sorted((n for n in names if re.fullmatch(r"ppt/slides/slide[0-9]+\.xml", n)),
                            key=lambda n: int(re.search(r"([0-9]+)\.xml$", n)[1]))
            if not slides:
                raise DocumentError("DOCUMENT_STRUCTURE_INVALID")
            return "\n\n".join(f"Diapositive (fichier) {n}\n" + "\n".join(paragraphs(read(n), ns+"p", ns+"t")) for n in slides), "Ordre des fichiers de diapositives ; ordre de présentation personnalisé, notes, images et animations non reconstruits."
        ns = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
        shared = []
        if "xl/sharedStrings.xml" in names:
            shared = ["".join(t.text or "" for t in item.iter(ns+"t")) for item in read("xl/sharedStrings.xml").iter(ns+"si")]
        sheets = sorted(n for n in names if re.fullmatch(r"xl/worksheets/sheet[0-9]+\.xml", n))
        if not sheets:
            raise DocumentError("DOCUMENT_STRUCTURE_INVALID")
        lines = []
        for name in sheets:
            lines.append("Feuille (fichier) " + name)
            for cell in read(name).iter(ns+"c"):
                value = cell.find(ns+"v")
                text = value.text or "" if value is not None else ""
                if cell.get("t") == "s":
                    if not re.fullmatch(r"[0-9]{1,6}", text) or int(text) >= len(shared):
                        raise DocumentError("DOCUMENT_CELL_INVALID")
                    text = shared[int(text)]
                elif cell.get("t") == "inlineStr":
                    text = "".join(t.text or "" for t in cell.iter(ns+"t"))
                label = cell.get("r", "?")
                if cell.find(ns+"f") is not None:
                    text = "[valeur de formule en cache, non recalculée] " + text
                lines.append(label + ": " + text)
        return "\n".join(lines), "Cellules et valeurs en cache ; formules jamais exécutées, dates/nombres non formatés, graphiques et feuilles cachées non distingués."


def _extract(data, kind):
    if kind in ("txt", "md", "csv"):
        text, limitation = data.decode("utf-8-sig"), "Texte UTF-8 ; CSV conservé comme texte, sans calcul."
    elif kind == "pdf":
        if not data.startswith(b"%PDF-"):
            raise DocumentError("DOCUMENT_STRUCTURE_INVALID")
        if not os.path.isfile("/usr/bin/pdftotext"):
            raise DocumentError("PDF_EXTRACTOR_UNAVAILABLE")
        run = subprocess.run(["/usr/bin/pdftotext", "-f", "1", "-l", "100", "-enc", "UTF-8", "-nopgbrk", "-", "-"],
                             input=data, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=4)
        if run.returncode:
            raise DocumentError("PDF_EXTRACTION_FAILED")
        text = run.stdout.decode("utf-8")
        limitation = "Couche texte des 100 premières pages au plus ; aucun OCR, mise en page et tableaux non garantis."
    else:
        text, limitation = _office(data, kind)
    if "\0" in text:
        raise DocumentError("DOCUMENT_TEXT_INVALID")
    text = "".join(c for c in text if c in "\n\t" or ord(c) >= 32).strip()
    if not text:
        raise DocumentError("DOCUMENT_NO_TEXT")
    return {"format": kind, "text": text[:MAX_TEXT], "truncated": len(text) > MAX_TEXT,
            "limitations": limitation, "untrusted": True}


def extract(data, name):
    kind = extension(name)
    if type(data) is not bytes or not 0 < len(data) <= MAX_BYTES:
        raise DocumentError("DOCUMENT_SIZE_INVALID")
    process = subprocess.Popen([sys.executable, "-I", "-B", str(Path(__file__).resolve()), "--worker", kind],
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                               cwd="/", env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"}, start_new_session=True)
    try:
        output, _ = process.communicate(data, timeout=8)
    except BaseException:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.communicate()
        raise DocumentError("DOCUMENT_EXTRACTION_INTERRUPTED") from None
    if process.returncode or len(output) > 200000:
        raise DocumentError("DOCUMENT_EXTRACTION_FAILED")
    result = json.loads(output)
    if "error" in result:
        raise DocumentError(result["error"])
    return dict(result, name=name, sha256=hashlib.sha256(data).hexdigest(), bytes=len(data))


def _worker(kind):
    import resource
    resource.setrlimit(resource.RLIMIT_CPU, (5, 5))
    resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024,) * 2)
    resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    try:
        data = sys.stdin.buffer.read(MAX_BYTES + 1)
        if not 0 < len(data) <= MAX_BYTES or kind not in FORMATS:
            raise DocumentError("DOCUMENT_SIZE_INVALID")
        result = _extract(data, kind)
    except DocumentError as exc:
        result = {"error": str(exc)}
    except Exception:
        result = {"error": "DOCUMENT_INVALID_OR_UNAVAILABLE"}
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__" and len(sys.argv) == 3 and sys.argv[1] == "--worker":
    _worker(sys.argv[2])
