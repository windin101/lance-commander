#!/usr/bin/env python3
"""v3 planar buildings, detail pass (LANCE-21): civstoragea/b/c and grainstorage with real cladding, framed openings, roofs with eaves,
gutters, interiors and collapse. Replaces the first-pass shed_*/grain in bld_family.py (which now imports these).

Cladding is geometry at LOD0 (corrugated ribs 0.3 m apart, lap boards 0.2 m, standing-seam roof sheets) and flat panels at LOD1 (the
library normal map carries the ribs). Openings are exact cuts with reveals; a torn opening gets thickness, curled edges, broken boards
and a dark interior with frame members showing through; a roof tear sags. All dimensions come from the Shared Source originals.
"""
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bld_kit import Ctx, uref, axis_angle, TAU  # noqa: E402
from bld_mesh import unit  # noqa: E402

V = np.array


def rect_keep(holes, extra=None):
    """keep(u, v) > 0 outside every rectangle hole (u0, v0, u1, v1) (Chebyshev field, exact straight edges) and where extra > 0."""
    def keep(u, v):
        u = np.asarray(u, float); v = np.asarray(v, float)
        k = np.full(u.shape, 1e3)
        for (u0, v0, u1, v1) in holes:
            k = np.minimum(k, np.maximum(np.maximum(u0 - u, u - u1), np.maximum(v0 - v, v - v1)))
        if extra is not None:
            k = np.minimum(k, extra(u, v))
        return k
    return keep


def grid_axes(L, h, nu, holes=(), v_extra=(), u_extra=(), fine_v=None):
    us = np.unique(np.round(np.r_[np.linspace(0, L, nu + 1), [x for hh in holes for x in (hh[0], hh[2])], list(u_extra)], 5))
    vs = np.r_[np.linspace(0, h, 3 if fine_v is None else max(3, int(h / fine_v) + 1)), [x for hh in holes for x in (hh[1], hh[3])], list(v_extra)]
    vs = np.unique(np.round(np.clip(vs, 0, h), 5))
    return us, vs


def clad(c, mat, p0, dirv, L, up, h, normal, kind="corr", holes=(), extra=None, thick=0.0, edge_mat="rust", tear_disp=None, v_extra=(), fine_v=None, swap=False):
    """A clad panel from p0 along dirv (L) and up (h), facing normal. kind: corr (vertical ribs), lap (horizontal boards), flat."""
    b = c.b
    p0 = V(p0, float); dirv = unit(dirv); up = unit(up); n = unit(normal)
    fine = c.fine
    flip = float(np.dot(np.cross(dirv, up), n)) < 0
    if kind == "corr" and fine and not (extra is not None and L > 8):
        per, amp = 0.30, 0.035
        nu = int(L / (per / 4)) + 1
        base = lambda u, v, k: amp * np.sin(TAU * u / per)
    elif kind == "lap" and fine:
        per, amp = 0.22, 0.03
        nu = max(2, int(L / 0.6))
        base = lambda u, v, k: amp * (((np.asarray(v) / per) % 1.0) ** 1.5)
        fine_v = fine_v or per / 3
    else:
        nu = max(2, int(L / (0.45 if fine else 0.9)))
        base = None
    holes = list(holes)
    if not holes and extra is None and base is None:
        c.b.quad(mat, p0 + dirv * L / 2 + up * h / 2, dirv, up, L, h, (0, h, L, 0), normal=n)
        return
    keep = rect_keep(holes, extra) if (holes or extra is not None) else None
    us, vs = grid_axes(L, h, nu, holes, v_extra, fine_v=fine_v if (kind == "lap" and fine) else (0.5 if (extra is not None) else None))
    pos = lambda u, v: p0 + np.asarray(u)[..., None] * dirv + np.asarray(v)[..., None] * up
    if tear_disp is not None or base is not None:
        disp = (lambda u, v, k: (base(u, v, k) if base else 0.0) + (tear_disp(u, v, k) if tear_disp else 0.0))
    else:
        disp = None
    uv = (lambda u, v: np.stack([v, u], -1)) if swap else (lambda u, v: np.stack([u, v], -1))
    b.cut_param(mat, pos, us, vs, keep, uv=uv, flip=flip, thickness=thick, edge_mat=edge_mat, disp=disp)


def torn(cu, cv, au, bv, ph=0.0):
    """extra keep for a ragged breach centred (cu, cv)."""
    def k(u, v):
        du, dv = (np.asarray(u) - cu), (np.asarray(v) - cv)
        g = np.sqrt((du / au) ** 2 + (dv / bv) ** 2)
        phi = np.arctan2(dv / bv, du / au)
        rho = 1 + 0.17 * np.sin(5 * phi + 1 + ph) + 0.1 * np.sin(9 * phi + 2) + 0.06 * np.sin(17 * phi)
        return (g - rho) * min(au, bv) * 0.9
    return k


def curl(cu, cv, au, bv, amp=0.14):
    """tear_disp: sheet edges bent outward around a breach, with a few wrinkles."""
    def d(u, v, k):
        w = np.clip(1 - np.asarray(k) / 0.35, 0, 1) ** 2
        return w * amp * (0.4 + 0.6 * np.sin(np.asarray(u) * 13 + np.asarray(v) * 7))
    return d


def ridge_keep(L, h, rng, lo=0.15, hi=0.6, teeth=0.06):
    a = rng.random(5) * TAU
    def k(u, v):
        u = np.asarray(u)
        top = h * (0.5 * (lo + hi) + 0.5 * (hi - lo) * (0.55 * np.sin(u / L * 9 + a[0]) + 0.3 * np.sin(u / L * 23 + a[1]) + 0.15 * np.sin(u / L * 47 + a[2])))
        top = top + teeth * h * np.abs(((u * 2.3) % 2.0) - 1.0)
        return top - np.asarray(v)
    return k


def slab_sheet(c, mat, p0, dirv, L, up, h, normal, ribs=True, thick=0.05, extra=None, tear_disp=None, sag=None, per=0.45, amp=0.045, edge_mat="rust"):
    """A roof/loose sheet with standing-rib geometry across dirv; sag(u, v) -> extra offset along the normal (sagging)."""
    b = c.b
    p0 = V(p0, float); dirv = unit(dirv); up = unit(up); n = unit(normal)
    fine = c.fine
    flip = float(np.dot(np.cross(dirv, up), n)) < 0
    nu = int(L / (per / 4)) + 1 if (ribs and fine) else max(2, int(L / 1.2))
    nv = 3 if extra is None and sag is None else max(6, int(h / 0.4))
    us = np.unique(np.round(np.linspace(0, L, nu + 1), 5)); vs = np.unique(np.round(np.linspace(0, h, nv), 5))
    pos = lambda u, v: p0 + np.asarray(u)[..., None] * dirv + np.asarray(v)[..., None] * up
    keep = extra
    def disp(u, v, k):
        d = (amp * np.sin(TAU * np.asarray(u) / per)) if (ribs and fine) else 0.0
        if sag is not None:
            d = d + sag(u, v)
        if tear_disp is not None:
            d = d + tear_disp(u, v, k)
        return d
    # the sheet's underside, so a thin sheet reads from both sides
    b.cut_param(mat, pos, us, vs, keep, uv=lambda u, v: np.stack([u, v], -1), flip=flip, thickness=thick, edge_mat=edge_mat, disp=disp)
    b.cut_param(mat, lambda u, v: pos(u, v) - n * thick, us, vs, keep, uv=lambda u, v: np.stack([u, v], -1), flip=not flip, disp=None if not (sag is not None) else (lambda u, v, k: sag(u, v)))


def interior_shell(c, x0, x1, z0, z1, h, floor=0.1):
    """Dark inward faces of a rectangular building, so a breach shows an interior."""
    b = c.b
    cx, cz = (x0 + x1) / 2, (z0 + z1) / 2
    for (p, d, L, n) in (((x0 + 0.1, 0, z0 + 0.1), (0, 0, 1), z1 - z0 - 0.2, (1, 0, 0)), ((x1 - 0.1, 0, z0 + 0.1), (0, 0, 1), z1 - z0 - 0.2, (-1, 0, 0)),
                         ((x0 + 0.1, 0, z0 + 0.1), (1, 0, 0), x1 - x0 - 0.2, (0, 0, 1)), ((x0 + 0.1, 0, z1 - 0.1), (1, 0, 0), x1 - x0 - 0.2, (0, 0, -1))):
        b.quad("interior", V(p) + unit(d) * L / 2 + V([0, h / 2, 0]), unit(d), V([0, 1.0, 0]), L, h, (0, h, L, 0), normal=n)
    b.quad("interior", V([cx, floor, cz]), V([1.0, 0, 0]), V([0, 0, 1.0]), x1 - x0 - 0.2, z1 - z0 - 0.2, (0, 0, 1, 1), normal=(0, 1, 0))


