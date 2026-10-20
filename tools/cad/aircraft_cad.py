"""Helpers for CAD rebuilds of the parked aircraft props (privatejet, shilonep): the original's own surfaces,
read from game/assets/objects/<app>.glb (via tools/art/cad_building.Original), turned into SolidCraft solids.

  * hull_loft: a closed component as a loft along game z through cross-sections sampled from the original
    (rays up and down at fixed fractions of each section's width), so the hull keeps its shape and its
    lengthwise creases, but gets smooth, closed volume.
  * pyramid_shell: a closed (or nearly closed) faceted component rebuilt exactly, facet for facet: each original
    triangle is the base of a shallow pyramid whose apex sits inside the solid (a two-section loft to an apex,
    4 planar faces; a loft through many sections is a spline surface and tessellates to ~30k triangles).
    Facets with less than 4 cm of solid behind them (paper-thin fins) become 3 cm slabs instead.
  * sheet_slabs: a zero-thickness sheet (the originals' wings and canards are single faces) as slabs of real
    thickness, one per planar patch, sketched on the patch's own plane and extruded both ways.
"""
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "art"))
from cad_building import Original  # noqa: E402
from building_cad import cad, cad_dir  # noqa: E402


def components(app):
    """[(tris (n,3,3))] per connected component of the original, ordered as connected_components labels them."""
    o = Original(app)
    t = o.tris.round(4)
    v, inv = np.unique(t.reshape(-1, 3), axis=0, return_inverse=True)
    f = inv.reshape(-1, 3)
    r = np.r_[f[:, 0], f[:, 1], f[:, 2]]
    c = np.r_[f[:, 1], f[:, 2], f[:, 0]]
    n, lab = connected_components(coo_matrix((np.ones(len(r)), (r, c)), shape=(len(v),) * 2), directed=False)
    return [o.tris[lab[f[:, 0]] == k] for k in range(n)]


def heights(tris, x, z):
    """Highest and lowest hit of vertical rays at (x, z) (arrays), nan where none."""
    a, b, c = tris[:, 0], tris[:, 1], tris[:, 2]
    P = np.c_[x, z]
    A, Bv, C = a[:, [0, 2]], b[:, [0, 2]], c[:, [0, 2]]
    v0, v1 = Bv - A, C - A
    den = v0[:, 0] * v1[:, 1] - v0[:, 1] * v1[:, 0]
    ok = np.abs(den) > 1e-9
    d = P[:, None, :] - A[None]
    u = (d[..., 0] * v1[None, :, 1] - d[..., 1] * v1[None, :, 0]) / np.where(ok, den, 1)[None]
    w = (v0[None, :, 0] * d[..., 1] - v0[None, :, 1] * d[..., 0]) / np.where(ok, den, 1)[None]
    inside = ok[None] & (u >= -1e-6) & (w >= -1e-6) & (u + w <= 1 + 1e-6)
    y = a[None, :, 1] + u * (b[:, 1] - a[:, 1])[None] + w * (c[:, 1] - a[:, 1])[None]
    top = np.where(inside, y, -np.inf).max(1)
    bot = np.where(inside, y, np.inf).min(1)
    top[~np.isfinite(top)] = np.nan
    bot[~np.isfinite(bot)] = np.nan
    return top, bot


def section(tris, z, ncol=12, min_t=0.04):
    """Cross-section polygon (x, y) at game z: the top from left to right, then the bottom back."""
    xs = np.linspace(tris[..., 0].min() - 0.01, tris[..., 0].max() + 0.01, 1200)
    top, bot = heights(tris, xs, np.full_like(xs, z))
    hit = np.where(~np.isnan(top))[0]
    if len(hit) == 0:
        return None
    xl, xr = xs[hit[0]], xs[hit[-1]]
    s = -np.cos(np.linspace(0, np.pi, ncol))          # denser near the edges
    px = (xl + xr) / 2 + (xr - xl) / 2 * s * 0.999
    t, b = heights(tris, px, np.full_like(px, z))
    t, b = np.nan_to_num(t, nan=np.nanmean(t)), np.nan_to_num(b, nan=np.nanmean(b))
    mid = (t + b) / 2
    t, b = np.maximum(t, mid + min_t / 2), np.minimum(b, mid - min_t / 2)
    upper = list(zip(px, t))
    lower = list(zip(px[::-1], b[::-1]))
    # the two edge columns become one point each
    upper[0] = (px[0], mid[0])
    upper[-1] = (px[-1], mid[-1])
    return upper + lower[1:-1]


def hull_loft(B, name, tris, zs, ncol=12, min_t=0.04):
    """One two-section loft per station gap (ruled, so it tessellates to a few faces a quad; a loft through
    every section is a smooth spline surface and tessellates to ~30k triangles). Bodies <name>_<k>."""
    sks = []
    for z in zs:
        poly = section(tris, z, ncol, min_t)
        sk = B._sketch("XZ", -z * 1000, flip=True)
        B.c("sketch.line", points=[[round(x * 1000, 2), round(y * 1000, 2)] for x, y in poly], closed=True)
        B.c("sketch.finish")
        sks.append(sk)
    out = []
    for k in range(len(sks) - 1):
        B.c("solid.loft", sections=[{"sketch": sks[k]}, {"sketch": sks[k + 1]}], body_name=f"{name}_{k}", operation="new")
        out.append(f"{name}_{k}")
    return out


