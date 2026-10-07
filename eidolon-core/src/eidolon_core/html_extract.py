# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : html_extract.py
# Description : Extraction bornée du texte visible d'un HTML UTF-8, sans réseau ni exécution
# Standard    : Eidolon Presentation Standard v1
# ==========================================================

"""Pure extractor (C-TASK-G026); optional research/WebReader integration in C-011.

Pure function over bytes: no fetch, no JavaScript, no remote resource, no file,
no model. The result is untrusted external text; nothing in a page becomes a
permission. Rendering rules are explicit and small (docs/HTML-EXTRACTION.md):
this is not a CSS engine, and a challenge/login/paywall page is not "solved" by
extraction, only exposed through neutral signals for a later classifier.
"""
from dataclasses import dataclass
import hashlib
from html.parser import HTMLParser
import re

from .contracts import ContractError

VERSION = "eidolon-html-extract/1"

# Content of these elements is never text: code, templates, embedded documents.
SKIPPED = {"script", "style", "template", "noscript", "svg", "math", "iframe", "object", "embed",
           "canvas", "select", "datalist", "head", "title"}
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param",
        "source", "track", "wbr"}
BLOCKS = {"address", "article", "aside", "blockquote", "body", "caption", "dd", "details", "dialog",
          "div", "dl", "dt", "fieldset", "figcaption", "figure", "footer", "form", "h1", "h2", "h3",
          "h4", "h5", "h6", "header", "hr", "html", "legend", "li", "main", "nav", "ol", "p", "pre",
          "section", "summary", "table", "tbody", "td", "tfoot", "th", "thead", "tr", "ul"}
# Valid HTML closes these implicitly (WHATWG "close a p element", li/dd/dt start tags);
# without it, unclosed <p>/<li> would reach the depth bound or stay hidden after a hidden one.
P_CLOSERS = {"address", "article", "aside", "blockquote", "center", "details", "dialog", "dir", "div",
             "dl", "fieldset", "figcaption", "figure", "footer", "form", "h1", "h2", "h3", "h4", "h5",
             "h6", "header", "hgroup", "hr", "li", "dd", "dt", "listing", "main", "menu", "nav", "ol",
             "p", "pre", "search", "section", "summary", "table", "ul", "xmp"}
# End tag optional in HTML: closing them implicitly is not a malformation.
OPTIONAL_END = {"html", "head", "body", "p", "li", "dd", "dt", "option", "optgroup", "rt", "rp",
                "tbody", "thead", "tfoot", "tr", "td", "th", "colgroup", "caption"}
SCOPE = {"applet", "button", "caption", "html", "marquee", "object", "table", "td", "template", "th"}
HIDDEN_STYLE = re.compile(r"(?:^|;)\s*(?:display\s*:\s*none|visibility\s*:\s*(?:hidden|collapse)"
                          r"|content-visibility\s*:\s*hidden)\s*(?:!important\s*)?(?:;|$)", re.I)
# C0 except tab/LF (CR and FF are HTML whitespace, normalised before), DEL and C1.
CONTROLS = re.compile(r"[\x00-\x08\x0b\x0e-\x1f\x7f-\x9f]")
BIDI = re.compile(r"[‪-‮⁦-⁩]")
SPACES = re.compile(r"[ \t\r\n\f ]+")


@dataclass(frozen=True)
class ExtractLimits:
    input_bytes: int = 128_000      # same order as the WebReader body bound
    output_chars: int = 64_000
    depth: int = 128                # open non-void elements
    segments: int = 2_000           # paragraphs, list items, headings, cells...

    def __post_init__(self):
        for name, maximum in (("input_bytes", 8_000_000), ("output_chars", 1_000_000),
                              ("depth", 1_000), ("segments", 100_000)):
            value = getattr(self, name)
            if type(value) is not int or not 1 <= value <= maximum:
                raise ContractError("INVALID_EXTRACT_LIMITS: " + name)


