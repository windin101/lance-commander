#!/usr/bin/env python3
"""T3b (2026-10-26): recover the mid-scale relief the original colour map carried, as a 2 m macro normal + AO map.

    python3 -I tools/art/terrain/relief.py mc2_04 [...]

Why: the burn-in was shaded from a hi-res height map we don't have. Its 4-40 px band correlates only 0.1-0.5 with
what the 25.6 m mesh predicts (measured), so most ridges, gullies and crater walls exist only in the burn-in's
shading. T1 divided the coarse shading out and the v3 ground is lit by the coarse mesh alone, so that band was lost.

How: the de-lit map's (albedo_macro.png) log-luminance, band-passed (2-64 px), outside cast shadows, is taken as the
residual relative shading r. With small slopes, N.L = Lz - grad(h).Lxy, so grad(h).Lxy = -r Lz. Solved for h in
the Fourier domain with Tikhonov regularisation across the light (Pentland's linear shape-from-shading):
    H = i Lz R (w.L) / ((w.L)^2 + lam |w|^2)
A painted albedo detail is read as relief too; at RTS distance that is what the original showed.
Output game/assets/terrain/v3/<map>/relief.png: R, G = macro normal x, z (world east, south; 128 = flat),
B = cavity AO (crevices and crater floors from the coarse heights plus the recovered detail), 255 = open;
A = the band's own value as a relative multiplier (0.5..1.5, 128 = 1.0).
"""
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter, binary_dilation

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
import delight as D  # noqa: E402
WORK = Path("/mnt/nvme1n1p1/mc2-rework/terrain"); DST = ROOT / "game/assets/terrain/v3"
STRENGTH = 1.0
LAM = 0.08
IMPORT = """[remap]

importer="texture"
type="CompressedTexture2D"

[params]

compress/mode=0
mipmaps/generate=true
process/fix_alpha_border=false
detect_3d/compress_to=0
"""


def run(m, strength=STRENGTH):
    T = WORK / m
    st = json.loads((T / "stats.json").read_text())
    L = np.array(st["light"], float); L /= np.linalg.norm(L)
    # source: the ORIGINAL burn-in's log-luminance, band-passed (its smooth hi-res shading and shadows; the coarse
    # mesh's own shading, only 0.1-0.5 correlated with it, is a minor part of this band). The de-lit map was tried
    # first: the coarse mesh's misregistered cast shadows printed 25.6 m stair-steps into the relief.
    a = np.asarray(Image.open(ROOT / f"game/assets/maps/{m}/burnin.jpg").convert("RGB")).astype(float)
    lum = np.log(a @ [0.2126, 0.7152, 0.0722] + 2.0)
    r = gaussian_filter(lum, 1.0) - gaussian_filter(lum, 32.0)
    r = gaussian_filter(np.clip(r, -0.6, 0.6), 1.2)   # soften JPEG blocks and the integration ladder
    n = r.shape[0]
    # image axes: col = +x (east), row = +y_img (south). Light in world (x east, y north): Ly_img = -Ly
    lx, ly, lz = L[0], -L[1], max(L[2], 0.15)
    wx = np.fft.fftfreq(n) * 2 * np.pi; wy = np.fft.fftfreq(n) * 2 * np.pi
    WX, WY = np.meshgrid(wx, wy)
    wl = WX * lx + WY * ly; w2 = WX ** 2 + WY ** 2
    R = np.fft.fft2(r)
    H = 1j * lz * R * wl / (wl ** 2 + LAM * w2 + 1e-9)
    H[0, 0] = 0
    h = np.real(np.fft.ifft2(H)) * strength          # in px units (slope dimensionless per px)
    hx = np.gradient(h, axis=1); hz = np.gradient(h, axis=0)
    nn = np.dstack([-hx, np.ones_like(h), -hz]); nn /= np.linalg.norm(nn, axis=-1, keepdims=True)
    # cavity AO: coarse heights + recovered detail (metres)
    t = json.loads((ROOT / f"game/data/maps/{m}/terrain.json").read_text())
    Hc, wpx = D.heights(t["elevation"], t["vertices_per_side"], t["world_units_per_vertex"], n)
    Hm = Hc * t["meters_per_world_unit"] + h * wpx * t["meters_per_world_unit"]
    cav = sum(np.clip(gaussian_filter(Hm, s) - Hm, 0, None) / s for s in (3.0, 9.0, 27.0))
    ao = np.clip(1.0 - cav * 0.9, 0.45, 1.0)
    # A: the band's own value (dark gullies, crater shadows, ridge crests as the original painted them), as a
    # relative multiplier exp(r) in 0.5..1.5 (128 = 1.0): the 4-64 m band only, never the 2 m photo itself
    shade = np.clip(np.exp(gaussian_filter(r, 1.5)), 0.5, 1.5)
    img = np.dstack([nn[..., 0] * 0.5 + 0.5, nn[..., 2] * 0.5 + 0.5, ao, shade - 0.5])
    o = DST / m; o.mkdir(parents=True, exist_ok=True)
    Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8)).save(o / "relief.png")
    (o / "relief.png.import").write_text(IMPORT)
    # a check image: the recovered relief relit with the burn light (should resemble the burn-in's shapes)
    relit = np.clip(nn @ np.array([lx, 1.0 * 0 + lz, ly]) if False else (nn[..., 0] * lx + nn[..., 1] * lz + nn[..., 2] * ly), 0, 1) * ao
    Image.fromarray((relit / max(relit.max(), 1e-6) * 255).astype(np.uint8)).save(T / "relief_check.png")
    slope = np.degrees(np.arctan(np.hypot(hx, hz)))
    print(m, "relief: slope p50/p99 %.1f/%.1f deg, AO mean %.2f" % (np.percentile(slope, 50), np.percentile(slope, 99), ao.mean()))


if __name__ == "__main__":
    for m_ in sys.argv[1:]:
        run(m_)