def timber(c, p0, p1, w=0.14, d=0.14, mat="wood", col=(0, 0, 0)):
    """A square timber between two points."""
    p0, p1 = V(p0, float), V(p1, float)
    ax = unit(p1 - p0)
    ref = V([0, 1.0, 0]) if abs(ax[1]) < 0.9 else V([1.0, 0, 0])
    s = unit(np.cross(ax, ref)); t = np.cross(ax, s)
    c.b.box(mat, (p0 + p1) / 2, (w, np.linalg.norm(p1 - p0), d), np.stack([s, ax, t], 1), col=col)


def gutter(c, p0, p1, r=0.07):
    c.b.tube("galv", p0, p1, r, 8 if c.fine else 4)


def downpipe(c, x, z, y0, y1, r=0.05):
    c.b.tube("galv", (x, y0, z), (x, y1, z), r, 8 if c.fine else 4)
    c.b.tube("galv", (x, y1, z), (x, y1 + 0.02, z), r + 0.03, 8 if c.fine else 4)


def window(c, centre_u_p0, dirv, up_y, w, h, normal, mullions=1, glass_back=0.12):
    """glass and frame behind a cut opening: p = point on the wall plane at the opening's horizontal centre."""
    b = c.b
    n = unit(normal); d = unit(dirv)
    p = V(centre_u_p0, float)
    gp = p - n * glass_back + V([0, up_y, 0])
    b.quad("glass", gp, d, V([0, 1.0, 0]), w, h, (0, h, w, 0), normal=n)
    for m in range(mullions):
        off = (-0.5 + (m + 1) / (mullions + 1)) * w
        b.box("steel", gp + d * off + n * 0.03, (0.05 if abs(d[0]) > 0.5 else 0.05, h, 0.05), np.stack([d, V([0, 1.0, 0]), n], 1) if False else None)
    # frame bars on the wall plane
    b.box("steel", p + V([0, up_y + h / 2 + 0.03, 0]) - n * 0.04, (w + 0.12, 0.07, 0.07), np.stack([d, V([0, 1.0, 0]), n], 1))
    b.box("steel", p + V([0, up_y - h / 2 - 0.03, 0]) - n * 0.04, (w + 0.16, 0.08, 0.14), np.stack([d, V([0, 1.0, 0]), n], 1))


def roller_door(c, p, dirv, normal, w, h, y0=0.0, tint=True):
    """A recessed roller door behind a cut opening, slatted, with a housing box above (p: wall-plane point at the door's centre)."""
    b = c.b
    n = unit(normal); d = unit(dirv)
    leaf = V(p, float) - n * 0.18
    rows = max(6, int(h / (0.14 if c.fine else 0.5)))
    vs = np.linspace(0, h, rows + 1)
    us = np.array([0.0, w])
    pos = lambda u, v: leaf + (np.asarray(u) - w / 2)[..., None] * d + (np.asarray(v) + y0)[..., None] * V([0, 1.0, 0])
    flip = float(np.dot(np.cross(d, V([0, 1.0, 0])), n)) < 0
    b.cut_param("galv", pos, us, vs, None, uv=lambda u, v: np.stack([u, v], -1), flip=flip,
                disp=(lambda u, v, k: 0.018 * (((np.asarray(v) / 0.14) % 1.0) ** 1.5)) if c.fine else None)
    # jambs, header, housing and bottom bar
    b.box("steel", V(p) + V([0, y0 + h / 2, 0]) + d * (w / 2 + 0.07) - n * 0.08, (0.14, h, 0.2), np.stack([d, V([0, 1.0, 0]), n], 1))
    b.box("steel", V(p) + V([0, y0 + h / 2, 0]) - d * (w / 2 + 0.07) - n * 0.08, (0.14, h, 0.2), np.stack([d, V([0, 1.0, 0]), n], 1))
    b.box("trim" if False else "galv", V(p) + V([0, y0 + h + 0.28, 0]) + n * 0.1, (w + 0.5, 0.56, 0.4), np.stack([d, V([0, 1.0, 0]), n], 1))
    b.tube("steel", V(p) + V([0, y0 + h + 0.28, 0]) + n * 0.34 - d * (w / 2 + 0.2), V(p) + V([0, y0 + h + 0.28, 0]) + n * 0.34 + d * (w / 2 + 0.2), 0.05, 6)
    b.box("steel", leaf + V([0, y0 + 0.06, 0]) + n * 0.02, (w, 0.1, 0.08), np.stack([d, V([0, 1.0, 0]), n], 1))
    if tint:
        b.quad("trim", V(p) + V([0, y0 + h + 0.28, 0]) + n * 0.31, d, V([0, 1.0, 0]), w + 0.4, 0.25, (0, 0.25 / 0.3 * 0.5, (w + 0.4) * 0.3, 0), normal=n, band=6, col=(1, 0, 0))


def lamp(c, p, n, d=0.8):
    c.b.tube("steel", V(p), V(p) + unit(n) * d + V([0, 0.25, 0]), 0.025, 6)
    c.b.box("steel", V(p) + unit(n) * d + V([0, 0.25, 0]), (0.28, 0.16, 0.28))


def debris(c, n, xr, zr, rng_scale=1.0, mats=("wood", "rust", "galv")):
    for k in range(n):
        m = mats[k % len(mats)]
        sz = (c.rng.uniform(0.3, 1.6) * rng_scale, c.rng.uniform(0.05, 0.4), c.rng.uniform(0.2, 0.9) * rng_scale)
        c.b.box(m, (c.rng.uniform(*xr), sz[1] / 2 + 0.05, c.rng.uniform(*zr)), sz, axis_angle(V([0, 1.0, 0]), c.rng.random() * 3.0))


def fallen_beam(c, p0, p1, w=0.16):
    timber(c, p0, p1, w, w)


def broken_boards(c, centre, n, normal, up_span, lateral, count=7, mat="wood", length=(0.8, 1.7)):
    """Splintered boards leaning out of a breach."""
    nn = unit(normal); d = unit(lateral)
    for k in range(count):
        a = c.rng.uniform(-1, 1)
        base = V(centre, float) + d * a * up_span[0] + V([0, c.rng.uniform(-up_span[1], up_span[1]), 0])
        ln = c.rng.uniform(*length)
        lean = c.rng.uniform(0.2, 0.9)
        top = base + nn * math.sin(lean) * ln + V([0, math.cos(lean) * ln * c.rng.choice([-1, 1]) * 0.7, 0]) + d * c.rng.uniform(-0.2, 0.2)
        timber(c, base, top, 0.16, 0.035, mat)


