#!/usr/bin/env python3
"""T7 (LAN-72): modern paving for the v3 terrain: base aprons (cement terrain types), roads and runways (overlay tiles).

    python3 -I tools/art/terrain/paved_pack.py

The layout stays MC2's: the same overlay tile per terrain quad and the same cement vertices. What changes is how they
are drawn. From the overlay atlas (game/assets/terrain/overlays_hd.webp: the retail 64 px tiles, 40 cm per texel, 4x
upscaled to 256 px = 10 cm per texel) this writes a MASK atlas with the same cell layout:
  R  asphalt coverage (dark, grey, opaque pixels of the tile)
  G  white marking, as a signed distance field (128 = edge, +-16 px over 0..255), so lane dashes, runway numbers and
     thresholds redraw crisp at any distance instead of magnifying the old pixels
  B  yellow marking, the same
  A  dirt/gravel track coverage (the tan, alpha-blended tracks)
and the paving material array game/assets/terrain/v3/paved_ah.webp / paved_nr.webp (Texture2DArray like the palettes):
  0 concrete  1 asphalt  2 gravel track   (ambientCG CC0 1.0; tools/art/terrain/sources.json)
The shader (terrain_v3.gdshader) lays the concrete as ~5.5 m slabs with joints, per-slab value, patch repairs,
cracks, stains and edge grime, and a kerb strip where concrete meets ground.
"""
import io
import json
import urllib.request
import zipfile
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.ndimage import distance_transform_edt, binary_opening, gaussian_filter

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
MAT = Path("/mnt/nvme1n1p1/mc2-rework/terrain/materials")
DST = ROOT / "game/assets/terrain/v3"
LAYERS = [("concrete", "Concrete024", 2.0), ("asphalt", "Asphalt015", 2.5), ("track", "Gravel022", 1.5)]
UA = {"User-Agent": "Mozilla/5.0"}
ARRAY_IMPORT = (HERE / "terrain_pack.py").read_text().split('IMPORT = """')[1].split('"""')[0].replace("slices/vertical=8", "slices/vertical=3")
MASK_IMPORT = """[remap]

importer="texture"
type="CompressedTexture2D"

[params]

compress/mode=0
mipmaps/generate=true
process/fix_alpha_border=false
detect_3d/compress_to=0
"""


def fetch(i):
    d = MAT / "1k" / i
    if not d.is_dir():
        z = urllib.request.urlopen(urllib.request.Request(f"https://ambientcg.com/get?file={i}_1K-JPG.zip", headers=UA), timeout=120).read()
        d.mkdir(parents=True); zipfile.ZipFile(io.BytesIO(z)).extractall(d)
    return d


def find(d, key):
    return next((d / f for f in sorted(p.name for p in d.iterdir()) if key in f), None)


def materials(res=1024):
    ah, nr, info = [], [], []
    for slot, i, tile in LAYERS:
        d = fetch(i)
        col = Image.open(find(d, "_Color")).convert("RGB").resize((res, res), Image.LANCZOS)
        # neutral grey: remove the scan's colour cast (paving must read grey under any v3 light)
        c = np.asarray(col).astype(float); m = c.reshape(-1, 3).mean(0)
        c = c * (m.mean() / m)
        hp, rp, npth = find(d, "_Displacement"), find(d, "_Roughness"), find(d, "_NormalGL")
        h = np.asarray(Image.open(hp).convert("L").resize((res, res))) if hp else np.full((res, res), 128)
        r = np.asarray(Image.open(rp).convert("L").resize((res, res))) if rp else np.full((res, res), 200)
        n = np.asarray(Image.open(npth).convert("RGB").resize((res, res))) if npth else np.full((res, res, 3), (128, 128, 255))
        ah.append(np.dstack([np.clip(c, 0, 255).astype(np.uint8), h.astype(np.uint8)]))
        nr.append(np.dstack([n.astype(np.uint8), r.astype(np.uint8)]))
        info.append({"slot": slot, "id": i, "tile_m": tile, "mean_albedo": np.clip(c, 0, 255).reshape(-1, 3).mean(0).round(1).tolist()})
    from terrain_pack import save_array
    save_array(np.concatenate(ah, 0), DST / "paved_ah.webp")
    save_array(np.concatenate(nr, 0), DST / "paved_nr.webp")
    for k in ("ah", "nr"):
        (DST / f"paved_{k}.webp.import").write_text(ARRAY_IMPORT)
    (DST / "paved.json").write_text(json.dumps({"layers": info}, indent=1))
    src = json.loads((HERE / "sources.json").read_text()) if (HERE / "sources.json").exists() else {}
    for _, i, _t in LAYERS:
        src[i] = {"source": f"{i} by ambientCG.com (CC0 1.0), https://ambientcg.com/view?id={i}"}
    (HERE / "sources.json").write_text(json.dumps(src, indent=1))


