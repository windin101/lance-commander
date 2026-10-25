#!/usr/bin/env python3
"""T3 (LAN-68): pack a map's v3 terrain inputs into game/assets/terrain/v3/ (behind --terrain-v3).

    python3 -I tools/art/terrain/terrain_pack.py mc2_01 [mc2_14 ...] [--res 1024]

Per palette (tools/art/terrain/palettes.json "maps" -> "biomes"):
  palettes/<palette>_ah.webp   8 layers stacked vertically (res x 8 res), RGB albedo + A height   } imported as
  palettes/<palette>_nr.webp   RGB normal (OpenGL, tangent space) + A roughness                  } Texture2DArray, BPTC
  palettes/<palette>.json     per layer: id, tile metres, mean albedo (for the far fallback)
Per map:
  <map>/splat.png   from terrain_splat.py (R class, G second class, B blend)
  <map>/tint.png    the T1 low-pass de-lit colour as RELATIVE variation: colour / map mean, x 0.5, so 128 = no change
                    (it never moves the map's palette, only its local light/dark and hue drift)
"""
import argparse
import json
import sys
import shutil
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
ROOT = HERE.parents[2]
DST = ROOT / "game/assets/terrain/v3"
MAT = Path("/mnt/nvme1n1p1/mc2-rework/terrain/materials")
WORK = Path("/mnt/nvme1n1p1/mc2-rework/terrain")
ASSUME = {"Rock": 300, "Snow": 250, "Ground": 200, "Gravel": 150, "Grass": 140, "Moss": 150, "Concrete": 200}
IMPORT = """[remap]

importer="2d_array_texture"
type="CompressedTexture2DArray"

[params]

compress/mode=2
compress/high_quality=true
compress/lossy_quality=0.7
compress/hdr_compression=1
compress/channel_pack=0
mipmaps/generate=true
mipmaps/limit=-1
slices/horizontal=1
slices/vertical=8
"""
IMPORT_2D = """[remap]

importer="texture"
type="CompressedTexture2D"

[params]

compress/mode={mode}
compress/high_quality=false
compress/lossy_quality=0.9
mipmaps/generate={mip}
roughness/mode=0
process/fix_alpha_border=false
detect_3d/compress_to=0
"""


def save_array(rgba, path):
    """A layer array as WebP: RGB lossy at quality 90, alpha (height or roughness) lossless, for the repo; Godot
    re-compresses it to BC7 on import anyway. Any old PNG of the same array is removed."""
    Image.fromarray(rgba, "RGBA").save(path, "WEBP", quality=90, alpha_quality=100, method=6)
    for old in (path.with_suffix(".png"), Path(str(path.with_suffix(".png")) + ".import")):
        old.unlink(missing_ok=True)


def find(d, key):
    return next((d / f for f in sorted(p.name for p in d.iterdir()) if key in f), None)


def pack_palette(name, slots, order, meta, res):
    ah, nr, info = [], [], []
    for s in order:
        i = slots[s]; d = MAT / "1k" / i
        col = Image.open(find(d, "_Color")).convert("RGB").resize((res, res), Image.LANCZOS)
        hp = find(d, "_Displacement"); rp = find(d, "_Roughness"); npth = find(d, "_NormalGL")
        h = Image.open(hp).convert("L").resize((res, res), Image.LANCZOS) if hp else Image.new("L", (res, res), 128)
        r = Image.open(rp).convert("L").resize((res, res), Image.LANCZOS) if rp else Image.new("L", (res, res), 200)
        n = Image.open(npth).convert("RGB").resize((res, res), Image.LANCZOS) if npth else Image.new("RGB", (res, res), (128, 128, 255))
        # height: stretch to 0..255 so the height blend has range on every layer
        ha = np.asarray(h).astype(float); lo, hi = np.percentile(ha, [1, 99]); ha = np.clip((ha - lo) / max(hi - lo, 1), 0, 1)
        ah.append(np.dstack([np.asarray(col), (ha * 255).astype(np.uint8)]))
        nr.append(np.dstack([np.asarray(n), np.asarray(r)]))
        cm = meta[i]["dim_cm"][0] or next(v for k, v in ASSUME.items() if i.startswith(k))
        info.append({"slot": s, "id": i, "tile_m": cm / 100.0, "mean_albedo": np.asarray(col).reshape(-1, 3).mean(0).round(1).tolist(),
                     "mean_roughness": round(float(np.asarray(r).mean() / 255), 3)})
    o = DST / "palettes"; o.mkdir(parents=True, exist_ok=True)
    save_array(np.concatenate(ah, 0), o / f"{name}_ah.webp")
    save_array(np.concatenate(nr, 0), o / f"{name}_nr.webp")
    for k in ("ah", "nr"):
        (o / f"{name}_{k}.webp.import").write_text(IMPORT)
    (o / f"{name}.json").write_text(json.dumps({"palette": name, "layers": info,
                                                "sources": "ambientCG.com, CC0 1.0 (tools/art/terrain/sources.json)"}, indent=1))