# ======================================================================================================== civstoragea
def shed_a(state, lod, seed):
    c = Ctx(state, lod, seed, breach=(3.85, 2.2, 0.5, 2.4), ledges=[(3.46, 2.4, 0.95), (0.6, 0.8, 0.6)], ao_rings=[(3.46, 1.2, 0.5)], ground_h=1.8)
    b = c.b
    fine = c.fine
    x0, x1, z0, z1, h = -3.85, 3.85, -5.79, 5.4, 3.46
    ln, wd = z1 - z0, x1 - x0
    dst = state == "destroyed"
    # foundation with a chamfered top, a proud plinth band
    b.box("concrete", (0, 0.2, (z0 + z1) / 2), (wd + 0.3, 0.4, ln + 0.3))
    b.box("concrete_dark", (0, 0.43, (z0 + z1) / 2), (wd + 0.12, 0.06, ln + 0.12))
    # side walls: corrugated, window strips (+x breached when damaged)
    wins = [(zz - z0 - 0.95, 1.9, zz - z0 + 0.95, 2.85) for zz in (-3.6, -1.2, 1.2, 3.6)]
    tearA = torn(ln * 0.5 + 0.5, 1.9, 2.1, 1.05, 0.3) if state == "damaged" else None
    kw = ridge_keep(ln, h, c.rng, 0.1, 0.55) if dst else None
    tdisp = curl(0, 0, 1, 1) if state == "damaged" else None
    clad(c, "corrugated", (x1, 0.45, z0), (0, 0, 1), ln, (0, 1, 0), h - 0.45, (1, 0, 0), "corr", holes=[] if dst else wins, extra=tearA or kw,
         thick=0.07 if not dst else 0.06, tear_disp=tdisp, v_extra=(1.4, 2.4) if tearA else ())
    clad(c, "corrugated", (x0, 0.45, z1), (0, 0, -1), ln, (0, 1, 0), h - 0.45, (-1, 0, 0), "corr", holes=[] if dst else wins[:0], extra=(ridge_keep(ln, h, c.rng, 0.05, 0.4) if dst else None), thick=0.06)
    if not dst:
        for zz in (-3.6, -1.2, 1.2, 3.6):
            if state == "damaged" and abs(zz - 0.5) < 1.9:
                continue
            window(c, (x1, 0, zz), (0, 0, 1), 2.375, 1.9, 0.95, (1, 0, 0), 1)
            b.box("steel", (x1 + 0.05, 1.85, zz), (0.14, 0.08, 2.1))      # sill
            c.decal_wall("streak_b", (x1, 0, zz), (0, 0, 1), 1.6, 0.9, 1.95, (1, 0, 0), off=0.04)
    # end walls: corrugated under the three gables, a roller door each (x -1.51..1.75)
    ends = ((z0, -1, x0, (1, 0, 0)), (z1, 1, x1, (-1, 0, 0)))
    for zz, nz, sx, d in ends:
        door = (-1.51 - sx if nz < 0 else sx - 1.75, 0.0, 0, 0)
        if nz < 0:
            u0, u1 = -1.51 - x0, 1.75 - x0
        else:
            u0, u1 = x1 - 1.75, x1 + 1.51
        holes = [(u0, 0.0, u1, 2.79 - 0.45)] if not dst else []
        kk = ridge_keep(wd, h, c.rng, 0.15, 0.6) if dst else None
        clad(c, "corrugated", (sx, 0.45, zz), d, wd, (0, 1, 0), h - 0.45, (0, 0, nz), "corr", holes=holes, extra=kk, thick=0.2 if holes else 0.06)
        if not dst:
            cx = (-1.51 + 1.75) / 2
            roller_door(c, (cx, 0.45, zz), (1, 0, 0), (0, 0, nz), 3.26, 2.34, 0.45)
            lamp(c, (cx, 3.2, zz + nz * 0.05), (0, 0, nz))
            # gable triangles over the three bays
            for rx in (-2.57, 0.0, 2.57):
                tri = [(rx - 1.285, 3.46, zz), (rx + 1.285, 3.46, zz), (rx, 4.2, zz)]
                Pq = V(tri); N = np.tile(V([0, 0, nz], float), (3, 1))
                b.add("corrugated", Pq, N, Pq[:, [0, 1]], [(0, 1, 2)])
    # roof: three gables along z, ridges 4.2 m at x -2.57, 0, 2.57, valleys 3.46 at +-1.285 (and the outer eaves)
    per = 0.45
    for rx in (-2.57, 0.0, 2.57):
        for sgn in (-1, 1):
            xs = rx + sgn * 1.285
            sl = V([xs - rx, 3.46 - 4.2, 0.0])
            slen = np.linalg.norm(sl)
            nrm = unit(np.cross(V([0, 0, 1.0]), sl)); nrm = nrm if nrm[1] > 0 else -nrm
            # overhang 0.4 at both ends, 0.2 at the eave
            p0 = V([rx, 4.2 + 0.06, z0 - 0.4]) + nrm * 0.06
            ext = 0.0
            tearR = None; sagR = None; tdR = None
            if state == "damaged" and rx == 0.0 and sgn == 1:
                tearR = torn(ln * 0.5 + 0.8, slen * 0.5, 1.6, 0.85, 1.0)
                sagR = lambda u, v: -0.25 * np.exp(-(((np.asarray(u) - ln * 0.5 - 0.8) / 2.4) ** 2 + ((np.asarray(v) - slen * 0.5) / 1.1) ** 2))
                tdR = curl(0, 0, 1, 1, 0.16)
            if dst:
                continue
            slab_sheet(c, "roofing", p0, (0, 0, 1), ln + 0.8, sl, slen + (0.2 if abs(xs) > 3.5 else 0.0), nrm, True, 0.05, tearR, tdR, sagR, per)
    if not dst:
        for rx in (-2.57, 0.0, 2.57):  # ridge caps
            b.box("galv", (rx, 4.26, (z0 + z1) / 2), (0.22, 0.1, ln + 0.8))
        # gutters and downpipes on the outer eaves, fascia boards
        for sx in (x0 - 0.15, x1 + 0.15):
            gutter(c, (sx, 3.4, z0 - 0.3), (sx, 3.3, z1 + 0.3))
            b.box("wood", (sx, 3.52, (z0 + z1) / 2), (0.05, 0.22, ln + 0.8))
        for (px, pz) in ((x0 - 0.15, z0 + 0.2), (x1 + 0.15, z1 - 0.2), (x1 + 0.15, z0 + 0.2), (x0 - 0.15, z1 - 0.2)):
            downpipe(c, px, pz, 0.4, 3.3)
        for (px, pz) in ((x0, z0), (x1, z0), (x0, z1), (x1, z1)):   # corner trims
            b.box("steel", (px, h / 2 + 0.2, pz), (0.22, h, 0.22))
        # a tint stripe above the +x windows
        b.quad("trim", V([x1 + 0.05, 3.1, (z0 + z1) / 2]), V([0, 0, 1.0]), V([0, 1.0, 0]), ln - 0.5, 0.32, (0, 0.5, (ln - 0.5) * 0.3, 0), normal=(1, 0, 0), band=6, col=(1, 0, 0))
        for k, zz in enumerate(np.linspace(-5.0, 4.6, 6)):
            if not (state == "damaged" and abs(zz - 0.5) < 2.3):
                c.decal_wall("streak_a" if k % 2 else "streak_b", (x1, 0, zz), (0, 0, 1), 1.9, 0.5, 3.4, (1, 0, 0), off=0.05)
        for k, zz in enumerate(np.linspace(-5.0, 4.8, 7)):
            c.decal_wall("rust_bleed", (x1, 0, zz), (0, 0, 1), 1.2, 0.45, 1.5, (1, 0, 0), off=0.05)
    if state == "damaged":
        interior_shell(c, x0, x1, z0, z1, h)
        for k in range(7):                                  # exposed rafters and a stud wall
            zz = z0 + 0.8 + k * 1.65
            timber(c, (x1 - 0.3, 3.4, zz), (x1 - 0.3, 0.5, zz), 0.1, 0.1)
            timber(c, (0, 4.15, zz), (x1 - 0.2, 3.5, zz), 0.1, 0.1)
        broken_boards(c, (x1, 1.9, 0.5), 7, (1, 0.2, 0), (1.9, 0.7), (0, 0, 1), 6, "corrugated", (0.8, 1.6))
        c.decal_ground("soot", (4.2, 0.5), 7, 8, 0.0, y=0.05)
        c.decal_ground("oil", (4.0, 2.5), 3, 3, 0.4, y=0.06)
    if dst:
        interior_shell(c, x0, x1, z0, z1, 0.9)
        # collapse: roof sheets down across the floor, one still propped on the -x wall, trusses and posts broken
        for k, (cx_, cz_) in enumerate(((-2.0, -3.4), (1.6, -1.2), (0.0, 2.8), (2.4, 3.8))):
            Rm = axis_angle(V([0, 0, 1.0]), c.rng.uniform(-0.35, 0.35)) @ axis_angle(V([1.0, 0, 0]), c.rng.uniform(-0.25, 0.25))
            ctr = V([cx_, 0.55 + 0.3 * k, cz_])
            b.M = (Rm, ctr - Rm @ ctr)
            slab_sheet(c, "roofing", ctr + V([-1.3, 0, -1.7]), (1, 0, 0), 2.6, (0, 0, 1), 3.4, (0, 1, 0), True, 0.05, None, None, None, per)
            b.M = None
        Rp = axis_angle(V([0, 0, 1.0]), 0.62)
        ctr = V([-3.0, 2.0, 0.0])
        b.M = (Rp, ctr - Rp @ ctr)
        slab_sheet(c, "roofing", ctr + V([-1.3, 0, -3.0]), (1, 0, 0), 2.6, (0, 0, 1), 6.0, (0, 1, 0), True, 0.05, None, None, None, per)
        b.M = None
        for k in range(8):
            ang = c.rng.uniform(-0.6, 0.6)
            a = V([c.rng.uniform(-3, 3), 0.35, c.rng.uniform(-5, 5)])
            timber(c, a, a + V([math.cos(ang) * 3.0, c.rng.uniform(0.3, 1.2), math.sin(ang) * 3.0]), 0.14, 0.14)
        for (px, pz) in ((x0, z0), (x1, z1), (x1, z0)):
            timber(c, (px, 0.4, pz), (px, 1.6 + c.rng.random(), pz), 0.2, 0.2, "steel")
        debris(c, 14, (-3.5, 3.5), (-5.5, 5.0))
        c.decal_ground("soot", (0, (z0 + z1) / 2), 12, 16, 0.0, y=0.05)
        c.decal_ground("oil", (-1.5, 2.0), 4, 4, 0.6, y=0.055)
    return c


