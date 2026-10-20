"""The six-storey city blocks (city6storya/b/c, helper for tools/cad/city6story*_cad.py).

The three originals are one box (x -6.901..10.856, z -10.718..7.039, to 21.33 m, 18 triangles) whose walls are each
two quads: the lower half (0..10.665 m) maps texture rows 317..511, the upper half (10.665..21.33 m) rows 0..181,
both on the left half of the 512 px texture (u 2..257) except the +x wall's lower half, which uses the right half
(u 259..513, the entrance). The roof is the top right quarter. tools/cad/city_facade.py maps one affine per wall, so
this maps each quad on its own. Windows are found as the texture's alpha cut-out panes (every window has some),
clustered into window columns and rows per texture region, and the full column x row grid is used (painted panes
included). Relief beyond city_facade.build_block: pilasters as separate proud bodies, recessed bays, roof plant,
tanks and pipes as true round 20-32 sided prisms.
"""
import math
import sys
from pathlib import Path

import numpy as np
from scipy import ndimage

sys.path.insert(0, str(Path(__file__).resolve().parent))
from city_facade import Original, UP, walls, roof_xz, ngon  # noqa: E402,F401

SEAM = 10.665
REGIONS = {"upper": (2, 0, 257, 181), "lower": (2, 317, 257, 511), "entrance": (259, 317, 513, 511)}


def quad(o, nk, half):
    """(triangle index, affine uv->world) of wall nk's 'upper' or 'lower' quad."""
    for i in walls(o)[tuple(nk)]:
        if (o.tris[i][:, 1].mean() > SEAM) == (half == "upper"):
            return i, np.linalg.solve(np.c_[o.uvs[i], np.ones(3)], o.tris[i]).T
    raise KeyError((nk, half))


def region_of(nk, half):
    if half == "upper":
        return "upper"
    return "entrance" if tuple(nk) == (1, 0, 0) else "lower"


def px_box(o, nk, half, box, res=512):
    """A texture pixel box (x0, y0, x1, y1) on one wall quad -> an opening dict on the wall plane."""
    i, A = quad(o, nk, half)
    n = np.array(nk, float)
    t = np.cross(UP, n)
    x0, y0, x1, y1 = (c / res for c in box)
    corners = np.array([A @ [u, v, 1] for u in (x0, x1) for v in (y0, y1)])
    ctr = corners.mean(0)
    ctr = ctr - n * (np.dot(ctr, n) - np.dot(o.tris[i][0], n))
    return {"center": ctr.tolist(), "normal": n.tolist(), "t": t.tolist(), "b": UP.tolist(),
            "w": float(np.ptp(corners @ t)), "h": float(np.ptp(corners[:, 1]))}


def px_y(o, half, row, res=512):
    """World height of texture row `row` on a quad of the given half."""
    _, A = quad(o, (0, 0, 1), half)
    return float((A @ [0.0, row / res, 1])[1])


def _cluster(spans, gap):
    spans = sorted(spans)
    out = []
    for a, b in spans:
        if out and a - out[-1][1] <= gap:
            out[-1] = (out[-1][0], max(out[-1][1], b))
        else:
            out.append((a, b))
    return out


def window_grid(o, region, vgap=8):
    """Window columns and rows (pixel spans) of one texture region, from its alpha cut-out panes."""
    x0, y0, x1, y1 = REGIONS[region]
    a = o.images[0][..., 3] < 0.5
    lab, _ = ndimage.label(a[y0:y1, x0:x1])
    xs, ys = [], []
    for s in ndimage.find_objects(lab):
        if (s[0].stop - s[0].start) * (s[1].stop - s[1].start) < 12:
            continue
        xs.append((s[1].start + x0, s[1].stop + x0))
        ys.append((s[0].start + y0, s[0].stop + y0))
    return _cluster(xs, 2), _cluster(ys, vgap)