def mask2(m, kind, o):
    """mask2.png (8-bit, 2 m/px like the splat): where a mixed map uses its second palette. "snow": the ORIGINAL
    colour map's snow (blue-white: L* > 42, chroma < 16, b* < 3) as seen in the burn-in, by local coverage over ~12 m,
    so only the painted snowfields turn white."""
    from scipy.ndimage import gaussian_filter, binary_opening
    import delight as D
    img = np.asarray(Image.open(ROOT / f"game/assets/maps/{m}/burnin.jpg").convert("RGB")).astype(float)
    lab = D.srgb_to_lab(gaussian_filter(img, (2, 2, 0)))
    if kind != "snow":
        raise SystemExit(f"mask2 kind {kind} not known")
    # snow reads blue-white against the map's warm ground even in burnt shadow: low or negative b*, low chroma
    sn = (lab[..., 0] > 42) & (np.hypot(lab[..., 1], lab[..., 2]) < 16) & (lab[..., 2] < 3)
    sn = binary_opening(sn, iterations=1)
    n = sn.shape[0]
    cov = gaussian_filter(sn.astype(float), 10.0)       # snowfields are patchy: coverage over ~20 m decides
    # natural shapes: warp the coverage field with low-frequency noise (+-12 px) so the original's per-quad steps
    # don't survive as rectangles, then soften the edge
    rng = np.random.default_rng(abs(hash(m)) % 2**32)
    from scipy.ndimage import map_coordinates
    wx = gaussian_filter(rng.standard_normal((n, n)), 24); wy = gaussian_filter(rng.standard_normal((n, n)), 24)
    wx *= 12 / (wx.std() + 1e-9); wy *= 12 / (wy.std() + 1e-9)
    yy, xx = np.mgrid[0:n, 0:n].astype(float)
    cov = map_coordinates(cov, [yy + wy, xx + wx], order=1, mode="nearest")
    det = gaussian_filter(rng.standard_normal((n, n)), 3) ; det /= det.std() + 1e-9
    w = np.clip((cov + 0.06 * det - 0.22) / 0.25, 0, 1)
    # less on steep ground, none on the paved cement grid (light drifting only)
    t = json.loads((ROOT / f"game/data/maps/{m}/terrain.json").read_text())
    side_m = t["vertices_per_side"] * t["world_units_per_vertex"] * t["meters_per_world_unit"]
    H, wpx = D.heights(t["elevation"], t["vertices_per_side"], t["world_units_per_vertex"], n)
    gy, gx = np.gradient(gaussian_filter(H * t["meters_per_world_unit"], 2.0), wpx * t["meters_per_world_unit"])
    slope = np.degrees(np.arctan(np.hypot(gx, gy)))
    w *= np.clip(1.0 - (slope - 25.0) / 20.0, 0.15, 1.0)
    V = t["vertices_per_side"]
    cem = np.isin(np.asarray(t["terrain_type"]).reshape(V, V), [10, 13, 14, 15, 16, 17, 18, 19, 20]).astype(float)
    from scipy.ndimage import zoom
    # off the paving in irregular drifts: distance from the paved quads, with a noise-warped edge (no rectangles)
    from scipy.ndimage import distance_transform_edt
    pv = zoom(cem, n / V, order=1)[:n, :n] > 0.6
    dist_m = (distance_transform_edt(~pv) - distance_transform_edt(pv)) * (side_m / n)
    edge_noise = gaussian_filter(rng.standard_normal((n, n)), 5); edge_noise *= 5.0 / (edge_noise.std() + 1e-9)
    w_free = w.copy()
    drift = np.clip((dist_m + edge_noise + 1.0) / 4.0, 0.0, 1.0)
    w *= 0.15 + 0.85 * drift
    # G: how much snow lies beside the paving (the snow it would have without the paving, over ~12 m); the shader
    # drifts that much onto the cement edge in irregular tongues (apron_sdf distance + noise), so the stepped quad
    # outline of the paving doesn't read as a rectangle cut out of a snowfield
    g = np.clip(gaussian_filter(w_free * (dist_m > 0), 6.0) / np.maximum(gaussian_filter((dist_m > 0).astype(float), 6.0), 0.05), 0, 1)
    g *= np.clip(1.0 - (-dist_m - 4.0) / 10.0, 0, 1)    # only near the paving edge
    Image.fromarray((np.dstack([w, g, np.zeros_like(w)]) * 255).astype(np.uint8), "RGB").save(o / "mask2.png")
    (o / "mask2.png.import").write_text(IMPORT_2D.format(mode=0, mip="true"))
    print(f"  mask2 ({kind}): {w.mean() * 100:.1f} % of the map")


