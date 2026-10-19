#!/usr/bin/env python3
"""Environment textures from the Shared Source release that the standard-library converter does not build:

    python3 -I tools/art/env_textures.py [--src reference/mc2-source/Source/Data]

  - game/assets/sky/sky%02d.png: an equirectangular panorama per [TheSky] SkyNumber (1-21). The original drew a
    16-face skybox model textured with Sky%02d_Back_Left.tga and Sky%02d_front_Right.tga (TGL/128, 256 px each,
    genactor.cpp:503-540). Each texture holds two horizon strips over a flat haze colour, so the four strips make
    a 360-degree band: it is laid along the horizon (0 to BAND_DEG elevation), faded into the strips' top colour
    towards the zenith, and the texture's flat haze colour fills below the horizon.
  - game/assets/maps/<mission>/water_detail.png: the 16 frames of <mission>.water0000..0015.tga (64 px, white
    with alpha: the sparkle layer, terrtxm2.cpp:1605-1628) as a 4 x 4 atlas.
  - game/assets/terrain/overlays.png + overlays.json: every road, runway, bridge and junction overlay tile
    (Textures/64Overlays, 64 px RGBA, one per terrain quad) and the cement tiles (Textures/64) in one padded
    atlas. The map stores an overlay as a runtime slot: slots run from OVERLAY_BASE in textures.fit's
    [OverlayTypeN] order, NumOverlays each (TerrTxm.cpp:273-322, 786-815; the rough set 285-292 is not drawn,
    TerrTxm.cpp:1299). overlays.json maps slot -> atlas cell and cement type -> atlas cell.
  - game/assets/maps/<mission>/detail.tga where a mission has none: Defaults/default_detail.tga
    (the original's fallback, terrtxm2.cpp:1564-1583).
The outputs derive from the Shared Source art and stay under its non-commercial terms.
"""
import argparse
import glob
import os
import shutil
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
BAND_DEG = 32.0


