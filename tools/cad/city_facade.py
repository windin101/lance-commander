"""Painted windows and doors of a city block, found in the original texture (helper for tools/cad/city*_cad.py).

The city blocks are plain boxes whose windows are painted, and only some panes are cut-outs, so
cad_building.py openings misses most of them. This finds each window in the texture as a dark-pane blob
(alpha cut-outs count as dark), merges the panes of one window, and maps its UV box onto the wall through
that face's UV -> position affine. Returns openings in cad_building.py's format (center, normal, t, b, w, h).
"""
import math
import sys
from pathlib import Path

import numpy as np
from scipy import ndimage

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "art"))
from cad_building import Original  # noqa: E402

UP = np.array([0.0, 1.0, 0.0])


def walls(orig):
    """Side walls: (normal, triangles' indices) grouped by axis normal."""
    out = {}
    for i, n in enumerate(orig.normal):
        if abs(n[1]) > 0.5:
            continue
        key = tuple(int(round(x)) for x in n)
        out.setdefault(key, []).append(i)
    return out


def affine(orig, i):
    """uv -> world for triangle i: p = A @ [u, v, 1]."""
    uv = np.c_[orig.uvs[i], np.ones(3)]
    return np.linalg.solve(uv, orig.tris[i]).T  # 3x3


def find(app, dark=0.22, close=2, min_wh=(0.4, 0.3), max_wh=(4.0, 4.5), grow=0.04):
    o = Original(app)
    im = o.images[0]
    H, W = im.shape[:2]
    lum = im[..., :3] @ np.array([0.299, 0.587, 0.114])
    mask = (lum < dark) | (im[..., 3] < 0.5)
    res = []
    for n, idx in walls(o).items():
        n = np.array(n, float)
        t = np.cross(UP, n)
        A = affine(o, idx[0])
        uv = o.uvs[idx].reshape(-1, 2)
        u0, v0 = uv.min(0)
        u1, v1 = uv.max(0)
        c0, c1 = int(np.floor(max(u0, 0) * W)), int(np.ceil(min(u1, 1) * W))
        r0, r1 = int(np.floor(max(v0, 0) * H)), int(np.ceil(min(v1, 1) * H))
        m = mask[r0:r1, c0:c1]
        m = ndimage.binary_closing(m, np.ones((close * 2 + 1, close * 2 + 1)))
        lab, k = ndimage.label(m)
        for sl in ndimage.find_objects(lab):
            ys, xs = sl
            ua, ub = (c0 + xs.start) / W, (c0 + xs.stop) / W
            va, vb = (r0 + ys.start) / H, (r0 + ys.stop) / H
            corners = np.array([A @ [u, v, 1] for u in (ua, ub) for v in (va, vb)])
            ctr = corners.mean(0)
            w = float(np.ptp(corners @ t)) + 2 * grow
            h = float(np.ptp(corners[:, 1])) + 2 * grow
            if not (min_wh[0] <= w <= max_wh[0] and min_wh[1] <= h <= max_wh[1]):
                continue
            ctr = ctr - n * (np.dot(ctr, n) - np.dot(o.tris[idx[0]][0], n))  # onto the wall plane
            res.append({"center": ctr.round(4).tolist(), "normal": n.tolist(), "t": t.tolist(), "b": UP.tolist(),
                        "w": round(w, 3), "h": round(h, 3), "uv": [ua, va, ub, vb]})
    return o, res


def snap_rows(ops, tol=0.25):
    """Give windows of one wall row a common centre height and height (detection jitter)."""
    for key in {tuple(op["normal"]) for op in ops}:
        row = sorted((op for op in ops if tuple(op["normal"]) == key), key=lambda op: op["center"][1])
        groups, cur = [], []
        for op in row:
            if cur and op["center"][1] - cur[-1]["center"][1] > tol:
                groups.append(cur)
                cur = []
            cur.append(op)
        groups.append(cur)
        for g in groups:
            cy = float(np.median([op["center"][1] for op in g]))
            hh = float(np.median([op["h"] for op in g]))
            for op in g:
                if abs(op["h"] - hh) < 0.3:
                    op["center"][1], op["h"] = cy, hh
    return ops


def _runs(p, frac, gap, minlen):
    p = ndimage.uniform_filter1d(p.astype(float), 3)
    lab, _ = ndimage.label(p > frac * p.max())
    runs = [(s.start, s.stop) for s, in ndimage.find_objects(lab)]
    out = []
    for a, b in runs:
        if out and a - out[-1][1] <= gap:
            out[-1] = (out[-1][0], b)
        else:
            out.append((a, b))
    return [r for r in out if r[1] - r[0] >= minlen]


