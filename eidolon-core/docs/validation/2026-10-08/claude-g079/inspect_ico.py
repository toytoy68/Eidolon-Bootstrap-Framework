# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : inspect_ico.py
# Description : Lecture indépendante de icon.ico : structure, PNG internes, transparence, contraste par taille (C-TASK-G079)
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""python3 inspect_ico.py <icon.ico> <out dir>

Standard library only. Parses the ICONDIR itself (it does not trust the generator), decodes
every embedded PNG (8-bit RGBA, all five filters) and writes each entry as entry-<size>.png,
byte-identical to what Windows reads."""
import json
import struct
import sys
import zlib
from pathlib import Path


def decode_png(data):
    assert data[:8] == b"\x89PNG\r\n\x1a\n", "PNG signature"
    pos, idat, ihdr = 8, b"", None
    while pos < len(data):
        length, kind = struct.unpack(">I4s", data[pos:pos + 8])
        chunk = data[pos + 8:pos + 8 + length]
        crc = struct.unpack(">I", data[pos + 8 + length:pos + 12 + length])[0]
        assert zlib.crc32(kind + chunk) == crc, f"CRC {kind}"
        if kind == b"IHDR":
            ihdr = struct.unpack(">IIBBBBB", chunk)
        elif kind == b"IDAT":
            idat += chunk
        pos += 12 + length
    w, h, depth, ctype, _, _, interlace = ihdr
    assert (depth, ctype, interlace) == (8, 6, 0), f"expected 8-bit RGBA non interlaced, got {ihdr}"
    raw, stride, bpp = zlib.decompress(idat), w * 4, 4
    rows, prev, i = [], bytearray(stride), 0
    for _ in range(h):
        f, line = raw[i], bytearray(raw[i + 1:i + 1 + stride]); i += 1 + stride
        for x in range(stride):
            a = line[x - bpp] if x >= bpp else 0
            b, c = prev[x], prev[x - bpp] if x >= bpp else 0
            if f == 1: line[x] = (line[x] + a) & 255
            elif f == 2: line[x] = (line[x] + b) & 255
            elif f == 3: line[x] = (line[x] + (a + b) // 2) & 255
            elif f == 4:
                p = a + b - c; pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                line[x] = (line[x] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        rows.append(bytes(line)); prev = line
    return w, h, rows


def lum(r, g, b):
    f = lambda v: v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4  # noqa: E731
    return 0.2126 * f(r / 255) + 0.7152 * f(g / 255) + 0.0722 * f(b / 255)


def measure(w, h, rows):
    px = [(row[4 * x], row[4 * x + 1], row[4 * x + 2], row[4 * x + 3]) for row in rows for x in range(w)]
    corners = [rows[y][4 * x + 3] for y, x in ((0, 0), (0, w - 1), (h - 1, 0), (h - 1, w - 1))]
    opaque = [p for p in px if p[3] >= 250]
    lums = sorted(lum(*p[:3]) for p in opaque)
    # "e" = brightest 10 % of opaque pixels, background = median: a rough legibility index.
    top = lums[int(len(lums) * 0.9):]
    fg, bg = sum(top) / len(top), lums[len(lums) // 2]
    return {"alpha_coins": corners, "opaque_pct": round(100 * len(opaque) / len(px), 1),
            "contraste_e_fond": round((fg + 0.05) / (bg + 0.05), 1)}


def main():
    ico, out = Path(sys.argv[1]), Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    data = ico.read_bytes()
    reserved, kind, count = struct.unpack("<HHH", data[:6])
    report = {"fichier": ico.name, "octets": len(data), "reserved": reserved, "type": kind, "images": count, "entrees": []}
    assert (reserved, kind) == (0, 1), "not an icon file"
    spans = []
    for n in range(count):
        bw, bh, colors, res, planes, bits, size, offset = struct.unpack("<BBBBHHII", data[6 + 16 * n:22 + 16 * n])
        dw, dh = bw or 256, bh or 256
        blob = data[offset:offset + size]
        assert offset + size <= len(data), "entry outside file"
        spans.append((offset, offset + size))
        w, h, rows = decode_png(blob)
        (out / f"entry-{dw}.png").write_bytes(blob)
        report["entrees"].append({"taille_annoncee": f"{dw}x{dh}", "png": f"{w}x{h}", "coherent": (w, h) == (dw, dh),
                                  "planes": planes, "bits": bits, "octets": size, **measure(w, h, rows)})
    spans.sort()
    report["chevauchement"] = any(a[1] > b[0] for a, b in zip(spans, spans[1:]))
    report["en_tete_attendu"] = spans[0][0] == 6 + 16 * count
    print(json.dumps(report, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
