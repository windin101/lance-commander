#!/usr/bin/env python3
"""v3 building trim sheet and decal atlas (LANCE-21), generated, no outside source.

    python3 -I tools/art/v3/bld_trim.py        # writes game/assets/v3/shared/buildings/{trim,decals}_*.png

Trim sheet: 8 bands of 1024 x 128 px; a band is one tile of 4.0 m x 0.5 m (256 px/m) that repeats along and across a
strip. The mesh gives the band in UV2.x and UV in metres; building_v3.gdshader does v = (band + fract(UV.y/0.5)) / 8.
  trim_ar.png  albedo RGB + roughness A          trim_nm.png  normal RG + metalness B + cavity A
Decal atlas 1024 x 1024 (4 x 4 cells of 256): decals_ar.png albedo RGB + coverage A. The cells are listed in CELLS and
mirrored in game/scripts/world/building_v3.gd (DECAL_CELLS). Digits 0-9 sit in the bottom row at 102 px.
"""
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[3]
DST = ROOT / "game/assets/v3/shared/buildings"
FONT = Path.home() / "Code/race-into-space/game/assets/fonts/Oswald-Variable.ttf"
W, BH, NB = 1024, 128, 8
rng = np.random.default_rng(21)
YEL, BLK, STEEL, RED, WHITE, ORANGE = (222, 176, 28), (28, 28, 30), (150, 154, 158), (176, 36, 30), (214, 214, 208), (226, 120, 24)


