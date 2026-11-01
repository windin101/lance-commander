#!/usr/bin/env python3
"""Understorey plant atlas for the v3 terrain dress (terrain polish round 3, 2026-11-01).

Writes game/assets/terrain/v3/plants_atlas.png: RGBA, 2 x 2 cells of 512 px, drawn from scratch with PIL (no
third-party art, so nothing beyond the project's own licence):
  0  fern: a rosette's worth of arching pinnate fronds growing from the bottom centre
  1  wildflowers: grass-blade leaves and thin stems carrying daisies, buttercups, violets, clover heads, umbels
  2  leaf mass: a TILEABLE dense foliage texture (leaves of five greens, ~9 % holes), for bushes and hedges
  3  dry scrub: grey-brown twigs with a few small sage-green and tan leaves, for arid, stony and snowy ground
The game tints every instance (shaders/plants.gdshader); the colours here are neutral-to-natural so a tint near mid
grey keeps them. Deterministic (numpy seed per cell). Run: python3 -I tools/art/terrain/plants_atlas.py
"""
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

OUT = Path(__file__).resolve().parents[3] / "game/assets/terrain/v3/plants_atlas.png"
CELL = 512
SS = 3
S = CELL * SS


def leaf_poly(x, y, ang, length, width, n=7):
    """A pointed leaf outline from (x, y) along `ang` (radians)."""
    ca, sa = math.cos(ang), math.sin(ang)
    left, right = [], []
    for i in range(n + 1):
        t = i / n
        w = width * math.sin(math.pi * t ** 0.8) * (1.0 - 0.15 * t)
        px, py = x + ca * length * t, y + sa * length * t
        left.append((px - sa * w, py + ca * w))
        right.append((px + sa * w, py - ca * w))
    return left + right[::-1]


def fern():
    rng = np.random.default_rng(101)
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    cx, by = S * 0.5, S * 0.985
    fronds = 9
    for k in range(fronds):
        spread = (k / (fronds - 1) - 0.5) * 2 * 0.95 + rng.normal(0, 0.06)   # -1.25..1.25 rad off vertical
        L = S * rng.uniform(0.5, 0.82) * (1.0 - 0.2 * abs(spread))
        droop = 0.55 * abs(spread) + rng.uniform(0.0, 0.25)
        g = rng.uniform(0.85, 1.15)
        N = 34
        pts = []
        for i in range(N + 1):
            t = i / N
            x = cx + math.sin(spread) * L * t
            y = by - math.cos(spread) * L * t * (1.0 - 0.15 * abs(spread)) + droop * L * t * t * 0.55
            pts.append((x, y))
        stem_w = max(2, int(S * 0.0045))
        for i in range(N):
            d.line([pts[i], pts[i + 1]], fill=(int(70 * g), int(100 * g), int(45 * g), 255), width=stem_w)
        for i in range(3, N, 2):
            t = i / N
            tx, ty = pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]
            sa = math.atan2(ty, tx)
            ll = L * 0.2 * (math.sin(math.pi * min(1.0, t ** 0.65)) + 0.12)
            lw = ll * 0.115
            base = (int(36 * g), int(66 * g), int(26 * g))
            tip = (int(118 * g), int(166 * g), int(70 * g))
            c = tuple(int(base[j] + (tip[j] - base[j]) * (0.35 + 0.65 * t)) for j in range(3)) + (255,)
            for side in (-1, 1):
                a = sa + side * math.radians(62 - 14 * t)
                d.polygon(leaf_poly(pts[i][0], pts[i][1], a, ll, lw), fill=c)
    return im


