#!/usr/bin/env python3
"""T3c (Lee 2026-10-26, option b): crisp procedural relief on top of MC2's 25.6 m height grid, for the v3 terrain.

    python3 -I tools/art/terrain/erosion.py mc2_04 [...] [--droplets 400000]

The coarse heights (sampled on the terrain triangles, 2 m/px) get a fractal seed, then biome-aware shaping:
  default   hydraulic droplet erosion (vectorised: all droplets step together, numpy scatter-adds), so drainage follows
            the real slopes: gully networks, crisp ridges, sediment fans at slope feet, flatter valley floors;
  lunar     multi-scale impact craters (raised rim, bowl, power-law sizes) and a little thermal slumping, no water;
  arid      wind-smoothed forms plus dune ripples on sand/dust classes;
  snow      the eroded field softened (snow cover rounds everything).
Only the DETAIL is kept: the result minus the coarse heights, high-passed at the grid scale (a Gaussian of 25.6 m is
subtracted), so its 25.6 m low-pass is ~0 and the sim's heights, which come from terrain.json and are not touched,
stay exactly what the units walk on. Written to game/assets/terrain/v3/<map>/relief.png:
  R, G  macro normal x, z of the detail (world east, south; 128 = flat)   B  cavity AO (255 = open)
  A     curvature (128 = flat, > ridge, < gully)
and /mnt/nvme1n1p1/mc2-rework/terrain/<map>/detail.npy (metres) + erosion_check.png (hillshade, for review).
"""
import argparse
import json
import sys
import zlib
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter, map_coordinates

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
import delight as D  # noqa: E402
WORK = Path("/mnt/nvme1n1p1/mc2-rework/terrain"); DST = ROOT / "game/assets/terrain/v3"
PX_M = 2.0
IMPORT = (HERE / "relief.py").read_text().split('IMPORT = """')[1].split('"""')[0]


def fbm(rng, n, scales_px, amps):
    out = np.zeros((n, n))
    for s, a in zip(scales_px, amps):
        f = gaussian_filter(rng.standard_normal((n, n)), s)
        out += a * f / (f.std() + 1e-9)
    return out


def bilinear(h, x, y):
    n = h.shape[0]
    x0 = np.clip(np.floor(x).astype(np.int64), 0, n - 2); y0 = np.clip(np.floor(y).astype(np.int64), 0, n - 2)
    fx = np.clip(x - x0, 0, 1); fy = np.clip(y - y0, 0, 1)
    h00 = h[y0, x0]; h10 = h[y0, x0 + 1]; h01 = h[y0 + 1, x0]; h11 = h[y0 + 1, x0 + 1]
    hv = h00 * (1 - fx) * (1 - fy) + h10 * fx * (1 - fy) + h01 * (1 - fx) * fy + h11 * fx * fy
    gx = (h10 - h00) * (1 - fy) + (h11 - h01) * fy
    gy = (h01 - h00) * (1 - fx) + (h11 - h10) * fx
    return hv, gx, gy, x0, y0, fx, fy


def splat(h, x0, y0, fx, fy, amount):
    np.add.at(h, (y0, x0), amount * (1 - fx) * (1 - fy)); np.add.at(h, (y0, x0 + 1), amount * fx * (1 - fy))
    np.add.at(h, (y0 + 1, x0), amount * (1 - fx) * fy); np.add.at(h, (y0 + 1, x0 + 1), amount * fx * fy)