def strips(img):
    """The two horizon strips of a sky texture, one in each half (the rows that vary across the width), and the
    flat haze colour below them."""
    a = np.asarray(img.convert("RGB")).astype(float)
    var = a.std(1).mean(1)
    out, flat = [], []
    hh = a.shape[0] // 2
    for lo in (0, hh):
        v = var[lo:lo + hh]
        rows = np.flatnonzero(v > max(1.0, 0.25 * v.max()))
        if len(rows) == 0:
            rows = np.arange(0, hh // 3)
        s0, s1 = lo + rows.min(), lo + rows.max() + 1
        out.append(a[s0:s1])
        flat.append(a[s1 + 4:lo + hh].reshape(-1, 3))
    flat = np.concatenate([f for f in flat if len(f)]) if any(len(f) for f in flat) else a[-1]
    return out, flat.mean(0)


def hblur(row, k):
    """Circular box blur along a row (k px), repeated three times (about Gaussian)."""
    r = row.copy()
    for _ in range(3):
        c = np.concatenate([r[-k:], r, r[:k]])
        cs = np.cumsum(np.vstack([np.zeros((1, 3)), c]), 0)
        r = (cs[2 * k + 1:] - cs[:-2 * k - 1])[: len(row)] / (2 * k + 1)
    return r


def panorama(n, src, w=2048, h=1024):
    tl = Image.open(f"{src}/TGL/128/Sky{n:02d}_Back_Left.tga")
    fr = Image.open(f"{src}/TGL/128/Sky{n:02d}_front_Right.tga")
    s1, haze1 = strips(tl)
    s2, haze2 = strips(fr)
    band = (s2[:2] + s1[:2])  # front, right, back, left
    hb = min(b.shape[0] for b in band)
    band = np.concatenate([np.asarray(Image.fromarray(b.astype(np.uint8)).resize((w // 4, hb), Image.BICUBIC)).astype(float) for b in band], 1)
    haze = (haze1 + haze2) / 2
    top = band[:3].mean((0, 1))
    pano = np.zeros((h, w, 3))
    band_px = int(h / 2 * BAND_DEG / 90.0)
    bandr = np.asarray(Image.fromarray(band.astype(np.uint8)).resize((w, band_px), Image.BICUBIC)).astype(float)
    hz = h // 2
    pano[hz - band_px:hz] = bandr
    soft = hblur(bandr[:4].mean(0), w // 16)  # above the band: its top rows blurred along the horizon, fading to
    for y in range(hz - band_px):            # their average colour at the zenith (no streaks)
        t = (1.0 - y / max(1, hz - band_px))
        t = t * t * (3 - 2 * t)
        mix_ = np.clip((hz - band_px - y) / 6.0, 0, 1)  # a 6 px blend from the band's own top row into the soft one
        pano[y] = (bandr[0] * (1 - mix_) + soft * mix_) * (1 - t) + top * t
    pano[hz:] = haze
    edge = np.linspace(0, 1, 24)[:, None, None]  # soft seam where the band meets the haze
    pano[hz:hz + 24] = bandr[-1] * (1 - edge) + haze * edge
    return Image.fromarray(np.clip(pano, 0, 255).astype(np.uint8))


OVERLAY_BASE = 255
OVERLAY_TYPES = [("dirtroad", 15), ("pavedRoad", 15), ("rough", 8), ("droad2proad", 4), ("droad2proadcross", 2),
                 ("2lanedirt", 15), ("Damagedroad", 15), ("runway", 15), ("X_DIRT_PAVED", 50), ("X_DIRT_2LANEDIRT", 50),
                 ("X_DIRT_DAMAGED", 50), ("X_2LANEDIRT_PAVED", 50), ("X_DAMAGED_PAVED", 50), ("X_2LANEDIRT_DAMAGED", 50),
                 ("Bridge", 15), ("X_PavedRoad_Bridge", 50), ("BridgeDAM", 15)]
CEMENT = {10: "Cement_1", 13: "Cement_1", 18: "Cement_1", 14: "Cement_2", 15: "Cement_2", 19: "Cement_2",
          16: "Cement_3", 17: "Cement_3", 20: "Cement_3"}  # textures.fit [TerrainTypeN] TerrainName
TILE, PAD = 64, 2


def find_ci(folder, name):
    """Case-insensitive file lookup (the release mixes .tga/.TGA and name case)."""
    want = name.lower()
    for f in os.listdir(folder):
        if f.lower() == want:
            return os.path.join(folder, f)
    return None


def overlay_atlas(src, out_dir):
    tex = f"{src}/Textures"
    tiles, slot_cell, cement_cell = [], {}, {}
    slot = OVERLAY_BASE
    for name, n in OVERLAY_TYPES:
        for i in range(n):
            if name != "rough":
                f = find_ci(f"{tex}/64Overlays", f"{name}{i:04d}.tga")
                if f:
                    slot_cell[slot] = len(tiles)
                    tiles.append(Image.open(f).convert("RGBA"))
            slot += 1
    for t, name in CEMENT.items():
        if name not in cement_cell:
            cement_cell[name] = len(tiles)
            tiles.append(Image.open(find_ci(f"{tex}/64", f"{name}.tga")).convert("RGBA"))
    cell = TILE + 2 * PAD
    cols = int(np.ceil(np.sqrt(len(tiles))))
    rows = int(np.ceil(len(tiles) / cols))
    atlas = Image.new("RGBA", (cols * cell, rows * cell), (0, 0, 0, 0))
    for k, im in enumerate(tiles):
        im = im.resize((TILE, TILE))
        padded = Image.fromarray(np.pad(np.asarray(im), ((PAD, PAD), (PAD, PAD), (0, 0)), mode="edge"))
        atlas.paste(padded, ((k % cols) * cell, (k // cols) * cell))
    out_dir.mkdir(parents=True, exist_ok=True)
    atlas.save(out_dir / "overlays.png")
    import json
    (out_dir / "overlays.json").write_text(json.dumps({
        "tile": TILE, "pad": PAD, "cols": cols, "rows": rows, "base": OVERLAY_BASE,
        "slots": {str(k): v for k, v in slot_cell.items()},
        "cement_types": {str(t): cement_cell[nm] for t, nm in CEMENT.items()}}, indent=0))
    print(f"overlay atlas: {len(tiles)} tiles ({len(slot_cell)} overlay, {len(cement_cell)} cement), {cols}x{rows}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=str(ROOT / "reference/mc2-source/Source/Data"))
    a = ap.parse_args()
    sky_dir = ROOT / "game/assets/sky"
    sky_dir.mkdir(parents=True, exist_ok=True)
    for n in range(1, 22):
        if os.path.exists(f"{a.src}/TGL/128/Sky{n:02d}_Back_Left.tga"):
            panorama(n, a.src).save(sky_dir / f"sky{n:02d}.png")
    print("skies:", len(list(sky_dir.glob("sky*.png"))))
    overlay_atlas(a.src, ROOT / "game/assets/terrain")
    tex = f"{a.src}/Textures"
    for mdir in sorted((ROOT / "game/assets/maps").glob("mc2_*")):
        m = mdir.name
        frames = sorted(glob.glob(f"{tex}/{m}.water00[0-9][0-9].tga"))
        if frames:
            atlas = Image.new("RGBA", (256, 256), (255, 255, 255, 0))
            for i, f in enumerate(frames[:16]):
                atlas.paste(Image.open(f).convert("RGBA").resize((64, 64)), ((i % 4) * 64, (i // 4) * 64))
            atlas.save(mdir / "water_detail.png")
        if not (mdir / "detail.tga").exists():
            shutil.copyfile(f"{tex}/Defaults/default_detail.tga", mdir / "detail.tga")
            print(m, "detail: default")
        print(m, "water frames", len(frames))


if __name__ == "__main__":
    main()
