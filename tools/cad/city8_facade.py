"""The eight-storey city towers (city8storya/b/c, helper for tools/cad/city8story{b,c}_cad.py).

The three originals are one box (x -7.442..10.315, z -7.536..10.221, to 28.369 m, 18 triangles) whose walls are
each two quads: the upper half (14.18..28.37 m) maps texture square TL (u 0..258, v 0..253), the lower half
(0..14.18 m) square BL (u 0..258, v 253..512), except the +x wall's lower half, which maps BR (u 256..514, the
entrance). The roof is the TR square (u 258..512, v 0..253). b and c share one window grid (the LitWin overlay's):
five columns, four storeys a half; this holds it and maps texture boxes onto the walls quad by quad.
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from city_facade import Original, UP, walls, roof_xz, ngon  # noqa: E402,F401

MID = 14.1845
# window panes (pixel spans) of the shared grid: columns (TL/BL u; BR is +256), rows per half
COLS = [(20, 36), (68, 84), (120, 136), (172, 188), (224, 240)]
ROWS = {"upper": [(20, 44), (84, 108), (144, 168), (208, 232)],
        "lower": [(276, 300), (340, 364), (404, 428), (468, 492)]}


def quad(o, nk, half):
    """(triangle index, affine uv->world) of wall nk's 'upper' or 'lower' quad."""
    for i in walls(o)[tuple(nk)]:
        if (o.tris[i][:, 1].mean() > MID) == (half == "upper"):
            return i, np.linalg.solve(np.c_[o.uvs[i], np.ones(3)], o.tris[i]).T
    raise KeyError((nk, half))


def ushift(nk, half):
    """Texture u offset of a quad against the TL/BL columns (the +x entrance quad is BR, +256)."""
    return 256 if (half == "lower" and tuple(nk) == (1, 0, 0)) else 0


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


def strip(B, o, name, nk, u0, u1, y0, y1, proud):
    """A flat proud plate on wall nk over TL texture columns u0..u1, from y0 to y1 m (world)."""
    _, A = quad(o, nk, "upper")
    n = np.array(nk, float)
    p0, p1 = A @ [u0 / 512, 0.5, 1], A @ [u1 / 512, 0.5, 1]
    lo, hi = np.minimum(p0, p1), np.maximum(p0, p1)
    lo[1], hi[1] = y0, y1
    k = int(np.argmax(np.abs(n)))
    w = lo[k]
    lo[k], hi[k] = (w, w + proud) if n[k] > 0 else (w - proud, w)
    return B.box(name, tuple(lo), tuple(hi))


def windows(o, gx=6, gy=(4, 3), skip=()):
    """Every window of every wall quad, grown to its painted frame: [(opening, half, (col, row), wall)].
    skip: [(wall, half, col, row)] (the entrance)."""
    out = []
    for nk in walls(o):
        for half in ("upper", "lower"):
            s = ushift(nk, half)
            for ci, (a, b) in enumerate(COLS):
                for ri, (c, d) in enumerate(ROWS[half]):
                    if (nk, half, ci, ri) in skip:
                        continue
                    op = px_box(o, nk, half, (a + s - gx, c - gy[0], b + s + gx, d + gy[1]))
                    out.append((op, half, (ci, ri), nk))
    return out


def rings(B, o, specs):
    """Bands around the block: [(name, y0, y1, proud)], one flat colour each."""
    (X0, _, Z0), (X1, _, Z1) = o.lo, o.hi
    for nm, y0, y1, p in specs:
        B.box(f"{nm}_mz@avg", (X0 - p, y0, Z0 - p), (X1 + p, y1, Z0 + 0.01))
        B.box(f"{nm}_pz@avg", (X0 - p, y0, Z1 - 0.01), (X1 + p, y1, Z1 + p))
        B.box(f"{nm}_px@avg", (X1 - 0.01, y0, Z0 + 0.01), (X1 + p, y1, Z1 - 0.01))
        B.box(f"{nm}_mx@avg", (X0 - p, y0, Z0 + 0.01), (X0 + 0.01, y1, Z1 - 0.01))


def parapet(B, o, rim=(262, 8, 502, 242), t=0.28, h=0.6):
    """A parapet on the roof's painted light rim (TR texture box)."""
    H = o.hi[1]
    rx0, rz0, rx1, rz1 = roof_xz(o, rim)
    PH = H + h
    for k, (lo, hi) in enumerate((((rx0, H, rz0), (rx1, PH, rz0 + t)), ((rx0, H, rz1 - t), (rx1, PH, rz1)),
                                  ((rx0, H, rz0 + t), (rx0 + t, PH, rz1 - t)), ((rx1 - t, H, rz0 + t), (rx1, PH, rz1 - t)))):
        B.box(f"parapet{k}", lo, hi)
