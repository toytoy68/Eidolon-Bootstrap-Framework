# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : build_ico.py
# Description : Assemble desktop/tauri/icons (icon.ico et PNG) depuis les rendus de logo_e.js
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
"""From eidolon-core/: python3 docs/proposals/2026-10-08-claude-icon-variants/build_ico.py

Choice validated by toytoy (08-09/10/2026): the simplified "e" (petit) up to 32 px, the full
icon (grand) from 40 px. Every ICO entry is a copied PNG (Windows Vista+), byte-identical to
its source in png/. Standard library only."""
import shutil
import struct
from pathlib import Path

HERE = Path(__file__).resolve().parent
ICONS = HERE.parents[2] / "desktop" / "tauri" / "icons"
LAST_SIMPLIFIED = 32
ICO_SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 256)
PNG_FILES = {"32x32.png": 32, "128x128.png": 128, "128x128@2x.png": 256, "icon.png": 512}


def source(size):
    return HERE / "png" / f"logo-e-{'petit' if size <= LAST_SIMPLIFIED else 'grand'}-{size}.png"


def build_ico(sizes):
    blobs = [source(s).read_bytes() for s in sizes]
    offset = 6 + 16 * len(sizes)
    head = struct.pack("<HHH", 0, 1, len(sizes))
    for size, blob in zip(sizes, blobs):
        # Width/height 0 means 256; 0 colors, 1 plane, 32 bits per pixel.
        head += struct.pack("<BBBBHHII", size % 256, size % 256, 0, 0, 1, 32, len(blob), offset)
        offset += len(blob)
    return head + b"".join(blobs)


def main():
    (ICONS / "icon.ico").write_bytes(build_ico(ICO_SIZES))
    for name, size in PNG_FILES.items():
        shutil.copyfile(source(size), ICONS / name)
    for s in ICO_SIZES:
        print(f"{s:>3} px <- {source(s).name}")


if __name__ == "__main__":
    main()