def sdf(mask, spread=16.0):
    inside = distance_transform_edt(mask); outside = distance_transform_edt(~mask)
    d = np.where(mask, inside - 0.5, -(outside - 0.5))
    d = gaussian_filter(d, 2.2)   # smooth the stair-stepped edges of the upscaled tiles: straight, crisp lines
    return np.clip(128 + d * (127 / spread), 0, 255).astype(np.uint8)


def masks():
    info = json.loads((ROOT / "game/assets/terrain/overlays_hd.json").read_text())
    a = np.asarray(Image.open(ROOT / "game/assets/terrain/overlays_hd.webp").convert("RGBA")).astype(float)
    t, pad, cols = info["tile"], info["pad"], info["cols"]; cell = t + 2 * pad
    out = np.zeros(a.shape, np.uint8)
    cement = set(info["cement_types"].values())
    for k in range(cols * info["rows"]):
        x0 = (k % cols) * cell; y0 = (k // cols) * cell
        T = a[y0:y0 + cell, x0:x0 + cell]
        if T.shape[0] < cell or T.shape[1] < cell or k in cement:
            continue
        al = T[..., 3] / 255; rgb = T[..., :3]; lum = rgb.mean(-1)
        sat = rgb.max(-1) - rgb.min(-1)
        opaque = al > 0.5
        grey = opaque & (sat < 45)
        from scipy.ndimage import binary_closing, binary_dilation, label
        asphalt = binary_opening(binary_closing(grey, iterations=3), iterations=3) & (al > 0.3)
        lb, nl = label(asphalt)
        if nl:
            sizes = np.bincount(lb.ravel()); keep = sizes >= 0.02 * cell * cell; keep[0] = False
            asphalt = keep[lb]
        base = np.median(lum[asphalt]) if asphalt.any() else 80.0
        near = binary_dilation(asphalt, iterations=3)
        white = near & opaque & (lum > base + 40) & (sat < 60)
        yellow = near & opaque & (rgb[..., 0] > 120) & (rgb[..., 1] > 90) & (rgb[..., 2] < 0.65 * rgb[..., 0])
        white = binary_dilation(binary_opening(white, iterations=1), iterations=1); yellow = binary_dilation(binary_opening(yellow, iterations=1), iterations=1)
        white = binary_closing(white, iterations=2); yellow = binary_closing(yellow, iterations=2)   # rejoin broken edge lines
        thick = binary_dilation(binary_opening(white, iterations=9), iterations=10)   # light shoulders and pads, not paint
        white &= ~thick
        asphalt |= white | yellow
        track = (al > 0.05) & ~binary_dilation(asphalt, iterations=2)
        out[y0:y0 + cell, x0:x0 + cell, 0] = (gaussian_filter(asphalt.astype(float), 0.8) * 255).astype(np.uint8)
        out[y0:y0 + cell, x0:x0 + cell, 1] = sdf(white)
        out[y0:y0 + cell, x0:x0 + cell, 2] = sdf(yellow)
        out[y0:y0 + cell, x0:x0 + cell, 3] = (np.where(track, al, 0) * 255).astype(np.uint8)
    Image.fromarray(out, "RGBA").save(DST / "overlay_mask.png")
    (DST / "overlay_mask.png.import").write_text(MASK_IMPORT)
    print("overlay mask atlas", out.shape)


if __name__ == "__main__":
    DST.mkdir(parents=True, exist_ok=True)
    import sys
    sys.path.insert(0, str(HERE))
    materials()   # (the old overlay_mask atlas, masks(), is superseded by markings.py and no longer written)