class _Parser(HTMLParser):
    def __init__(self, limits):
        super().__init__(convert_charrefs=True)
        self.limits = limits
        self.stack = []             # open elements: (tag, hidden_or_skipped)
        self.skip = 0               # depth inside skipped or hidden elements
        self.pre = 0
        self.segments, self.current = [], []
        self.prefix = ""
        self.lists = []             # "ul" / ["ol", n]
        self.warnings = set()
        self.halted = None          # limit code once a bound is reached
        self.title, self.title_open, self.title_done = [], False, False
        self.controls = False       # a control character came from an entity
        self.password_field, self.forms, self.hidden_skipped, self.unbalanced = False, 0, 0, 0

    # ---- segments ---------------------------------------------------------------------------
    def _flush(self):
        text = "".join(self.current)
        self.current = []
        text = text if self.pre else SPACES.sub(" ", text).strip()
        if self.pre:
            text = text.strip("\n")
        if CONTROLS.search(text):
            text, self.controls = CONTROLS.sub("", text), True
        if not text.strip():
            self.prefix = ""
            return
        if len(self.segments) >= self.limits.segments:
            self.halted = self.halted or "SEGMENT_LIMIT"
            return
        self.segments.append(self.prefix + text)
        self.prefix = ""

    # ---- tags -------------------------------------------------------------------------------
    def handle_starttag(self, tag, attrs):
        if self.halted:
            return
        values = dict(attrs)
        if tag == "input" and (values.get("type") or "").lower() == "password":
            self.password_field = True
        if tag == "form":
            self.forms += 1
        if tag in VOID:
            if tag == "br" and self.pre and not self.skip:
                self.current.append("\n")
            elif tag in {"br", "hr"} and not self.skip:
                self._flush()  # a line break outside <pre> starts a new segment
            return
        self._implicit_close(tag)
        if len(self.stack) >= self.limits.depth:
            self.halted = "DEPTH_LIMIT"
            return
        if tag == "title" and not self.title_done and not any(n in {"svg", "math"} for n, _ in self.stack):
            self.title_open = True  # first document title only; an SVG/MathML title is not one
        hidden = "hidden" in values or HIDDEN_STYLE.search(values.get("style") or "") is not None
        excluded = tag in SKIPPED or hidden
        if hidden and not self.skip:
            self.hidden_skipped += 1
        self.stack.append((tag, excluded))
        if excluded:
            self.skip += 1
            return
        if self.skip:
            return
        if tag in BLOCKS:
            self._flush()
        if tag == "pre":
            self.pre += 1
        if tag == "ul":
            self.lists.append("ul")
        elif tag == "ol":
            self.lists.append(["ol", 0])
        elif tag == "li":
            kind = self.lists[-1] if self.lists else "ul"
            if isinstance(kind, list):
                kind[1] += 1
                self.prefix = f"{kind[1]}. "
            else:
                self.prefix = "- "

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID and self.stack and self.stack[-1][0] == tag:
            self.handle_endtag(tag)

    def _implicit_close(self, tag):
        targets = ({"li"} if tag == "li" else {"dd", "dt"} if tag in {"dd", "dt"} else set())
        for name, _ in reversed(self.stack):
            if name in targets:
                self._close(name, implicit=True)
                break
            if name in SCOPE or (targets and name in BLOCKS and name not in {"address", "div", "p"}):
                break
        if tag in P_CLOSERS:
            for name, _ in reversed(self.stack):
                if name == "p":
                    self._close("p", implicit=True)
                    break
                if name in SCOPE:
                    break

    def handle_endtag(self, tag):
        if self.halted or tag in VOID:
            return
        if tag not in [name for name, _ in self.stack]:
            self.unbalanced += 1      # stray end tag: ignored
            return
        self._close(tag)

    def _close(self, tag, implicit=False):
        while self.stack:
            name, excluded = self.stack.pop()
            if name != tag and not implicit and name not in OPTIONAL_END:
                self.unbalanced += 1  # element closed by a mismatched end tag
            if name == "title" and self.title_open:
                self.title_open, self.title_done = False, True
            if excluded:
                self.skip -= 1
            elif not self.skip:
                if name in BLOCKS:
                    self._flush()
                if name == "pre":
                    self.pre -= 1
                if name in {"ul", "ol"} and self.lists:
                    self.lists.pop()
            if name == tag:
                break

    def handle_data(self, data):
        if self.title_open and len("".join(self.title)) < 300:
            self.title.append(data)
        if self.halted or self.skip:
            return
        self.current.append(data)

    # comments, declarations, processing instructions and CDATA are never text
    def handle_comment(self, data):
        return None

    def unknown_decl(self, data):
        return None