def hydraulic(h, rng, droplets, batch=40000, steps=140, inertia=0.3, cap=4.0, erode=0.25, deposit=0.2, evap=0.012,
              min_slope=0.01, radius_blur=1.6, jitter=0.45):
    """Particle erosion on h (metres, PX_M per px), droplets in batches; erosion is applied to a blurred footprint."""
    n = h.shape[0]
    for b in range(0, droplets, batch):
        m = min(batch, droplets - b)
        x = rng.uniform(1, n - 2, m); y = rng.uniform(1, n - 2, m)
        inertia_b = inertia * rng.uniform(0.5, 1.5)   # per batch
        dx = np.zeros(m); dy = np.zeros(m); vel = np.ones(m); water = np.ones(m); sed = np.zeros(m)
        alive = np.ones(m, bool)
        ero = np.zeros_like(h)
        for _ in range(steps):
            hv, gx, gy, x0, y0, fx, fy = bilinear(h, x, y)
            dx = dx * inertia_b - gx * (1 - inertia_b); dy = dy * inertia_b - gy * (1 - inertia_b)
            L = np.hypot(dx, dy); ok = alive & (L > 1e-9)
            dx = np.where(ok, dx / np.maximum(L, 1e-9), 0); dy = np.where(ok, dy / np.maximum(L, 1e-9), 0)
            # direction jitter and a random step length, so trails on a uniform slope wander instead of running
            # in lock-step parallel lines (the washboard of the first pass)
            ja = rng.normal(0, jitter, m); cj, sj = np.cos(ja), np.sin(ja)
            dx, dy = dx * cj - dy * sj, dx * sj + dy * cj
            stepl = rng.uniform(0.6, 1.4, m)
            nx = x + dx * stepl; ny = y + dy * stepl
            inside = (nx > 1) & (nx < n - 2) & (ny > 1) & (ny < n - 2)
            alive &= ok & inside
            nh = bilinear(h, np.clip(nx, 1, n - 2), np.clip(ny, 1, n - 2))[0]
            dh = nh - hv
            c = np.maximum(-dh, min_slope) * vel * water * cap
            dep = np.where((sed > c) | (dh > 0), np.where(dh > 0, np.minimum(dh, sed), (sed - c) * deposit), 0.0)
            er = np.where((sed <= c) & (dh <= 0), np.minimum((c - sed) * erode, -dh), 0.0)
            amount = np.where(alive, dep - er, 0.0)
            sed = sed - dep + er
            splat(ero, x0, y0, fx, fy, amount)
            vel = np.sqrt(np.maximum(vel * vel - dh * 0.5, 0.01))
            water *= 1 - evap
            died = ~alive & (sed > 0)
            if died.any():   # a droplet that stops leaves its sediment where it is (no pits)
                splat(ero, x0[died], y0[died], fx[died], fy[died], sed[died]); sed[died] = 0
            x, y = np.where(alive, nx, x), np.where(alive, ny, y)
            if not alive.any():
                break
        h += np.clip(gaussian_filter(ero, radius_blur), -0.7, 0.7)
    return h


def thermal(h, iters=20, talus_deg=34.0, k=0.25):
    t = np.tan(np.radians(talus_deg)) * PX_M
    for _ in range(iters):
        for ax, sh in ((0, 1), (0, -1), (1, 1), (1, -1)):
            nb = np.roll(h, sh, axis=ax)
            d = h - nb - t
            mv = np.where(d > 0, d * k * 0.5, 0)
            h -= mv; h += np.roll(mv, -sh, axis=ax)
    return h


def craters(h, rng, n, count_scale=1.0):
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float32)
    det = np.zeros((n, n), np.float32)
    # power-law radii 3..60 m: many small, few large
    for r_m in np.exp(rng.uniform(np.log(2.5), np.log(45), int(1300 * count_scale))) ** 1.0:
        if r_m > 25 and rng.random() > 0.35:
            continue
        r = r_m / PX_M; cx, cy = rng.uniform(0, n, 2); R = int(r * 2.2) + 2
        x0, x1, y0, y1 = int(max(cx - R, 0)), int(min(cx + R, n)), int(max(cy - R, 0)), int(min(cy + R, n))
        if x0 >= x1 or y0 >= y1:
            continue
        d = np.hypot(xx[y0:y1, x0:x1] - cx, yy[y0:y1, x0:x1] - cy) / r
        depth = 0.18 * r_m * rng.uniform(0.6, 1.0)
        bowl = np.where(d < 1, (d * d - 1) * depth, 0)
        rim = np.where(d >= 0.8, 0.16 * r_m * np.exp(-((d - 1.0) / 0.32) ** 2), 0) + np.where(d < 1, 0.16 * r_m * np.exp(-((d - 1.0) / 0.12) ** 2), 0)
        det[y0:y1, x0:x1] += bowl + rim
    return h + det