def flower(d, rng, x, y, kind, r):
    if kind == 0:     # daisy: white petals, yellow eye
        for k in range(11):
            a = 2 * math.pi * k / 11
            d.polygon(leaf_poly(x, y, a, r, r * 0.2, 5), fill=(214, 210, 196, 255))
        d.ellipse([x - r * 0.32, y - r * 0.32, x + r * 0.32, y + r * 0.32], fill=(226, 184, 40, 255))
    elif kind == 1:   # buttercup: five rounded yellow petals
        for k in range(5):
            a = 2 * math.pi * k / 5 + 0.3
            cx, cy = x + math.cos(a) * r * 0.5, y + math.sin(a) * r * 0.5
            d.ellipse([cx - r * 0.5, cy - r * 0.5, cx + r * 0.5, cy + r * 0.5], fill=(236, 200, 36, 255))
        d.ellipse([x - r * 0.2, y - r * 0.2, x + r * 0.2, y + r * 0.2], fill=(200, 140, 20, 255))
    elif kind == 2:   # violet / purple spike: a small cluster of dots
        for k in range(9):
            cx, cy = x + rng.normal(0, r * 0.5), y + rng.normal(0, r * 0.5) + k * r * 0.12
            d.ellipse([cx - r * 0.28, cy - r * 0.28, cx + r * 0.28, cy + r * 0.28], fill=(128, 84, 176, 255))
    elif kind == 3:   # clover head: a pink ball
        d.ellipse([x - r * 0.7, y - r * 0.7, x + r * 0.7, y + r * 0.7], fill=(206, 110, 148, 255))
        for k in range(8):
            cx, cy = x + rng.normal(0, r * 0.4), y + rng.normal(0, r * 0.4)
            d.ellipse([cx - r * 0.2, cy - r * 0.2, cx + r * 0.2, cy + r * 0.2], fill=(228, 150, 176, 255))
    else:             # umbel: many small white dots
        for k in range(16):
            cx, cy = x + rng.normal(0, r * 0.75), y + rng.normal(0, r * 0.4)
            d.ellipse([cx - r * 0.2, cy - r * 0.2, cx + r * 0.2, cy + r * 0.2], fill=(206, 206, 190, 255))


def flowers():
    """A low mound of wildflowers: a leafy base and many short-stemmed heads of five kinds, so one card is a colour patch
    that still reads at RTS range (the first version, tall thin stems, came out as white specks)."""
    rng = np.random.default_rng(202)
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    cx, by = S * 0.5, S * 0.985
    for k in range(34):   # leaves: short blades and rounded leaves, spread across the width
        x0 = cx + rng.normal(0, S * 0.17)
        ang = -math.pi / 2 + rng.normal(0, 0.7)
        L = S * rng.uniform(0.1, 0.26) * (1.0 - min(0.5, abs(x0 - cx) / S))
        d.polygon(leaf_poly(x0, by, ang, L, S * 0.016, 6), fill=(int(46 + rng.uniform(-8, 14)), int(92 + rng.uniform(-14, 16)), int(34), 255))
    heads = []
    for k in range(46):
        x0 = cx + rng.normal(0, S * 0.19)
        top = by - S * rng.uniform(0.15, 0.38) * (1.0 - min(0.45, abs(x0 - cx) / S * 0.9))
        heads.append((x0, top))
    heads.sort(key=lambda h: h[1])   # highest (furthest) first so lower heads overlap them
    for x0, top in heads:
        d.line([(x0 + rng.normal(0, S * 0.01), by - S * 0.04), (x0, top)], fill=(60, 100, 42, 255), width=max(3, int(S * 0.006)))
        flower(d, rng, x0, top, int(rng.choice([0, 1, 2, 3, 4], p=[0.08, 0.3, 0.25, 0.22, 0.15])), S * rng.uniform(0.03, 0.045))
    return im


