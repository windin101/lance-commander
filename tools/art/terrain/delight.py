#!/usr/bin/env python3
"""T1 (LAN-66): remove MC2's burnt-in terrain lighting from a map's colour map.

    python3 -I tools/art/terrain/delight.py mc2_01 [mc2_14 ...] [--out /mnt/nvme1n1p1/mc2-rework/terrain]

MC2's editor burnt the light into the colour map (reference/mc2-source/Source/MCLib/terrtxm2.cpp:389-930,
TerrainColorMap::burnInShadows). This is a numpy re-implementation of that pass, from the map's own 25.6 m height grid
and its mission's light (game/data/missions/<m>.json Cameras):

  height   per colour-map pixel, from the terrain triangles exactly as MapData::terrainElevation samples them
           (alternating diagonals, mapdata.cpp:1584); no hi-res <map>.height.tga ships, so this is the fallback the
           editor used when it had none;
  shadow   a ray march toward the light, one pixel per step, heights x ShadowEnhance 2.0, until the ray is higher
           than the highest point (cast shadow = light factor 0);
  normal   the mean of the 8 triangle normals around the pixel, height differences x ContrastEnhance 1.5;
           light factor = N . L (L = (cos(yaw+45), sin(yaw+45), sin(pitch)), normalised or not: --raw-light);
  smooth   every pixel next to a shadowed one is clamped to <= 0.2;
  apply    colour x (Light * f + Ambient) / 255 per channel (Ambient alone for f <= 0), clamped at 255, truncated.

The de-lit map is burnin / that factor (albedo_macro.png, 8-bit sRGB, plus a 16-bit copy). The gate re-lights it with
the same formula and reports CIE76 delta E against the original, plus the checks the round trip alone can't see:
how much terrain shading is left in the de-lit map (its luminance against the light factor) and how much the division
amplifies JPEG noise in cast shadow.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[3]
CONTRAST, SHADOW_ENH = 1.5, 2.0


def heights(elev, V, wupv, npx):
    """Per-pixel elevation (world units) on the terrain triangles; row 0 = top of the map (+y)."""
    E = np.asarray(elev, float).reshape(V, V)
    w = V * wupv / npx
    p = np.arange(npx) * w
    X, Y = np.meshgrid(p, p)                    # X along columns, Y down the rows (world y decreasing)
    c = np.clip((X // wupv).astype(int), 0, V - 2); r = np.clip((Y // wupv).astype(int), 0, V - 2)
    fx = X / wupv - c; fy = Y / wupv - r          # fy: 0 at the upper row, 1 at the lower
    e1, e2, e3, e4 = E[r, c], E[r, c + 1], E[r + 1, c + 1], E[r + 1, c]   # TL TR BR BL
    br = ((r & 1) ^ (c & 1)) == 0                # BOTTOMRIGHT: diagonal TL-BR, else TR-BL
    top = fx > fy
    h_br = np.where(top, e1 + (e2 - e1) * fx + (e3 - e2) * fy, e1 + (e3 - e4) * fx + (e4 - e1) * fy)
    top2 = (1 - fx) > fy
    # top-left triangle (TL, TR, BL), else bottom-right (TR, BR, BL)
    h_bl = np.where(top2, e1 + (e2 - e1) * fx + (e4 - e1) * fy, e3 + (e4 - e3) * (1 - fx) + (e2 - e3) * (1 - fy))
    return np.where(br, h_br, h_bl), w


def light_factor(H, w, L, march=True):
    n = H.shape[0]
    P = np.pad(H, 1, mode="edge")
    v = {k: P[1 + dy:1 + dy + n, 1 + dx:1 + dx + n] for k, (dx, dy) in
         {0: (0, 0), 1: (-1, -1), 2: (0, -1), 3: (1, -1), 4: (1, 0), 5: (1, 1), 6: (0, 1), 7: (-1, 1), 8: (-1, 0)}.items()}
    # the 8 triangles of terrtxm2.cpp, as (vector a, vector b) in world x, y (y up = row - 1), z = dh * contrast
    off = {1: (-w, w), 2: (0, w), 3: (w, w), 4: (w, 0), 5: (w, -w), 6: (0, -w), 7: (-w, -w), 8: (-w, 0)}
    pairs = [(2, 1), (3, 2), (4, 3), (5, 4), (6, 5), (7, 6), (8, 7), (1, 8)]
    N = np.zeros(H.shape + (3,))
    for a, b in pairs:
        A = np.stack([np.full_like(H, off[a][0]), np.full_like(H, off[a][1]), (v[a] - v[0]) * CONTRAST], -1)
        B = np.stack([np.full_like(H, off[b][0]), np.full_like(H, off[b][1]), (v[b] - v[0]) * CONTRAST], -1)
        c = np.cross(A, B)
        N += c / np.linalg.norm(c, axis=-1, keepdims=True)
    N /= 8.0
    f = N @ L
    shadow = np.zeros(H.shape, bool)
    if march and (L[0] or L[1]):
        Hs = H * SHADOW_ENH
        high = H.max() * SHADOW_ENH             # highPoint = max raw height, then *= ShadowEnhance
        yy, xx = np.mgrid[0:n, 0:n].astype(float)
        z = Hs.copy()
        px, py = xx.copy(), yy.copy()
        alive = np.ones(H.shape, bool)
        for _ in range(4 * n):
            px += L[0]; py -= L[1]; z += L[2] * w   # vertexPos += shadowDir: z rises unenhanced against 2x heights
            ok = alive & (px >= 0) & (py >= 0) & (px <= n - 1) & (py <= n - 1) & (z < high)
            if not ok.any():
                break
            hx = np.clip(np.round(px).astype(int), 0, n - 1); hy = np.clip(np.round(py).astype(int), 0, n - 1)
            hit = ok & (Hs[hy, hx] >= z)
            shadow |= hit
            alive = ok & ~hit
    from scipy.ndimage import binary_dilation
    near = binary_dilation(shadow, np.ones((3, 3), bool)) & ~shadow
    f = np.where(near, np.minimum(f, 0.2), f)
    f[shadow] = 0.0
    return f, shadow


def light_rgb(f, cam):
    Lc = np.array([cam["LightRed"], cam["LightGreen"], cam["LightBlue"]], float)
    Ac = np.array([cam["AmbientRed"], cam["AmbientGreen"], cam["AmbientBlue"]], float)
    out = np.where(f[..., None] > 0, np.minimum(np.round(Lc * f[..., None] + Ac), 255), Ac)
    return out / 255.0


def srgb_to_lab(rgb):
    c = rgb / 255.0
    c = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    M = np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]])
    xyz = c @ M.T / np.array([0.95047, 1.0, 1.08883])
    fx = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    return np.stack([116 * fx[..., 1] - 16, 500 * (fx[..., 0] - fx[..., 1]), 200 * (fx[..., 1] - fx[..., 2])], -1)


def fit_direction(img, H, w):
    """The burn-time light direction from the colour map itself: the (yaw, pitch) whose slope lighting N.L best
    correlates with the map's luminance (no cast shadows in the search; 15 deg yaw, 10 deg pitch steps)."""
    lum = (img @ [0.2126, 0.7152, 0.0722])[::4, ::4]
    Hs = H[::4, ::4]
    best = (-2, 0, 0)
    for yd in range(0, 360, 15):
        for pd in range(20, 80, 10):
            y_, p_ = np.radians(yd), np.radians(pd)
            L = np.array([np.cos(y_), np.sin(y_), np.sin(p_)]); L /= np.linalg.norm(L)
            f, _ = light_factor(Hs, w * 4, L, march=False)
            r = np.corrcoef(lum.ravel(), f.ravel())[0, 1]
            if r > best[0]:
                best = (r, y_, p_)
    print(f"  fitted burn-time light direction: yaw {np.degrees(best[1]) - 45:.0f} pitch {np.degrees(best[2]):.0f} (r {best[0]:.2f})", file=sys.stderr)
    return best[1], best[2]


