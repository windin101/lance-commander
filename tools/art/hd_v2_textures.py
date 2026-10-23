#!/usr/bin/env python3
"""Shared procedural textures for the v2 unit and building shaders (HD rework, 2026-10-23).

    python3 -I tools/art/hd_v2_textures.py      # writes game/assets/v2/shared/*.png

Building sets (<name>_albedo.png RGB + roughness in A, <name>_normal.png; one tile = 2 m): sheet (galvanised
corrugated sheet), panel (painted end-wall boards), concrete, trim (painted steel), door.
grunge.png (512, tiles): R large blotches (paint fade, scorch), G medium mottling, B fine chips (edge wear
breakup), A vertical streaks (rain and oil runs). Band-limited white noise shaped in the Fourier domain, so every
channel tiles exactly. Seeded with crc32 of the file name: a rerun writes the same pixels. New work, project terms.
"""
import zlib
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "game/assets/v2/shared"


def band(rng, n, f0, f1, aniso=(1.0, 1.0)):
    w = rng.standard_normal((n, n))
    fy, fx = np.meshgrid(np.fft.fftfreq(n) * n, np.fft.fftfreq(n) * n, indexing="ij")
    f = np.hypot(fx * aniso[0], fy * aniso[1])
    filt = np.exp(-((np.log(np.maximum(f, 1e-3)) - np.log(np.sqrt(f0 * f1))) ** 2) / (2 * (np.log(f1 / f0) / 2) ** 2))
    x = np.real(np.fft.ifft2(np.fft.fft2(w) * filt))
    x = (x - x.mean()) / (x.std() + 1e-9)
    return np.clip(0.5 + 0.18 * x, 0, 1)


def normal_from_height(h, strength):
    gy, gx = np.gradient(h)
    n = np.dstack([-gx * strength, gy * strength, np.ones_like(h)])
    n /= np.linalg.norm(n, axis=2, keepdims=True)
    return ((n * 0.5 + 0.5) * 255).astype(np.uint8)


def write_set(name, albedo, rough, height, strength):
    """<name>_albedo.png (RGB + roughness in A) and <name>_normal.png, 512 px, one tile = 2 m (building UVs are
    metres / 2)."""
    a = np.dstack([np.clip(albedo, 0, 1), np.clip(rough, 0, 1)])
    Image.fromarray((a * 255).astype(np.uint8), "RGBA").save(OUT / f"{name}_albedo.png", optimize=True)
    Image.fromarray(normal_from_height(height, strength), "RGB").save(OUT / f"{name}_normal.png", optimize=True)
    print(OUT / f"{name}_albedo.png")


def materials():
    """Building surface sets: galvanised sheet, painted panel, concrete, painted steel trim, painted door."""
    n = 512
    for name in ("sheet", "panel", "concrete", "trim", "door"):
        rng = np.random.default_rng(zlib.crc32(name.encode()))
        big, mid, fine = band(rng, n, 2, 6), band(rng, n, 8, 30), band(rng, n, 60, 200)
        streak = band(rng, n, 4, 50, aniso=(5.0, 0.2))
        if name == "sheet":      # zinc: cool grey, spangle, darker run marks, a little rust low down
            base = np.array([0.56, 0.58, 0.6])
            col = base * (0.86 + 0.28 * mid[..., None]) * (0.9 + 0.2 * fine[..., None])
            col = col * (1 - 0.25 * np.clip((streak[..., None] - 0.55) * 4, 0, 1))
            rust = 0.6 * np.clip((big - 0.75) * 6, 0, 1)[..., None]
            col = col * (1 - rust) + np.array([0.42, 0.25, 0.14]) * rust
            rough = 0.42 + 0.25 * mid + 0.2 * rust[..., 0]
            height = fine * 0.3 + mid * 0.2
            st = 3.0
        elif name == "panel":    # painted end-wall boards: off-white grey-green, faint vertical boards
            x = np.arange(n) / n
            boards = (np.abs(((x * 8) % 1.0) - 0.5) > 0.47).astype(float)[None, :].repeat(n, 0)
            base = np.array([0.66, 0.67, 0.6])
            col = base * (0.88 + 0.22 * mid[..., None]) * (1 - 0.35 * boards[..., None])
            col = col * (1 - 0.2 * np.clip((streak[..., None] - 0.55) * 4, 0, 1))
            rough = 0.7 + 0.15 * fine
            height = -boards * 0.6 + fine * 0.15
            st = 4.0
        elif name == "concrete":
            base = np.array([0.55, 0.54, 0.51])
            col = base * (0.8 + 0.3 * big[..., None]) * (0.85 + 0.3 * fine[..., None])
            pores = (fine < 0.25).astype(float)[..., None]
            col = col * (1 - 0.3 * pores)
            rough = 0.85 + 0.1 * fine
            height = fine * 0.5 - pores[..., 0] * 0.4
            st = 4.0
        elif name == "trim":
            base = np.array([0.3, 0.33, 0.3])
            col = base * (0.85 + 0.3 * mid[..., None])
            chip = np.clip((fine - 0.78) * 8, 0, 1)[..., None]
            col = col * (1 - chip) + np.array([0.5, 0.5, 0.5]) * chip
            rough = 0.55 + 0.2 * mid - 0.2 * chip[..., 0]
            height = fine * 0.2
            st = 2.0
        else:                    # door: painted steel, olive drab
            base = np.array([0.33, 0.35, 0.26])
            col = base * (0.85 + 0.3 * mid[..., None]) * (1 - 0.2 * np.clip((streak[..., None] - 0.55) * 4, 0, 1))
            rough = 0.6 + 0.2 * fine
            height = fine * 0.2
            st = 2.0
        write_set(name, col, rough, height, st)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    materials()
    rng = np.random.default_rng(zlib.crc32(b"grunge.png"))
    n = 512
    r = band(rng, n, 2, 6)
    g = band(rng, n, 8, 24)
    b = band(rng, n, 40, 140)
    a = band(rng, n, 6, 60, aniso=(4.0, 0.25))   # stretched along v: vertical runs
    img = (np.stack([r, g, b, a], -1) * 255).astype(np.uint8)
    Image.fromarray(img, "RGBA").save(OUT / "grunge.png", optimize=True)
    print(OUT / "grunge.png")


if __name__ == "__main__":
    main()