def leaf_mass():
    rng = np.random.default_rng(303)
    im = Image.new("RGBA", (S, S), (22, 38, 16, 255))
    d = ImageDraw.Draw(im)
    greens = [(44, 82, 28), (58, 100, 34), (72, 118, 40), (36, 66, 24), (88, 128, 48)]
    # three passes: dark and small underneath, lighter and bigger on top, so there is depth in the texture
    for p, (count, lo, hi, lum) in enumerate(((520, 0.045, 0.075, 0.55), (620, 0.05, 0.085, 0.8), (460, 0.055, 0.09, 1.1))):
        for k in range(count):
            x, y = rng.uniform(0, S), rng.uniform(0, S)
            ang = rng.uniform(0, 2 * math.pi)
            L = S * rng.uniform(lo, hi)
            c = greens[rng.integers(len(greens))]
            c = tuple(int(np.clip(v * lum * rng.uniform(0.85, 1.15), 0, 255)) for v in c) + (255,)
            for ox in (-S, 0, S):
                for oy in (-S, 0, S):
                    if -L < x + ox < S + L and -L < y + oy < S + L:
                        d.polygon(leaf_poly(x + ox, y + oy, ang, L, L * 0.28, 6), fill=c)
    a = np.asarray(im).copy()
    # holes: ~9 % of the area, in blobs a few leaves wide, tileable (wrapped noise)
    noise = rng.normal(0, 1, (24, 24))
    big = np.asarray(Image.fromarray(((noise - noise.min()) / (noise.max() - noise.min()) * 255).astype(np.uint8)).resize((S, S), Image.BICUBIC)).astype(float) / 255.0
    # wrap the coarse noise so the tile edges agree
    n2 = np.tile(noise, (3, 3))
    big = np.asarray(Image.fromarray(((n2 - n2.min()) / (n2.max() - n2.min()) * 255).astype(np.uint8)).resize((S * 3, S * 3), Image.BICUBIC)).astype(float) / 255.0
    big = big[S:2 * S, S:2 * S]
    a[..., 3] = np.where(big > np.quantile(big, 0.915), 0, 255).astype(np.uint8)
    return Image.fromarray(a, "RGBA")


def scrub():
    rng = np.random.default_rng(404)
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    cx, by = S * 0.5, S * 0.985
    leaves = []

    def twig(x, y, ang, L, w, depth):
        if L < S * 0.03 or depth > 5:
            return
        n = 7
        pts = [(x, y)]
        a = ang
        for i in range(n):
            a += rng.normal(0, 0.14)
            x += math.cos(a) * L / n
            y += math.sin(a) * L / n
            pts.append((x, y))
        for i in range(n):
            d.line([pts[i], pts[i + 1]], fill=(98 - depth * 6, 86 - depth * 5, 70 - depth * 4, 255), width=max(2, int(w * (1 - i / (n * 1.4)))))
        for i in range(2, n + 1):
            if depth >= 2 and rng.random() < 0.45:
                leaves.append((pts[i][0], pts[i][1], a + rng.choice([-1, 1]) * rng.uniform(0.5, 1.2), S * rng.uniform(0.02, 0.034)))
        kids = 3 if depth < 2 else 2
        for k in range(kids):
            t = rng.uniform(0.3, 0.95)
            px, py = pts[int(t * n)]
            twig(px, py, a + rng.choice([-1, 1]) * rng.uniform(0.35, 0.9), L * rng.uniform(0.45, 0.65), w * 0.66, depth + 1)
        twig(pts[-1][0], pts[-1][1], a + rng.normal(0, 0.3), L * 0.55, w * 0.62, depth + 1)

    for k in range(5):
        twig(cx + rng.normal(0, S * 0.04), by, -math.pi / 2 + (k - 2) * 0.32 + rng.normal(0, 0.06), S * rng.uniform(0.5, 0.78), S * 0.011, 0)
    for (x, y, a, L) in leaves:
        c = [(122, 132, 84), (150, 138, 90), (104, 120, 78), (170, 150, 98)][rng.integers(4)]
        d.polygon(leaf_poly(x, y, a, L, L * 0.34, 5), fill=c + (255,))
    return im


def main():
    cells = [fern(), flowers(), leaf_mass(), scrub()]
    atlas = Image.new("RGBA", (2 * CELL, 2 * CELL), (0, 0, 0, 0))
    for i, c in enumerate(cells):
        c = c.resize((CELL, CELL), Image.LANCZOS)
        a = np.asarray(c).astype(float)
        m = a[..., 3] > 100
        rgb = Image.fromarray(a[..., :3].astype(np.uint8)).filter(ImageFilter.MaxFilter(7))
        a[..., :3] = np.where(m[..., None], a[..., :3], np.asarray(rgb))   # colour bleed under the cut-out for clean mips
        atlas.paste(Image.fromarray(a.astype(np.uint8), "RGBA"), ((i % 2) * CELL, (i // 2) * CELL))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    atlas.save(OUT, optimize=True)
    print("wrote", OUT, OUT.stat().st_size // 1024, "KB")


if __name__ == "__main__":
    main()