# ======================================================================================================== civstorageb
def shed_b(state, lod, seed):
    c = Ctx(state, lod, seed, breach=(3.12, 2.2, -4.0, 2.4), ledges=[(4.01, 2.4, 0.95), (1.18, 0.9, 0.6)], ao_rings=[(4.01, 1.2, 0.5)], ground_h=1.8)
    b = c.b
    fine = c.fine
    x0, x1, z0, z1, h = -3.12, 3.12, -11.43, 3.26, 4.01
    ln, wd = z1 - z0, x1 - x0
    dst = state == "destroyed"
    b.box("concrete", (0, 0.15, (z0 + z1) / 2), (wd + 0.3, 0.3, ln + 0.3))
    b.box("concrete_dark", (0, 0.33, (z0 + z1) / 2), (wd + 0.12, 0.06, ln + 0.12))
    # +x wall: corrugated with a band of high windows; -x wall: three roller doors above the docks
    wins = [(zz - z0 - 0.9, 2.3, zz - z0 + 0.9, 3.2) for zz in np.linspace(z0 + 1.2, z1 - 1.2, 8)]
    tearB = torn(ln * 0.45, 1.9, 2.3, 1.05, 0.6) if state == "damaged" else None
    kw = ridge_keep(ln, h, c.rng, 0.1, 0.5) if dst else None
    clad(c, "corrugated", (x1, 0.33, z0), (0, 0, 1), ln, (0, 1, 0), h - 0.33, (1, 0, 0), "corr", holes=[] if dst else [(a, b_ - 0.33, c_, d - 0.33) for a, b_, c_, d in wins], extra=tearB or kw,
         thick=0.07, tear_disp=curl(0, 0, 1, 1) if tearB else None, v_extra=(1.4, 2.4) if tearB else ())
    docks = [z0 + 2.6, z0 + 7.5, z0 + 12.4]
    dh = [(zz - z0 - 1.75, 1.18 - 0.33, zz - z0 + 1.75, 3.5 - 0.33) for zz in docks]
    clad(c, "corrugated", (x0, 0.33, z1), (0, 0, -1), ln, (0, 1, 0), h - 0.33, (-1, 0, 0), "corr", holes=[] if dst else [(ln - (zz - z0) - 1.75, 0.85, ln - (zz - z0) + 1.75, 3.17) for zz in docks],
         extra=ridge_keep(ln, h, c.rng, 0.1, 0.5) if dst else None, thick=0.2 if not dst else 0.06)
    if not dst:
        for zz in (docks if True else []):
            roller_door(c, (x0, 1.18, zz), (0, 0, 1), (-1, 0, 0), 3.5, 2.32, 1.18, tint=True)
            b.box("concrete", (x0 - 0.42, 0.6, zz), (0.84, 1.18, 3.9))        # dock
            b.box("steel", (x0 - 0.86, 1.2, zz), (0.08, 0.1, 3.9))            # dock edge bumper
            for dz in (-1.7, 1.7):
                b.box("steel", (x0 - 0.5, 0.3, zz + dz), (0.5, 0.6, 0.1))
        for zz in np.linspace(z0 + 1.2, z1 - 1.2, 8):
            if state == "damaged" and abs(zz - (z0 + ln * 0.45)) < 2.0:
                continue
            window(c, (x1, 0, zz), (0, 0, 1), 2.75, 1.8, 0.9, (1, 0, 0), 1)
    for sz, nz, sx, d in ((z0, -1, x0, (1, 0, 0)), (z1, 1, x1, (-1, 0, 0))):
        clad(c, "corrugated", (sx, 0.33, sz), d, wd, (0, 1, 0), h - 0.33, (0, 0, nz), "corr", extra=ridge_keep(wd, h, c.rng, 0.15, 0.55) if dst else None, thick=0.06)
    # sawtooth roof: three 4.9 m bays, each falling from 5.33 (clerestory, +z) to 4.01 (-z), ribbed sheets with glazing strips
    if not dst:
        for k in range(3):
            zb0 = z0 + 0.1 + k * 4.9
            zb1 = zb0 + 4.9
            sl = V([0, 4.01 - 5.33, -4.9])             # down toward -z from the clerestory crest
            slen = np.linalg.norm(sl)
            nrm = unit(np.cross(V([1.0, 0, 0]), sl)); nrm = nrm if nrm[1] > 0 else -nrm
            p0 = V([x0 - 0.15, 5.33 + 0.06, zb1]) + nrm * 0.06
            tearR = sagR = tdR = None
            if state == "damaged" and k == 1:
                tearR = torn(wd * 0.5 + 0.15, slen * 0.5, 1.5, 1.1, 0.3)
                sagR = lambda u, v: -0.3 * np.exp(-(((np.asarray(u) - wd * 0.5) / 2.0) ** 2 + ((np.asarray(v) - slen * 0.5) / 1.3) ** 2))
                tdR = curl(0, 0, 1, 1, 0.16)
            slab_sheet(c, "roofing", p0, (1, 0, 0), wd + 0.3, sl, slen, nrm, True, 0.05, tearR, tdR, sagR, 0.45)
            # clerestory: a glazed strip under a hood, with mullions and a sill
            b.quad("glass", V([0, 4.7, zb1 + 0.0]), V([1.0, 0, 0]), V([0, 1.0, 0]), wd - 0.3, 1.0, (0, 1, wd, 0), normal=(0, 0, 1))
            for m in range(7 if fine else 3):
                xm = x0 + 0.15 + m * (wd - 0.3) / (6 if fine else 2)
                b.box("steel", (xm, 4.7, zb1 + 0.02), (0.06, 1.1, 0.08))
            b.box("steel", (0, 4.18, zb1 + 0.04), (wd, 0.1, 0.16)); b.box("galv", (0, 5.3, zb1 + 0.18), (wd + 0.3, 0.1, 0.5))
            b.box("steel", (0, 4.01 + 0.02, zb1 - 0.04), (wd, 0.2, 0.08))
        for sx in (x0 - 0.15, x1 + 0.15):
            gutter(c, (sx, 3.95, z0 - 0.2), (sx, 3.85, z1 + 0.2))
        for (px, pz) in ((x0 - 0.2, z0 + 0.3), (x1 + 0.2, z1 - 0.3), (x1 + 0.2, z0 + 0.3)):
            downpipe(c, px, pz, 0.35, 3.9)
        for (px, pz) in ((x0, z0), (x1, z0), (x0, z1), (x1, z1)):
            b.box("steel", (px, h / 2 + 0.17, pz), (0.22, h, 0.22))
        b.quad("trim", V([x1 + 0.05, 3.55, (z0 + z1) / 2]), V([0, 0, 1.0]), V([0, 1.0, 0]), ln - 0.4, 0.3, (0, 0.5, (ln - 0.4) * 0.3, 0), normal=(1, 0, 0), band=6, col=(1, 0, 0))
        for k, zz in enumerate(np.linspace(-10.5, 2.6, 8)):
            if not (state == "damaged" and abs(zz - (z0 + ln * 0.45)) < 2.4):
                c.decal_wall("streak_a" if k % 2 else "streak_b", (x1, 0, zz), (0, 0, 1), 1.9, 0.5, 3.9, (1, 0, 0), off=0.05)
        for k, zz in enumerate(np.linspace(-11, 3, 9)):
            c.decal_wall("rust_bleed", (x1, 0, zz), (0, 0, 1), 1.2, 0.4, 1.5, (1, 0, 0), off=0.05)
    if state == "damaged":
        interior_shell(c, x0, x1, z0, z1, h)
        for k in range(7):
            zz = z0 + 1.2 + k * 2.0
            timber(c, (x1 - 0.3, 3.9, zz), (x1 - 0.3, 0.4, zz), 0.12, 0.12, "steel")
            timber(c, (x0 + 0.3, 4.0, zz), (x1 - 0.3, 4.0, zz), 0.1, 0.18, "steel")
        broken_boards(c, (x1, 1.9, z0 + ln * 0.45), 7, (1, 0.2, 0), (2.0, 0.7), (0, 0, 1), 6, "corrugated", (0.8, 1.7))
        c.decal_ground("soot", (4.2, z0 + ln * 0.45), 7, 8, 0.0, y=0.05)
    if dst:
        interior_shell(c, x0, x1, z0, z1, 0.9)
        for k, cz_ in enumerate((-8.0, -4.2, -0.6)):
            Rm = axis_angle(V([1.0, 0, 0]), c.rng.uniform(-0.3, 0.3)) @ axis_angle(V([0, 0, 1.0]), c.rng.uniform(-0.3, 0.3))
            ctr = V([0.0, 0.5 + 0.35 * k, cz_])
            b.M = (Rm, ctr - Rm @ ctr)
            slab_sheet(c, "roofing", ctr + V([-3.0, 0, -2.2]), (1, 0, 0), 6.0, (0, 0, 1), 4.6, (0, 1, 0), True, 0.05, None, None, None, 0.45)
            b.M = None
        Rp = axis_angle(V([0, 0, 1.0]), -0.5)
        ctr = V([2.4, 1.5, -2.0])
        b.M = (Rp, ctr - Rp @ ctr)
        slab_sheet(c, "roofing", ctr + V([-1.3, 0, -2.5]), (1, 0, 0), 2.6, (0, 0, 1), 5.0, (0, 1, 0), True, 0.05, None, None, None, 0.45)
        b.M = None
        for k in range(8):
            a = V([c.rng.uniform(-2.8, 2.8), 0.35, c.rng.uniform(-11, 2.5)])
            timber(c, a, a + V([c.rng.uniform(-3, 3), c.rng.uniform(0.3, 1.0), c.rng.uniform(-3, 3)]), 0.14, 0.14, "steel")
        debris(c, 16, (-3.0, 3.0), (-11, 3.0))
        c.decal_ground("soot", (0, (z0 + z1) / 2), 12, 20, 0.0, y=0.05)
        c.decal_ground("oil", (1.0, -3.0), 4, 4, 0.3, y=0.055)
    return c