def run(mech_map, out, raw_light=False, flip=False, fit=False, shared=False):
    t = json.loads((ROOT / f"game/data/maps/{mech_map}/terrain.json").read_text())
    cam = json.loads((ROOT / f"game/data/missions/{mech_map}.json").read_text())["Cameras"]
    fitted = None
    if fit:   # the burn-time light, fitted from the colour map itself (fit_light)
        cam, fitted = fit_light(mech_map, raw_light, shared=shared)
    img = np.asarray(Image.open(ROOT / f"game/assets/maps/{mech_map}/burnin.jpg").convert("RGB")).astype(float)
    n = img.shape[0]
    H, w = heights(t["elevation"], t["vertices_per_side"], t["world_units_per_vertex"], n)
    yaw, pitch = np.radians(cam["LightDirYaw"] + 45.0), np.radians(cam["LightDirPitch"])
    if not (5.0 < float(cam["LightDirPitch"]) < 175.0):   # night maps (pitch 270, 0): the burn-time sun is unknown
        yaw, pitch = fit_direction(img, H, w)
        cam = dict(cam, LightDirYaw=float(np.degrees(yaw)) - 45.0, LightDirPitch=float(np.degrees(pitch)))
    L = np.array([np.cos(yaw), np.sin(yaw), np.sin(pitch)])
    if flip:
        L[1] = -L[1]
    if not raw_light:
        L = L / np.linalg.norm(L)
    f, shadow = light_factor(H, w, L)
    K = light_rgb(f, cam)
    alb = img / np.maximum(K, 1e-3)
    clipped = (alb > 255.5).any(-1)
    alb8 = np.clip(np.round(alb), 0, 255)
    relit = np.floor(alb8 * K)
    de = np.linalg.norm(srgb_to_lab(relit) - srgb_to_lab(img), axis=-1)
    # residual shading: correlation of de-lit luminance with the light factor (0 = none left), lit pixels only
    lum0 = img @ [0.2126, 0.7152, 0.0722]; lum1 = alb8 @ [0.2126, 0.7152, 0.0722]
    lit = ~shadow
    r0 = np.corrcoef(lum0[lit], f[lit])[0, 1]; r1 = np.corrcoef(lum1[lit], f[lit])[0, 1]
    # shadow vs lit contrast across the shadow edge (de-lit should match its sunny neighbours)
    from scipy.ndimage import binary_dilation, uniform_filter
    ring = binary_dilation(shadow, np.ones((9, 9), bool)) & ~binary_dilation(shadow, np.ones((3, 3), bool))
    core = shadow & ~binary_dilation(~shadow, np.ones((5, 5), bool))
    hf = lambda a: np.abs(a - uniform_filter(a, 5))
    stats = {"map": mech_map, "light": L.round(4).tolist(), "raw_light": raw_light, "flip_y": flip, "fitted_light": fitted,
             "light_rgb": [cam["LightRed"], cam["LightGreen"], cam["LightBlue"]],
             "ambient_rgb": [cam["AmbientRed"], cam["AmbientGreen"], cam["AmbientBlue"]],
             "dE_mean": round(float(de.mean()), 3), "dE_p95": round(float(np.percentile(de, 95)), 3),
             "dE_max": round(float(de.max()), 2), "dE_mean_shadow": round(float(de[shadow].mean()), 3) if shadow.any() else None,
             "shadow_px_share": round(float(shadow.mean()), 4), "albedo_clipped_share": round(float(clipped.mean()), 5),
             "corr_lum_vs_light_before": round(float(r0), 3), "corr_lum_vs_light_after": round(float(r1), 3),
             "shadow_core_vs_ring_lum_after": [round(float(lum1[core].mean()), 1) if core.any() else None,
                                               round(float(lum1[ring].mean()), 1) if ring.any() else None],
             "hf_noise_shadow_before_after": [round(float(hf(lum0)[core].mean()), 2) if core.any() else None,
                                              round(float(hf(lum1)[core].mean()), 2) if core.any() else None],
             "hf_noise_lit_before_after": [round(float(hf(lum0)[lit].mean()), 2), round(float(hf(lum1)[lit].mean()), 2)]}
    o = Path(out) / mech_map; o.mkdir(parents=True, exist_ok=True)
    Image.fromarray(alb8.astype(np.uint8)).save(o / "albedo_macro.png")
    np.save(o / "light_factor.npy", f.astype(np.float32))
    Image.fromarray(relit.astype(np.uint8)).save(o / "relit.png")
    dimg = np.clip(de * 255 / 10.0, 0, 255).astype(np.uint8)     # 0..10 dE -> black..white
    Image.fromarray(dimg).save(o / "delta_e.png")
    Image.fromarray((np.clip(K, 0, 1) * 255).astype(np.uint8)).save(o / "light.png")
    (o / "stats.json").write_text(json.dumps(stats, indent=1))
    lowpass(o, alb8, f)
    return stats


