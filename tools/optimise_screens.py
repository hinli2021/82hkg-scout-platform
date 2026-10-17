#!/usr/bin/env python3
"""Turn freshly taken QA screenshots into small WebP files.

The browser checks (`tools/checks/check_*.py`) drop PNGs into docs/screens/.
That folder is not version-controlled, but it does travel inside the release
pack, so keeping it lean matters:

    cd scout-platform-py && python3 tools/optimise_screens.py

Every *.png under docs/screens/ is re-encoded as WebP (width ≤ 1100, quality 88)
and the PNG is removed when the WebP is smaller — which it always is.
Existing *.webp files are left alone. Safe to run any time.
"""
from __future__ import annotations

import pathlib

from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parent.parent
FOLDER = ROOT / "docs" / "screens"


def main() -> None:
    before = after = 0
    converted = skipped = 0
    for png in sorted(FOLDER.glob("*.png")):
        size = png.stat().st_size
        before += size
        try:
            img = Image.open(png)
            img.load()
        except Exception as exc:                      # noqa: BLE001
            print("kept (unreadable):", png.name, exc)
            after += size
            skipped += 1
            continue
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGB")
        if img.width > 1100:
            img = img.resize((1100, round(img.height * 1100 / img.width)), Image.LANCZOS)
        out = png.with_suffix(".webp")
        img.save(out, "WEBP", quality=88, method=6)
        new = out.stat().st_size
        if new < size:
            png.unlink()
            after += new
            converted += 1
        else:
            out.unlink()
            after += size
            skipped += 1
    print(f"converted {converted} · kept {skipped} · "
          f"{before/1048576:.1f} MB → {after/1048576:.1f} MB")


if __name__ == "__main__":
    main()