# ======================================================================================================== civstoragec
def shed_c(state, lod, seed):
    c = Ctx(state, lod, seed, breach=(2.24, 4.2, -1.7, 1.7), ledges=[(5.0, 1.8, 0.9), (2.54, 0.9, 0.6)], ao_rings=[(2.54, 1.5, 0.6)], ground_h=1.6)
    b = c.b
    fine = c.fine
    x0, x1, z0, z1 = -2.24, 2.24, -3.34, 0.10
    ln, wd = z1 - z0, x1 - x0
    deck = 2.54
    dst = state == "destroyed"
    posts = [(-2.09, -3.20), (2.09, -3.20), (-2.09, -0.04), (2.09, -0.04)]
    # timber trestles: square posts on concrete footings, X braces and a girt each side, bolted
    for k, (px, pz) in enumerate(posts):
        b.box("concrete", (px, 0.12, pz), (0.55, 0.24, 0.55))
        top = deck if not (dst and px > 0) else 0.9 + 0.5 * (k % 2)
        timber(c, (px, 0.2, pz), (px, top, pz), 0.26, 0.26)
        if not dst or px < 0:
            for yy in (0.9, deck - 0.4):
                b.tube("steel", (px - 0.16, yy, pz), (px + 0.16, yy, pz), 0.025, 6) if fine else None
    if not dst:
        for (a, bq) in ((0, 1), (2, 3), (0, 2), (1, 3)):
            pa, pb = posts[a], posts[bq]
            timber(c, (pa[0], 0.55, pa[1]), (pb[0], deck - 0.35, pb[1]), 0.12, 0.1)
            timber(c, (pa[0], deck - 0.35, pa[1]), (pb[0], 0.55, pb[1]), 0.12, 0.1)
            timber(c, (pa[0], 1.1, pa[1]), (pb[0], 1.1, pb[1]), 0.14, 0.12)
        # deck beams and boards
        for xs in (-1.7, -0.6, 0.6, 1.7):
            timber(c, (xs, deck - 0.22, z0 - 0.15), (xs, deck - 0.22, z1 + 0.25), 0.14, 0.2)
        for k in range(int((ln + 0.5) / 0.2) if fine else 3):
            zz = z0 - 0.2 + k * 0.2
            b.box("boards", (0, deck - 0.05, zz + 0.1), (wd + 0.5, 0.06, 0.19))
        b.box("wood", (0, deck - 0.12, z0 - 0.2), (wd + 0.5, 0.2, 0.1)); b.box("wood", (0, deck - 0.12, z1 + 0.3), (wd + 0.5, 0.2, 0.1))
    else:
        b.box("boards", (-0.5, 0.4, -1.7), (4.4, 0.12, 3.4), axis_angle(V([0, 0, 1.0]), 0.12))
        for xs in (-1.5, -0.5, 0.6):
            timber(c, (xs, 0.3, -3.2), (xs + 0.4, 0.8, 0.2), 0.14, 0.2)
    # cabin walls: lap siding, 5.00 m (-x) rising to 5.98 m (+x) under the roof; door and window framed with depth
    y0 = deck
    tearC = torn(ln * 0.5, 1.7, 1.0, 0.8, 0.2) if state == "damaged" else None
    kdst = ridge_keep(ln, 1.6, c.rng, 0.15, 0.6) if dst else None
    doorh = [(ln - 0.0 - 1.28 - 0.4, 0.0, ln - 0.0 - 0.4, 2.15)]
    # +x wall (taller side), -x wall with a small window, end walls (door on +z)
    clad(c, "lapwood", (x1, y0, z0), (0, 0, 1), ln, (0, 1, 0), 3.4, (1, 0, 0), "lap", extra=tearC or kdst, thick=0.05, edge_mat="wood", tear_disp=curl(0, 0, 1, 1, 0.1) if tearC else None, v_extra=(1.0, 2.0) if tearC else ())
    clad(c, "lapwood", (x0, y0, z1), (0, 0, -1), ln, (0, 1, 0), 2.46, (-1, 0, 0), "lap", holes=[] if dst else [(1.0, 1.0, 2.2, 1.9)], extra=kdst, thick=0.1, edge_mat="wood")
    clad(c, "lapwood", (x0, y0, z0), (1, 0, 0), wd, (0, 1, 0), 2.7, (0, 0, -1), "lap", extra=kdst, thick=0.05, edge_mat="wood")
    clad(c, "lapwood", (x1, y0, z1), (-1, 0, 0), wd, (0, 1, 0), 2.7, (0, 0, 1), "lap", holes=[] if dst else [(0.9, 0.0, 2.18, 2.15)], extra=kdst, thick=0.12, edge_mat="wood")
    if not dst:
        # door: leaf set back with a frame, a step and a threshold; window with a shutter and sill
        b.box("boards", (-0.9 + 0.0, y0 + 1.07, z1 - 0.1), (1.18, 2.1, 0.06))
        for dxs in (-1.54, -0.26):
            timber(c, (dxs, y0, z1 + 0.04), (dxs, y0 + 2.2, z1 + 0.04), 0.14, 0.1)
        timber(c, (-1.58, y0 + 2.2, z1 + 0.04), (-0.22, y0 + 2.2, z1 + 0.04), 0.16, 0.1)
        b.tube("steel", (-0.45, y0 + 1.0, z1 + 0.02), (-0.45, y0 + 1.1, z1 + 0.02), 0.04, 6)
        b.quad("glass", V([x0 - 0.0 - 0.0, y0 + 1.45, -1.6 + 0.0 - 0.0]) + V([-0.08 + 0.1, 0, 0]), V([0, 0, 1.0]), V([0, 1.0, 0]), 1.0, 0.8, (0, 0.8, 1.0, 0), normal=(-1, 0, 0))
        timber(c, (x0 - 0.05, y0 + 0.95, -1.6 - 0.62), (x0 - 0.05, y0 + 0.95, -1.6 + 0.62), 0.12, 0.1) if False else None
        b.box("wood", (x0 - 0.1, y0 + 0.95, -1.6 + 0.0 - 0.0), (0.16, 0.08, 1.35))
        b.box("boards", (x0 - 0.08, y0 + 1.45, -1.6 - 0.75), (0.05, 0.9, 0.5))
        for yy in (y0 + 0.02, y0 + 2.4):
            pass
        # corner posts and a deck rim, ridge of the cabin
        for (px, pz, hh) in ((x0, z0, 2.46), (x1, z0, 3.4), (x0, z1, 2.46), (x1, z1, 3.4)):
            timber(c, (px, y0, pz), (px, y0 + hh, pz), 0.14, 0.14)
        # mono-pitch roof: ribbed sheet with 0.3 m overhang, fascia, gutter, bracketed
        sl = V([wd + 0.6, 5.98 - 5.00 + 0.0, 0.0])
        slen = np.linalg.norm(sl)
        nrm = unit(np.cross(V([0, 0, 1.0]), sl)); nrm = nrm if nrm[1] > 0 else -nrm
        p0 = V([x0 - 0.3, 5.00 + 0.07 - 0.0, z0 - 0.45]) + nrm * 0.07
        tearR = sagR = tdR = None
        if state == "damaged":
            tearR = torn(ln * 0.5 + 0.45, slen * 0.6, 1.2, 0.8, 0.4)
            sagR = lambda u, v: -0.22 * np.exp(-(((np.asarray(u) - ln * 0.5 - 0.45) / 1.8) ** 2 + ((np.asarray(v) - slen * 0.6) / 1.1) ** 2))
            tdR = curl(0, 0, 1, 1, 0.14)
        slab_sheet(c, "roofing", p0, (0, 0, 1), ln + 0.9, sl, slen, nrm, True, 0.05, tearR, tdR, sagR, 0.45)
        b.box("wood", (x1 + 0.3, 6.0, (z0 + z1) / 2), (0.06, 0.2, ln + 0.9)); b.box("wood", (x0 - 0.3, 5.03, (z0 + z1) / 2), (0.06, 0.2, ln + 0.9))
        gutter(c, (x0 - 0.38, 4.95, z0 - 0.45), (x0 - 0.38, 4.9, z1 + 0.45), 0.05)
        downpipe(c, x0 - 0.38, z1 + 0.35, deck, 4.9, 0.04)
        b.quad("trim", V([x1 + 0.03, y0 + 2.3, (z0 + z1) / 2]), V([0, 0, 1.0]), V([0, 1.0, 0]), ln, 0.28, (0, 0.5, ln * 0.3, 0), normal=(1, 0, 0), band=6, col=(1, 0, 0))
        for k, zz in enumerate(np.linspace(-3.0, 0.0, 3)):
            c.decal_wall("streak_a" if k % 2 else "streak_b", (x1, 0, zz), (0, 0, 1), 1.4, y0 + 0.3, y0 + 3.2, (1, 0, 0), off=0.04)
        # stair: timber stringers, nine treads, a handrail
        for sx in (-0.63, 0.63):
            timber(c, (sx, deck - 0.1, 0.18), (sx, 0.1, 3.8), 0.1, 0.22)
            timber(c, (sx, deck + 0.95, 0.2), (sx, 0.95, 3.8), 0.07, 0.07) if fine else None
        for k in range(9):
            b.box("boards", (0, deck - 0.28 * (k + 1) - 0.0, 0.18 + 0.4 * (k + 1)), (1.35, 0.05, 0.38))
        if state == "damaged":
            pass
    if state == "damaged":
        interior_shell(c, x0, x1, z0, z1 + 0.0, 5.0 - 0.0 + 0.0 if False else 3.0)
        b.M = (np.eye(3), V([0, deck, 0]))
        b.M = None
        for k in range(4):
            zz = z0 + 0.45 + k * 0.85
            timber(c, (x1 - 0.12, deck, zz), (x1 - 0.12, deck + 3.2, zz), 0.1, 0.1)
        broken_boards(c, (x1, deck + 1.7, -1.7), 7, (1, 0.2, 0), (1.0, 0.8), (0, 0, 1), 7, "wood", (0.7, 1.5))
        c.decal_ground("soot", (3.0, -1.7), 6, 6, 0.0, y=0.05)
    if dst:
        interior_shell(c, x0, x1, z0, z1, 0.4)
        for k in range(4):
            Rm = axis_angle(V([1.0, 0, 0]), c.rng.uniform(-0.3, 0.3)) @ axis_angle(V([0, 0, 1.0]), c.rng.uniform(-0.4, 0.4))
            ctr = V([c.rng.uniform(-1.5, 1.5), 0.45 + 0.3 * k, c.rng.uniform(-3.0, 0.2)])
            b.M = (Rm, ctr - Rm @ ctr)
            slab_sheet(c, "roofing", ctr + V([-1.1, 0, -1.2]), (1, 0, 0), 2.2, (0, 0, 1), 2.4, (0, 1, 0), True, 0.05, None, None, None, 0.45)
            b.M = None
        for k in range(9):
            a = V([c.rng.uniform(-2.5, 2.5), 0.3, c.rng.uniform(-3.5, 0.4)])
            timber(c, a, a + V([c.rng.uniform(-2, 2), c.rng.uniform(0.2, 0.9), c.rng.uniform(-2, 2)]), 0.12, 0.12)
        for k in range(6):
            a = V([c.rng.uniform(-1.0, 1.0), 0.3, 1.0 + k * 0.4])
            timber(c, a, a + V([0.1, 0.1, 0.6]), 0.1, 0.2)
        debris(c, 12, (-2.8, 2.8), (-3.8, 2.8), 0.8, ("wood", "boards", "galv"))
        c.decal_ground("soot", (0, -1.6), 9, 10, 0.0, y=0.05)
    return c


