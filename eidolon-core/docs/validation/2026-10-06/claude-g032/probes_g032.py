# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : probes_g032.py
# Description : Sondes de robustesse de l'extracteur HTML, avant/après (C-TASK-G032)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""Run with PYTHONPATH pointing to the tree under test. Prints one line per probe."""
import time

from eidolon_core.contracts import ContractError
from eidolon_core.html_extract import ExtractLimits, extract


def show(name, result, keys=("status", "text", "title", "warnings")):
    print(f"{name}: " + " | ".join(f"{k}={result[k]!r}" for k in keys))


def page(body, head="<title>T</title>"):
    return f"<!doctype html><html><head>{head}</head><body>{body}</body></html>".encode()


# 1. Implicitly closed <p> and <li> (valid HTML): depth and visibility
show("P1 200 <p> sans fermeture, profondeur 128", extract(b"<p>x" * 200), ("status", "warnings"))
show("P2 <li> sans fermeture, profondeur 20", extract(page("<ul>" + "<li>item" * 30 + "</ul><p>ne pas oublier</p>"), ExtractLimits(depth=20)), ("status", "warnings"))
show("P3 <li hidden> puis <li> visible", extract(page("<ul><li hidden>caché<li>visible : ne pas conclure</ul>")))
show("P4 <p hidden> puis <div> visible", extract(page("<p hidden>caché<div>visible</div>")))
show("P5 <dt>/<dd> non fermés", extract(page("<dl><dt>terme<dd>définition<dt>terme 2<dd>déf 2</dl>")), ("status", "text", "warnings"))

# 2. Titles
show("T1 <title> dans <svg>", extract(page("<svg><title>icône</title></svg><p>texte</p>")))
show("T2 deux <title>", extract(page("<p>a</p><title>second</title>", head="<title>premier</title>")))
show("T3 <title> dans <body> (non affiché)", extract(b"<body><title>titre</title><p>texte</p></body>"))

# 3. Controls and whitespace
show("C1 CR seul entre deux mots", extract(b"<p>ne\rpas conclure</p>"))
show("C2 CRLF ordinaire", extract(b"<p>ligne\r\nsuite</p>"))
show("C3 saut de page entre deux mots", extract(b"<p>ne\x0cpas</p>"))
show("C4 contrôle par entité &#7;", extract(b"<p>a&#7;b</p>"))
show("C5 C1 brut U+0085", extract("<p>a\u0085b</p>".encode()))
show("C6 bidi par entité &#x202E;", extract(b"<p>abc&#x202E;def</p>"), ("text", "warnings"))
show("C7 NUL par entité &#0;", extract(b"<p>a&#0;b</p>"))

# 4. Limits passed as falsy values
for value in ({}, 0, "", [], False):
    try:
        extract(b"<p>x</p>", limits=value)
        print(f"L1 limits={value!r}: ACCEPTÉ (défauts utilisés)")
    except ContractError as exc:
        print(f"L1 limits={value!r}: refusé {exc}")

# 5. One segment longer than output_chars
show("S1 segment unique de 200 > 80", extract(page("<p>" + "mot " * 50 + "</p>"), ExtractLimits(output_chars=80)),
     ("status", "text", "warnings"))

# 6. Hidden style variants
for style in ("display:none", "DISPLAY : NONE", "display:none!important", "color:red;display:none",
              "display: none ; color:red", "visibility:collapse", "content-visibility:hidden"):
    r = extract(page(f'<p style="{style}">caché</p><p>visible</p>'))
    print(f"H1 style={style!r}: text={r['text']!r}")

# 7. Cost at the maximum input (128 000 bytes)
for name, body in (("paragraphes", b"<p>" + b"mot " * 30 + b"</p>"), ("imbrication", b"<div>"), ("entités", b"&amp;" * 20)):
    data = (body * (128_000 // len(body)))[:128_000]
    start = time.perf_counter()
    r = extract(data)
    print(f"K1 {name} {len(data)} octets: {r['status']} {r['warnings']} {1000 * (time.perf_counter() - start):.0f} ms")