def extract(data, limits=None):
    """Return a structured, bounded extraction of the visible text of UTF-8 HTML bytes."""
    if type(data) is not bytes:
        raise ContractError("INVALID_HTML_INPUT: bytes required")
    limits = ExtractLimits() if limits is None else limits  # {} or 0 is an error, not the defaults
    if not isinstance(limits, ExtractLimits):
        raise ContractError("INVALID_EXTRACT_LIMITS")
    result = {"version": VERSION, "status": None, "complete": False, "text": None,
              "source_sha256": hashlib.sha256(data).hexdigest(), "source_bytes": len(data),
              "text_sha256": None, "text_chars": 0, "segments": 0, "title": None,
              "signals": {"password_field": False, "forms": 0, "classification": None},
              "warnings": [], "limits": {"input_bytes": limits.input_bytes, "output_chars": limits.output_chars,
                                          "depth": limits.depth, "segments": limits.segments},
              "trust": "untrusted_external_text", "authorizes_execution": False}
    if len(data) > limits.input_bytes:
        result.update(status="REFUSED", warnings=["INPUT_TOO_LARGE"])
        return result
    try:
        decoded = data.decode("utf-8-sig")  # strict: no replacement characters, no charset guessing
    except UnicodeDecodeError:
        result.update(status="REFUSED", warnings=["INVALID_UTF8"])
        return result
    warnings = set()
    # CR and FF are HTML whitespace: removing them would glue words ("ne\rpas" -> "nepas").
    decoded = decoded.replace("\r\n", "\n").replace("\r", "\n").replace("\f", " ")
    if CONTROLS.search(decoded):
        warnings.add("CONTROL_CHARACTERS_REMOVED")
        decoded = CONTROLS.sub("", decoded)
    parser = _Parser(limits)
    try:
        parser.feed(decoded)
        parser.close()
    except (RecursionError, AssertionError) as exc:  # html.parser is lenient; keep a bounded diagnostic
        result.update(status="REFUSED", warnings=sorted(warnings | {"PARSER_ERROR:" + type(exc).__name__}))
        return result
    if not parser.halted:
        parser._flush()
    if not parser.halted and any(name not in OPTIONAL_END for name, _ in parser.stack):
        warnings.add("UNCLOSED_ELEMENTS")
    if parser.unbalanced:
        warnings.add("UNBALANCED_TAGS")
    if parser.controls:
        warnings.add("CONTROL_CHARACTERS_REMOVED")
    if parser.hidden_skipped:
        warnings.add("HIDDEN_CONTENT_SKIPPED")
    # Whole segments only: a cut never splits a sentence or drops a following negation silently.
    kept, size = [], 0
    for segment in parser.segments:
        extra = len(segment) + (2 if kept else 0)
        if size + extra > limits.output_chars:
            parser.halted = parser.halted or "OUTPUT_LIMIT"
            break
        kept.append(segment)
        size += extra
    text = "\n\n".join(kept)
    if BIDI.search(text):
        warnings.add("BIDI_CONTROLS_PRESENT")
    if parser.halted:
        warnings.add(parser.halted)
    title = SPACES.sub(" ", "".join(parser.title)).strip()[:300] or None
    result.update(text=text or None, text_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest() if text else None,
                  text_chars=len(text), segments=len(kept), title=title,
                  signals={"password_field": parser.password_field, "forms": parser.forms, "classification": None},
                  warnings=sorted(warnings))
    if parser.halted:
        result["status"] = "PARTIAL"
    elif not text:
        result.update(status="EMPTY", complete=True)
    else:
        result.update(status="OK", complete=True)
    return result