# ======================================================================================================== grainstorage
def grain(state, lod, seed):
    c = Ctx(state, lod, seed, breach=(2.0, 11.0, -4.1, 3.4), ledges=[(15.1, 2.5, 0.9), (10.21, 2.0, 0.7)], ao_rings=[(10.21, 1.4, 0.4)], ground_h=2.5)
    b = c.b
    fine = c.fine
    x0, x1, z0, z1, zb = -4.17, 12.68, -4.13, 0.38, 4.13
    W = x1 - x0
    hh = 10.21
    dst = state == "destroyed"
    sil = (-2.03, 2.16, 6.35, 10.54)
    zc = 2.19
    # foundation slab
    b.box("concrete", ((x0 + x1) / 2, 0.15, (z0 + zb) / 2), (W + 0.5, 0.3, zb - z0 + 0.5))
    # --- silos: true round, seamed rings, caps with hatches, vent stacks, streaks
    for k, sx in enumerate(sil):
        seg = 56 if fine else 28
        if dst:
            hs = 3.5 + 3.2 * c.rng.random()
            keep = lambda t, y, hs=hs, sx=sx: hs + 1.2 * np.sin(np.asarray(t) * 4 + sx) + 0.7 * np.sin(np.asarray(t) * 11) + 0.25 * np.abs(((np.asarray(t) * 5.0 / TAU * 2) % 2) - 1) - np.asarray(y)
            b.cut_surface("silo", lambda yy: np.full_like(yy, 2.0), np.unique(np.r_[np.linspace(0, 9, 36)]), 56 if fine else 28, keep, cx=sx, cz=zc, uref=uref(2.0, 2.0), thickness=0.08,
                          disp=lambda t, y, kk: np.clip(1 - kk / 0.4, 0, 1) ** 2 * 0.2)
            b.revolve("interior", [(1.9, y) for y in np.linspace(0, 7, 8)], 28, cx=sx, cz=zc, flip=True, uref=2.0)
            b.disc("interior", (sx, 0.32, zc), 1.9, seg=28)
            for j in range(6):
                a = c.rng.random() * TAU
                b.box("paint", (sx + 2.0 * math.cos(a), 0.9 + c.rng.random() * 1.5, zc + 2.0 * math.sin(a)), (0.05, c.rng.uniform(0.8, 1.8), c.rng.uniform(0.6, 1.2)),
                      axis_angle(V([0, 1.0, 0]), -a) @ axis_angle(V([0, 0, 1.0]), c.rng.uniform(0.2, 0.7)))
            continue
        if state == "damaged" and k == 1:
            ys = np.unique(np.r_[np.linspace(0, 10.21, 16), np.linspace(5.5, 10.21, 24)])
            thc = math.radians(270)
            def keep(t, y, thc=thc):
                u = ((np.asarray(t) - thc + math.pi) % TAU - math.pi) * 2.0
                g = np.sqrt((u / 1.1) ** 2 + ((np.asarray(y) - 8.2) / 1.7) ** 2)
                return (g - (1 + 0.15 * np.sin(5 * np.arctan2(np.asarray(y) - 8.2, u) + 1))) * 1.0
            b.cut_surface("silo", lambda yy: np.full_like(yy, 2.0), ys, seg, keep, cx=sx, cz=zc, uref=uref(2.0, 2.0), thickness=0.08, disp=lambda t, y, kk: np.clip(1 - kk / 0.4, 0, 1) ** 2 * 0.2)
            b.revolve("interior", [(1.92, y) for y in np.linspace(0, 10.21, 10)], 28, cx=sx, cz=zc, flip=True, uref=2.0)
        else:
            b.revolve("silo", [(2.0, y) for y in np.linspace(0, 10.21, 14)], seg, cx=sx, cz=zc, uref=uref(2.0, 2.0))
        for yy in (1.8, 3.9, 6.0, 8.1):
            c.ring("galv", yy - 0.05, yy + 0.05, 2.0, 0.07, sx, zc, 28)
        for j in range(8 if fine else 0):                       # vertical seams
            a = TAU * (j + 0.5) / 8
            b.tube("steel", (sx + 2.0 * math.cos(a), 0.3, zc + 2.0 * math.sin(a)), (sx + 2.01 * math.cos(a), 10.1, zc + 2.01 * math.sin(a)), 0.03, 5, caps=False)
        # cap: cone, a hatch with hinge, a vent stack, a rim rail
        if not (state == "damaged" and k == 1) or True:
            b.revolve("roofing", [(2.08, 10.21), (2.0, 10.4), (0.9, 10.95), (0.0, 11.2)], seg, cx=sx, cz=zc, uref=uref(2.0, 1.5))
            b.box("steel", (sx + 0.6, 11.05, zc + 0.3), (0.8, 0.12, 0.8))
            b.box("trim", (sx + 0.6, 11.12, zc + 0.3), (0.74, 0.01, 0.74), band=1) if False else None
            b.tube("steel", (sx - 0.4, 11.0, zc - 0.2), (sx - 0.4, 11.9, zc - 0.2), 0.12, 10 if fine else 5)
            b.revolve("steel", [(0.2, 11.9), (0.26, 11.96), (0.0, 12.1)], 10, cx=sx - 0.4, cz=zc - 0.2, uref=1.0)
        c.decal_rev("streak_a" if k % 2 else "streak_b", 0.4 + k, 1.5, 6.0, 10.1, 2.0, sx, zc, off=0.04)
        c.decal_rev("rust_bleed", 3.5 - k, 1.4, 2.0, 4.0, 2.0, sx, zc, off=0.04)
        c.decal_rev("diamond", math.radians(270), 1.0, 5.0, 6.0, 2.0, sx, zc, off=0.04) if k in (0, 3) else None
    # --- hall: columns, cladding, big doors, vents, gallery, ladder
    hall_h = 15.16
    doors = [(-1.2 + 0.0, 4.8), (4.0, 4.8)]
    vents = [(x0 + 1.5 + 2.4 * j, 7.6, x0 + 1.5 + 2.4 * j + 1.7, 8.6) for j in range(6)] if False else []
    holes = [(d0 - x0, 0.0, d0 - x0 + dw, 4.2) for d0, dw in doors]
    holes += [(vx - x0, 6.4, vx - x0 + 1.9, 7.6) for vx in np.arange(x0 + 1.0, x1 - 1.0, 2.9)]
    holes += [(vx - x0, 12.3, vx - x0 + 2.4, 13.3) for vx in np.arange(x0 + 1.4, x1 - 1.4, 3.6)]
    if not dst:
        tearG = torn(W * 0.62, 8.0, 2.6, 3.4, 0.5) if state == "damaged" else None
        clad(c, "corrugated", (x0, 0.3, z0), (1, 0, 0), W, (0, 1, 0), hall_h - 0.3, (0, 0, -1), "corr", holes=[(a, b_ - 0.3, c_, d - 0.3) for a, b_, c_, d in holes], extra=tearG, thick=0.15 if not tearG else 0.08,
             tear_disp=curl(0, 0, 1, 1, 0.16) if tearG else None, v_extra=(5.0, 9.0) if tearG else ())
        # side walls and the back block above the silos
        clad(c, "corrugated", (x0, 0.3, z0), (0, 0, 1), z1 - z0, (0, 1, 0), 13.5, (-1, 0, 0), "corr", thick=0.06)
        clad(c, "corrugated", (x1, 0.3, z0), (0, 0, 1), z1 - z0, (0, 1, 0), 13.5, (1, 0, 0), "corr", thick=0.06)
        clad(c, "corrugated", (x0, hh, z1), (0, 0, 1), zb - z1, (0, 1, 0), 3.4, (-1, 0, 0), "corr", thick=0.06)
        clad(c, "corrugated", (x1, hh, z1), (0, 0, 1), zb - z1, (0, 1, 0), 3.4, (1, 0, 0), "corr", thick=0.06)
        clad(c, "corrugated", (x0, hh, zb), (1, 0, 0), W, (0, 1, 0), 2.0, (0, 0, 1), "corr", thick=0.06)
        for d0, dw in doors:                                                   # big doors: framed leaves with a hood and a rail
            cx = d0 + dw / 2
            b.quad("galv", V([cx, 2.1, z0 - 0.18]), V([1.0, 0, 0]), V([0, 1.0, 0]), dw, 4.2, (0, 4.2, dw, 0), normal=(0, 0, -1))
            for m in range(1, 4):
                b.box("steel", (d0 + dw * m / 4, 2.1, z0 - 0.2), (0.12, 4.2, 0.1))
            for yy in (0.6, 2.1, 3.6):
                b.box("steel", (cx, yy, z0 - 0.2), (dw, 0.12, 0.1))
            b.box("steel", (cx, 4.45, z0 - 0.5), (dw + 0.8, 0.22, 1.0), axis_angle(V([1.0, 0, 0]), 0.25))
            for sgn in (-1, 1):
                b.box("steel", (cx + sgn * (dw / 2 + 0.15), 2.1, z0 - 0.1), (0.3, 4.2, 0.3))
        for vx in np.arange(x0 + 1.0, x1 - 1.0, 2.9):                         # louvre vents: dark back and slats
            b.quad("interior", V([vx + 0.95, 7.0, z0 - 0.1]), V([1.0, 0, 0]), V([0, 1.0, 0]), 1.9, 1.2, (0, 1, 1, 0), normal=(0, 0, -1))
            for j in range(5 if fine else 2):
                b.box("galv", (vx + 0.95, 6.5 + j * 0.24, z0 - 0.2), (1.95, 0.05, 0.22), axis_angle(V([1.0, 0, 0]), -0.5))
        for vx in np.arange(x0 + 1.4, x1 - 1.4, 3.6):
            b.quad("glass", V([vx + 1.2, 12.8, z0 - 0.1]), V([1.0, 0, 0]), V([0, 1.0, 0]), 2.4, 1.0, (0, 1, 2.4, 0), normal=(0, 0, -1))
            b.box("steel", (vx + 1.2, 12.8, z0 - 0.14), (2.5, 0.06, 0.06)); b.box("steel", (vx + 1.2, 12.3, z0 - 0.18), (2.55, 0.08, 0.16))
        # columns along the front and a gallery rail above the doors
        for xx in np.linspace(x0, x1, 9 if fine else 5):
            b.box("steel", (xx, 7.6, z0 - 0.22), (0.28, 15.1, 0.28))
            b.box("steel", (xx, 15.16, z0 - 0.2), (0.4, 0.3, 0.4))
        b.box("steel", ((x0 + x1) / 2, 5.0, z0 - 0.3), (W, 0.18, 0.36))
        # tint band under the eave and a hazard stripe above the doors
        b.quad("trim", V([(x0 + x1) / 2, 14.2, z0 - 0.26]), V([1.0, 0, 0]), V([0, 1.0, 0]), W, 0.9, (0, 0.5, W * 0.3, 0), normal=(0, 0, -1), band=6, col=(1, 0, 0))
        b.quad("trim", V([(x0 + x1) / 2, 5.5, z0 - 0.34]), V([1.0, 0, 0]), V([0, 1.0, 0]), W, 0.5, (0, 0.5, W * 0.3, 0), normal=(0, 0, -1), band=0)
        # roof: a ribbed mono-pitch sheet 15.16 (front) -> 12.17 (back), with an eave overhang, gutter and ridge flashing
        sl = V([0, 12.17 - 15.16, zb - z0 + 0.6])
        slen = np.linalg.norm(sl)
        nrm = unit(np.cross(V([1.0, 0, 0]), sl)); nrm = nrm if nrm[1] > 0 else -nrm
        p0 = V([x0 - 0.3, 15.16 + 0.1, z0 - 0.5]) + nrm * 0.08
        tearR = sagR = tdR = None
        if state == "damaged":
            tearR = torn(W * 0.3, slen * 0.5, 2.8, 1.4, 0.3)
            sagR = lambda u, v: -0.4 * np.exp(-(((np.asarray(u) - W * 0.3) / 3.4) ** 2 + ((np.asarray(v) - slen * 0.5) / 1.8) ** 2))
            tdR = curl(0, 0, 1, 1, 0.18)
        slab_sheet(c, "roofing", p0, (1, 0, 0), W + 0.6, sl, slen, nrm, True, 0.05, tearR, tdR, sagR, 0.45)
        gutter(c, (x0 - 0.3, 15.1, z0 - 0.5), (x1 + 0.3, 15.1, z0 - 0.5), 0.1)
        for xx in (x0 + 0.2, x1 - 0.2):
            downpipe(c, xx, z0 - 0.55, 0.3, 15.0, 0.07)
        # loading gallery: an enclosed inclined conveyor from the hall wall up to the silo tops, on trestles, with a cat-walk
        p_lo = V([x0 - 0.2, 6.0, 1.0]); p_hi = V([sil[0], 10.6, zc])
        full = state == "intact"
        if full:
            gp0 = V([x0 - 3.6, 3.2, 0.0]); gp1 = V([sil[0] - 0.4, 11.5, zc - 0.2])
            d = unit(gp1 - gp0); sd = unit(np.cross(d, V([0, 1.0, 0]))); up_ = np.cross(sd, d)
            Lg = np.linalg.norm(gp1 - gp0)
            b.box("galv", (gp0 + gp1) / 2, (1.5, Lg, 1.2), np.stack([sd, d, up_], 1))
            b.box("steel", (gp0 + gp1) / 2 + up_ * 0.68, (1.7, Lg, 0.08), np.stack([sd, d, up_], 1))
            for t in np.linspace(0.12, 0.88, 5 if fine else 3):
                q = gp0 + (gp1 - gp0) * t
                timber(c, (q[0], 0.3, q[2] - 0.7), (q[0], q[1] - 0.6, q[2] - 0.7), 0.2, 0.2, "steel")
                timber(c, (q[0], 0.3, q[2] + 0.7), (q[0], q[1] - 0.6, q[2] + 0.7), 0.2, 0.2, "steel")
                timber(c, (q[0], q[1] - 0.7, q[2] - 0.8), (q[0], q[1] - 0.7, q[2] + 0.8), 0.18, 0.16, "steel")
            for j in range(6 if fine else 2):                                         # windows along the gallery
                q = gp0 + (gp1 - gp0) * (0.15 + 0.14 * j)
                b.box("glass", q + sd * 0.78, (0.04, 0.5, 0.5), np.stack([sd, d, up_], 1))
            # ladder with a cage on the east wall, up to the roof
            lx = x1 + 0.2
            for sgn in (-1, 1):
                b.tube("steel", (lx, 0.3, z0 + 1.8 + sgn * 0.25), (lx, 14.6, z0 + 1.8 + sgn * 0.25), 0.03, 6)
            for k in range(int(14 / (0.3 if fine else 0.9))):
                yy = 0.5 + k * (0.3 if fine else 0.9)
                b.tube("steel", (lx, yy, z0 + 1.55), (lx, yy, z0 + 2.05), 0.02, 5, caps=False)
            if fine:
                for yy in np.arange(2.8, 14.0, 0.95):
                    path = [(lx + 0.45 * math.cos(a), yy, z0 + 1.8 + 0.45 * math.sin(a)) for a in np.linspace(-1.6, 1.6, 12)]
                    b.sweep("steel", path, 0.012, 5)
            for yy in np.arange(1.5, 14.5, 3.0):
                for sgn in (-1, 1):
                    b.tube("steel", (lx, yy, z0 + 1.8 + sgn * 0.25), (lx - 0.2, yy, z0 + 1.8 + sgn * 0.25), 0.025, 5)
        # a conveyor tower pipe and a few ground vents
        for xx in (1.0, 8.4):
            b.tube("galv", (xx, 0.3, z0 - 1.2), (xx, 2.6, z0 - 1.2), 0.25, 10 if fine else 5)
            b.revolve("galv", [(0.34, 2.6), (0.0, 3.0)], 10 if fine else 5, cx=xx, cz=z0 - 1.2, uref=1.0)
        c.decal_ground("oil", (3.0, z0 - 3.0), 4, 4, 0.5, y=0.33)
        for k in range(10):
            xx = x0 + 1.2 + k * 1.7
            c.decal_wall("streak_a" if k % 2 else "streak_b", (xx, 0, z0 - 0.25), (1, 0, 0), 1.6, 8.0, 14.8, (0, 0, -1), off=0.03)
        for k in range(8):
            xx = x0 + 1.5 + k * 2.1
            c.decal_wall("rust_bleed", (xx, 0, z0 - 0.25), (1, 0, 0), 1.3, 3.0, 5.0, (0, 0, -1), off=0.03)
        if state == "damaged":
            interior_shell(c, x0, x1, z0, zb, 12.0)
            for k in range(9):
                xx = x0 + 1.0 + k * 1.85
                timber(c, (xx, 0.4, z0 + 0.3), (xx, 12.6, z0 + 0.3), 0.3, 0.3, "steel")
                timber(c, (xx, 14.0, z0 + 0.3), (xx, 12.2, zb - 0.3), 0.25, 0.25, "steel")
            broken_boards(c, (x0 + W * 0.62, 8.0, z0), 7, (0, 0.2, -1), (2.6, 3.2), (1, 0, 0), 9, "corrugated", (1.2, 2.6))
            c.decal_ground("soot", (x0 + W * 0.62, z0 - 3.0), 12, 10, 0.0, y=0.35)
    else:
        # collapse: the front wall down to a broken skirt, columns bent, the roof sheet folded across the hall, the gallery fallen
        interior_shell(c, x0, x1, z0, zb, 1.1)
        clad(c, "corrugated", (x0, 0.3, z0), (1, 0, 0), W, (0, 1, 0), 6.0, (0, 0, -1), "corr", extra=ridge_keep(W, 6.0, c.rng, 0.15, 0.6), thick=0.1)
        clad(c, "corrugated", (x0, 0.3, z0), (0, 0, 1), z1 - z0, (0, 1, 0), 5.0, (-1, 0, 0), "corr", extra=ridge_keep(z1 - z0, 5.0, c.rng, 0.15, 0.7), thick=0.1)
        clad(c, "corrugated", (x1, 0.3, z0), (0, 0, 1), z1 - z0, (0, 1, 0), 4.0, (1, 0, 0), "corr", extra=ridge_keep(z1 - z0, 4.0, c.rng, 0.15, 0.7), thick=0.1)
        for xx in np.linspace(x0, x1, 9):
            hcol = c.rng.uniform(1.5, 7.0)
            lean = c.rng.uniform(-0.5, 0.5)
            timber(c, (xx, 0.3, z0 - 0.22), (xx + lean, hcol, z0 - 0.22 - abs(lean)), 0.28, 0.28, "steel")
        for k, xx in enumerate((x0 + 2.2, x0 + 7.0, x0 + 12.0)):
            Rm = axis_angle(V([0, 0, 1.0]), c.rng.uniform(-0.25, 0.25)) @ axis_angle(V([1.0, 0, 0]), c.rng.uniform(-0.45, 0.2))
            ctr = V([xx, 1.5 + 0.8 * k, z0 + 3.0])
            b.M = (Rm, ctr - Rm @ ctr)
            slab_sheet(c, "roofing", ctr + V([-2.6, 0, -4.0]), (1, 0, 0), 5.2, (0, 0, 1), 8.0, (0, 1, 0), True, 0.05, None, None, None, 0.45)
            b.M = None
        Rp = axis_angle(V([0, 0, 1.0]), 0.0) @ axis_angle(V([1.0, 0, 0]), -0.75)
        ctr = V([x0 + 6.0, 5.0, z0 - 0.5])
        b.M = (Rp, ctr - Rp @ ctr)
        slab_sheet(c, "roofing", ctr + V([-4.0, 0, 0]), (1, 0, 0), 8.0, (0, 0, 1), 6.0, (0, 1, 0), True, 0.05, None, None, None, 0.45)
        b.M = None
        gp0 = V([x0 - 3.6, 0.5, 0.0])
        timber(c, gp0, gp0 + V([-1.8, 0.6, -4.0]), 0.8, 0.7, "galv")
        timber(c, gp0 + V([1.0, 0.0, 3.0]), gp0 + V([3.0, 0.7, 6.5]), 0.8, 0.7, "galv")
        for k in range(14):
            a = V([c.rng.uniform(x0, x1), 0.4, c.rng.uniform(z0 - 6.0, zb)])
            timber(c, a, a + V([c.rng.uniform(-3, 3), c.rng.uniform(0.3, 1.2), c.rng.uniform(-3, 3)]), 0.18, 0.18, "steel")
        debris(c, 22, (x0 - 1, x1 + 1), (z0 - 6.0, zb), 1.2)
        c.decal_ground("soot", ((x0 + x1) / 2, (z0 + zb) / 2 - 1.0), 30, 20, 0.0, y=0.33)
        c.decal_ground("oil", (3.0, z0 - 3.0), 7, 7, 0.4, y=0.34)
    return c
