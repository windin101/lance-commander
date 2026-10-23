#!/usr/bin/env python3
"""Weapon and damage effect sprites (I87), drawn procedurally: nothing generated, nothing from the original.

    python3 -I tools/art/fx_textures.py

Writes game/assets/fx/: glow.png (soft round flash), spark.png (a streak, head at the top), smoke.png and
fire.png (4 x 4 sheets of 128 px puffs: smoke is grey, top-lit, with a billowy edge; fire is an intensity map in
R with alpha, coloured by a ramp in fx_sprite.gdshader), ring.png (a shock ring) and noise.png (tileable value
noise for beam shimmer and heat haze). Each sprite's noise is seeded with crc32(name), so a rerun reproduces
the files byte for byte. Used by game/scripts/world/effects_view.gd.
"""
import zlib
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "game/assets/fx"


def rng(name):
    return np.random.default_rng(zlib.crc32(name.encode()))


def fbm(n, r, octaves=5, base=4.0, wrap=True):
    """Fractal value noise in [0, 1], tileable when wrap."""
    acc = np.zeros((n, n))
    amp, tot = 1.0, 0.0
    for o in range(octaves):
        sigma = n / (base * 2 ** o) / 2.5
        layer = ndimage.gaussian_filter(r.random((n, n)), sigma, mode="wrap" if wrap else "reflect")
        layer = (layer - layer.mean()) / (layer.std() + 1e-9)
        acc += amp * layer
        tot += amp
        amp *= 0.55
    acc /= tot
    return np.clip(0.5 + acc * 0.22, 0, 1)


def grid(n):
    y, x = np.mgrid[0:n, 0:n].astype(float)
    return (x + 0.5) / n * 2 - 1, (y + 0.5) / n * 2 - 1


def save(img, name):
    OUT.mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.clip(img * 255 + 0.5, 0, 255).astype(np.uint8), "RGBA").save(OUT / name, optimize=True)
    print("wrote", OUT / name)


def glow(n=128):
    x, y = grid(n)
    r2 = x * x + y * y
    a = np.exp(-r2 * 5.0) * 0.75 + np.exp(-r2 * 28.0) * 0.25
    a *= np.clip((1 - r2) * 4, 0, 1)
    img = np.ones((n, n, 4))
    img[..., 3] = a / a.max()
    return img


def spark(w=32, h=128):
    y, x = np.mgrid[0:h, 0:w].astype(float)
    u = (x + 0.5) / w * 2 - 1
    v = (y + 0.5) / h  # 0 = head (top), 1 = tail
    across = np.exp(-(u * 2.4) ** 2)
    along = np.clip(v * 12, 0, 1) * (1 - v) ** 1.6
    img = np.ones((h, w, 4))
    img[..., 3] = across * along / (across * along).max()
    return img


def puff(n, r, edge=0.55):
    """One billowy cloud cell: (density 0..1, light 0..1)."""
    x, y = grid(n)
    d = np.sqrt(x * x + y * y)
    warp = fbm(n, r, 4, 3.0, wrap=False)
    lumps = fbm(n, r, 5, 2.5, wrap=False)
    rr = d * (0.62 + 0.45 * warp)
    body = np.clip((1.0 - rr) / (1.0 - edge * 0.6), 0, 1)
    dens = np.clip(body * (0.55 + 0.9 * lumps) - 0.15, 0, 1)
    dens = ndimage.gaussian_filter(dens, n / 128)
    dens *= np.clip((0.98 - d) * 6, 0, 1)
    gy, gx = np.gradient(ndimage.gaussian_filter(dens, n / 16))
    light = np.clip(0.6 - (gx + gy) * n * 0.12 + 0.22 * (lumps - 0.5) - 0.18 * y, 0, 1)  # lit from the top left
    return dens / (dens.max() + 1e-9), light


def sheet(name, cell, fn, cells=4):
    r = rng(name)
    out = np.zeros((cell * cells, cell * cells, 4))
    for i in range(cells * cells):
        cy, cx = divmod(i, cells)
        out[cy * cell:(cy + 1) * cell, cx * cell:(cx + 1) * cell] = fn(cell, r, i)
    return out


def smoke_cell(n, r, i):
    dens, light = puff(n, r)
    img = np.zeros((n, n, 4))
    shade = 0.55 + 0.45 * light
    img[..., 0] = img[..., 1] = img[..., 2] = shade
    img[..., 3] = np.clip(dens * 1.15, 0, 1) ** 1.1
    return img


def fire_cell(n, r, i):
    dens, _ = puff(n, r, edge=0.4)
    streaks = fbm(n, r, 4, 6.0, wrap=False)
    x, y = grid(n)
    core = np.exp(-(x * x + y * y) * 2.2)
    inten = np.clip(dens * (0.45 + 0.75 * streaks) * (0.55 + 0.6 * core), 0, 1)
    inten = inten / (inten.max() + 1e-9)
    img = np.zeros((n, n, 4))
    img[..., 0] = inten
    img[..., 1] = inten
    img[..., 2] = inten
    img[..., 3] = np.clip(dens * 1.4, 0, 1)
    return img


def ring(n=256):
    x, y = grid(n)
    d = np.sqrt(x * x + y * y)
    a = np.exp(-((d - 0.82) / 0.07) ** 2) + 0.25 * np.exp(-((d - 0.7) / 0.18) ** 2)
    a *= np.clip((1 - d) * 20, 0, 1)
    img = np.ones((n, n, 4))
    img[..., 3] = a / a.max()
    return img


def noise(n=256):
    r = rng("noise")
    a = fbm(n, r, 5, 4.0)
    b = fbm(n, r, 5, 4.0)
    img = np.ones((n, n, 4))
    img[..., 0] = (a - a.min()) / (a.max() - a.min())
    img[..., 1] = (b - b.min()) / (b.max() - b.min())
    img[..., 2] = 0.5
    return img


def main():
    save(glow(), "glow.png")
    save(spark(), "spark.png")
    save(sheet("smoke", 128, smoke_cell), "smoke.png")
    save(sheet("fire", 128, fire_cell), "fire.png")
    save(ring(), "ring.png")
    save(noise(), "noise.png")


if __name__ == "__main__":
    main()