def _typical(runs, lo=0.6, hi=1.6):
    """Keep runs near the median length (a window column or row; drops slivers and wide bands)."""
    if not runs:
        return runs
    med = float(np.median([b - a for a, b in runs]))
    return [r for r in runs if lo * med <= r[1] - r[0] <= hi * med]


def grid(app, dark=0.15, frac=0.3, gap=3, minlen=4, skip=(), extra=(), orig=None, margin=4):
    """Every painted window of each wall as the product of its column runs and row runs (dark-pane profiles of
    the wall's own UV box). skip: (normal, u, v) cells to drop (doors, a garage door), matched by containment;
    extra: (normal, ua, va, ub, vb) UV boxes to add (doors). Returns (orig, openings), uv kept on each."""
    o = orig or Original(app)
    im = o.images[0]
    H, W = im.shape[:2]
    lum = im[..., :3] @ np.array([0.299, 0.587, 0.114])
    mask = (lum < dark) | (im[..., 3] < 0.5)
    res = []
    for nk, idx in walls(o).items():
        n = np.array(nk, float)
        t = np.cross(UP, n)
        A = affine(o, idx[0])
        uv = o.uvs[idx].reshape(-1, 2)
        u0, v0 = np.clip(uv.min(0), 0, 1)
        u1, v1 = np.clip(uv.max(0), 0, 1)
        c0, c1 = int(round(u0 * W)) + margin, int(round(u1 * W)) - margin
        r0, r1 = int(round(v0 * H)) + margin, int(round(v1 * H)) - margin
        m = mask[r0:r1, c0:c1]
        cols = _typical(_runs(m.mean(0), frac, gap, minlen))
        rows = _typical(_runs(m.mean(1), frac, gap, minlen))
        boxes = [((c0 + a) / W, (r0 + c) / H, (c0 + b) / W, (r0 + d) / H) for a, b in cols for c, d in rows]
        boxes = [bx for bx in boxes if not any(tuple(sn) == nk and bx[0] <= su <= bx[2] and bx[1] <= sv <= bx[3]
                                               for sn, su, sv in skip)]
        boxes += [tuple(e[1:]) for e in extra if tuple(e[0]) == nk]
        d0 = np.dot(o.tris[idx[0]][0], n)
        for ua, va, ub, vb in boxes:
            corners = np.array([A @ [u, v, 1] for u in (ua, ub) for v in (va, vb)])
            ctr = corners.mean(0)
            ctr = ctr - n * (np.dot(ctr, n) - d0)
            res.append({"center": ctr.round(4).tolist(), "normal": n.tolist(), "t": t.tolist(), "b": UP.tolist(),
                        "w": round(float(np.ptp(corners @ t)), 3), "h": round(float(np.ptp(corners[:, 1])), 3),
                        "uv": [ua, va, ub, vb]})
    return o, res


# --- the shared city-block build (city2storya, city4story*) --------------------------------------------------

def wall_of(o, nk):
    return walls(o)[tuple(nk)]


def px_box(o, nk, box, res=512):
    """A texture pixel box (x0, y0, x1, y1) on wall nk -> an opening dict on that wall's plane."""
    idx = wall_of(o, nk)
    n = np.array(nk, float)
    t = np.cross(UP, n)
    A = affine(o, idx[0])
    x0, y0, x1, y1 = (c / res for c in box)
    corners = np.array([A @ [u, v, 1] for u in (x0, x1) for v in (y0, y1)])
    ctr = corners.mean(0)
    ctr = ctr - n * (np.dot(ctr, n) - np.dot(o.tris[idx[0]][0], n))
    return {"center": ctr.tolist(), "normal": n.tolist(), "t": t.tolist(), "b": UP.tolist(),
            "w": float(np.ptp(corners @ t)), "h": float(np.ptp(corners[:, 1]))}


def px_height(o, nk, y, res=512):
    """Wall height (m) of texture row y on wall nk."""
    A = affine(o, wall_of(o, nk)[0])
    return float((A @ [0.0, y / res, 1])[1])


def roof_xz(o, box, res=512):
    """A roof texture pixel box -> (x0, z0, x1, z1) world."""
    i = next(i for i, n in enumerate(o.normal) if n[1] > 0.5)
    A = affine(o, i)
    x0, y0, x1, y1 = (c / res for c in box)
    p = np.array([A @ [u, v, 1] for u in (x0, x1) for v in (y0, y1)])
    return p[:, 0].min(), p[:, 2].min(), p[:, 0].max(), p[:, 2].max()