def washboard(detail):
    """Regular-groove score: in 24 m tiles, the 2-12 m band's dominant-orientation coherence times its energy share
    in that band (structure tensor). High = parallel grooves; natural gullies branch and score low."""
    b = gaussian_filter(detail, 0.8) - gaussian_filter(detail, 4.0)
    gy, gx = np.gradient(b)
    jxx, jyy, jxy = (gaussian_filter(v, 6.0) for v in (gx * gx, gy * gy, gx * gy))
    coh = np.sqrt((jxx - jyy) ** 2 + 4 * jxy ** 2) / (jxx + jyy + 1e-9)
    e = gaussian_filter(b * b, 6.0)
    strong = e > np.percentile(e, 70)
    return float((coh > 0.8)[strong].mean())


def run(m, droplets, biome_override=None):
    t = json.loads((ROOT / f"game/data/maps/{m}/terrain.json").read_text())
    V, wupv, mpu = t["vertices_per_side"], t["world_units_per_vertex"], t["meters_per_world_unit"]
    side = V * wupv * mpu; n = int(round(side / PX_M))
    Hc, _ = D.heights(t["elevation"], V, wupv, n)
    Hc = gaussian_filter(Hc * mpu, 5.0)                      # smooth the 25.6 m triangle facets
    P = json.loads((HERE / "palettes.json").read_text())["maps"].get(m, {})
    pal = P.get("palette", "temperate"); biome = "lunar" if pal == "lunar" else "arid" if pal == "arid" else "snow" if pal == "snow" else "default"
    if biome_override:                                       # a proposal run, before Lee has picked the palette
        biome = biome_override
    rng = np.random.default_rng(zlib.crc32(m.encode()))  # str hash() is salted per process
    slope = np.hypot(*np.gradient(Hc, PX_M))                 # rise per metre
    relief_amp = np.clip(slope * 10.0 + 1.5, 1.5, 6.0)       # rolling ground on flats, more relief on slopes (m)
    seed = fbm(rng, n, (3, 8, 20, 40), (0.06, 0.25, 0.6, 0.8)) * relief_amp
    h = Hc + seed
    if biome == "lunar":
        h = craters(h, rng, n, side / 2560.0)
        h = thermal(h, 10, 36)
    else:
        h = hydraulic(h, rng, int(droplets * 0.6 * (side / 2560.0) ** 2))
        h = hydraulic(h, rng, int(droplets * 0.5 * (side / 2560.0) ** 2), radius_blur=3.0, cap=8.0)   # broader valleys
        h = thermal(h, 12, 38)
        # band shaping against regular combs and trail moire: the fine (2-5 m) band only on slopes and in patches,
        # the mid (5-16 m, the gully spacing) band modulated by broad noise so gullies vary in depth and spacing
        dune = None
        d0 = h - Hc
        fine = d0 - gaussian_filter(d0, 2.5)
        mid = gaussian_filter(d0, 2.5) - gaussian_filter(d0, 8.0)
        sl = np.hypot(*np.gradient(gaussian_filter(Hc, 3.0), PX_M))
        on_slope = np.clip((sl - 0.06) / 0.2, 0, 1)
        pf = np.clip(fbm(rng, n, (40,), (1.0,)) * 0.6 + 0.55, 0.15, 1.0)
        pm = np.clip(fbm(rng, n, (60,), (1.0,)) * 0.5 + 0.7, 0.3, 1.1)
        h = h - fine * (1 - 0.6 * pf * on_slope) - mid * (1 - pm)
        if biome == "arid":
            h = gaussian_filter(h, 1.2)
            sp = np.asarray(Image.open(WORK / m / "splat.png"))[..., 0]
            sand = gaussian_filter(np.isin(sp, [0, 5]).astype(float), 3) * (slope < 0.15)
            yy, xx = np.mgrid[0:n, 0:n] * PX_M
            # dunes with a wandering crest direction and period (low-frequency noise), in patches, never one grid
            ang = 0.65 + 0.6 * fbm(rng, n, (90,), (1.0,))
            per = 9.0 * np.exp(0.35 * fbm(rng, n, (70,), (1.0,)))
            u = xx * np.cos(ang) + yy * np.sin(ang) + fbm(rng, n, (25,), (8.0,))
            phase = 2 * np.pi * u / per
            crest = 0.5 * (np.sin(phase) + 0.35 * np.sin(2 * phase + 1.3))   # asymmetric dunes
            patch = np.clip(fbm(rng, n, (60,), (1.0,)) * 0.9 + 0.2, 0, 1)
            # (no cross ripple: 2.6 m is below the 4 m Nyquist of this 2 m/px field and aliased into moire)
            # the dunes go to their own map (ripple.png) so the shader can fade them out with distance:
            # at 300-612 m their 6-13 m period read as corduroy
            dune = 0.45 * crest * patch * sand
        if biome == "snow":
            h = gaussian_filter(h, 1.8)
    if biome != "arid":
        dune = None
    detail = h - Hc
    for _ in range(3):   # high-pass at the grid scale (its 25.6 m low-pass -> ~0), with a soft limit of +-6 m
        detail = detail - gaussian_filter(detail, 25.6 / PX_M)
        detail = 8.0 * np.tanh(detail / 8.0)
    detail = detail - gaussian_filter(detail, 25.6 / PX_M)
    lp_err = float(np.abs(gaussian_filter(detail, 25.6 / PX_M)).max())
    np.save(WORK / m / "detail.npy", detail.astype(np.float32))
    gz, gx = np.gradient(detail, PX_M)                         # rows = south (+z), cols = east (+x)
    nn = np.dstack([-gx, np.ones_like(detail), -gz]); nn /= np.linalg.norm(nn, axis=-1, keepdims=True)
    full = Hc + detail
    cav = sum(np.clip(gaussian_filter(full, s) - full, 0, None) / (s * PX_M) for s in (2.0, 6.0, 18.0))
    ao = np.clip(1.0 - cav * 1.6, 0.5, 1.0)
    curv = -(gaussian_filter(detail, 1.0) - gaussian_filter(detail, 5.0))   # > 0 ridge, < 0 gully
    curv_enc = np.clip(0.5 + curv * 0.6, 0, 1)
    img = np.dstack([nn[..., 0] * 0.5 + 0.5, nn[..., 2] * 0.5 + 0.5, ao, curv_enc])
    o = DST / m; o.mkdir(parents=True, exist_ok=True)
    Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8), "RGBA").save(o / "relief.png")
    (o / "relief.png.import").write_text(IMPORT)
    np.save(WORK / m / "curvature.npy", curv.astype(np.float32))
    rp = o / "ripple.png"
    if dune is not None:
        dz, dx = np.gradient(dune - gaussian_filter(dune, 25.6 / PX_M), PX_M)
        dn = np.dstack([-dx, np.ones_like(dune), -dz]); dn /= np.linalg.norm(dn, axis=-1, keepdims=True)
        Image.fromarray((np.clip(np.dstack([dn[..., 0] * 0.5 + 0.5, dn[..., 2] * 0.5 + 0.5, np.full_like(dune, 0.5)]), 0, 1) * 255).astype(np.uint8), "RGB").save(rp)
        (o / "ripple.png.import").write_text(IMPORT)
    else:
        for f in (rp, o / "ripple.png.import"):
            f.unlink(missing_ok=True)
    # review hillshade of the full field
    L = np.array([0.5, -0.6, 0.62]); L /= np.linalg.norm(L)
    fz, fx2 = np.gradient(full, PX_M)
    N = np.dstack([-fx2, -fz * -1, np.ones_like(full)]); N /= np.linalg.norm(N, axis=-1, keepdims=True)
    hs = np.clip(N @ L, 0, 1) * ao
    Image.fromarray((hs * 255).astype(np.uint8)).save(WORK / m / "erosion_check.png")
    print(f"{m}: washboard share {washboard(detail):.3f}")
    print(f"{m} ({biome}): detail rms {detail.std():.2f} m, max {np.abs(detail).max():.1f} m, 25.6 m low-pass max {lp_err:.3f} m")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("maps", nargs="+"); ap.add_argument("--droplets", type=int, default=400000)
    ap.add_argument("--biome", choices=["default", "lunar", "arid", "snow"], help="override the biome palettes.json implies")
    a = ap.parse_args()
    for m_ in a.maps:
        run(m_, a.droplets, a.biome)