def patches(tris, tol=0.02):
    """Group a sheet's triangles into planar patches; each patch -> (normal, boundary loop of points)."""
    n = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    n /= np.linalg.norm(n, axis=1)[:, None]
    key = lambda p: tuple(np.round(p, 3))
    left = set(range(len(tris)))
    out = []
    while left:
        i = left.pop()
        grp = [i]
        changed = True
        while changed:
            changed = False
            for j in list(left):
                if abs(n[j] @ n[i]) > 0.995 and abs((tris[j] - tris[i][0]) @ n[i]).max() < tol and \
                        len({key(p) for p in tris[j]} & {key(p) for g in grp for p in tris[g]}) >= 2:
                    grp.append(j)
                    left.discard(j)
                    changed = True
        edges = Counter()
        pts = {}
        for g in grp:
            for a, b in ((0, 1), (1, 2), (2, 0)):
                ka, kb = key(tris[g][a]), key(tris[g][b])
                pts[ka], pts[kb] = tris[g][a], tris[g][b]
                edges[tuple(sorted((ka, kb)))] += 1
        nxt = defaultdict(list)
        for (ka, kb), cnt in edges.items():
            if cnt == 1:
                nxt[ka].append(kb)
                nxt[kb].append(ka)
        start = next(iter(nxt))
        loop, prev, cur = [start], None, start
        while True:
            cand = [q for q in nxt[cur] if q != prev]
            if not cand or cand[0] == start:
                break
            prev, cur = cur, cand[0]
            loop.append(cur)
        out.append((n[i], [pts[k] for k in loop]))
    return out


def slab(B, name, normal, loop, thick):
    """A planar polygon (game metres) extruded `thick` m symmetrically about its plane."""
    loop = [np.asarray(p, float) for p in loop]
    o = loop[0]
    nC = cad_dir(normal)
    xd = cad_dir(loop[1] - loop[0])
    xd -= nC * (xd @ nC)
    xd /= np.linalg.norm(xd)
    yd = np.cross(nC, xd)
    oC = np.array(cad(o))
    pts = [[round(float((np.array(cad(p)) - oC) @ xd), 2), round(float((np.array(cad(p)) - oC) @ yd), 2)] for p in loop]
    B.n_sk += 1
    sk = f"sk{B.n_sk}"
    B.c("sketch.create", plane={"origin": oC.round(2).tolist(), "x_dir": xd.round(6).tolist(), "y_dir": yd.round(6).tolist()},
        name=sk)
    B.c("sketch.line", points=pts, closed=True)
    B.c("sketch.finish")
    B.c("solid.extrude", distance=round(thick * 1000, 2), sketch=sk, direction="symmetric", body_name=name, operation="new")
    return name


def sheet_slabs(B, name, tris, thick):
    return [slab(B, f"{name}{k}", nrm, loop, thick) for k, (nrm, loop) in enumerate(patches(tris)) if len(loop) >= 3]


def ray_depth(tris, k):
    """Distance from triangle k's centroid, along its inward normal, to the next face of the component."""
    a, b, c = tris[k]
    n = np.cross(b - a, c - a)
    n /= np.linalg.norm(n)
    o, d = (a + b + c) / 3, -n
    best = np.inf
    for j, (p0, p1, p2) in enumerate(tris):
        if j == k:
            continue
        e1, e2 = p1 - p0, p2 - p0
        h = np.cross(d, e2)
        det = e1 @ h
        if abs(det) < 1e-9:
            continue
        s = o - p0
        u = (s @ h) / det
        q = np.cross(s, e1)
        v = (d @ q) / det
        t = (e2 @ q) / det
        if u >= -1e-6 and v >= -1e-6 and u + v <= 1 + 1e-6 and t > 1e-4:
            best = min(best, t)
    return best, n


def _plane(B, sk, origin, xd, yd):
    B.c("sketch.create", plane={"origin": np.round(origin, 2).tolist(), "x_dir": np.round(xd, 6).tolist(),
                                "y_dir": np.round(yd, 6).tolist()}, name=sk)


def pyramid_shell(B, name, tris, max_depth=0.35, sheet=0.03):
    out = []
    for k, tri in enumerate(tris):
        depth, n = ray_depth(tris, k)
        nm = f"{name}{k}"
        if depth < 0.04:
            slab(B, nm, n, [tri[0], tri[1], tri[2]], sheet)
            out.append(nm)
            continue
        depth = min(max_depth, 0.45 * depth)
        P = [np.array(cad(p)) for p in tri]
        nC = cad_dir(n)
        xd = P[1] - P[0]
        xd /= np.linalg.norm(xd)
        yd = np.cross(nC, xd)
        B.n_sk += 1
        a = f"sk{B.n_sk}"
        _plane(B, a, P[0], xd, yd)
        B.c("sketch.line", points=[[round(float((p - P[0]) @ xd), 2), round(float((p - P[0]) @ yd), 2)] for p in P], closed=True)
        B.c("sketch.finish")
        B.n_sk += 1
        b = f"sk{B.n_sk}"
        _plane(B, b, P[0] - nC * depth * 1000, xd, yd)
        cen = (P[0] + P[1] + P[2]) / 3 - P[0]
        B.c("sketch.point", point=[round(float(cen @ xd), 2), round(float(cen @ yd), 2)])
        B.c("sketch.finish")
        B.c("solid.loft", sections=[{"sketch": a}, {"sketch": b, "point": "p1"}], body_name=nm, operation="new")
        out.append(nm)
    return out
