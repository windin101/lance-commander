#!/usr/bin/env python3
"""Ground-mark textures (world-rendering step 4): footprints, craters, scorch and a water wake ring.

    python3 -I tools/art/decals.py [--src reference/mc2-source/Source/Data]

The original's marks are tiny: per-mech footprints are 16 px cells in Textures/Defaults/feet0001.tga (8 x 8
grid, a left and right cell per mech in craterUVTable order, MCLib/crater.cpp:48-112), craters 32 px cells in
feet0000.tga. This keeps each mech's own foot SHAPE (the cell's alpha, smoothly enlarged) and draws it at 128 px
as a pressed-in print (darker floor, lighter rim), and draws four new 512 px craters and a scorch mark
procedurally (charred centre, ejecta ring, radial streaks). Writes game/assets/decals/: feet/<mech>_l.png,
feet/<mech>_r.png, crater_0..3.png, scorch.png, wake.png. Used by game/scripts/world/decals_view.gd.
The footprint shapes derive from the Shared Source art; the rest is new.
"""
import argparse
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "game/assets/decals"
MECHS = ["anubis", "atlas", "bloodasp", "bushwacker", "catapult", "cougar", "cyclops", "enfield", "flea", "highlander",
         "hollander", "hunchback", "jaegermech", "laohu", "madcat", "menshen", "raven", "ryoken", "shadowcat", "shayu",
         "shootist", "starslayer", "thor", "uller", "urbanmech", "vulture", "werewolf", "wolfhound", "zeus"]


def noise(n, scale, rng):
    a = ndimage.gaussian_filter(rng.random((n, n)), scale, mode="wrap")
    return (a - a.min()) / (a.max() - a.min() + 1e-9)


def footprint(cell_alpha, size=128):
    """A pressed-in print from a 16 px cell's alpha: enlarged smoothly, floor darker, rim lighter."""
    c = cell_alpha.astype(float)
    c = c / (c.max() + 1e-9)  # the original's alpha only reaches about 0.4
    c = ndimage.grey_dilation(c, size=(2, 2))  # 1 px toe strokes -> a foot body
    a = np.asarray(Image.fromarray((c * 255).astype(np.uint8)).resize((size, size), Image.BICUBIC)).astype(float) / 255
    a = ndimage.gaussian_filter(a, size / 48)
    m = np.clip((a - 0.35) * 6, 0, 1)
    depth = ndimage.distance_transform_edt(m > 0.5)
    depth = depth / (depth.max() + 1e-9)
    rgba = np.zeros((size, size, 4))
    rgba[..., :3] = 0.18 + 0.12 * (1 - depth[..., None])  # dark compacted floor, lighter toward the edge
    rim = np.clip(ndimage.gaussian_filter(m, 2.0) - m, 0, 1)  # displaced soil just outside the print
    rgba[..., :3] = rgba[..., :3] * (1 - rim[..., None]) + 0.55 * rim[..., None]
    rgba[..., 3] = np.clip(m * 0.75 + rim * 0.5, 0, 1)
    return Image.fromarray((rgba * 255).astype(np.uint8), "RGBA")


def crater(seed, size=512):
    rng = np.random.default_rng(seed)
    y, x = np.mgrid[0:size, 0:size] / (size / 2) - 1.0
    r = np.hypot(x, y)
    ang = np.arctan2(y, x)
    n1 = noise(size, size / 40, rng)
    n2 = noise(size, size / 10, rng)
    n3 = noise(size, size / 25, rng)
    rr = r * (0.7 + 0.6 * n2) + 0.12 * (n3 - 0.5)  # irregular outline, no clean circle
    bowl = np.clip(1 - rr / 0.55, 0, 1) ** 0.8
    ring = np.exp(-((rr - 0.62) / 0.12) ** 2) * (0.4 + 0.6 * n3)  # broken ejecta ring
    streaks = np.clip(np.sin(ang * rng.integers(9, 15) + n2 * 6) * 0.5 + 0.5, 0, 1) ** 3 * np.clip(1 - rr, 0, 1) * (rr > 0.5)
    char = np.clip(bowl * 1.4, 0, 1)
    col = np.zeros((size, size, 3))
    soil = np.array([0.32, 0.27, 0.21])
    col[:] = soil * (0.75 + 0.5 * n1[..., None])
    col = col * (1 - char[..., None]) + np.array([0.06, 0.055, 0.05]) * char[..., None]
    col = col * (1 - 0.35 * ring[..., None]) + 0.12 * ring[..., None] * soil
    alpha = np.clip(char + ring * 0.9 + streaks * 0.6, 0, 1) * np.clip((1.05 - rr) * 5, 0, 1)
    alpha *= 0.85 + 0.15 * n1
    return Image.fromarray(np.dstack([col, alpha]).clip(0, 1).__mul__(255).astype(np.uint8), "RGBA")


def scorch(size=512):
    rng = np.random.default_rng(99)
    y, x = np.mgrid[0:size, 0:size] / (size / 2) - 1.0
    r = np.hypot(x, y) * (0.8 + 0.4 * noise(size, size / 12, rng))
    a = np.clip(1 - r, 0, 1) ** 1.5 * (0.7 + 0.3 * noise(size, size / 30, rng))
    col = np.dstack([np.full_like(a, 0.05), np.full_like(a, 0.045), np.full_like(a, 0.04)])
    return Image.fromarray((np.dstack([col, a]) * 255).astype(np.uint8), "RGBA")


def wake(size=256):
    y, x = np.mgrid[0:size, 0:size] / (size / 2) - 1.0
    r = np.hypot(x, y)
    a = np.exp(-((r - 0.82) / 0.06) ** 2) + 0.5 * np.exp(-((r - 0.6) / 0.05) ** 2)
    return Image.fromarray((np.dstack([np.ones_like(a), np.ones_like(a), np.ones_like(a), np.clip(a, 0, 1) * 0.8]) * 255).astype(np.uint8), "RGBA")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=str(ROOT / "reference/mc2-source/Source/Data"))
    a = ap.parse_args()
    (OUT / "feet").mkdir(parents=True, exist_ok=True)
    feet = np.asarray(Image.open(f"{a.src}/Textures/Defaults/feet0001.tga").convert("RGBA"))
    cell = feet.shape[0] // 8
    for i, mech in enumerate(MECHS):
        for side, k in (("l", 2 * i), ("r", 2 * i + 1)):
            cx, cy = (k % 8) * cell, (k // 8) * cell
            alpha = feet[cy:cy + cell, cx:cx + cell, 3]

            footprint(alpha).save(OUT / "feet" / f"{mech}_{side}.png")
    for i in range(4):
        crater(10 + i).save(OUT / f"crater_{i}.png")
    scorch().save(OUT / "scorch.png")
    wake().save(OUT / "wake.png")
    print(f"decals: {2 * len(MECHS)} footprints, 4 craters, scorch, wake -> {OUT}")


if __name__ == "__main__":
    main()
