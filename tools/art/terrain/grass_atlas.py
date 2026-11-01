#!/usr/bin/env python3
"""Ground-cover atlas for the v3 terrain dress (terrain polish, 2026-11-01).

Writes game/assets/terrain/v3/grass_atlas.png: RGBA, 4 cells of 256 px in a row, drawn from scratch with PIL (no
third-party art, so no licence beyond the project's):
  0, 1  grass clumps (tapered, curved blades, dark base to pale tip)
  2     tall dry grass / reeds (fewer, longer, straighter blades)
  3     low herb / sedge tuft (short broad blades, a few seed heads)
Colour is a neutral green-grey ramp; the game tints every instance (the map palette's own mean ground colours), so
one atlas serves every biome. Deterministic: numpy seed per cell. Run: python3 tools/art/terrain/grass_atlas.py
"""
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

OUT = Path(__file__).resolve().parents[3] / "game/assets/terrain/v3/grass_atlas.png"
CELL = 256
SS = 3  # supersample


def blade(d, rng, x0, y0, length, width, lean, curl, col_base, col_tip):
    n = 14
    pts_l, pts_r = [], []
    for i in range(n + 1):
        t = i / n
        # a bent stem: lean at the base, curl toward the tip
        x = x0 + lean * length * (t ** 1.4) + curl * length * (t ** 2.6)
        y = y0 - length * t * (1.0 - 0.18 * abs(curl))
        w = width * (1.0 - t) ** 0.8 * (1.0 if t > 0.02 else 0.85)
        pts_l.append((x - w, y))
        pts_r.append((x + w, y))
    for i in range(n):
        t = i / n
        c = tuple(int(col_base[k] + (col_tip[k] - col_base[k]) * t) for k in range(3))
        d.polygon([pts_l[i], pts_r[i], pts_r[i + 1], pts_l[i + 1]], fill=c + (255,))


def cell(idx):
    rng = np.random.default_rng(777 + idx)
    S = CELL * SS
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    cx = S / 2
    base_y = S * 0.985
    if idx in (0, 1):
        nb = 34 if idx == 0 else 26
        for k in range(nb):
            spread = rng.normal(0, 0.55)
            x0 = cx + rng.normal(0, S * 0.045)
            length = S * rng.uniform(0.38, 0.92) * (1.0 - 0.35 * min(abs(spread), 1.0))
            width = S * rng.uniform(0.008, 0.016)
            g = rng.uniform(0.85, 1.15)
            blade(d, rng, x0, base_y, length, width, spread * 0.5, rng.uniform(-0.25, 0.25) + spread * 0.2,
                  (int(40 * g), int(62 * g), int(26 * g)), (int(150 * g), int(176 * g), int(78 * g)))
    elif idx == 2:
        for k in range(16):
            x0 = cx + rng.normal(0, S * 0.07)
            length = S * rng.uniform(0.7, 0.98)
            width = S * rng.uniform(0.006, 0.011)
            s = rng.normal(0, 0.18)
            g = rng.uniform(0.9, 1.1)
            blade(d, rng, x0, base_y, length, width, s, s * 0.6 + rng.uniform(-0.1, 0.1),
                  (int(70 * g), int(78 * g), int(36 * g)), (int(188 * g), int(184 * g), int(106 * g)))
    else:
        for k in range(22):
            x0 = cx + rng.normal(0, S * 0.10)
            length = S * rng.uniform(0.28, 0.6)
            width = S * rng.uniform(0.016, 0.03)
            s = rng.normal(0, 0.9)
            g = rng.uniform(0.9, 1.1)
            blade(d, rng, x0, base_y, length, width, s * 0.45, s * 0.35,
                  (int(46 * g), int(70 * g), int(30 * g)), (int(126 * g), int(158 * g), int(70 * g)))
        for k in range(5):  # seed heads on thin stems
            x0 = cx + rng.normal(0, S * 0.09)
            h = S * rng.uniform(0.6, 0.86)
            d.line([(x0, base_y), (x0 + rng.normal(0, 8), base_y - h)], fill=(120, 130, 70, 255), width=int(S * 0.004))
            tx, ty = x0, base_y - h
            d.ellipse([tx - S * 0.012, ty - S * 0.035, tx + S * 0.012, ty + S * 0.01], fill=(176, 160, 96, 255))
    im = im.resize((CELL, CELL), Image.LANCZOS)
    # colour bleed under transparent texels, so mip filtering does not fringe
    a = np.asarray(im).copy()
    rgb = a[..., :3].astype(float)
    m = a[..., 3] > 8
    if m.any():
        mean = rgb[m].mean(0)
        rgb[~m] = mean
        blurred = np.asarray(Image.fromarray(rgb.astype(np.uint8)).filter(ImageFilter.GaussianBlur(2)))
        rgb = np.where(m[..., None], rgb, blurred)
    a[..., :3] = rgb.astype(np.uint8)
    return Image.fromarray(a)


def main():
    atlas = Image.new("RGBA", (CELL * 4, CELL), (0, 0, 0, 0))
    for i in range(4):
        atlas.paste(cell(i), (i * CELL, 0))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    atlas.save(OUT, optimize=True)
    print("wrote", OUT, OUT.stat().st_size // 1024, "KB")


if __name__ == "__main__":
    main()
