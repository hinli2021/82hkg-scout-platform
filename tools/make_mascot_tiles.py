"""Makes the per-patrol pictures used by the small views.

The big camp scene (`scene.jpg`) carries the sign-in page on wide screens. Where
space is tight — the ≤360 px fallback cards on the sign-in page, the 96–104 px
art on the name picker and the "create your password" page — each patrol needs
its own picture. Those are cut here as clean 4:5 portrait tiles out of the same
artwork, so every view shows the same animals.

(A true cut-out with transparency was tried first: the artwork is one painted
scene, so a mask either left the tent and the trees in or ate the wings. Tiles
are deliberate, tidy and match the rounded cards they sit in.)

Run from the project root:   python3 tools/make_mascot_tiles.py
"""
from __future__ import annotations

import pathlib

from PIL import Image, ImageOps

ROOT = pathlib.Path(__file__).resolve().parent.parent
SOURCE = ROOT / "static/img/mascots/_source/scene-master.png"
OUT = ROOT / "static/img/mascots"
TILE = (620, 775)                    # 4:5, the shape the cards use

# where each animal lives in the 1407×768 master (fractions), and where inside
# that box to aim the crop (0 = top, 1 = bottom)
BOXES = {
    "otter":   ((0.050, 0.155, 0.340, 0.965), 0.42),
    "tiger":   ((0.360, 0.050, 0.663, 0.875), 0.40),
    "seagull": ((0.657, 0.135, 0.950, 0.880), 0.40),
}

if __name__ == "__main__":
    master = Image.open(SOURCE).convert("RGB")
    W, H = master.size
    for name, ((l, t, r, b), aim) in BOXES.items():
        crop = master.crop((int(l * W), int(t * H), int(r * W), int(b * H)))
        tile = ImageOps.fit(crop, TILE, method=Image.LANCZOS, centering=(0.5, aim))
        path = OUT / f"{name}.webp"
        tile.save(path, quality=88, method=6)
        print(f"{name}.webp  {tile.size[0]}×{tile.size[1]}  {path.stat().st_size / 1024:,.0f} KB")
