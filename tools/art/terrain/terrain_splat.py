#!/usr/bin/env python3
"""T2 (LAN-67): per-pixel material classes for the v3 terrain, from MC2's own map data.

    python3 -I tools/art/terrain/terrain_splat.py mc2_01 [mc2_14 ...] [--out /mnt/nvme1n1p1/mc2-rework/terrain]

One material class per palette slot (tools/art/terrain/palettes.json lists, per biome, the CC0 layer in each slot):

  0 ground   the map's dominant ground          4 scree    debris at slope feet, gravel aprons, verges
  1 ground2  its second ground (vegetated/dry)  5 dust     bright, dry, flat ground
  2 rock     steep ground                       6 forest   forest floor under the forest cells
  3 cliff    very steep ground                  7 wet      shores, shallows and mud

Each class is scored per colour-map pixel (2 m) from:
  - the T1 low-pass de-lit colour (albedo_macro_lowfreq.png) taken RELATIVE to the map's own mean (Lab
    deviations), so a map's absolute palette never decides a class: greener than the map -> ground2,
    brighter and greyer -> dust, darker -> wet/forest;
  - slope and curvature from the 25.6 m height grid (sampled on its triangles, then smoothed);
  - terrain_type where the map has painted types (TacRGB value relative to the map's mean tac colour);
    cement types (10, 13-20) count as aprons;
  - cells.bin: forest, road, shallow, deep;
  - building footprints (objects.json, class 1 types, extent_radius), as aprons;
  - unit_weather.json snow (adds to dust, which a snow palette fills with snow) and dust.
The two best classes and a blend are packed like Terrain3D's control map into splat.png (R = class, G = second class,
B = blend 0..255 toward the second, A = 255), at the colour map's 2 m resolution; the shader height-blends between
them, so a 1 m version adds nothing. A hand override, overrides/<map>.png (same size, R = class + 1, 0 = keep;
G = blend), wins where it is painted. splat_debug.png colours the classes over a hillshade.
"""
import argparse
import json
import zlib
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter, binary_dilation, zoom

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
import sys
sys.path.insert(0, str(HERE))
import delight as D  # noqa: E402

CLASSES = ["ground", "ground2", "rock", "cliff", "scree", "dust", "forest", "wet"]
DEBUG_RGB = np.array([[170, 150, 90], [90, 150, 60], [140, 130, 120], [90, 85, 80], [200, 170, 120],
                      [235, 215, 160], [40, 90, 40], [60, 90, 140]], float)
CEMENT = {10, 13, 14, 15, 16, 17, 18, 19, 20}


def smooth01(x, a, b):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def tac_colours():
    import re
    s = (ROOT / "reference/mc2-source/Source/Data/Textures/textures.fit").read_text(errors="replace")
    out = {}
    blocks = re.split(r"\[TerrainType(\d+)\]", s)
    for i in range(1, len(blocks), 2):
        m = re.search(r"TerrainTacRGB\s*=\s*(0x[0-9A-Fa-f]+)", blocks[i + 1])
        if m:
            v = int(m.group(1), 16); out[int(blocks[i])] = ((v >> 16) & 255, (v >> 8) & 255, v & 255)
    return out