def albedo_gain(m, pal, P):
    """Keep the map's overall value (2026-10-26: lunar and grass maps came out washed out and pale): the palette's
    expected albedo luminance (layer means weighted by the map's class shares) against the original colour map's mean
    luminance x 1.35 (the burn-in is lit, mean N.L about 0.75), clamped 0.55..1.15. Hue is never touched."""
    lin = lambda c: np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    y = lambda rgb: float(lin(np.asarray(rgb, float) / 255) @ [0.2126, 0.7152, 0.0722])
    sp = json.loads((WORK / m / "splat_stats.json").read_text())["classes_share"]
    layers = {l["slot"]: l for l in json.loads((DST / "palettes" / f"{pal}.json").read_text())["layers"]}
    exp = sum(sp[k] * y(layers[k]["mean_albedo"]) for k in sp)
    img = np.asarray(Image.open(ROOT / f"game/assets/maps/{m}/burnin.jpg").convert("RGB").resize((256, 256))).reshape(-1, 3)
    orig = float(np.mean(lin(img / 255.0) @ [0.2126, 0.7152, 0.0722])) * 1.35
    return round(float(np.clip(orig / max(exp, 1e-4), 0.55, 1.15)), 3)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("maps", nargs="+"); ap.add_argument("--res", type=int, default=1024)
    a = ap.parse_args()
    P = json.loads((HERE / "palettes.json").read_text()); meta = json.loads((MAT / "palette_meta.json").read_text())
    shutil.copy(MAT / "sources.json", HERE / "sources.json")
    done = set()
    for m in a.maps:
        pal = P["maps"][m]["palette"]
        if pal not in done:
            pack_palette(pal, P["biomes"][pal], P["slots"], meta, a.res); done.add(pal)
        o = DST / m; o.mkdir(parents=True, exist_ok=True)
        shutil.copy(WORK / m / "splat.png", o / "splat.png")
        (o / "splat.png.import").write_text(IMPORT_2D.format(mode=0, mip="false"))
        lo = np.asarray(Image.open(WORK / m / "albedo_macro_lowfreq.png").convert("RGB")).astype(float)
        rel = np.clip(lo / lo.reshape(-1, 3).mean(0), 0.6, 1.6)
        Image.fromarray(np.clip(rel * 127.5, 0, 255).astype(np.uint8)).save(o / "tint.png")
        (o / "tint.png.import").write_text(IMPORT_2D.format(mode=0, mip="true"))
        info = {"map": m, "palette": pal, "relief_strength": float(P["maps"][m].get("relief_strength", 1.0 if pal == "lunar" else 2.0)), "approved": P["maps"][m].get("approved"), "albedo_gain": float(P["maps"][m].get("albedo_gain", 1.0)),
                "albedo_gain_suggested": albedo_gain(m, pal, P)}   # a hint only: water and burnt shadow bias it low
        pal2 = P["maps"][m].get("palette2")
        if pal2:   # a mixed map: a second palette where mask2.png says so (same class slots, blended by the mask)
            if pal2 not in done:
                pack_palette(pal2, P["biomes"][pal2], P["slots"], meta, a.res); done.add(pal2)
            mask2(m, P["maps"][m].get("mask2", "snow"), o)
            info["palette2"] = pal2
        (o / "terrain_v3.json").write_text(json.dumps(info, indent=1))
        print(m, pal, "->", o)