def noise(h, w, scale, seed):
    r = np.random.default_rng(seed)
    n = r.random((max(2, h // scale), max(2, w // scale)))
    return np.asarray(Image.fromarray((n * 255).astype(np.uint8)).resize((w, h), Image.BICUBIC)) / 255.0


def band_images():
    """(albedo, rough, height, metal) float arrays per band, each 128 x 1024; tileable in both directions."""
    out = []
    yy, xx = np.mgrid[0:BH, 0:W].astype(float)
    for b in range(NB):
        a = np.zeros((BH, W, 3)); rgh = np.full((BH, W), 0.6); hgt = np.zeros((BH, W)); met = np.zeros((BH, W))
        if b == 0:  # hazard chevrons: 1.0 m period along, V shaped
            ph = ((xx % 1024) / 256.0 * 2.0 + np.abs((yy / BH - 0.5)) * 2.0) % 1.0
            m = ph < 0.5
            a[:] = np.where(m[..., None], YEL, BLK); rgh[:] = np.where(m, 0.55, 0.7)
        elif b == 1:  # hazard diagonal
            ph = ((xx / 256.0 + yy / 256.0) * 2.0) % 1.0
            m = ph < 0.5
            a[:] = np.where(m[..., None], YEL, BLK); rgh[:] = np.where(m, 0.55, 0.7)
        elif b == 2:  # bolted lap strip: two bolt rows, 25 cm pitch (64 px), 10 cm heads (25 px)
            a[:] = STEEL; rgh[:] = 0.5; met[:] = 0.7
            hgt[:] = 0.2
            for row in (BH * 0.28, BH * 0.72):
                d = np.hypot(((xx - 32) % 64) - 32, yy - row)
                hgt += np.clip(1 - d / 12.5, 0, 1) ** 0.6
                a[d < 12.5] = (112, 116, 120)
        elif b == 3:  # weld bead across the middle
            a[:] = (170, 172, 170); rgh[:] = 0.6
            d = np.abs(yy - BH / 2 + 3 * np.sin(xx / 17.0) )
            hgt = np.clip(1 - d / 15, 0, 1) ** 0.7 * (0.8 + 0.2 * np.sin(xx / 4.0))
            a[d < 14] = (96, 90, 84); met[d < 14] = 0.6; rgh[d < 14] = 0.55
        elif b == 4:  # painted stiffener flange: flat with a rolled edge
            a[:] = (176, 178, 174); rgh[:] = 0.55
            hgt = np.clip(np.minimum(yy, BH - 1 - yy) / 14, 0, 1)
        elif b == 5:  # red / white hot-work stripe, vertical stripes
            m = (xx // 64) % 2 == 0
            a[:] = np.where(m[..., None], RED, WHITE); rgh[:] = 0.6
        elif b == 6:  # safety yellow with scuffs
            a[:] = YEL; rgh[:] = 0.5
            sc = noise(BH, W, 6, 7)
            a *= (0.8 + 0.2 * sc)[..., None]
        elif b == 7:  # panel: seams every 1 m (256 px) with rivet dots
            a[:] = (182, 184, 180); rgh[:] = 0.6
            seam = np.abs(((xx + 128) % 256) - 128)
            hgt = -np.clip(1 - seam / 3.0, 0, 1)
            a[seam < 2.5] = (70, 72, 74)
            for row in (BH * 0.2, BH * 0.8):
                d = np.hypot((((xx + 128) % 256) - 128).clip(-30, 30) * 0 + ((xx % 32) - 16), yy - row)
                near = seam < 40
                hgt += np.where(near, np.clip(1 - d / 6, 0, 1), 0)
        # grain and dirt for every band
        g = noise(BH, W, 3, 100 + b)
        a *= (0.92 + 0.16 * g)[..., None]
        out.append((a.clip(0, 255), rgh, hgt, met))
    return out


def trim_sheet():
    A = np.zeros((NB * BH, W, 4), np.uint8); N = np.zeros((NB * BH, W, 4), np.uint8)
    for b, (a, rgh, hgt, met) in enumerate(band_images()):
        sl = slice(b * BH, (b + 1) * BH)
        A[sl, :, :3] = a.astype(np.uint8); A[sl, :, 3] = (rgh * 255).astype(np.uint8)
        gx = (np.roll(hgt, -1, 1) - np.roll(hgt, 1, 1)) * 0.5 * 5.0
        gy = (np.roll(hgt, -1, 0) - np.roll(hgt, 1, 0)) * 0.5 * 5.0
        nz = 1.0 / np.sqrt(gx * gx + gy * gy + 1)
        N[sl, :, 0] = ((-gx * nz * 0.5 + 0.5) * 255).astype(np.uint8)
        N[sl, :, 1] = ((gy * nz * 0.5 + 0.5) * 255).astype(np.uint8)  # OpenGL: +Y up in the image = -row
        N[sl, :, 2] = (met * 255).astype(np.uint8)
        N[sl, :, 3] = (np.clip(0.75 + 0.25 * hgt, 0, 1) * 255).astype(np.uint8)
    Image.fromarray(A).save(DST / "trim_ar.png", optimize=True)
    Image.fromarray(N).save(DST / "trim_nm.png", optimize=True)


CELLS = {"panel": 0, "diamond": 1, "id_plate": 2, "hatch": 3, "arrow": 4, "streak_a": 5, "streak_b": 6, "oil": 7,
         "soot": 8, "rust_bleed": 9, "stripe_corner": 10, "valve_tag": 11}


def cell_origin(i):
    return (i % 4) * 256, (i // 4) * 256


def decals():
    im = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
    f = ImageFont.truetype(str(FONT), 70)
    try:
        f.set_variation_by_axes([700])
    except Exception:
        pass
    d = ImageDraw.Draw(im)
    # control panel: dark housing, a green readout, two rows of buttons, a red lever slot
    x, y = cell_origin(CELLS["panel"])
    d.rounded_rectangle((x + 20, y + 14, x + 236, y + 242), 10, fill=(58, 62, 66, 255), outline=(30, 32, 34, 255), width=6)
    d.rectangle((x + 40, y + 36, x + 216, y + 100), fill=(18, 40, 30, 255))
    for k in range(5):
        h = 14 + (k * 23 % 40)
        d.rectangle((x + 52 + k * 32, y + 96 - h, x + 72 + k * 32, y + 96), fill=(70, 200, 110, 255))
    for r in range(2):
        for c in range(4):
            col = [(200, 60, 50, 255), (220, 180, 40, 255), (70, 150, 220, 255), (170, 170, 170, 255)][(r + c) % 4]
            d.ellipse((x + 46 + c * 44, y + 120 + r * 40, x + 74 + c * 44, y + 148 + r * 40), fill=col)
    d.rectangle((x + 40, y + 206, x + 216, y + 226), fill=(26, 26, 28, 255))
    d.rectangle((x + 60, y + 208, x + 110, y + 224), fill=(176, 36, 30, 255))
    # flammable diamond: a rotated square, red field, white flame
    x, y = cell_origin(CELLS["diamond"])
    c = (x + 128, y + 128)
    d.polygon([(c[0], c[1] - 112), (c[0] + 112, c[1]), (c[0], c[1] + 112), (c[0] - 112, c[1])], fill=(190, 36, 30, 255), outline=(240, 240, 235, 255))
    d.polygon([(c[0], c[1] - 108), (c[0] + 108, c[1]), (c[0], c[1] + 108), (c[0] - 108, c[1])], outline=(20, 20, 20, 255), width=6)
    flame = [(c[0] - 4, c[1] - 62), (c[0] + 30, c[1] - 14), (c[0] + 40, c[1] + 24), (c[0] + 20, c[1] + 58), (c[0] - 26, c[1] + 58), (c[0] - 44, c[1] + 18), (c[0] - 26, c[1] - 16), (c[0] - 12, c[1] + 4)]
    d.polygon(flame, fill=(244, 240, 232, 255))
    # id plate: black stencil box (digits are laid by the mesh from the digit row)
    x, y = cell_origin(CELLS["id_plate"])
    d.rounded_rectangle((x + 12, y + 70, x + 244, y + 186), 8, fill=(236, 232, 214, 255), outline=(20, 20, 20, 255), width=8)
    # hatch: rectangle outline with a handle bar
    x, y = cell_origin(CELLS["hatch"])
    d.rectangle((x + 30, y + 14, x + 226, y + 242), fill=(168, 170, 168, 255), outline=(40, 42, 44, 255), width=8)
    d.rectangle((x + 40, y + 24, x + 216, y + 232), outline=(110, 112, 112, 255), width=4)
    d.rounded_rectangle((x + 170, y + 110, x + 206, y + 146), 6, fill=(190, 150, 30, 255), outline=(40, 40, 40, 255), width=3)
    # arrow: flow arrow in black
    x, y = cell_origin(CELLS["arrow"])
    d.polygon([(x + 20, y + 100), (x + 150, y + 100), (x + 150, y + 56), (x + 236, y + 128), (x + 150, y + 200), (x + 150, y + 156), (x + 20, y + 156)], fill=(24, 24, 26, 235))
    # grime streaks: vertical soft dark runs, alpha only
    for nm, seed in (("streak_a", 3), ("streak_b", 4)):
        x, y = cell_origin(CELLS[nm])
        r = np.random.default_rng(seed)
        al = np.zeros((256, 256))
        for _ in range(14):
            cx = r.integers(10, 246); L = r.integers(90, 250); wd = r.uniform(1.5, 6)
            yy, xx = np.mgrid[0:256, 0:256]
            fall = np.clip(1 - yy / L, 0, 1) ** 1.3 * (yy < L)
            al += np.exp(-((xx - cx - 3 * np.sin(yy / 23.0)) ** 2) / (2 * wd * wd)) * fall * r.uniform(0.25, 0.7)
        al = np.clip(al, 0, 1) * np.clip(1 - np.abs(np.arange(256) - 128) / 128 * 0.05, 0, 1)[None, :]
        t = np.zeros((256, 256, 4), np.uint8); t[..., :3] = (34, 28, 22) if nm == "streak_a" else (82, 40, 20)
        t[..., 3] = (al * 200).astype(np.uint8)
        im.paste(Image.fromarray(t), (x, y))
    x, y = cell_origin(CELLS["oil"])
    n = noise(256, 256, 24, 11); yy, xx = np.mgrid[0:256, 0:256]
    al = np.clip(1 - np.hypot(xx - 128, yy - 128) / (96 + 30 * (n - 0.5)), 0, 1) ** 0.8
    t = np.zeros((256, 256, 4), np.uint8); t[..., :3] = (20, 18, 14); t[..., 3] = (al * 210).astype(np.uint8)
    im.paste(Image.fromarray(t), (x, y))
    x, y = cell_origin(CELLS["soot"])
    n = noise(256, 256, 16, 12)
    al = np.clip(1 - np.hypot(xx - 128, (yy - 200) * 0.7) / (190 + 60 * (n - 0.5)), 0, 1) ** 1.2
    t = np.zeros((256, 256, 4), np.uint8); t[..., :3] = (10, 9, 8); t[..., 3] = (al * 235).astype(np.uint8)
    im.paste(Image.fromarray(t), (x, y))
    x, y = cell_origin(CELLS["rust_bleed"])
    n = noise(256, 256, 10, 13)
    al = np.clip((n - 0.45) * 3, 0, 1) * np.clip(1 - yy / 256.0, 0, 1) ** 0.5 * np.clip(1 - np.abs(xx - 128) / 120.0, 0, 1)
    t = np.zeros((256, 256, 4), np.uint8); t[..., :3] = (118, 58, 28); t[..., 3] = (al * 215).astype(np.uint8)
    im.paste(Image.fromarray(t), (x, y))
    x, y = cell_origin(CELLS["stripe_corner"])
    tile = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    td = ImageDraw.Draw(tile)
    for k in range(8):
        td.polygon([(k * 64 - 60, 256), (k * 64 - 28, 256), (k * 64 + 60, 0), (k * 64 + 28, 0)], fill=YEL + (255,) if k % 2 == 0 else BLK + (255,))
    im.paste(tile, (x, y))
    x, y = cell_origin(CELLS["valve_tag"])
    d.ellipse((x + 56, y + 56, x + 200, y + 200), fill=(176, 36, 30, 255), outline=(30, 30, 30, 255), width=6)
    d.ellipse((x + 106, y + 106, x + 150, y + 150), fill=(40, 40, 42, 255))
    for k in range(4):
        a = k * math.pi / 2
        d.line((x + 128, y + 128, x + 128 + 70 * math.cos(a), y + 128 + 70 * math.sin(a)), fill=(40, 40, 42, 255), width=10)
    # digits 0-9 in the bottom row, 102 px cells
    fd = ImageFont.truetype(str(FONT), 96)
    try:
        fd.set_variation_by_axes([700])
    except Exception:
        pass
    for k in range(10):
        d.text((k * 102 + 51, 768 + 128), str(k), font=fd, fill=(24, 24, 26, 255), anchor="mm")
    im.save(DST / "decals_ar.png", optimize=True)


if __name__ == "__main__":
    DST.mkdir(parents=True, exist_ok=True)
    trim_sheet()
    decals()
    print("ok")