def lowpass(o, alb, f, sigma=16.0):
    """The weak map tint (T1, accepted 2026-10-25): the de-lit map low-passed (sigma 16 px ~ 32 m) with cast-shadow
    rims down-weighted, so cast shadows and edge misregistration vanish. albedo_macro_lowfreq.png."""
    from scipy.ndimage import binary_dilation, gaussian_filter
    sh = f == 0
    edge = binary_dilation(sh, np.ones((9, 9), bool)) & (~sh | binary_dilation(~sh, np.ones((9, 9), bool)))
    wgt = np.where(edge, 0.05, 1.0)
    lo = np.stack([gaussian_filter(alb[..., c] * wgt, sigma) / gaussian_filter(wgt, sigma) for c in range(3)], -1)
    Image.fromarray(np.clip(lo, 0, 255).astype(np.uint8)).save(o / "albedo_macro_lowfreq.png")



def fit_light(mech_map, raw_light=False, soft=1.5, shared=False):
    """The editor's light at burn time need not be the mission's. Fit per-channel scales on the mission's Light and
    Ambient colours (and a soft shadow edge) so that the de-lit map has no shading left: across a cast-shadow edge the
    albedo is the same (core/ring match), and lit-pixel luminance is uncorrelated with N.L. Returns the fitted camera."""
    from scipy.ndimage import binary_dilation, gaussian_filter
    t = json.loads((ROOT / f"game/data/maps/{mech_map}/terrain.json").read_text())
    cam = dict(json.loads((ROOT / f"game/data/missions/{mech_map}.json").read_text())["Cameras"])
    img = np.asarray(Image.open(ROOT / f"game/assets/maps/{mech_map}/burnin.jpg").convert("RGB")).astype(float)
    n = img.shape[0]
    H, w = heights(t["elevation"], t["vertices_per_side"], t["world_units_per_vertex"], n)
    yaw, pitch = np.radians(cam["LightDirYaw"] + 45.0), np.radians(cam["LightDirPitch"])
    if not (5.0 < float(cam["LightDirPitch"]) < 175.0):
        yaw, pitch = fit_direction(img, H, w)
    L = np.array([np.cos(yaw), np.sin(yaw), np.sin(pitch)])
    if not raw_light:
        L = L / np.linalg.norm(L)
    f, shadow = light_factor(H, w, L)
    ring = binary_dilation(shadow, np.ones((11, 11), bool)) & ~binary_dilation(shadow, np.ones((5, 5), bool))
    core = shadow & ~binary_dilation(~shadow, np.ones((7, 7), bool))
    lit = ~binary_dilation(shadow, np.ones((5, 5), bool))
    best = None
    # shared: one (ambient, light) scale pair fitted on the channel mean and applied to all three. Independent
    # per-channel fits went magenta on mc2_02 (snow clipped at 255 skews each channel's optimum differently).
    keys = ("Red", "Green", "Blue")
    for ch, key in enumerate(("Grey",) if shared else keys):
        if shared:
            Lc = float(np.mean([cam["Light" + k] for k in keys])); Ac = float(np.mean([cam["Ambient" + k] for k in keys]))
            x = img.mean(-1)
        else:
            Lc, Ac = float(cam["Light" + key]), float(cam["Ambient" + key])
            x = img[..., ch]
        bc = None
        for a in np.linspace(0.6, 3.0, 49):
            for l in np.linspace(0.4, 1.4, 21):
                K = np.where(f > 0, np.minimum(Lc * l * f + Ac * a, 255), Ac * a)
                al = x / K
                cr = abs(al[core].mean() / al[ring].mean() - 1) if core.any() else 0
                cc = abs(np.corrcoef(al[lit][::7], f[lit][::7])[0, 1])
                s = cr + cc
                if bc is None or s < bc[0]:
                    bc = (s, a, l, cr, cc)
        for k in (keys if shared else (key,)):
            cam["Ambient" + k] = round(float(cam["Ambient" + k]) * bc[1], 1); cam["Light" + k] = round(float(cam["Light" + k]) * bc[2], 1)
        best = (best or []) + [dict(channel=key, ambient_scale=round(bc[1], 3), light_scale=round(bc[2], 3),
                                    core_ring_err=round(bc[3], 3), corr=round(bc[4], 3))]
    return cam, best

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("maps", nargs="+")
    ap.add_argument("--out", default="/mnt/nvme1n1p1/mc2-rework/terrain")
    ap.add_argument("--raw-light", action="store_true")
    ap.add_argument("--flip-y", action="store_true")
    ap.add_argument("--fit", action="store_true", help="fit the burn-time light colours from the colour map")
    ap.add_argument("--fit-shared", action="store_true", help="with --fit: one scale pair for all channels (keeps the light's own hue)")
    a = ap.parse_args()
    for m in a.maps:
        print(json.dumps(run(m, a.out, a.raw_light, a.flip_y, a.fit, a.fit_shared), default=float))