def cells(o, nk, cols, rows, skip=()):
    """Windows on wall nk: every (col, row) pixel box except skip [(ci, ri)]."""
    return [px_box(o, nk, (c[0], r[0], c[1], r[1])) for ci, c in enumerate(cols) for ri, r in enumerate(rows)
            if (ci, ri) not in skip]


def ngon(r, n, cx, cz):
    return [(cx + r * math.cos(2 * math.pi * (j + 0.5) / n), cz + r * math.sin(2 * math.pi * (j + 0.5) / n)) for j in range(n)]


def build_block(B, o, windows, doors=(), garages=(), plinth=0.3, ledges=(), win_depth=0.15, box_edges=None):
    """The block: main box (chamfered corners), recessed windows with sills, recessed doors with a hood and a
    step, a garage door recess with a lintel, a cornice and plinth (one flat colour each), ledges [(y0, y1, proud)]
    as string courses, and a parapet. Returns the roof height H."""
    (X0, Y0, Z0), (X1, H, Z1) = o.lo, o.hi
    main = B.box("main", (X0, 0.0, Z0), (X1, H, Z1), chamfer=0.04,
                 chamfer_edges=box_edges((X0, 0.0, Z0), (X1, H, Z1), "vertical"))
    for k, w in enumerate(windows):
        B.recess(main, w, win_depth)
        B.sill(f"sill{k}", w, proud=0.09, thick=0.07, overhang=0.07)
    for k, d in enumerate(doors):
        B.recess(main, d, 0.2)
        B.sill(f"doorhood{k}", d, proud=0.35, thick=0.1, overhang=0.2, top=True)
        n, t = np.array(d["normal"]), np.array(d["t"])
        c = np.array(d["center"])
        a = c + t * (d["w"] / 2 + 0.25)
        b = c - t * (d["w"] / 2 + 0.25) + n * 0.4
        lo, hi = np.minimum(a, b), np.maximum(a, b)
        B.box(f"doorstep{k}@8f8b84", (lo[0], 0.0, lo[2]), (hi[0], 0.15, hi[2]))
    for k, g in enumerate(garages):
        B.recess(main, g, 0.3)
        B.sill(f"lintel{k}", g, proud=0.2, thick=0.25, overhang=0.15, top=True)
    rings = [("cornice", H - 0.3, H - 0.05, 0.08), ("plinth", 0.0, plinth, 0.04)]
    rings += [(f"ledge{i}", y0, y1, p) for i, (y0, y1, p) in enumerate(ledges)]
    for nm, y0, y1, p in rings:
        B.box(f"{nm}_mz@avg", (X0 - p, y0, Z0 - p), (X1 + p, y1, Z0 + 0.01))
        B.box(f"{nm}_pz@avg", (X0 - p, y0, Z1 - 0.01), (X1 + p, y1, Z1 + p))
        B.box(f"{nm}_px@avg", (X1 - 0.01, y0, Z0 + 0.01), (X1 + p, y1, Z1 - 0.01))
        B.box(f"{nm}_mx@avg", (X0 - p, y0, Z0 + 0.01), (X0 + 0.01, y1, Z1 - 0.01))
    T, PH, E = 0.2, H + 0.35, 0.05
    a0, a1, b0, b1 = X0 + E, X1 - E, Z0 + E, Z1 - E
    for i, (lo, hi) in enumerate((((a0, H, b0), (a1, PH, b0 + T)), ((a0, H, b1 - T), (a1, PH, b1)),
                                  ((a0, H, b0 + T), (a0 + T, PH, b1 - T)), ((a1 - T, H, b0 + T), (a1, PH, b1 - T)))):
        B.box(f"parapet{i}", lo, hi)
    return H


def roof_unit(B, o, name, box, height, inset=0.2, fans=(), fan_r=None, drum=0.15):
    """A painted roof unit raised as a housing (sides one flat colour, a thin painted cap), with round fan
    drums at the given pixel centres (fans: [(x, y, r_px)])."""
    x0, z0, x1, z1 = roof_xz(o, box)
    H = o.hi[1]
    B.box(f"{name}@avg", (x0 + inset, H, z0 + inset), (x1 - inset, H + height, z1 - inset))
    B.box(f"{name}cap", (x0 + inset - 0.03, H + height, z0 + inset - 0.03), (x1 - inset + 0.03, H + height + 0.07, z1 - inset + 0.03))
    for k, (fx, fy, fr) in enumerate(fans):
        cx, cz, _, _ = roof_xz(o, (fx, fy, fx, fy))
        r = fr * 17.92 / 254
        B.prism_y(f"{name}fan{k}", ngon(r, 28, cx, cz), H + height + 0.07, H + height + 0.07 + drum)