def grid(o):
    """Columns and rows per region. The panes are only partly cut out, so the columns are the upper region's (the
    entrance region's are the same shifted by 256 px) and the lower rows are pooled from both lower regions."""
    cols, up_rows = window_grid(o, "upper")
    low_rows = _cluster(window_grid(o, "lower")[1] + window_grid(o, "entrance")[1], 8)
    return {"upper": (cols, up_rows), "lower": (cols, low_rows),
            "entrance": ([(a + 256, b + 256) for a, b in cols], low_rows)}


def windows(o, grow=2, skip=()):
    """Every window of every wall quad: [(opening, region, (col, row), wall)]; skip: [(region, col, row)]."""
    g = grid(o)
    out = []
    for nk in walls(o):
        for half in ("upper", "lower"):
            reg = region_of(nk, half)
            cols, rows = g[reg]
            for ci, (a, b) in enumerate(cols):
                for ri, (c, d) in enumerate(rows):
                    if (reg, ci, ri) in skip:
                        continue
                    op = px_box(o, nk, half, (a - grow, c - grow, b + grow, d + grow))
                    out.append((op, reg, (ci, ri), nk))
    return out


def pilaster(B, o, name, nk, u0, u1, y0, y1, proud):
    """A flat proud strip on wall nk over texture columns u0..u1 (upper-quad u), from y0 to y1 m."""
    _, A = quad(o, nk, "upper")
    n = np.array(nk, float)
    p0, p1 = A @ [u0 / 512, 0.5, 1], A @ [u1 / 512, 0.5, 1]
    lo = np.minimum(p0, p1)
    hi = np.maximum(p0, p1)
    lo[1], hi[1] = y0, y1
    k = int(np.argmax(np.abs(n)))
    w = lo[k]
    lo[k], hi[k] = (w, w + proud) if n[k] > 0 else (w - proud, w)
    return B.box(name, tuple(lo), tuple(hi))


def roof_pt(o, x, y):
    cx, cz, _, _ = roof_xz(o, (x, y, x, y))
    return cx, cz


def pipe(B, o, name, a, b, r, y):
    """A round 20-sided pipe on the roof between pixel points a and b (axis-aligned), centre height y."""
    (ax, az), (bx, bz) = roof_pt(o, *a), roof_pt(o, *b)
    if abs(ax - bx) > abs(az - bz):
        B.prism_x(name, ngon(r, 20, az, y), min(ax, bx), max(ax, bx))
    else:
        B.prism_z(name, ngon(r, 20, ax, y), min(az, bz), max(az, bz))


def saddles(B, o, name, a, b, r, y, H, n=2):
    (ax, az), (bx, bz) = roof_pt(o, *a), roof_pt(o, *b)
    along_x = abs(ax - bx) > abs(az - bz)
    for j in range(n):
        t = (j + 1) / (n + 1)
        sx, sz = ax + (bx - ax) * t, az + (bz - az) * t
        dx, dz = (0.08, 0.14) if along_x else (0.14, 0.08)
        B.box(f"{name}saddle{j}@8f8b84", (sx - dx, H, sz - dz), (sx + dx, y - r + 0.02, sz + dz))


def drum(B, o, name, c, r_px, y0, y1, sides=32):
    cx, cz = roof_pt(o, *c)
    r = r_px * 17.757 / 254
    return B.prism_y(name, ngon(r, sides, cx, cz), y0, y1)


def roof_box(B, o, name, box, y0, h, inset=0.0, cap=True):
    x0, z0, x1, z1 = roof_xz(o, box)
    B.box(f"{name}@avg", (x0 + inset, y0, z0 + inset), (x1 - inset, y0 + h, z1 - inset))
    if cap:
        B.box(f"{name}cap", (x0 + inset - 0.04, y0 + h, z0 + inset - 0.04), (x1 - inset + 0.04, y0 + h + 0.08, z1 - inset + 0.04))