if __name__ == "__main__" and not (len(sys.argv) > 1 and sys.argv[1] == "--apron"):
    main()


def apron_sdf(m, px_m=0.5, spread=8.0, slab_m=5.5):
    """Per-map apron (cement) signed distance field for the v3 paving (Lee 2026-10-26, option a): the outline follows the
    cement grid, so it is the union of the 25.6 m terrain quads whose four corner vertices are cement (types 10, 13-20),
    straight along the quad borders, square corners, never past the old full-cement extent. Light chipping only: small
    broken bites along the edge and a few missing slabs (the shader's 5.5 m slab grid) at the edge. Metres to the edge,
    128 = edge, + inside, +-spread m over 0..255."""
    from scipy.ndimage import distance_transform_edt, binary_erosion
    t = json.loads((ROOT / f"game/data/maps/{m}/terrain.json").read_text())
    V = t["vertices_per_side"]; q_m = t["world_units_per_vertex"] * t["meters_per_world_unit"]; side = V * q_m
    cem = np.isin(np.asarray(t["terrain_type"]).reshape(V, V), [10, 13, 14, 15, 16, 17, 18, 19, 20])
    quad = (cem[:-1, :-1].astype(int) + cem[1:, :-1] + cem[:-1, 1:] + cem[1:, 1:]) >= 3   # old cement drew >= 3-corner quads near full
    quad = np.pad(quad, ((0, 1), (0, 1)))
    f = int(round(q_m / px_m)); n = V * f; px_m = side / n
    inside = np.kron(quad, np.ones((f, f), bool))
    rng = np.random.default_rng(abs(hash(m)) % 2**32)
    yy, xx = np.mgrid[0:n, 0:n]
    edge = inside & ~binary_erosion(inside, iterations=1)
    # missing slabs at the edge: slab cells (world x = col * px - side/2, z = row * px - side/2) touching the edge
    sx = np.floor((xx * px_m - side / 2) / slab_m).astype(np.int64); sz = np.floor((yy * px_m - side / 2) / slab_m).astype(np.int64)
    key = sx * 100003 + sz
    ek = np.unique(key[edge])
    gone = ek[rng.random(len(ek)) < 0.05]
    inside &= ~np.isin(key, gone)
    # small bites: a few half-discs (0.4-1.4 m) eaten out of the edge
    er, ec = np.nonzero(inside & ~binary_erosion(inside, iterations=1))
    k = rng.random(len(er)) < 0.012 * px_m
    for r, c in zip(er[k], ec[k]):
        rad = rng.uniform(0.4, 1.4) / px_m; R = int(rad) + 2
        r0, r1, c0, c1 = max(r - R, 0), min(r + R + 1, n), max(c - R, 0), min(c + R + 1, n)
        inside[r0:r1, c0:c1] &= (yy[r0:r1, c0:c1] - r) ** 2 + (xx[r0:r1, c0:c1] - c) ** 2 > rad * rad
    d = (distance_transform_edt(inside) - distance_transform_edt(~inside)) * px_m
    img = np.clip(128 + d / spread * 127, 0, 255).astype(np.uint8)
    o = DST / m; o.mkdir(parents=True, exist_ok=True)
    Image.fromarray(img).save(o / "apron_sdf.png")
    (o / "apron_sdf.png.import").write_text(IMPORT_2D.format(mode=0, mip="true"))
    return n


if __name__ == "__main__" and len(sys.argv) > 1 and sys.argv[1] == "--apron":
    for m_ in sys.argv[2:]:
        print(m_, "apron sdf", apron_sdf(m_))