def run(m, out):
    T = Path(out) / m
    t = json.loads((ROOT / f"game/data/maps/{m}/terrain.json").read_text())
    V, wupv = t["vertices_per_side"], t["world_units_per_vertex"]
    lo = np.asarray(Image.open(T / "albedo_macro_lowfreq.png").convert("RGB")).astype(float)
    n = lo.shape[0]
    S = V * wupv
    H, w = D.heights(t["elevation"], V, wupv, n)
    Hs = gaussian_filter(H, 2.0)
    gy, gx = np.gradient(Hs, w)
    slope = np.degrees(np.arctan(np.hypot(gx, gy)))
    curv = gaussian_filter(Hs, 4.0) - gaussian_filter(Hs, 12.0)       # < 0: concave (slope feet, gullies)
    # relative colour: Lab deviation from the map mean
    lab = D.srgb_to_lab(lo)
    dlab = lab - lab.reshape(-1, 3).mean(0)
    dL, da, db = dlab[..., 0], dlab[..., 1], dlab[..., 2]
    sat = np.hypot(lab[..., 1], lab[..., 2]); dsat = sat - sat.mean()
    # cells (300 or 360 per side) and per-vertex types, to pixels
    cb = t["cell_bits"]
    cells = np.fromfile(ROOT / f"game/data/maps/{m}/cells.bin", dtype="<u4")
    nc = int(round(np.sqrt(cells.size))); cells = cells.reshape(nc, nc)
    bit = lambda k: zoom(((cells >> cb[k][0]) & cb[k][1]).astype(float) > 0, n / nc, order=0)
    forest, road, shallow, deep = bit("forest"), bit("road"), bit("shallow"), bit("deep")
    tt = np.asarray(t["terrain_type"]).reshape(V, V)
    ttp = zoom(tt, n / V, order=0)[:n, :n]
    tac = tac_colours()
    tl = np.array([0.2126, 0.7152, 0.0722])
    tacL = np.vectorize(lambda k: float(np.dot(tac.get(int(k), (128, 128, 128)), tl)))(tt)
    varied = (tt != np.bincount(tt.ravel()).argmax()).mean() > 0.05
    tacLp = zoom(gaussian_filter(tacL - tacL.mean(), 1.0), n / V, order=1)[:n, :n] if varied else np.zeros((n, n))
    # building footprints
    o = json.loads((ROOT / f"game/data/maps/{m}/objects.json").read_text())
    apron = np.zeros((n, n), bool)
    yy, xx = np.mgrid[0:n, 0:n]
    for ob in o["objects"]:
        ty = o["types"].get(str(ob["type"]))
        if not ty or ty.get("class") != 1:
            continue
        px = (ob["x"] + S / 2) / w; py = (S / 2 - ob["y"]) / w   # world units throughout (S, w, objects.json)
        r = max(2.0, ty.get("extent_radius", 30.0) * 1.6 / w)
        x0, x1, y0, y1 = int(max(px - r, 0)), int(min(px + r + 1, n)), int(max(py - r, 0)), int(min(py + r + 1, n))
        if x0 < x1 and y0 < y1:
            apron[y0:y1, x0:x1] |= (xx[y0:y1, x0:x1] - px) ** 2 + (yy[y0:y1, x0:x1] - py) ** 2 <= r * r
    cement = np.isin(ttp, list(CEMENT))
    wx = json.loads((ROOT / "game/data/unit_weather.json").read_text()).get(m, {})
    snow, dust = float(wx.get("snow", 0.0)), float(wx.get("dust", 0.3))
    # scores
    sc = np.zeros((n, n, 8))
    steep = smooth01(slope, 24, 38); vsteep = smooth01(slope, 36, 52)
    sc[..., 0] = 0.55 - 0.02 * np.abs(dL) - 0.3 * steep
    sc[..., 1] = smooth01(-da + dsat * 0.2, 1.0, 6.0) * 0.9 + smooth01(-tacLp, 2, 10) * 0.3 - 0.5 * steep
    sc[..., 2] = steep * (1 - vsteep) * 1.1
    sc[..., 3] = vsteep * 1.3
    near_steep = gaussian_filter(steep, 6.0)
    # aprons and verges: ragged, broken edges (fBm at 4-30 m), not blobs (T3 review 2026-10-25)
    rng = np.random.default_rng(zlib.crc32(m.encode()))  # str hash() is salted per process
    fbm = sum(gaussian_filter(rng.standard_normal((n, n)), s_) * (s_ ** 0.9) for s_ in (2.0, 5.0, 14.0))
    fbm = (fbm - fbm.mean()) / (fbm.std() + 1e-9)
    paved = gaussian_filter((road | cement | apron).astype(float), 3.0)
    sc[..., 4] = (smooth01(-curv, 2, 12) * near_steep * (1 - steep)) * 1.2 + \
        np.clip(paved * 1.6 + 0.45 * fbm - 0.35, 0, 1.2)
    sc[..., 5] = smooth01(dL - 0.6 * np.abs(dsat), 2.0, 9.0) * (1 - steep) * (0.6 + dust) + snow * 0.8 * (1 - vsteep)
    sc[..., 6] = gaussian_filter(binary_dilation(forest, iterations=2).astype(float), 2.0) * (1 - steep) * 1.1
    shore = binary_dilation(deep | shallow, iterations=6) & ~deep
    sc[..., 7] = gaussian_filter((shallow | shore).astype(float), 2.0) * 1.0 + smooth01(-dL, 4, 12) * 0.25 * (1 - steep)
    # curvature from erosion.py (procedural relief), subtle: rock on convex ridges, scree/sediment in gullies
    cp = Path(out) / m / "curvature.npy"
    if cp.exists():
        cv = np.load(cp).astype(float)
        if cv.shape[0] != n:
            cv = zoom(cv, n / cv.shape[0], order=1)[:n, :n]
        cv = gaussian_filter(cv, 1.0)
        ridge = smooth01(cv, 0.25, 0.9) * smooth01(slope, 10, 25); gully = smooth01(-cv, 0.25, 0.9) * smooth01(slope, 6, 20)
        sc[..., 2] += 0.28 * ridge
        sc[..., 4] += 0.25 * gully
    order = np.argsort(-sc, axis=-1)
    c1, c2 = order[..., 0], order[..., 1]
    s1 = np.take_along_axis(sc, c1[..., None], -1)[..., 0]; s2 = np.take_along_axis(sc, c2[..., None], -1)[..., 0]
    blend = np.clip(np.maximum(s2, 0) / np.maximum(s1 + np.maximum(s2, 0), 1e-6), 0, 0.5) * 2   # 1 = even mix
    ov = HERE / "overrides" / f"{m}.png"
    if ov.exists():
        oa = np.asarray(Image.open(ov).convert("RGB"))
        k = oa[..., 0] > 0
        c1[k] = oa[..., 0][k] - 1; blend[k] = oa[..., 1][k] / 255.0
    # A = wear (T3 fix pass): darker compacted ground around roads and bases, worn tracks between nearby buildings,
    # erosion channels in valleys. 0 = none. Off on water, rock and cliff.
    from scipy.ndimage import distance_transform_edt
    hard = road | cement | apron
    dist_hard = distance_transform_edt(~hard) * w * t["meters_per_world_unit"]          # metres
    compact = np.exp(-dist_hard / 28.0) * (~hard)
    centres = []
    for ob in o["objects"]:
        ty = o["types"].get(str(ob["type"]))
        if ty and ty.get("class") == 1:
            centres.append(((ob["x"] + S / 2) / w, (S / 2 - ob["y"]) / w))
    trk = np.zeros((n, n))
    if len(centres) > 1:
        C_ = np.array(centres)
        from scipy.spatial import cKDTree
        tr = cKDTree(C_); maxd = 260.0 / (w * t["meters_per_world_unit"])
        seen = set()
        for i, (x0, y0) in enumerate(C_):
            for j in tr.query(C_[i], k=min(3, len(C_)))[1][1:]:
                a_, b_ = sorted((i, int(j)))
                if (a_, b_) in seen: continue
                seen.add((a_, b_)); x1, y1 = C_[j]
                L_ = np.hypot(x1 - x0, y1 - y0)
                if L_ < 3 or L_ > maxd: continue
                k_ = int(L_ * 2)
                xs = np.clip(np.linspace(x0, x1, k_).astype(int), 0, n - 1); ys = np.clip(np.linspace(y0, y1, k_).astype(int), 0, n - 1)
                trk[ys, xs] = 1.0
        trk = np.clip(gaussian_filter(trk, 1.6) * 6, 0, 1) * np.clip(0.75 + 0.5 * fbm, 0, 1)
    ero = smooth01(-gaussian_filter(curv, 2.0), 1.5, 8.0) * smooth01(slope, 3, 12) * (1 - steep)
    wear = np.clip(compact * 0.75 + trk * 0.85 + ero * 0.55, 0, 1) * (~(deep | shallow)) * (1 - steep)
    wear *= np.clip(0.8 + 0.35 * fbm, 0, 1)
    splat = np.stack([c1, c2, np.round(blend * 255), np.round(wear * 255)], -1).astype(np.uint8)
    Image.fromarray(splat, "RGBA").save(T / "splat.png")
    # debug: class colours over a hillshade
    Lx = np.array([0.5, 0.5, 0.7]); Lx /= np.linalg.norm(Lx)
    N = np.dstack([-gx, gy, np.ones_like(gx) * 1.0]); N /= np.linalg.norm(N, axis=-1, keepdims=True)
    shade = np.clip(N @ Lx, 0.2, 1.0)[..., None]
    col = DEBUG_RGB[c1] * (1 - blend[..., None] * 0.5) + DEBUG_RGB[c2] * blend[..., None] * 0.5
    dbg = np.clip(col * (0.45 + 0.55 * shade), 0, 255).astype(np.uint8)
    Image.fromarray(dbg).save(T / "splat_debug.png")
    share = {CLASSES[i]: round(float((c1 == i).mean()), 4) for i in range(8)}
    stats = {"map": m, "classes_share": share, "terrain_types_varied": bool(varied), "snow": snow, "dust": dust,
             "buildings_px": int(apron.sum()), "forest_px": int(forest.sum()),
             "mean_lowfreq_rgb": lo.reshape(-1, 3).mean(0).round(1).tolist(),
             "mean_lowfreq_lab": lab.reshape(-1, 3).mean(0).round(1).tolist(),
             "slope_pct_over_30deg": round(float((slope > 30).mean()), 4)}
    (T / "splat_stats.json").write_text(json.dumps(stats, indent=1))
    return stats


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("maps", nargs="+")
    ap.add_argument("--out", default="/mnt/nvme1n1p1/mc2-rework/terrain")
    a = ap.parse_args()
    for m in a.maps:
        print(json.dumps(run(m, a.out)))
